# Proposal: a separate vision model for the Vision agent (2026-10-17)

Status (2026-10-17): the team approved the local-first plan. Step 1 of the implementation plan is DONE (code and tests, nothing downloaded, no model run): `VISION_CHAIN`, the `task` field of `/llm`, the `ollama` and `hf` providers, `scripts/llm_ping.py --task vision`, 11 new unit tests with a fake HTTP layer. Steps 2 to 6 are open and need the downloads below to be approved.

Step 2 attempt (2026-10-17, Docker route approved by the team, no Windows install): the existing image `ollama/ollama:0.34.0` started with `--gpus all` and detected the GPU (CUDA, RTX 3050 6 GiB, driver 13.0) in a container `ollama-disasterai` with volume `ollama_disasterai`. The pull of `qwen3-vl:4b` failed at 0 percent of 3.3 GB with an input/output error, then the Docker engine stopped answering. After `docker desktop restart` the engine came back, but a test write to the volume reported "No space left on device" inside Docker's virtual disk (`docker_data.vhdx`, 20.1 GB on the host, C: has about 127 GB free), and the engine became unresponsive again. The model was not downloaded and no vision call was made. Likely cause: the Docker virtual disk is full (images such as `ollama/ollama:0.34.0` alone take 9.2 GB). This is a diagnosis from symptoms, not confirmed. The same engine instability happened earlier in the session (2026-10-16, engine stopped without a command of ours). Model facts (size, licence, hosting) were read from the Hugging Face API and the Ollama library pages on 2026-10-17. No model was run, so quality claims below are expectations, not results.

## Why

- The Vision agent needs a model that accepts images. In the shared model chain only Gemini and two free OpenRouter models qualify, and all of them were out of quota in the real runs. The Vision step answered in only one logged run (the image test after the upload fix, nemotron-3.5-super-vl, 80.8 s). Every other image run ended with `image_status: analysis_failed` or, before the fix, `unusable`.
- Text calls and vision calls compete for the same few quotas. A vision model that does not depend on them removes both the dependency and the failure.
- Disaster photos can be sensitive. A local model keeps them on the machine.

## What stays and what changes

Stays: n8n orchestrates, the Vision node and its prompt, the JSON contract (`backend/schemas/vision.schema.json`), `/validate`, the report fields. Python stays a transport and guardrail layer, not an agent graph.

Changes (small):
1. `/llm` gets a `task` field (`text` by default, `vision`). A vision call uses its own chain, `VISION_CHAIN` in `.env`, and falls back to the shared chain only if `VISION_CHAIN` is empty.
2. Two new providers in `backend/llm_chain.py`, both OpenAI-compatible so they reuse the existing adapter: `ollama` (local, no key) and `hf` (Hugging Face Inference Providers, `HF_TOKEN`).
3. The n8n Vision node sends `task: "vision"`.

Example `.env` (to be verified with `scripts/llm_ping.py --image` before use):

```
VISION_CHAIN=ollama:qwen3-vl:4b,hf:Qwen/Qwen3-VL-8B-Instruct,gemini:gemini-3.6-flash,openrouter:nvidia/nemotron-3.5-super-vl:free
OLLAMA_BASE_URL=http://localhost:11434/v1
HF_TOKEN=
```

## Where the model can run

| Option | How | For | Against |
|--------|-----|-----|---------|
| A. Local with Ollama (recommended first step) | Ollama serves a quantised model on `localhost:11434` with an OpenAI-compatible API. Ollama is not installed on this machine, but a Docker image `ollama/ollama:0.34.0` from another project is present locally. | No quota, images stay local, one line per model, handles quantisation and GPU offload | Download (Ollama about 1 GB, model 2 to 3 GB), cold start 20 to 60 s, a small model is less accurate |
| B. Hugging Face Inference Providers | `https://router.huggingface.co/v1` with a token. Providers listed on 2026-10-17: Qwen3-VL-8B on novita and featherless-ai, gemma-3-4b-it on deepinfra and featherless-ai, Qwen3.5-9B on deepinfra, featherless-ai, ovhcloud, together | Bigger models than the laptop can run, no install | Free credits are limited (I did not check the current amounts), another quota to watch, images leave the machine |
| C. In-process `transformers` | Load the VLM inside the RAG service | No extra service | Only CPU PyTorch is installed here (`torch 2.7.1+cpu`), memory and GPU contention with the embedder, slower start. Not recommended. |
| D. Keep the shared chain | status quo | nothing to build | the failure above |

Machine: NVIDIA GeForce RTX 3050 Laptop, 6 GB VRAM, about 23.6 GB RAM, 127 GB free disk, Intel Core 7 240H. A 4-bit model of 3 to 4 GB fits the GPU, an 8B model does not fit fully and would split between GPU and CPU.

## Model shortlist

Parameters, licence and hosting come from the Hugging Face API. Ollama sizes are the quantised download sizes shown on ollama.com.

| Rank | Model | Params | Licence | Ollama tag and size | Hosted on HF providers | Remarks |
|------|-------|--------|---------|---------------------|------------------------|---------|
| 1 | `Qwen/Qwen3-VL-4B-Instruct` | 4.4 B | Apache-2.0 | `qwen3-vl:4b`, 3.3 GB | featherless-ai | Best fit for 6 GB. Qwen VL models are generally reported to follow instructions and JSON formats well, not measured here. |
| 2 | `Qwen/Qwen3-VL-2B-Instruct` | 2.1 B | Apache-2.0 | `qwen3-vl:2b`, 1.9 GB | featherless-ai | Fallback, fast, can run on CPU. |
| 3 | `Qwen/Qwen3-VL-8B-Instruct` | 8.8 B | Apache-2.0 | `qwen3-vl:8b`, 6.1 GB | novita, featherless-ai | Too big for full GPU use here. Good as the hosted second link. |
| 4 | `google/gemma-3-4b-it` | 4.3 B | Gemma licence, gated (accept on the model page) | `gemma3:4b`, 3.4 GB | deepinfra, featherless-ai | Multilingual, a second family for diversity. |
| 5 | `Qwen/Qwen3.5-4B` | 4.7 B | Apache-2.0 | not checked | featherless-ai | Newer (2026-03), listed as image-text-to-text, check that it takes images in Ollama before use. |
| 6 | `openbmb/MiniCPM-V-4.6` | 1.3 B | Apache-2.0 | not checked (`minicpm-v:8b` is the older 8B, 5.5 GB) | none | Small, recent (2026-08). |
| 7 | `vikhyatk/moondream2` | 1.9 B | Apache-2.0 | `moondream`, 1.7 GB, 2K context | none | Short captions only, weak at long JSON, last resort. |
| 8 | `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` | 0.5 B | Apache-2.0 | not checked | none | CPU emergency option. |

Not suited: OCR and document models in the same listing (DeepSeek-OCR, chandra-ocr-2, surya-ocr-2, GOT-OCR2, dots.ocr, granite-docling, PaddleOCR-VL). They read documents, not scenes. `microsoft/Florence-2-base` and `-large` (MIT) caption and detect objects but do not follow a JSON instruction, so they would need extra code.

## Making a small model reliable

1. **Do not show the report to the vision model.** Vision prompt v1 gives the model the incident text so it can check consistency. Its own hypothesis list names confirmation bias as a risk, and small models agree with the text easily. Proposed vision v2: image only, output observations, visible text, `not_determinable`. The consistency check with the report becomes a text step (the risk agent already produces `conflicts_between_sources`) or a small deterministic comparison. This also halves the tokens of the vision call. It is a prompt change and needs a CHANGELOG entry and a test.
2. **Ask for less.** One scene summary, at most six observations, a fixed list of categories (the schema already has them).
3. **Validate the output** in the existing Parse node (enums, required keys). On failure the chain tries the next model, then n8n retries once, then the report says `analysis_failed`.
4. **Keep the model loaded** (`keep_alive` in Ollama) so only the first call pays the load time. The current image timeout of 120 s is enough.

## Implementation plan

| Step | Work | Needs from you |
|------|------|----------------|
| 1 | DONE 2026-10-17. `llm_chain.py`: providers `ollama` and `hf`, `VISION_CHAIN`, `task` field in `/llm` and in the workflow's Vision node, unit tests with the fake HTTP layer (95 backend tests pass). | nothing |
| 2 | Install Ollama (about 1 GB download) or start the existing Docker image with GPU, `ollama pull qwen3-vl:4b` (3.3 GB) | your OK for the downloads |
| 3 | `scripts/llm_ping.py --model ollama:qwen3-vl:4b --image --json` | nothing |
| 4 | `scripts/vision_bench.py`: run each candidate on a set of images, score with ground-truth tags (smoke, flames, flood water, structural damage, people) and a manual look for invented objects. Needs about 12 images, with licences, instead of the 4 stand-ins. | someone to select and label the images |
| 5 | Vision prompt v2 (image only), before and after on the benchmark | team decision |
| 6 | Re-run the six incidents with images, log in `docs/EVIDENCE_LOG.md` | fresh text-model quota |

Rough effort: steps 1 to 3 half a day, step 4 one day, steps 5 and 6 one day. These are estimates.

## What to measure

- JSON valid and schema valid rate over N images and 3 runs each.
- Category recall against the ground-truth tags, and invented observations counted by hand.
- Detection of the mismatch in `edge_02_conflict` (smoke-haze over a dry yard against a flood report).
- Latency (first call and warm), memory and VRAM use.
- Same table for each candidate, one row per model, so the choice is evidence-based.

## Risks

- A 2B to 4B model describes less and may invent details. The `not_determinable` list and the confidence field must be checked in the benchmark, not assumed.
- Windows and GPU: Ollama supports NVIDIA GPUs on Windows, the Docker route depends on GPU pass-through in Docker Desktop. I did not test either here.
- Hosted models add a new quota (credits) and send images outside the machine.
- Gated models (Gemma) need the licence accepted with a Hugging Face account.
- Model names and availability change quickly (several entries in the listing date from the last few weeks). Re-check before relying on any name.

## Decisions for the team

1. Local first (A) with a hosted second link (B), or hosted only?
2. Approve installing Ollama and pulling `qwen3-vl:4b`?
3. Approve changing the Vision prompt to image-only (v2) and moving the consistency check to the text side?
4. Who selects and labels about 12 test images?
