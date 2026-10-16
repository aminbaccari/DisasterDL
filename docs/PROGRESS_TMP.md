# DisasterAI: progress report (temporary)

*Status as of 2026-10-17, about 00:15. Temporary working document for the team: it records what has been built, what we measured, what went wrong and what we recommend next. The content is meant to be reused in the final report and slides; delete this file once it has been merged there.*

*Update of 2026-10-17: recommendations 8.1 to 8.3 of the previous version have been implemented, except the human judging itself (section 8 gives the status of each item).*

---

## 1. Summary

| Area | Status |
|---|---|
| Project skeleton, data schemas (`src/schemas.py`) | Done |
| Corpus: **18 official PDFs**, about 1,550 pages (11 EN, 6 FR), provenance in `data/sources.csv` | Done |
| RAG indexing pipeline (extract, clean, chunk, embed, store) | Done; 4 collections built |
| Retriever: dense search + type filter + threshold + **RRF fusion, cross-encoder reranking, per-source cap** | Done |
| Retrieval test set (**40 queries: 27 EN, 9 FR, 4 AR**) and evaluation script (15 configurations) | Done |
| Pooled human relevance judging | Sheet of **325 pages** ready, **not judged yet** |
| LLM client (local Ollama, `gemma3:4b`), versioned prompt loader | Done |
| Knowledge agent (retrieval + reranking, rewrite/fusion for Arabic) | Done |
| Query-rewrite prompts v1, v2, v3, evaluated | Done; used alone they hurt, fused with the raw query they help Arabic |
| Other agents (incident, vision, risk, verifier, report), FastAPI, n8n workflow | **Not started** |

Tests: 41 passing (`.venv/Scripts/python -m pytest`), all offline: no model download and no LLM needed.
Nothing has been committed to git yet.

Main findings (keyword labels, 34 relevant queries, provisional until human judging):
1. **Cross-encoder reranking is the best configuration**: MRR@10 0.726, Hit@5 0.912, Hit@10 1.000, source precision@5 0.806, against 0.696 / 0.824 / 0.882 / 0.776 without it. It costs about 4 s per query on CPU.
2. **Fixed-size and structure-aware chunking remain tied** (MRR@10 0.682 vs 0.699; head-to-head 6 wins, 8 losses, 20 ties).
3. **The contextual-header effect did not replicate.** It helped in the first run (0.726 vs 0.686) but not after the corpus and label changes (0.696 with header vs 0.714 without). We cannot claim it helps.
4. **LLM query rewriting used alone hurts** (v3: MRR@10 0.647). **Fused with the raw query (RRF) it helps**: MRR@10 0.708, and it is decisive for Arabic (MRR@10 0.369 → 0.812).
5. **multilingual-e5-base beats e5-small** on every breakdown (MRR@10 0.696 vs 0.599), which justifies the larger model.
6. **The per-source cap** (max 2 chunks per document) raises Hit@5 (0.824 → 0.882) at the cost of source precision.

---

## 2. Environment

| Item | Choice / state |
|---|---|
| Python | 3.13, virtual environment `.venv` (rebuilt; the old one pointed to a deleted Python 3.15) |
| Embedding stack | `torch` (CPU wheel) + `transformers`. **`sentence-transformers` was removed**, see problem ENV-01 |
| Vector store | ChromaDB, persistent, folder `chroma_db/` (gitignored) |
| LLM / VLM | **Ollama 0.40.5**, model **`gemma3:4b`** (multimodal, multilingual, about 3.3 GB) |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (about 0.5 GB, downloaded on first use) |
| Hardware (dev laptop) | i5-10300H, 8 GB RAM, GTX 1650 4 GB VRAM. gemma3:4b runs split 54% CPU / 46% GPU: about 24 s for the first call (model load), about 5 s per call after that. Dense retrieval about 0.13 s per query; with reranking about 4 s |

Setup for a teammate:
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install -r requirements.txt
# install Ollama (https://ollama.com), then:
ollama pull gemma3:4b
# download the PDFs listed in data/sources.csv into data/raw/ (data/raw is gitignored)
.venv/Scripts/python -m src.rag.ingest --strategy all      # about 30 min on CPU
```

---

## 3. Corpus

### 3.1 Documents (`data/sources.csv`)

| ID | Document | Publisher | Year | Lang | Type | Pages |
|---|---|---|---|---|---|---|
| FIRE-01 | Be Prepared for a Wildfire (V-1013) | FEMA / Ready.gov | 2018 | en | fire | 2 |
| FIRE-02 | How to Prepare for a Wildfire | FEMA / Ready.gov | ? | en | fire | 13 |
| FIRE-03 | Fire Management: Voluntary Guidelines | FAO | 2006 | en | fire | 74 |
| FIRE-04 | Guide de prévention des feux de végétation | Sécurité civile Nouvelle-Calédonie | 2017 | fr | fire | 81 |
| **FIRE-05** | Fire safety in the home | UK Government (Fire Kills) | 2021 | en | fire | 24 |
| **FIRE-06** | La sécurité incendie chez soi | UK Government (Fire Kills) | 2022 | fr | fire | 13 |
| **FIRE-07** | Guide sur la sécurité incendie (résidences, limitations à l'évacuation) | Ministère de la Sécurité publique du Québec | 2021 | fr | fire | 100 |
| FLOOD-01 | Be Prepared for a Flood (V-1005) | FEMA / Ready.gov | 2024 | en | flood | 2 |
| FLOOD-03 | Flood After Fire fact sheet | FEMA / NFIP | 2012 | en | flood | 1 |
| FLOOD-04 | Inondations – que faire? | Sécurité publique Canada | 2011 | fr | flood | 20 |
| FLOOD-05 | Floods in the WHO European Region: health effects | WHO Europe | 2013 | en | flood | 146 |
| STRUCT-01 | INSARAG Guidelines Vol. II Manual B: Operations | INSARAG / UN OCHA | 2020 | en | structural | 58 |
| STRUCT-02 | Post-disaster building evaluation guideline (draft) | NSET Nepal / UNDP | 2009 | en | structural | 30 |
| STRUCT-03 | FEMA P-2055 Post-disaster Building Safety Evaluation | FEMA | 2019 | en | structural | 228 |
| **STRUCT-04** | SOP on Collapsed Structure Search and Rescue | NDRF, Government of India | 2019 | en | structural | 62 |
| GEN-01 | CERT Basic Training Participant Manual | FEMA / Ready.gov | 2019 | en | general | 268 |
| GEN-02 | IFRC key messages for households and schools (2nd ed.) | IFRC / Save the Children | 2018 | en | general | 176 |
| GEN-03 | Same, French edition | IFRC / Save the Children | 2018 | fr | general | 165 |

**Bold** = added on 2026-10-16 to cover building fires (an urban emergency, typed `fire`) and collapse rescue, and to add French sources. The IDs are not consecutive (FLOOD-02 and FLOOD-06 are missing) because the Arabic documents were removed; IDs are kept stable so that labels never need renumbering.

### 3.2 Selection rationale
- **Official sources only** (government agencies, UN bodies, IFRC). The system grounds a safety-related assessment, so reliability and traceable citations matter more than volume. The `reliability` column is `high` for all but the NSET draft (`medium`).
- **Small and inspectable.** The corpus is small enough to be read and labelled for evaluation in the time available.
- **Content targeted at the agents' needs:** hazard description and secondary risks, safety and response actions, post-event assessment (building safety, re-entry), rescue procedures, and checklists of information to collect.
- **`general` category** for cross-hazard documents (evacuation, first aid, CERT skills), always allowed through the type filter.

### 3.3 Excluded and why
| Excluded | Reason |
|---|---|
| Arabic PDFs (FEMA flood sheet AR, Red Cross flood checklist AR) | Broken text extraction (RAG-01). Files kept in `data/raw/excluded/` |
| FEMA "Be Prepared for Any Hazard" suite | Duplicates the flood and wildfire sheets, and adds off-scope hazards |
| FEMA P-530 Earthquake Safety at Home | Earthquakes judged out of project scope |
| Scanned PDFs, news, Wikipedia | No OCR in scope; not authoritative |
| Gas-explosion guidance | No official, text-based public document found (only university/utility pages) |

---

## 4. RAG pipeline: architecture and choices

```
OFFLINE (python -m src.rag.ingest --strategy fixed|structure|all [--no-header] [--model M] [--dry-run])
data/sources.csv + data/raw/*.pdf
  -> extract.py     PyMuPDF: text blocks with page number, font size, bold; PDF bookmarks;
                    re-joins lines split across side-by-side text boxes
  -> clean          NFKC unicode, dehyphenation, running header/footer removal,
                    page numbers, dot leaders, private-use glyphs
  -> chunkers.py    A: fixed-size   |   B: structure-aware (+ contextual header)
  -> embeddings.py  multilingual-e5-base, "passage: " prefix, mean pooling, L2 norm
  -> Chroma         kb_fixed, kb_structure, kb_structure_noheader, kb_structure_multilingual-e5-small
                    (cosine HNSW) + data/processed/<collection>.jsonl and _stats.json

ONLINE (knowledge agent, src/agents/knowledge_agent.py)
IncidentInfo
  -> query = reported observations (raw)
     + if the language is not EN/FR: LLM rewrite to English (prompt rag_query_rewrite v3)
  -> "query: " prefix -> 30 dense candidates per query, filter disaster_type ∈ {type, general}
  -> reciprocal rank fusion of the query lists (when 2 queries)
  -> threshold 0.785 on cosine similarity
  -> cross-encoder reranking -> top-5
  -> KnowledgeResult(query_used, chunks with chunk_id, source, page range, heading, score)
```

### 4.1 Code map
| File | Responsibility |
|---|---|
| `src/config.py` | All settings (models, paths, chunk sizes, LLM endpoint) from `.env` / defaults |
| `src/rag/extract.py` | PDF → cleaned `Block`s (text, page, size, bold) + bookmarks; split-line merging |
| `src/rag/chunkers.py` | `fixed_size` and `structure_aware` behind one interface |
| `src/rag/embeddings.py` | Tokenizer-based token counter; e5 embedder (no sentence-transformers) |
| `src/rag/ingest.py` | Indexing CLI (strategy, header ablation, embedding model), JSONL dump, statistics |
| `src/rag/retriever.py` | `search()` pipeline: candidates → RRF fusion → threshold → rerank → per-source cap; CLI |
| `src/rag/reranker.py` | Multilingual cross-encoder reranker |
| `src/rag/evaluate.py` | Metrics, 15 configurations, rewrite cache, pooled judging sheet, reports |
| `src/llm/client.py` | OpenAI-compatible client (Ollama by default); `chat_json` validates with Pydantic, one retry |
| `src/llm/prompt_loader.py` | Loads `prompts/<name>/v<N>.yaml`; latest by default, pin with `PROMPT_<NAME>_VERSION` |
| `src/agents/knowledge_agent.py` | Knowledge agent (see pipeline above) |

### 4.2 Chunking
| | A. Fixed-size (baseline) | B. Structure-aware |
|---|---|---|
| Unit | Sliding token windows over the whole document | Document sections |
| Size / overlap | 400 tokens / 60 (15%), snapped to word starts | ≤ 400 tokens; long sections split by paragraph → sentence → window; sections < 80 tokens merged into the next one; overlap = trailing whole sentences ≤ 60 tokens |
| Headings | none | From PDF bookmarks if ≥ 5 entries, else typography (size ≥ body + 1.5 pt, or short bold line); levels by font-size rank |
| Embedded header | document title | `Title > Section > Subsection` |
| Chunks built (18 docs) | 1,917 (avg 397 tokens) | 2,575 (avg 287 tokens); 2,218 without header |

Justification:
- **400 tokens** because e5 truncates at 512 tokens. Sizes are counted **with the embedding model's own tokenizer**, so no chunk is ever silently truncated (0 chunks over the limit).
- **15% overlap** keeps boundary sentences retrievable without filling the top-k with near-duplicates.
- **Structure-aware** because guidance documents are organised by headings ("Before / During / After a flood"); a section is one coherent unit of advice.
- **Rejected alternatives:**
  - Semantic chunking: costly, unstable thresholds, and our documents already contain explicit structure.
  - Page chunks: too long, and they mix topics.
  - Sentence chunks: too little context to cite.

### 4.3 Embedding model: `intfloat/multilingual-e5-base`
- Multilingual (FR/EN documents, FR/AR/EN reports), so an incident in one language can retrieve a passage in another.
- Runs locally on CPU: no API cost and no network dependency during the demo.
- **Measured against `multilingual-e5-small`:** e5-base wins on every metric and breakdown (MRR@10 0.696 vs 0.599; fire 0.704 vs 0.515), so the extra size is worth it.
- **Rejected alternatives:**
  - `paraphrase-multilingual-MiniLM`: max 128 tokens, so our chunks would be truncated.
  - English-only models: fail on French and Arabic.
  - `bge-m3`: about twice the size, slow on CPU.
  - Hosted embeddings: cost, and a network dependency.
- Implemented directly with `transformers`: attention-masked mean pooling + L2 normalisation, with the asymmetric `query:` / `passage:` prefixes e5 was trained with.

### 4.4 Vector store and retrieval
- **ChromaDB**: embedded (no server), persistent, native metadata filtering, cosine HNSW. One collection per configuration.
- **Filter:** `disaster_type ∈ {incident type, "general"}`; no filter when the type is unknown or other.
- **Reciprocal rank fusion** (k = 60): merges the result lists of several queries by rank. It is rank-based, so the lists' scores don't need to be on the same scale.
- **Cross-encoder reranking** (two-stage retrieval): the bi-encoder searches the whole index cheaply; the cross-encoder reads query and passage together (full cross-attention) over the 30 candidates only.
- **Per-source cap:** at most N chunks per document; available, but not used by default (see 6.4).
- **Threshold:** 0.785 cosine, applied before reranking (see 6.6).

---

## 5. Evaluation method

### 5.1 Test set (`evaluation/retrieval_testset.csv`)
- **40 queries:** 34 relevant (12 fire, 12 flood, 10 structural) and 6 out-of-scope negatives (couscous recipe, email password, exchange rate, tax return, tourism in Tozeur, and a near-domain "locust swarms" question).
- **Languages:** 27 EN / 9 FR / 4 AR.
- **Styles:** 24 questions / 10 incident-style reports.
- **Added on 2026-10-16:**
  - English documents accepted as relevant for the French queries;
  - the new documents added to existing queries' labels where relevant;
  - 4 queries on building fire and collapse rescue;
  - 4 Arabic queries whose relevant documents are English/French, to measure cross-lingual retrieval.
- **Labels:** relevant `source_id:pages`, at **document + page level**, so the same labels are valid for every chunking strategy.
- **Protocol:** queries written before looking at retrieval results; pages labelled by keyword search over each document's page text.
- **Bias caveat:** the same person built the chunker and the test set, so a teammate should review it.

### 5.2 Metrics
- **Positive queries:**
  - Hit@k (k = 1, 3, 5, 10): a relevant chunk appears in the top k.
  - MRR@10: mean reciprocal rank of the first relevant chunk.
  - Source precision@5: share of the top 5 chunks from a relevant document.
- **Negative queries:** top-1 similarity, used to calibrate the threshold.
- **Breakdowns:** by disaster type, language and query style; head-to-head per query; list of failed queries with their top-3 results.
- **Noise:** run-to-run differences of up to about 0.006 were observed (approximate HNSW search). Differences smaller than one query (1/34 ≈ 0.03 on Hit@k) are not meaningful.

### 5.3 Commands
```bash
.venv/Scripts/python -m src.rag.evaluate --rewrite 3              # all 15 configurations
.venv/Scripts/python -m src.rag.evaluate --make-pool --rewrite 3 --pool-depth 3   # judging sheet
.venv/Scripts/python -m src.rag.retriever "water is entering houses" --type flood -k 5 --rerank
```
Reports go to `evaluation/results/retrieval_<timestamp>.md` (+ per-query `.csv`, `_summary.json`); rewrites are cached in `rewrites_v<N>.json`. Reference run for this document: `retrieval_20261017_0003.md`.

---

## 6. Results (keyword labels, 34 relevant queries, no human judgments yet)

### 6.1 All configurations
| Config | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 | Source P@5 |
|---|---|---|---|---|---|---|
| fixed | 0.529 | 0.794 | 0.882 | 0.882 | 0.682 | 0.753 |
| fixed+filter | 0.529 | 0.794 | 0.882 | 0.882 | 0.682 | 0.782 |
| structure | 0.618 | 0.765 | 0.824 | 0.882 | 0.699 | 0.753 |
| structure+filter | 0.618 | 0.735 | 0.824 | 0.882 | 0.696 | 0.776 |
| structure-noheader+filter | 0.618 | 0.735 | 0.824 | 0.971 | 0.714 | 0.735 |
| structure+filter [e5-small] | 0.500 | 0.676 | 0.765 | 0.824 | 0.599 | 0.712 |
| fixed+filter+cap2 | 0.529 | 0.824 | 0.912 | 0.912 | 0.691 | 0.701 |
| structure+filter+cap2 | 0.618 | 0.765 | 0.882 | 0.882 | 0.704 | 0.718 |
| **structure+filter+rerank** | 0.588 | 0.794 | **0.912** | **1.000** | **0.726** | 0.806 |
| structure+filter+rerank+cap2 | 0.588 | 0.824 | 0.912 | 0.941 | 0.720 | 0.706 |
| fixed+filter+rw3 | 0.529 | 0.765 | 0.794 | 0.882 | 0.654 | 0.635 |
| structure+filter+rw3 | 0.529 | 0.735 | 0.794 | 0.853 | 0.647 | 0.676 |
| structure+filter+fusion3 | 0.588 | 0.824 | 0.912 | 0.941 | 0.708 | 0.741 |
| structure+filter+fusion3+cap2 | 0.588 | **0.853** | 0.882 | 0.941 | 0.707 | 0.658 |
| structure+filter+fusion3+rerank | 0.559 | 0.824 | 0.912 | 0.971 | 0.707 | **0.812** |

(`rw3` = rewrite v3 alone; `fusion3` = raw query + rewrite v3 merged with RRF; `cap2` = at most 2 chunks per document.)

### 6.2 Breakdowns for the main configurations (Hit@5 / MRR@10)
| Config | fire (12) | flood (12) | structural (10) | EN (22) | FR (8) | AR (4) |
|---|---|---|---|---|---|---|
| fixed+filter | 1.000 / 0.642 | 0.917 / 0.792 | 0.700 / 0.600 | 0.909 / 0.782 | 0.875 / 0.500 | 0.750 / 0.500 |
| structure+filter | 0.917 / 0.704 | 0.833 / 0.804 | 0.700 / 0.558 | 0.909 / 0.788 | 0.750 / 0.608 | 0.500 / 0.369 |
| structure+filter+rerank | 0.750 / 0.600 | 1.000 / 0.875 | 1.000 / 0.698 | 0.909 / 0.743 | 0.875 / 0.705 | 1.000 / 0.675 |
| structure+filter+fusion3 | 0.833 / 0.706 | 1.000 / 0.889 | 0.900 / 0.492 | 0.909 / 0.705 | 0.875 / 0.664 | 1.000 / 0.812 |
| structure+filter+fusion3+rerank | 0.833 / 0.618 | 0.917 / 0.778 | 1.000 / 0.728 | 0.955 / 0.752 | 0.750 / 0.500 | 1.000 / 0.875 |

Key observations:
- **Reranking** helps flood and structural queries and non-English queries, but hurts fire queries (MRR 0.704 → 0.600). Its gain on reports (Hit@5 0.700 → 0.800) is larger than on questions.
- **Fusion** is the best option for Arabic; reranking alone is better for French.
- **No configuration wins everywhere.** The default (reranking, plus fusion only for languages absent from the corpus) follows the overall and per-language results.

### 6.3 Chunking (E1), filter (E2), header (E3)
- **Chunking:** fixed vs structure-aware MRR@10 0.682 vs 0.699; head-to-head 6 better / 8 worse / 20 tied → **no significant difference**. Structure-aware is better on fire (0.704 vs 0.642) and French (0.608 vs 0.500), worse on Arabic.
- **Filter:** ranks unchanged; only source precision moves (0.753 → 0.782 for fixed).
- **Header:** with header 0.696, without 0.714 (Hit@10 0.882 vs 0.971). In the first run (14 docs, 26 queries) the header helped (0.726 vs 0.686). The effect is **not robust**; report both runs honestly.

### 6.4 Per-source cap (E5)
cap2 raises Hit@5 (structure+filter 0.824 → 0.882; fixed+filter 0.882 → 0.912) by making room for short targeted documents, but lowers source precision (0.776 → 0.718), because it pushes in documents that are not labelled relevant. It is **available but off by default**: the reranker brings the same Hit@5 without that loss.

### 6.5 Query rewriting (E4): three prompt versions
| Query | MRR@10 (structure+filter) | EN | FR | AR |
|---|---|---|---|---|
| raw | **0.696** | **0.788** | 0.608 | 0.369 |
| rewrite v1 alone (26-query set) | 0.599 | – | – | – |
| rewrite v2 alone (26-query set) | 0.429 | – | – | – |
| rewrite v3 alone | 0.647 | 0.678 | 0.385 | **1.000** |
| raw + v3 fused (RRF) | **0.708** | 0.705 | **0.664** | 0.812 |

- **v1** compressed queries into keywords and lost facts.
- **v2** added generic "what should residents do" clauses that pulled generic content.
- **v3** keeps hazard-specific wording. Alone it still loses on EN/FR, but it translates Arabic perfectly, and fused with the raw query it is the best non-reranked configuration.
- **v3 still invents facts** in 3 of 40 rewrites ("coastal area" for Nabeul; "floodwater contamination causing carbon monoxide"; "livestock" in the locust question): a guardrail failure to document in the prompt library.

### 6.6 Threshold (best configuration: structure+filter+rerank)
- Score of the first relevant chunk: min 0.753, median 0.854, max 0.892.
- Top-1 score on out-of-scope queries: min 0.742, median 0.777, max 0.827.

| Threshold | Relevant hits kept | Negatives rejected |
|---|---|---|
| 0.780 | 90% | 67% |
| **0.785** | **87%** | **83%** |
| 0.800 | 81% | 83% |
| 0.830 | 61% | 100% |

The knowledge agent uses **0.785**, the best balanced value, which favours recall; the verifier agent is the second line of defence. The "locust swarms" question (0.827) cannot be rejected without losing many relevant hits.

### 6.7 Failed queries (no relevant chunk in top 5, best configuration)
- **FIRE-Q02** (smoke and asthma): the reranker prefers generic health passages.
- **FIRE-Q05** (French wildfire pushed by the wind toward a village).
- **FIRE-Q07** (fire extinguisher): the reranker moved the CERT extinguisher pages down.

All three are fire queries, consistent with the reranker's weak fire result. FIRE-Q08 (burn scar + rain), which failed in every configuration of the first run, is now solved by fusion with the v3 rewrite (which names "debris flow and flooding hazards").

---

## 7. Problems encountered

All entries are also in `evaluation/FAILURES.md` (IDs match).

### Environment
| ID | Problem | Cause | Fix | Status |
|---|---|---|---|---|
| ENV-01 | `sentence-transformers` (and even `transformers`) failed to import | Windows Application Control blocked a SciPy DLL from the system Python | Isolated venv; e5 pooling reimplemented with `transformers` | Fixed |
| ENV-02 | `.venv` unusable | Created with a Python 3.15 that was later uninstalled | Recreated with Python 3.13 | Fixed |
| ENV-03 | fema.gov blocks scripted downloads (HTTP 403) | Bot protection | Manual browser download | Workaround |
| ENV-04 | Full re-index takes about 50 min for 4 collections on CPU | e5 on CPU | `--dry-run` while tuning, one strategy at a time | Accepted |

### Extraction and chunking
| ID | Problem | Status |
|---|---|---|
| RAG-01 | Arabic PDFs: lam-alef letters swapped by extraction | Open: Arabic documents excluded, Arabic queries served cross-lingually (now measured, 6.2) |
| RAG-02 | Front-matter/cover headings became permanent parents | Mostly fixed |
| RAG-03 | Contents-page lines matched as headings | Fixed |
| RAG-04 | Icon-bullet glyphs in text | Fixed |
| RAG-09 | FIRE-04 lines cut across side-by-side text boxes | **Fixed**: split-line merging, enabled only for documents with overlapping seams (FIRE-04 has 338 such seams; the IFRC book, a true column layout, has 0) |
| RAG-10 | Corpus imbalance, no building-fire or collapse-rescue documents, few French documents | **Partly fixed**: 4 documents added (3 FR/EN fire-safety, 1 collapse SAR); still no gas-explosion guidance |

### Retrieval and evaluation
| ID | Problem | Status |
|---|---|---|
| RAG-05 | Keyword labels miss relevant passages | Open: 325-page judging sheet ready |
| RAG-06 | FIRE-Q08 (burn scar + rain) failed everywhere | **Solved by fusion** with the v3 rewrite |
| RAG-07 | French much weaker than English | **Improved**: French MRR 0.608 → 0.705 with reranking (labels now also accept English documents) |
| RAG-08 | Out-of-scope scores overlap relevant ones | Mitigated: threshold 0.785; verifier as second line |
| RAG-11 | Large general documents crowd the top-k | **Mitigated**: per-source cap and reranker both raise Hit@5 to 0.88–0.91 |
| RAG-12 *(new)* | Reranker hurts fire queries (MRR 0.704 → 0.600; FIRE-Q02, Q07 fail) | Open: mMARCO cross-encoder favours generic passages for these; candidate fix: rerank only the top 10, or combine reranker and cosine scores |
| RAG-13 *(new)* | Contextual-header effect not reproducible across runs | Open: report as inconclusive |

### Prompts
| ID | Problem | Status |
|---|---|---|
| PROMPT-01 | Rewrite v1: over-compression into keywords (MRR 0.599) | Iterated |
| PROMPT-02 | Rewrite v2: generic need clause dilutes the embedding (MRR 0.429) | Iterated |
| PROMPT-03 | Rewrite v3: better alone (0.647) but still below raw on EN/FR; invents facts in 3/40 rewrites | Used only through fusion for languages absent from the corpus; guardrail to strengthen in v4 |

---

## 8. Recommendations: status and what is left

### 8.1 Must do
| # | Item | Status |
|---|---|---|
| 1 | Pooled relevance judging | **Sheet ready**: `evaluation/retrieval_judgments.csv`, **325 (query, document, page) rows**, top-3 of 5 main configurations (fixed+filter, structure+filter, +cap2, +rerank, +fusion3). **Judging still to do by two teammates** (fill `relevant` with 1/0; the person who built the chunker should not judge); then re-run `python -m src.rag.evaluate --rewrite 3` |
| 2 | English documents accepted for French queries | Done (labels extended) |
| 3 | Re-run all experiments and freeze tables | Done on keyword labels (`retrieval_20261017_0003.md`); **re-run once more after judging** |

### 8.2 Should do
| # | Item | Status |
|---|---|---|
| 4 | Multi-query fusion (RRF) | Done (`retriever.rrf_fuse`); best for Arabic |
| 5 | Rewrite prompt v3 | Done (`prompts/rag_query_rewrite/v3.yaml`); results in 6.5 |
| 6 | Per-source cap | Done (`max_per_source`); off by default (6.4) |
| 7 | Cross-encoder reranker | Done (`src/rag/reranker.py`); **default in the knowledge agent** |
| 8 | FIRE-04 reading order | Done (RAG-09) |

### 8.3 Could do
| # | Item | Status |
|---|---|---|
| 9 | More documents (building fire, collapse, French) | Done: FIRE-05/06/07, STRUCT-04; gas explosion still missing |
| 10 | Arabic queries | Done: 4 queries; Arabic MRR 0.369 (raw) → 0.875 (fusion + rerank) |
| 11 | e5-base vs e5-small | Done: e5-base better everywhere (4.3) |

### 8.4 Remaining RAG improvements (optional)
- Fix RAG-12: rerank fewer candidates, or blend reranker and cosine scores; re-evaluate on fire queries.
- Rewrite prompt v4: stronger no-new-facts guardrail (e.g. require that every content word comes from the report, or verify the rewrite with a second check).
- Widen the test set (34 relevant queries is small; 1 query = 3 points of Hit@k).

### 8.5 Rest of the project (not started, needed for the demo)
- **Agents:**
  - Incident agent (`prompts/incident_extraction`): structured extraction with `chat_json`; its `language` field drives the knowledge agent's fusion decision.
  - Vision agent (`gemma3:4b` multimodal, `client.vision` already exists).
  - Risk agent, verifier agent (LLM-as-judge on evidence), report agent.
- **FastAPI** endpoints per agent plus `/pipeline`.
- **n8n workflow** calling the endpoints.
- **Prompt library** (`prompts/PROMPT_LIBRARY.md`): the query-rewrite v1 → v2 → v3 story (6.5) is its first complete entry, with failures and numbers.
- **Latency budget:** about 5 s per gemma3:4b call, plus 4 s of reranking. A full pipeline (about 5 LLM calls, 1 vision call) takes about 35–45 s. Warm the model before the demo (first call about 24 s).

---

## 9. Points to be ready for in Q&A
- **Why tokens counted with the model's tokenizer?** Truncation at 512 is silent; French and Arabic tokenise into more tokens per word.
- **Bi-encoder vs cross-encoder:** why dense retrieval first, why the cross-encoder only reranks 30 candidates, and why it costs about 30× more time.
- **Reciprocal rank fusion:** why rank-based (scores of different queries are not comparable), k = 60.
- **e5 prefixes and mean pooling;** cosine on L2-normalised vectors = dot product.
- **HNSW is approximate:** it explains the small run-to-run differences we observed.
- **Why page-level labels and pooled judging** (fair across strategies; TREC-style pooling).
- **Why the filter didn't change rankings, and why we kept it.**
- **Why query rewriting failed alone but works fused:** a rewrite loses or invents facts, while fusion keeps the raw query's evidence and adds translation.
- **Why reranking is the default even though it hurts fire queries** (overall and multilingual gains; known trade-off, logged as RAG-12).
- **Why e5-base and not e5-small** (measured).
- **Why no fine-tuning:** no labelled data at the needed scale, short timeline; RAG + prompting provide the grounding. Know how LoRA would work here.
- **Why the threshold is 0.785** (recall-oriented, score compression, verifier as second line of defence).
