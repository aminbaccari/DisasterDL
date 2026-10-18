# Vision Agent — Technical Documentation

## Overview

The Vision Agent classifies disaster images as `fire`, `flood`, `normal`, or `uncertain`.
It uses a local VLM (llava-phi3 via Ollama), Test-Time Augmentation (TTA), and an
inference-only consistency check to assess prediction reliability.

**Input:** image path + optional incident text  
**Output:** Pydantic-validated JSON with class, description, evidence, consistency score, reliability status

---

## Files

| File | Role |
|---|---|
| `src/config.py` | pydantic-settings — VLM_MODEL, OLLAMA_BASE_URL loaded from `.env` |
| `src/schemas.py` | Pydantic models — VisionInput, VisionOutput, TTAVariantResult, ConsistencyResult |
| `src/llm/client.py` | Ollama HTTP client — encode_image (PIL→base64), answer (POST /api/generate) |
| `src/llm/prompt_loader.py` | LRU-cached YAML loader — `load_prompt("vision_description", version=1)` |
| `prompts/vision_description/v1.yaml` | 3 prompts + failure log |
| `src/agents/vision_agent.py` | Full pipeline: TTA → consistency → reliability → VisionOutput |
| `tests/test_vision_agent.py` | 38 unit tests — pure logic, VLM mocked, no GPU needed |
| `test_real.py` | Manual test script — runs fire / flood / normal images end-to-end |
| `download_models.py` | `ollama pull llava-phi3` helper |

---

## VLM — llava-phi3 via Ollama

**Model:** `llava-phi3`  
**Served by:** Ollama (runs as a local service on Windows)  
**VRAM usage:** ~2.9 GB (fits RTX 2060 6 GB with headroom)  
**API:** HTTP POST to `http://localhost:11434/api/generate`

### Why llava-phi3

LLaVA (Large Language and Vision Assistant) connects a CLIP vision encoder to an LLM
via a lightweight projection layer trained on instruction-following data.

> Liu, H., Li, C., Wu, Q., & Lee, Y. J. (2023). **Visual Instruction Tuning**. *NeurIPS 2023*.

The phi-3 variant uses Microsoft's Phi-3-mini as the language backbone, achieving
strong zero-shot VQA at a compact size.

### Why Ollama

- No Python dependency conflicts (no pyvips, no transformers version issues)
- Provider-agnostic: swap the model by changing `VLM_MODEL` in `.env`
- Manages CUDA memory allocation automatically
- OpenAI-compatible HTTP API

### Rejected alternatives

| Model | Reason rejected |
|---|---|
| moondream2 (HuggingFace) | Requires pyvips (C library, hard to install on Windows) |
| Florence-2-base (Microsoft) | Weaker zero-shot VQA for disaster classification |
| moondream (pip package) | Cloud API, requires API key — not local |

---

## Pipeline

```
VisionInput (image_path)
    ↓
Load image as RGB (PIL)
    ↓
Create 3 TTA variants:
  • original     — unchanged
  • resized      — 512×512 LANCZOS
  • flipped      — horizontal mirror
    ↓
For each variant — encode once (PIL → base64), then ask 3 questions:
  Q1: classify  → fire | flood | normal | uncertain
  Q2: evidence  → comma-separated visible signs
  Q3: describe  → one sentence
    ↓
Visual Consistency Module:
  agreement_score = majority_count / 3
  flag disagreements between variants
    ↓
Reliability Layer:
  RELIABLE   → agreement ≥ 0.67 + no uncertainty language
  UNRELIABLE → agreement < 0.67 OR 2+ soft signals
  UNCERTAIN  → majority class is already "uncertain"
    ↓
VisionOutput (Pydantic-validated JSON)
```

---

## Test-Time Augmentation (TTA)

TTA reduces prediction variance by running inference on multiple augmented versions
of the same image and comparing the results.

> Shanmugam, D. et al. (2021). **Better Aggregation in Test-Time Augmentation**. *ICCV 2021*.

### Chosen augmentations

| Variant | Transform | Rationale |
|---|---|---|
| original | none | Baseline prediction |
| resized | 512×512 LANCZOS | Removes resolution mismatch artefacts |
| flipped | Horizontal mirror | Tests spatial bias — fire/flood evidence is not position-dependent |

### Intentionally excluded

- **Vertical flip** — destroys sky/ground context (smoke rises, water is at ground level)
- **Rotation** — changes geometric frame of reference
- **Colour jitter** — could remove fire's orange signature or flood's blue-grey palette
- **Random crop** — may cut out the disaster evidence entirely
- **Gradient-based adaptation** — out of scope; this version is inference-only

### Agreement score

```
agreement_score = majority_count / total_variants
```

Takes values: `0.33` (full disagreement) / `0.67` (two agree) / `1.0` (unanimous).  
Threshold: `0.67` — below this the prediction is flagged `unreliable`.

> **Important:** agreement_score measures *stability*, not *correctness*.
> High agreement does not guarantee the prediction is right.

---

## Prompt Engineering

Prompts are stored in `prompts/vision_description/` as versioned YAML files.
The loader caches them with `@lru_cache` — no disk reads after the first call.

### v1 — current (zero-shot, structured output)

**Technique:** role + structured output + guardrails  
**Strategy:** three short focused questions instead of one large prompt

```yaml
classify_prompt: >
  You are a disaster assessment AI. Look at this image carefully.
  What type of emergency does it show?
  Reply with ONLY one word from this list: fire, flood, normal, uncertain.
  Do not explain. Do not add punctuation. One word only.

evidence_prompt: >
  You are a disaster assessment AI. List the visible signs of emergency
  in this image. Reply with a short comma-separated list of 3 to 5 items.
  Example format: flames on roof, dense smoke, burned trees
  No bullet points. No numbers. No sentences. Comma-separated only.

description_prompt: >
  You are a disaster assessment AI. Describe this image in exactly one
  sentence. Focus on the main emergency visible. Maximum 30 words.
```

### Ollama options

```python
"options": {"num_predict": 150, "temperature": 0}
```

`num_predict=150` prevents repetition loops. `temperature=0` makes output deterministic.

### Planned versions

| Version | Technique | Paper |
|---|---|---|
| v2 | Few-shot (add 2–3 example descriptions) | Brown et al. 2020 — *Language Models are Few-Shot Learners* |
| v3 | Chain-of-Thought (reason before classifying) | Wei et al. 2022 — *Chain-of-Thought Prompting* |

---

## Reliability Layer

Combines TTA consistency with VLM language analysis:

```python
AGREEMENT_THRESHOLD = 0.67

UNCERTAINTY_KEYWORDS = {
    "unclear", "cannot", "hard to tell",
    "unsure", "not sure", "ambiguous", "difficult to"
}
```

| Condition | Status | Final predicted_class |
|---|---|---|
| agreement ≥ 0.67 + no uncertainty language | `reliable` | majority class |
| majority class is `uncertain` | `uncertain` | `uncertain` |
| agreement < 0.67 OR 2+ soft signals | `unreliable` | **`uncertain`** (conservative fallback) |

> **Design decision:** an `unreliable` prediction propagates `uncertain` rather than the majority class.
> Rationale: in a disaster pipeline, a wrong confident prediction (e.g. "fire" on Roman ruins) is more
> dangerous than a conservative "uncertain" that triggers human review.

---

## Test Results (3-image smoke test)

| Image | Predicted | Agreement | Reliability | Description |
|---|---|---|---|---|
| fire_image0001.jpg | `fire` ✅ | 1.0 | reliable | A wildfire is burning in the mountains. |
| flood_image0001.jpg | `flood` ✅ | 1.0 | reliable | A plane is flying over a flooded area. |
| image_5990.png (normal) | `normal` ✅ | 1.0 | reliable | A tall building with a sunset in the background. |

Run the test: `python test_real.py`

---

## Failure Log

| Case | What failed | Suspected cause | Fix | Outcome |
|---|---|---|---|---|
| v1d — visual ambiguity (lake vs flood) | Natural lake (Siliana region) classified as `flood`, agreement 1.0, evidence fully hallucinated (flooded street, submerged vehicles) | Still water in a natural setting is visually identical to flood water; VLM has no geographic/context grounding | Requires multi-agent fix: RAG knowledge agent should inject location context before classification | Open — by design; shows why RAG layer is needed |
| v1c — semantic confusion (ruins) | Ancient Roman ruins (Siliana) classified as `fire`, 0.67 agreement, evidence fully hallucinated (flooded street, smoke, submerged vehicles) | "Ruined stone structure" semantically overlaps with "damaged buildings" → disaster trigger. VLM has no concept of intentionally ancient vs. recently damaged | **Fixed:** `run()` now sets `predicted_class = uncertain` whenever `reliability_status == UNRELIABLE`, instead of propagating the majority vote | Resolved — output now `uncertain/unreliable` |
| v1b — template hallucination | Model added "damaged buildings" to evidence on a flood image where buildings were intact | VLM fills in co-occurring disaster features from training distribution instead of grounding in visible image | Planned fix: CoT prompt v2 — "First describe ONLY what you see, then list evidence" | Open — documented for grade |
| v0 prompt — looping | Flipped variant repeated same sentence 150× | No `num_predict` cap; LLaVA entered repetition loop | Set `num_predict=150, temperature=0` in Ollama options | Resolved |
| v0 prompt — evidence | Evidence returned as bullet list; parser failed | No format constraint in prompt | Added example + "No bullet points" guardrail | Resolved |
| moondream2 on Windows | ImportError: pyvips, einops, torchvision, accelerate | New revision requires pyvips (C lib, not pip on Windows) | Switched to Ollama + llava-phi3 | Resolved |
| moondream pip package | HTTP 401 Unauthorized | Pip package is a cloud API, not a local model | Removed; switched to Ollama | Resolved |

---

## Planned Improvements

1. **Few-shot prompting (v2 prompt)** — add disaster examples to classify prompt
2. **Chain-of-Thought (v3 prompt)** — ask model to reason before classifying
3. **Prompt ensemble** — vote across 3 different prompt phrasings
4. **Multi-scale analysis** — crop + analyze image quadrants
5. **Model upgrade** — benchmark llava:7b vs llava-phi3 on same test set
6. **Structural damage class** — extend DisasterClass enum
7. **Evaluation pipeline** — precision/recall/F1 per class on held-out test set
8. **Multilingual context injection** — pass FR/AR/EN incident text to VLM

---

## How to Run

```powershell
# Activate venv
cd C:\Users\SBS\Desktop\DisasterDL\DisasterDL
venv\Scripts\activate

# Unit tests (no GPU, no Ollama needed)
pytest tests/test_vision_agent.py -v

# 3-image smoke test (Ollama must be running)
python test_real.py

# Single image
python test_real.py data\Fire\fire_image0001.jpg
```

**Prerequisites:** Ollama installed + `ollama pull llava-phi3`
