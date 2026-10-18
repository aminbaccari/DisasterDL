# DisasterAI: progress report (temporary)

*Status as of 2026-10-17, about 20:45. Temporary working document for the team: it records what has been built, what we measured, what went wrong and what we recommend next. The content is meant to be reused in the final report and slides; delete this file once it has been merged there.*

*Update of 2026-10-18: the RAG now includes generation (steps 5–6) and its evaluation (step 7); `docs/RAG.md` is the full reference for the RAG.*

*Update of 2026-10-17 evening: the retrieval evaluation is now final. Relevance labels come from a panel of three LLM judges (section 5.3), and Arabic was dropped from the evaluation (36 EN/FR queries).*

---

## 1. Summary

| Area | Status |
|---|---|
| Project skeleton, data schemas (`src/schemas.py`) | Done |
| Corpus: 18 official PDFs, about 1,550 pages (13 EN, 5 FR), provenance in `data/sources.csv` | Done |
| RAG indexing pipeline (extract, clean, chunk, embed, store) | Done; 4 collections |
| Retriever: dense search + type filter + threshold + RRF fusion + cross-encoder reranking + per-source cap | Done |
| Retrieval test set (36 queries: 27 EN, 9 FR; Arabic dropped) | Done |
| **Relevance labels by an LLM judging panel** (gpt-oss-120b, Qwen3.8-27B, Llama 3.1 8B tie-breaker) | **Done** |
| **Final retrieval evaluation**, 15 configurations, lenient and strict labels | **Done** |
| LLM client (local Ollama `gemma3:4b`; Groq for the offline judges), versioned prompt loader | Done |
| Knowledge agent (retrieval + reranking + **grounded answer generation**, prompt `rag_answer` v3) | Done |
| **Generation evaluation** (36 queries: citation validity 100%, quote grounding 85%, faithfulness 80% consensus of two judges) | **Done**, see `docs/RAG.md` section 8 |
| Other agents (incident, vision, risk, verifier, report), FastAPI, n8n workflow | **Not started** |

Tests: 47 passing (`.venv/Scripts/python -m pytest`), all offline.

Main findings (final labels, 30 relevant queries, among the five configurations included in the judging pool):
1. **Cross-encoder reranking is the best configuration under both label sets**: MRR@10 0.868 (strict) / 1.000 (lenient), against 0.781 / 0.906 for the same retriever without it.
2. **Fusion with the LLM query rewrite is second** (0.835 / 0.978). Used alone, the rewrite is clearly worse than the raw query.
3. **Structure-aware chunking does not beat fixed-size chunking**: 0.781 vs 0.803 (strict), 0.906 vs 0.950 (lenient); head-to-head 5 wins / 5 losses / 20 ties (strict).
4. **The contextual header does not help** in the final run (0.781 with vs 0.813 without, strict), consistent with the inconclusive earlier runs.
5. **multilingual-e5-base clearly beats e5-small** (0.781 vs 0.662 strict, 0.906 vs 0.781 lenient).
6. **The keyword labels were unreliable**: they agree with the panel labels on only 53.6% of pooled pages (κ = 0.21). All earlier results (before 2026-10-17 evening) underestimated recall and should not be quoted as final.

---

## 2. Environment

| Item | Choice / state |
|---|---|
| Python | 3.13, virtual environment `.venv` |
| Embedding stack | `torch` (CPU wheel) + `transformers` (`sentence-transformers` removed, see ENV-01) |
| Vector store | ChromaDB, persistent, `chroma_db/` (gitignored) |
| System LLM / VLM | Ollama 0.40.5, `gemma3:4b` (multimodal, about 3.3 GB) |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (about 0.5 GB) |
| Offline relevance judges | Groq API: `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`; local Ollama: `llama3.1:8b` (4-bit) |
| Secrets | `.env` (gitignored): `JUDGE_API_KEY` (Groq). Setting names listed in `.env.example` |
| Hardware (dev laptop) | i5-10300H, 8 GB RAM, GTX 1650 4 GB. gemma3:4b about 5 s per call; dense retrieval about 0.13 s per query, with reranking about 4 s; llama3.1:8b about 34 s per judgment |

Setup for a teammate:
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install -r requirements.txt
ollama pull gemma3:4b                     # system model
# download the PDFs listed in data/sources.csv into data/raw/ (data/raw is gitignored)
.venv/Scripts/python -m src.rag.ingest --strategy all      # about 30 min on CPU
```

**Keys:** the two Groq keys and the Mistral key were pasted into the working chat. Revoke them after the project (Groq and Mistral consoles).

---

## 3. Corpus

### 3.1 Documents (`data/sources.csv`)

| ID | Document | Publisher | Year | Lang | Type | Pages |
|---|---|---|---|---|---|---|
| FIRE-01 | Be Prepared for a Wildfire (V-1013) | FEMA / Ready.gov | 2018 | en | fire | 2 |
| FIRE-02 | How to Prepare for a Wildfire | FEMA / Ready.gov | ? | en | fire | 13 |
| FIRE-03 | Fire Management: Voluntary Guidelines | FAO | 2006 | en | fire | 74 |
| FIRE-04 | Guide de prévention des feux de végétation | Sécurité civile Nouvelle-Calédonie | 2017 | fr | fire | 81 |
| FIRE-05 | Fire safety in the home | UK Government (Fire Kills) | 2021 | en | fire | 24 |
| FIRE-06 | La sécurité incendie chez soi | UK Government (Fire Kills) | 2022 | fr | fire | 13 |
| FIRE-07 | Guide sur la sécurité incendie (résidences, limitations à l'évacuation) | Ministère de la Sécurité publique du Québec | 2021 | fr | fire | 100 |
| FLOOD-01 | Be Prepared for a Flood (V-1005) | FEMA / Ready.gov | 2024 | en | flood | 2 |
| FLOOD-03 | Flood After Fire fact sheet | FEMA / NFIP | 2012 | en | flood | 1 |
| FLOOD-04 | Inondations – que faire? | Sécurité publique Canada | 2011 | fr | flood | 20 |
| FLOOD-05 | Floods in the WHO European Region: health effects | WHO Europe | 2013 | en | flood | 146 |
| STRUCT-01 | INSARAG Guidelines Vol. II Manual B: Operations | INSARAG / UN OCHA | 2020 | en | structural | 58 |
| STRUCT-02 | Post-disaster building evaluation guideline (draft) | NSET Nepal / UNDP | 2009 | en | structural | 30 |
| STRUCT-03 | FEMA P-2055 Post-disaster Building Safety Evaluation | FEMA | 2019 | en | structural | 228 |
| STRUCT-04 | SOP on Collapsed Structure Search and Rescue | NDRF, Government of India | 2019 | en | structural | 62 |
| GEN-01 | CERT Basic Training Participant Manual | FEMA / Ready.gov | 2019 | en | general | 268 |
| GEN-02 | IFRC key messages for households and schools (2nd ed.) | IFRC / Save the Children | 2018 | en | general | 176 |
| GEN-03 | Same, French edition | IFRC / Save the Children | 2018 | fr | general | 165 |

IDs are not consecutive (FLOOD-02 and FLOOD-06 were the excluded Arabic documents); they are kept stable so labels never need renumbering.

### 3.2 Selection rationale
- **Official sources only** (government agencies, UN bodies, IFRC): the system grounds a safety-related assessment, so reliability and traceable citations matter more than volume.
- **Small and inspectable.** The corpus is small enough to be read and labelled within the project time.
- **Content targeted at the agents' needs:** hazard and secondary risks, safety and response actions, post-event building assessment, rescue procedures, information to collect.
- **`general` category** for cross-hazard documents, always allowed through the type filter.

### 3.3 Excluded and why
| Excluded | Reason |
|---|---|
| Arabic PDFs | Broken text extraction (RAG-01) |
| FEMA "Be Prepared for Any Hazard" suite | Duplicates, plus off-scope hazards |
| FEMA P-530 Earthquake Safety at Home | Earthquakes out of project scope |
| Scanned PDFs, news, Wikipedia | No OCR; not authoritative |
| Gas-explosion guidance | No official, text-based public document found |

---

## 4. RAG pipeline: architecture and choices

```
OFFLINE (python -m src.rag.ingest --strategy fixed|structure|all [--no-header] [--model M] [--dry-run])
data/sources.csv + data/raw/*.pdf
  -> extract.py     PyMuPDF blocks with page, font size, bold; bookmarks; split-line merging
  -> clean          NFKC, dehyphenation, header/footer removal, page numbers, dot leaders, private-use glyphs
  -> chunkers.py    A: fixed-size   |   B: structure-aware (+ contextual header)
  -> embeddings.py  multilingual-e5-base, "passage: " prefix, mean pooling, L2 norm
  -> Chroma         kb_fixed, kb_structure, kb_structure_noheader, kb_structure_multilingual-e5-small

ONLINE (knowledge agent)
IncidentInfo -> query = reported observations (+ LLM rewrite fused by RRF only for non-EN/FR reports)
  -> 30 dense candidates, filter disaster_type ∈ {type, general}
  -> threshold 0.785 -> cross-encoder reranking -> top-5 -> KnowledgeResult
```

### 4.1 Code map
| File | Responsibility |
|---|---|
| `src/config.py` | All settings (models, paths, chunk sizes, LLM endpoint, judge endpoints) |
| `src/rag/extract.py` | PDF → cleaned blocks + bookmarks; split-line merging |
| `src/rag/chunkers.py` | `fixed_size` and `structure_aware` |
| `src/rag/embeddings.py` | Tokenizer-based token counter; e5 embedder |
| `src/rag/ingest.py` | Indexing CLI, JSONL dump, statistics |
| `src/rag/retriever.py` | `search()`: candidates → RRF fusion → threshold → rerank → per-source cap |
| `src/rag/reranker.py` | Multilingual cross-encoder |
| `src/rag/evaluate.py` | Metrics, 15 configurations, pooled judging sheet, reports |
| `src/rag/judging.py` | LLM judging panel: blinding, judges, quote check, κ, vote, final labels |
| `src/llm/client.py` | OpenAI-compatible client; per-call endpoint/key; JSON validation with one retry; rate-limit retry |
| `src/llm/prompt_loader.py` | Versioned prompts `prompts/<name>/v<N>.yaml` |
| `src/agents/knowledge_agent.py` | Knowledge agent |

### 4.2 Chunking
| | A. Fixed-size (baseline) | B. Structure-aware |
|---|---|---|
| Unit | Sliding token windows over the whole document | Document sections |
| Size / overlap | 400 tokens / 60 (15%), snapped to word starts | ≤ 400 tokens; split by paragraph → sentence → window; sections < 80 tokens merged; overlap = trailing whole sentences ≤ 60 tokens |
| Headings | none | PDF bookmarks if ≥ 5, else typography |
| Embedded header | document title | `Title > Section > Subsection` |
| Chunks (18 docs) | 1,917 (avg 397 tokens) | 2,575 (avg 287 tokens); 2,218 without header |

The rationale for each parameter is unchanged: 400 tokens leaves margin under e5's 512-token window, and sizes are counted with the model's own tokenizer. The final evaluation shows **no retrieval gain from structure-aware chunking** on this corpus (6.2). Its remaining advantage is qualitative: chunks carry their section heading, which is useful for citations in the report agent.

### 4.3 Embedding model
`intfloat/multilingual-e5-base`: multilingual, local, no API cost. **Measured against e5-small:** e5-base wins clearly in both label sets (6.2), so the larger model is justified. Implemented with `transformers` (masked mean pooling, L2 normalisation, `query:`/`passage:` prefixes).

### 4.4 Vector store and retrieval
ChromaDB (embedded, persistent, metadata filters, cosine HNSW); one collection per configuration. Filter on `disaster_type ∈ {type, general}`; reciprocal rank fusion (k = 60) for multi-query; cross-encoder reranking of 30 candidates (two-stage retrieval); optional per-source cap; threshold 0.785.

---

## 5. Evaluation method

### 5.1 Test set (`evaluation/retrieval_testset.csv`)
- **36 queries:** 30 relevant (11 fire, 10 flood, 9 structural) and 6 out-of-scope.
- **Languages:** 27 EN / 9 FR overall; the 30 relevant queries are 22 EN / 8 FR. The 4 Arabic queries were dropped from the evaluation on 2026-10-17.
- **Styles (relevant queries):** 22 questions / 8 incident-style reports.
- Queries were written before looking at retrieval results.
- **Caveat:** the queries were drafted with the help of the same assistant (Claude) that built the system. The labels (5.3) are independent of it; the choice of queries is not. A teammate should review the query list.

### 5.2 Pooling
- **Pool:** the top-3 pages of five main configurations (fixed+filter, structure+filter, structure+filter+cap2, structure+filter+rerank, structure+filter+fusion3), giving **279 (query, document, page) pairs**.
- **Unit:** relevance is judged at page level, so the labels apply to every chunking strategy.
- **Fallback:** pages outside the pool keep their keyword label (rarely used: only the 10 non-pooled configurations retrieve them).

### 5.3 Relevance labels: LLM judging panel ("LLM jury")
| Role | Model | Family | Items |
|---|---|---|---|
| Judge 1 | `openai/gpt-oss-120b` (reasoning, effort high), Groq | OpenAI | all 279 |
| Judge 2 | `qwen/qwen3.8-27b`, Groq | Alibaba | all 279 |
| Tie-breaker | `llama3.1:8b` (4-bit), local Ollama | Meta | 91 disputed |

- **Independence:** none of the three families is used by the system. Claude (which built the system) and Gemma (which writes the query rewrites) were excluded on purpose.
- **Blinding:** judges see only the query, the document title, the page number and the page text (≤ 2,500 characters), in shuffled order. Configuration names and keyword labels stay hidden.
- **Prompt:** `prompts/relevance_judge/v3.yaml`:
  - rubric 0/1/2;
  - one few-shot anchor per grade (written for the prompt, not taken from the test set);
  - one-sentence reason, then the score;
  - a verbatim quote for scores of 1 or 2.
- **Quote check:** every quote is checked automatically against the page. A vote with an invented quote is discarded.
- **Vote:**
  - An item is disputed when the two judges' scores differ or a vote is invalid. Disputed items go to the tie-breaker.
  - The final score is the median of the valid votes; with two valid votes that differ, the lower one is kept.
  - Final labels: **lenient** = score ≥ 1, **strict** = score 2.
- **Choosing the judges** (prompt-engineering evidence, FAILURES.md PROMPT-04, JUDGE-01, ENV-05):
  - `qwen2.5:3b` defaulted to 0 and was rejected.
  - `gemma3:4b` was set aside because it also writes the query rewrites.
  - `llama3.1:8b` was calibrated on 25 items: 14/15 keyword-relevant pages found, 1 invented quote.
  - Mistral was dropped because its free account had a zero quota.

**Agreement** (`evaluation/judging/agreement.md`):
| Measure | Value |
|---|---|
| Cohen's κ, judge 1 vs judge 2, binary lenient | **0.747** (substantial) |
| Cohen's κ, binary strict | 0.733 |
| Cohen's κ, 3 levels | 0.657 |
| Raw agreement: exact score / lenient | 78.0% / 90.5% |
| Invalid votes (invented quotes) | gpt-oss-120b 28 (10%), Qwen 12, Llama 4 of 91 |
| Disputed items | 91; the tie-breaker sided with Qwen 41 times, with gpt-oss 26 times |
| Final scores 0 / 1 / 2 | 76 / 77 / 125; 1 item unresolved (keeps its keyword label) |
| Agreement of old keyword labels with panel labels | 53.6% (κ = 0.206) |

**Earlier, abandoned attempt** (archived in `evaluation/judging/archive/2026-10-17_claude-llama-human/`):
- Judges: Claude subagents and llama3.2:3b, κ = 0.48, followed by human adjudication of 125 items.
- Dropped because the human step took too long, and because Claude also built the system.

### 5.4 Metrics and commands
- **Metrics:** Hit@k (1, 3, 5, 10), MRR@10 and source precision@5 on relevant queries; top-1 similarity on out-of-scope queries for the threshold.
- **Noise:** about ±0.006 between runs (approximate HNSW search); with 30 queries, one query moves Hit@k by 3.3 points.
```bash
.venv/Scripts/python -m src.rag.evaluate --rewrite 3 --tag lenient
.venv/Scripts/python -m src.rag.evaluate --rewrite 3 --judgments evaluation/retrieval_judgments_strict.csv --tag strict
.venv/Scripts/python -m src.rag.judging prepare | judge --judge judge1|judge2|tiebreaker | analyse | merge
```
**Reference runs:** `evaluation/results/retrieval_20261017_2028_lenient.md` and `retrieval_20261017_2039_strict.md`.

---

## 6. Final results (panel labels, 30 relevant queries)

### 6.1 Pooled configurations: the fair comparison
These five configurations supplied the judged pool, so every page they return in the top 3 is judged.

| Config | MRR@10 strict | Hit@1 strict | Hit@5 strict | MRR@10 lenient | Hit@1 lenient | Source P@5 lenient |
|---|---|---|---|---|---|---|
| **structure+filter+rerank** | **0.868** | **0.800** | 0.933 | **1.000** | **1.000** | 0.947 |
| structure+filter+fusion3 | 0.835 | 0.767 | 0.933 | 0.978 | 0.967 | 0.907 |
| fixed+filter | 0.803 | 0.733 | 0.933 | 0.950 | 0.933 | 0.920 |
| structure+filter+cap2 | 0.796 | 0.667 | **0.967** | 0.918 | 0.867 | 0.883 |
| structure+filter | 0.781 | 0.667 | 0.900 | 0.906 | 0.867 | 0.933 |

**The ranking is identical under both label sets** (rerank > fusion3 > fixed+filter > cap2 > structure+filter), so the conclusions are robust to how strictly "relevant" is defined.

### 6.2 Other configurations (not pooled)
These configurations can return pages outside the pool, which then fall back to the weaker keyword labels, so their scores lean pessimistic. Large differences remain informative.

| Config | MRR@10 strict | MRR@10 lenient | Reading |
|---|---|---|---|
| fixed | 0.803 | 0.921 | ≈ fixed+filter |
| structure | 0.781 | 0.900 | ≈ structure+filter |
| structure-noheader+filter | 0.813 | 0.906 | header gives no gain |
| structure+filter [e5-small] | 0.662 | 0.781 | **e5-base clearly better** |
| fixed+filter+cap2 | 0.809 | 0.950 | ≈ fixed+filter |
| structure+filter+rerank+cap2 | 0.850 | 1.000 | cap adds nothing on top of reranking |
| fixed+filter+rw3 / structure+filter+rw3 | 0.641 / 0.669 | 0.786 / 0.859 | **rewrite alone hurts** |
| structure+filter+fusion3+rerank | 0.842 | 0.934 | combining both doesn't beat reranking alone |

### 6.3 Breakdowns (MRR@10 strict)
| Config | fire (11) | flood (10) | structural (9) | EN (22) | FR (8) |
|---|---|---|---|---|---|
| fixed+filter | **0.841** | 0.825 | 0.731 | 0.811 | 0.781 |
| structure+filter | 0.828 | 0.800 | 0.704 | 0.811 | 0.701 |
| structure+filter+rerank | 0.799 | **0.875** | **0.944** | **0.859** | 0.893 |
| structure+filter+fusion3 | **0.877** | 0.792 | 0.833 | 0.798 | **0.938** |

- **Reranking:** gains concentrate on structural (0.704 → 0.944) and flood queries. It is still slightly weaker on fire queries (0.828 → 0.799), the known RAG-12 trade-off, now much smaller than with keyword labels.
- **Fusion:** best on fire and French queries, but with only 8 French queries this is not enough to justify a per-language rule.

### 6.4 Lenient labels saturate
- **The problem:** with lenient labels, many configurations reach Hit@5 = 1.000 and reranking gets MRR@10 = 1.000, so these labels barely separate the configurations.
- **Why:** pages that are only partly relevant (score 1) are common in this domain.
- **Consequence:** **report strict labels as the primary result** and lenient ones as an upper bound.

### 6.5 Threshold
- **Lenient labels:** the best balanced threshold is 0.785, which keeps 83% of relevant hits and rejects 5 of 6 out-of-scope queries. The knowledge agent uses this.
- **Strict labels:** 0.830 rejects all 6 out-of-scope queries but keeps only 71%.

Out-of-scope top-1 scores range from 0.742 to 0.827 ("locust swarms"), overlapping the relevant ones, so the verifier remains the second line of defence.

### 6.6 Remaining failures (strict, best configuration)
- **FIRE-Q02** (smoke and asthma)
- **FIRE-Q05** (French: wildfire pushed by the wind toward a village)

Both are fire queries, consistent with RAG-12.

---

## 7. Problems encountered

All entries are in `evaluation/FAILURES.md` (IDs match). Highlights:

| ID | Problem | Status |
|---|---|---|
| ENV-01 | `sentence-transformers` blocked by Windows Application Control (SciPy DLL) | Fixed (pure `transformers`) |
| ENV-05 | Groq free tier: 200k tokens/day per model (about 145 judgments); Mistral free account with zero quota | Worked around (second Groq key; local tie-breaker) |
| RAG-01 | Arabic PDFs extract with swapped lam-alef letters | Arabic documents excluded; Arabic now also dropped from the evaluation |
| RAG-05 | Keyword labels incomplete | **Resolved** by the LLM panel (κ 0.21 between old and new labels) |
| RAG-09 | FIRE-04 lines split across text boxes | Fixed (split-line merging) |
| RAG-12 | Reranker slightly weaker on fire queries | Open, smaller with final labels (0.828 → 0.799) |
| RAG-13 | Contextual-header effect | **Settled:** no gain in the final run |
| RAG-14 | Hindi in a legacy font in the NDRF SOP becomes gibberish | Open, low impact |
| PROMPT-01..03 | Query rewrite v1/v2/v3 alone hurt retrieval | Rewrite used only through fusion |
| PROMPT-04 | Small judges default to 0 or invent quotes | Judge selection by calibration |
| JUDGE-01 | Even gpt-oss-120b invents quotes (10%) | Automatic quote check discards those votes |

---

## 8. What is left

### 8.1 RAG (optional)
- **RAG-12:** try reranking only the top 10, or blending reranker and cosine scores, and re-check on fire queries.
- **Bigger test set:** 30 relevant queries is small; another 20–30 queries would make the chunking comparison more conclusive.
- **Human spot-check:** a teammate scores 20 random pooled pages, to report human-vs-panel agreement as extra validation.

### 8.2 Rest of the project (needed for the demo)
- **Agents:**
  - Incident agent: structured extraction with `chat_json`; its `language` field drives the fusion decision.
  - Vision agent: `gemma3:4b` multimodal.
  - Risk agent, verifier (LLM-as-judge on evidence, at runtime), report agent.
- **FastAPI** endpoints and **n8n workflow**.
- **Prompt library** (`prompts/PROMPT_LIBRARY.md`): two complete prompt stories are ready.
  - Query rewrite v1 → v2 → v3, with retrieval numbers.
  - Relevance judge v1 → v2 → v3, with calibration and agreement numbers.
- **Latency:** about 5 s per gemma3:4b call plus 4 s of reranking; a full pipeline takes about 35–45 s.

---

## 9. Points to be ready for in Q&A
- **What the LLM judges evaluate:** retrieval only (context relevance), offline, to build the answer key (qrels). Generation will be evaluated separately (faithfulness).
- **Why a panel of three families and not Claude:** independence from the system's author; single-judge bias; κ as a reliability measure; a tie-breaker instead of human adjudication ("Replacing Judges with Juries", Verga et al. 2024).
- **Why not fine-tune (LoRA) a judge:** no human-labelled data; training on another model's labels would copy its bias.
- **Pooling, graded relevance, lenient vs strict, saturation of lenient labels.**
- **Why the quote check:** even strong judges invent evidence (10%); a verbatim requirement makes judgments verifiable.
- **Why reranking is the default:** best under both label sets, about 4 s per query cost; the fire-query trade-off.
- **Bi-encoder vs cross-encoder; RRF; e5 prefixes and pooling; HNSW approximation; threshold choice.**
- **Why structure-aware chunking isn't the default for retrieval quality** (no measured gain), and what it still brings (section headings for citations).
- **Why no fine-tuning of the generator:** no labelled data, short timeline; RAG + prompting provide the grounding.
