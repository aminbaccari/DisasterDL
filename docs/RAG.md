# DisasterAI: the RAG component

*Reference document for the team and the final report. Status as of 2026-10-18. It covers the whole retrieval-augmented generation (RAG) component, all seven steps (loading, chunking, embedding and indexing, retrieval, prompt construction, generation, evaluation): what it does, what we built, every design choice and why, how we evaluated it, what failed, where we stand, and what could still be improved.*

---

## 1. In one page

**What the RAG does.** Given an incident (a fire, flood or building emergency described by a citizen), it retrieves the most relevant passages of official disaster-response documents, with their source and page. It then generates a short **grounded answer**, in which every statement cites its passage and quotes it verbatim. The downstream agents (risk, verifier, report) therefore build on documented guidance instead of the LLM's general knowledge. When nothing relevant is found, or the request is not an emergency, it returns no guidance and says so.

| RAG step | Implementation |
|---|---|
| 1. Document loading | `src/rag/extract.py`: 18 official PDFs, page-level extraction and cleaning |
| 2. Chunking | `src/rag/chunkers.py`: fixed-size and structure-aware, 400 tokens |
| 3. Embedding and indexing | `src/rag/embeddings.py`, `src/rag/ingest.py`: multilingual-e5-base, ChromaDB |
| 4. Retrieval | `src/rag/retriever.py`, `reranker.py`: filter, threshold, reranking, fusion |
| 5. Prompt construction | `prompts/rag_answer/v4.yaml` + `src/rag/generate.py`: numbered passages with source, page and section |
| 6. Generation | `src/rag/generate.py`: gemma3:4b with built-in safeguards (scope gate, scope decision, refusal retry, citation and quote checks) |
| 7. Evaluation | Retrieval: `evaluate.py` + `judging.py`. Generation: `evaluate_generation.py` |

**What we built.**
- A corpus of **18 official PDFs** (FEMA, WHO, FAO, IFRC, INSARAG/UN OCHA, India's NDRF, Public Safety Canada, the UK Government and Québec), about 1,550 pages in English and French.
- An indexing pipeline: PDF extraction and cleaning, **two chunking strategies**, multilingual embeddings, and a ChromaDB vector store.
- A retriever with metadata filtering, a relevance threshold, multi-query fusion, cross-encoder reranking and a per-document cap.
- An evaluation with a 36-query test set and **relevance labels from a panel of three independent LLM judges**, 15 retrieval configurations compared, and every failure logged.

**Final configuration** (used by the knowledge agent):

> structure-aware chunks → multilingual-e5-base embeddings → 30 candidates filtered by disaster type → threshold 0.785 → cross-encoder reranking → top 5

**Headline result** (30 relevant test queries, strict labels):

| | Best configuration (with reranking) | Same retriever without reranking |
|---|---|---|
| MRR@10 | **0.868** | 0.781 |
| Hit@1 | **0.80** | 0.67 |
| Hit@5 | 0.93 | 0.90 |
| Hit@10 | **1.00** | 0.93 |

So the first retrieved passage is directly relevant for 80% of queries, and a relevant passage is always in the top 10.

**Generation result** (same 36 queries, prompt `rag_answer` v4, judged claim by claim by two models independent from the generator):

| Metric | Value |
|---|---|
| Out-of-scope queries correctly refused | **6/6** |
| Relevant queries answered with guidance | 29/30 (no false refusal; 1 retrieval miss) |
| Citations pointing to a provided passage | **100%** (180/180) |
| Statements passed on after the quote check | 141 of 174 |
| Of those: both judges "supported" / at least one "unsupported" | **84.4% / 1.4%** |
| Answer relevance (0–2) | 1.83 (gpt-oss) / 1.62 (Qwen) |
| Latency per answer (median) | 78 s |

**Is it satisfying?** Yes, for a prototype and for the course requirements, with honest caveats: a small test set, labels from LLMs rather than humans, weaker fire queries, and slow generation on the laptop (about 80 s). The full assessment is in section 10.

---

## 2. Requirements we answer

The course brief asks the RAG part (25% of the grade) to justify four things and evaluate retrieval. We also evaluate generation, which the brief does not require:

| Requirement | Where it is answered |
|---|---|
| Choice of corpus (source, size, format, fit to the use case) | Section 3 |
| Chunking strategy, size and overlap, and why; comparison of two strategies "strongly valued" | Section 4.2, results in 7 |
| Embedding model and vector store | Sections 4.3, 4.4 |
| Retrieval setup (top-k, filters, reranking) | Section 4.5 |
| Short evaluation of retrieval quality on test queries | Sections 6 and 7 |
| (Beyond the brief) Generation and its evaluation | Section 8 |

---

## 3. Corpus

### 3.1 Documents

| ID | Document | Publisher | Year | Lang | Type | Pages |
|---|---|---|---|---|---|---|
| FIRE-01 | Be Prepared for a Wildfire | FEMA / Ready.gov | 2018 | en | fire | 2 |
| FIRE-02 | How to Prepare for a Wildfire | FEMA / Ready.gov | ? | en | fire | 13 |
| FIRE-03 | Fire Management: Voluntary Guidelines | FAO | 2006 | en | fire | 74 |
| FIRE-04 | Guide de prévention des feux de végétation | Sécurité civile Nouvelle-Calédonie | 2017 | fr | fire | 81 |
| FIRE-05 | Fire safety in the home | UK Government (Fire Kills) | 2021 | en | fire | 24 |
| FIRE-06 | La sécurité incendie chez soi | UK Government (Fire Kills) | 2022 | fr | fire | 13 |
| FIRE-07 | Guide sur la sécurité incendie (résidences) | Ministère de la Sécurité publique du Québec | 2021 | fr | fire | 100 |
| FLOOD-01 | Be Prepared for a Flood | FEMA / Ready.gov | 2024 | en | flood | 2 |
| FLOOD-03 | Flood After Fire fact sheet | FEMA / NFIP | 2012 | en | flood | 1 |
| FLOOD-04 | Inondations – que faire? | Sécurité publique Canada | 2011 | fr | flood | 20 |
| FLOOD-05 | Floods in the WHO European Region: health effects | WHO Europe | 2013 | en | flood | 146 |
| STRUCT-01 | INSARAG Guidelines Vol. II Manual B: Operations | INSARAG / UN OCHA | 2020 | en | structural | 58 |
| STRUCT-02 | Post-disaster building evaluation guideline (draft) | NSET Nepal / UNDP | 2009 | en | structural | 30 |
| STRUCT-03 | FEMA P-2055 Post-disaster Building Safety Evaluation | FEMA | 2019 | en | structural | 228 |
| STRUCT-04 | SOP on Collapsed Structure Search and Rescue | NDRF, Government of India | 2019 | en | structural | 62 |
| GEN-01 | CERT Basic Training Participant Manual | FEMA / Ready.gov | 2019 | en | general | 268 |
| GEN-02 | IFRC key messages for households and schools | IFRC / Save the Children | 2018 | en | general | 176 |
| GEN-03 | Same, French edition | IFRC / Save the Children | 2018 | fr | general | 165 |

Totals: 18 documents (13 English, 5 French), about 1,550 pages; 7 fire, 4 flood, 4 structural, 3 general. Provenance, reliability, URL and licence for each document are in `data/sources.csv`.

### 3.2 Why this corpus
- **Official sources only.** The system grounds a preliminary assessment of a safety-related situation. Authoritative, traceable guidance matters more than volume, and every citation must point to a real document and page. The `reliability` column is `high` for all documents except the 2009 NSET draft (`medium`).
- **Content matched to what the agents need:** hazard descriptions and secondary risks, what to do before, during and after an event, post-event building assessment and re-entry, rescue procedures, and checklists of information to collect (which feed the "missing information" field).
- **A `general` category** for cross-hazard documents (evacuation, first aid, volunteer response skills). It is always allowed through the type filter.
- **Small on purpose.** About 18 documents can be read, inspected and labelled for evaluation within a five-week project. A large scraped corpus would add near-duplicates and noise, not better answers.
- **Format:** text-based PDFs, extracted page by page so that every passage keeps its page number.

### 3.3 What we excluded, and why
| Excluded | Reason |
|---|---|
| Arabic PDFs (FEMA flood sheet, Red Cross checklist) | Text extraction swaps letters (failure RAG-01); Arabic was later dropped from the evaluation too |
| FEMA "Be Prepared for Any Hazard" suite | Duplicates our flood and wildfire sheets and adds off-scope hazards (active shooter, cyberattack) |
| FEMA P-530 Earthquake Safety at Home | Earthquakes are out of the project's scope |
| Scanned PDFs, news, Wikipedia | No OCR in scope; not authoritative |
| Gas-explosion guidance | We found no official, text-based public document |

### 3.4 How the corpus evolved
- **First version:** 15 documents, including 2 in Arabic.
- **Arabic removed:** both Arabic PDFs were dropped (broken extraction). FEMA P-2055 was added, and P-530 was left out.
- **Imbalance analysis:** the first corpus had no building-fire guidance, collapse-rescue procedures or French fire safety (failure RAG-10).
- **Four documents added:** FIRE-05/06/07 and STRUCT-04, after which the corpus was re-indexed.

---

## 4. Pipeline and design choices

```
OFFLINE: python -m src.rag.ingest --strategy fixed|structure|all [--no-header] [--model M] [--dry-run]
data/sources.csv + data/raw/*.pdf
  → extract   PyMuPDF: text blocks with page number, font size, bold; PDF bookmarks
  → clean     unicode NFKC, dehyphenation, header/footer removal, page numbers, dot leaders,
              private-use glyphs, re-joining lines split across text boxes
  → chunk     A. fixed-size  |  B. structure-aware with contextual header
  → embed     multilingual-e5-base ("passage: " prefix, mean pooling, L2 normalisation)
  → store     ChromaDB collection per configuration (cosine HNSW) + JSONL dump for inspection

ONLINE: knowledge agent (src/agents/knowledge_agent.py)
incident → query (reported observations; + LLM rewrite fused by RRF for non-EN/FR reports)
  → "query: " prefix → 30 dense candidates, filter disaster_type ∈ {incident type, general}
  → threshold 0.785 → cross-encoder reranking → top 5 → passages with source, page, section
```

| File | Role |
|---|---|
| `src/rag/extract.py` | PDF extraction and cleaning |
| `src/rag/chunkers.py` | The two chunking strategies |
| `src/rag/embeddings.py` | Token counter and e5 embedder |
| `src/rag/ingest.py` | Indexing command line, statistics |
| `src/rag/retriever.py` | Retrieval pipeline |
| `src/rag/reranker.py` | Cross-encoder reranker |
| `src/rag/evaluate.py` | Retrieval evaluation |
| `src/rag/judging.py` | LLM judging panel for the relevance labels |
| `src/agents/knowledge_agent.py` | Agent that wraps retrieval for the pipeline |

### 4.1 Extraction and cleaning
- **PyMuPDF**, page by page, keeping each text block's page number, dominant font size and boldness. Typography is what the structure-aware chunker uses to find headings when a PDF has no bookmarks.
- **Cleaning steps:**
  - Unicode NFKC normalisation (splits ligatures such as "ﬁ");
  - removal of soft hyphens and zero-width characters;
  - dehyphenation of words split across lines;
  - removal of running headers and footers (margin lines repeated on 30% or more of pages);
  - removal of page-number lines, table-of-contents dot leaders and private-use icon glyphs.
- **Split-line merging** (added after failure RAG-09).
  - **The problem:** one French guide cuts every line of a paragraph into a left and a right text box, often mid-word.
  - **The fix:** lines on the same baseline whose boxes touch or overlap are re-joined, and a seam character repeated by overlapping boxes is dropped.
  - **Why it can't damage two-column layouts:** wider seams are merged only in documents detected as split layouts (at least 25% overlapping seams). Real two-column documents (0 overlapping seams) are left alone.

### 4.2 Chunking: two strategies compared
| | A. Fixed-size (baseline) | B. Structure-aware |
|---|---|---|
| Unit | Token windows over the whole document | Document sections |
| Size | 400 tokens | ≤ 400 tokens |
| Overlap | 60 tokens (15%) | Trailing whole sentences ≤ 60 tokens |
| Boundaries | Snapped to word starts | Headings: PDF bookmarks when at least 5 exist, else typography (≥ 1.5 pt above body size, or a short bold line); long sections split by paragraph, then sentence, then window; sections under 80 tokens merged into the next |
| Embedded text | Document title + chunk | `Title > Section > Subsection` + chunk |
| Chunks built | 1,917 (average 397 tokens) | 2,575 (average 287 tokens) |

**Why these parameters**
- **400 tokens** because the e5 model truncates at 512 tokens. Sizes are counted with **the embedding model's own tokenizer**, so no chunk is ever silently truncated: zero chunks exceed the limit. Counting characters would not guarantee this, especially for French, which uses more tokens per word.
- **15% overlap** keeps a sentence that straddles a boundary retrievable from either side, without filling the top results with near-duplicates.
- **Structure-aware** was our hypothesis: guidance documents are organised by headings ("Before / During / After a flood"), so a section is one coherent unit of advice, and the header injects hazard words into chunks whose body never names the hazard.
- **Alternatives rejected:**
  - semantic chunking (costly, unstable thresholds, and the documents already have explicit structure);
  - page-level chunks (too long, they mix topics);
  - sentence-level chunks (too little context to cite).

**What the evaluation showed:** no retrieval gain from structure-aware chunking (section 7.2). We still use it in the final configuration, because its chunks carry their section heading, which the report agent can cite ("FEMA P-2055, §3.1.2 Assessment Work, p. 11"). Since retrieval quality is equal, that's a usability reason, not a quality one.

### 4.3 Embedding model: `intfloat/multilingual-e5-base`
- **Multilingual.** Documents are in English and French, and reports may come in either, so an incident in one language can retrieve a passage in the other.
- **Runs locally on CPU:** no API cost and no network dependency during the demo. Indexing all collections takes about 30 minutes.
- **Measured against `multilingual-e5-small`:** e5-base wins on every breakdown (strict MRR@10 0.781 vs 0.662).
- **Rejected alternatives:**
  - `paraphrase-multilingual-MiniLM`: truncates at 128 tokens, so it would cut our chunks.
  - English-only models: fail on French.
  - `bge-m3`: about twice the size, too slow on CPU.
  - Hosted embeddings: cost, and a network dependency.
- **Implementation:** a transformer with attention-masked mean pooling and L2 normalisation, written directly with `transformers` (sentence-transformers was blocked on the development machine, ENV-01). Queries get the `query:` prefix and passages `passage:`, as e5 was trained.

### 4.4 Vector store: ChromaDB
- **Embedded and persistent:** no server to run. It has native metadata filtering and cosine similarity over an HNSW index.
- **One collection per configuration** (strategy, header, model), so all experiments run against identical queries.
- **Metadata on every chunk:** source ID, title, publisher, year, language, disaster type, reliability, page range, section heading, token count, strategy.
- **Rejected:** FAISS (no metadata filtering or persistence built in), and Qdrant, Weaviate or pgvector (they need a server, overkill for about 2,500 vectors).
- **Note:** HNSW is approximate. We observed differences of about ±0.006 between identical runs, which is negligible.

### 4.5 Retrieval setup
| Setting | Value | Why |
|---|---|---|
| Candidates | 30 | The pool that reranking (and fusion or the cap) work on |
| Final top-k | 5 | Enough evidence for the risk agent without weak passages; Hit@5 = 0.93 |
| Metadata filter | `disaster_type ∈ {incident type, general}`; none if the type is unknown | Stops flood guidance being cited for a fire, while keeping cross-hazard advice |
| Threshold | Cosine ≥ 0.785 | Lets the retriever answer "nothing relevant"; calibrated on out-of-scope queries (section 7.6) |
| Reranking | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` on the 30 candidates | A cross-encoder reads query and passage together, which is more precise than comparing two separate vectors, but too slow for the whole index (two-stage retrieval) |
| Multi-query fusion | Reciprocal rank fusion (k = 60) of the raw query and an LLM rewrite | Rank-based, so it merges lists whose scores aren't comparable. Used only for reports in languages the corpus doesn't contain |
| Per-document cap | Optional (max 2 chunks per document) | Stops one long document filling the top-k. Off by default: reranking gives the same gain without the loss in precision |

---

## 5. Prompts used by the RAG

Prompts are versioned YAML files (`prompts/<name>/v<N>.yaml`) that record their role, techniques, changelog and the failures each version fixed.

**Query rewrite** (`rag_query_rewrite`, model gemma3:4b): rewrites an incident report into one English search query.

| Version | Change | Result (MRR@10, keyword labels) | Diagnosis |
|---|---|---|---|
| v1 | Plain instruction, JSON output | 0.599 vs 0.726 raw | Over-compression into 3–5 keywords drops decisive facts ("roads blocked, water entering homes" → "flood response ground floor flooding") |
| v2 | Natural 15–30-word sentence keeping facts and the person's need, 3 few-shot examples | 0.429 | The generic need clause ("what immediate safety measures should residents take") dominates the embedding and pulls generic messages |
| v3 | Hazard-specific wording like a document heading, list of generic phrases to avoid, few-shot examples | Alone: 0.669 strict vs 0.781 raw (final labels). **Fused with the raw query: 0.835** | Alone still loses on English/French, and invents facts in 3 of 40 rewrites ("coastal area" for Nabeul). As a second query, it adds what the raw query misses (e.g. names "debris flow and flooding hazards" for a burn-scar report) |

**Decision:** the raw query is always used. The rewrite is added through fusion only for reports in a language absent from the corpus (Arabic).

**Grounded answer** (`rag_answer`, model gemma3:4b): the generation step (section 8).

| Version | Change | Observed behaviour | Diagnosis |
|---|---|---|---|
| v1 | Grounding rules, numbered passages, citation tags, verbatim quote, abstention path, JSON | **False abstention** on "Heavy flooding in Nabeul, roads blocked, water entering ground-floor homes", although the 5 passages were flood-safety guidance | Its `not_covered` list explained it: "the specific details of the flooding in Nabeul". The model read "relevant" as "about this exact event" |
| v2 | States that documents are general guidance and relevance means "applies to this type of situation"; abstain only if every passage is about another hazard; no tags inside statements; one example | Nabeul answered (6 statements, 5/6 quotes verified), but **over-correction**: "best recipe for lamb couscous" got food-hygiene advice | Making abstention harder made the model treat any passage as applicable |
| v3 | v2 + a **scope check first**: if the input does not describe an emergency or disaster situation, return no guidance | Nabeul 6/6 quotes verified; couscous refused ("outside the scope of the knowledge base"). Still answers 2 of 6 out-of-scope questions (locust swarms, income tax), refuses 1 French wildfire report, 7.9% of statements unsupported | The scope check passes for near-domain questions (GEN-03); descriptive passages read as not applicable (GEN-05); general knowledge attached to the nearest citation (GEN-04) |
| **v4** | Scope as an explicit `in_scope` field enforced in code, limited to fire, flood and building emergencies; **hazard match** (passages must concern the incident's hazard); "how the hazard behaves" counts as guidance; **quote first** (copy the sentence, then rephrase only it) | Out-of-scope refused **6/6**; **no false refusal**; statements passed on: 1.4% unsupported (v3: 1.7%) with more of them kept (141 vs 119) | Trade-off: more statements and quote attempts lower raw faithfulness (74.7% vs 80.0%) and one judge rates answers less relevant (1.62 vs 1.89); see GEN-08 |

**Generation judge** (`generation_judge` v1, offline evaluation only): claim-level faithfulness and answer relevance (section 8.3).

**Relevance judge** (`relevance_judge`, offline evaluation only), versions v1 → v3. See section 6.3.

---

## 6. How we evaluated retrieval

### 6.1 Test set (`evaluation/retrieval_testset.csv`)
- **36 queries:** 30 relevant (11 fire, 10 flood, 9 structural) and 6 out-of-scope (couscous recipe, email password, exchange rate, tax return, tourism in Tozeur, locust swarms).
- **Languages and styles:** 22 English and 8 French relevant queries; 22 questions and 8 incident-style reports ("Heavy flooding in Nabeul, several roads are blocked…").
- The queries were written before looking at any retrieval result.
- **Arabic:** 4 Arabic queries existed and were dropped from the final evaluation by team decision.

### 6.2 Pooling
- **What's judged:** only the pages that the main configurations actually return. This is TREC-style pooling.
- **The pool:** the **top 3 pages of 5 configurations** (fixed+filter, structure+filter, +cap2, +rerank, +fusion), giving **279 (query, document, page) pairs**.
- **Page-level judging:** relevance is judged per page, not per chunk, so the same labels apply to every chunking strategy and the comparison stays fair.

### 6.3 Relevance labels from a panel of LLM judges
**Why not keyword labels.** Our first labels came from keyword search over the PDFs. They missed relevant pages that use other wording, so correct results were counted as failures (RAG-05). Measured afterwards, they agree with the final labels on only **53.6% of pages (κ = 0.21)**.

**Why a panel instead of one judge.**
- **One judge has systematic biases** (leniency, preferred wording) and gives no way to measure how reliable its labels are.
- **Two judges from different model families** have different blind spots, and their agreement (Cohen's κ) is a reliability figure.
- **A third family breaks ties.** This approach is known as an "LLM jury" (Verga et al., 2024, *Replacing Judges with Juries*).

| Role | Model | Family | Items |
|---|---|---|---|
| Judge 1 | `openai/gpt-oss-120b`, reasoning effort high (Groq) | OpenAI | All 279 |
| Judge 2 | `qwen/qwen3.8-27b` (Groq) | Alibaba | All 279 |
| Tie-breaker | `llama3.1:8b`, 4-bit (local Ollama) | Meta | The 91 disputed items |

**Safeguards**
- **Independence:** none of these families is used by the system. Claude, which helped build the system and draft the queries, and Gemma, which writes the query rewrites, were deliberately excluded.
- **Blinding:** each judge sees only the query, the document title, the page number and the page text (up to 2,500 characters), in shuffled order. Configuration names and old labels stay hidden.
- **Prompt v3:** a 0/1/2 rubric, one anchor example per grade (written for the prompt, not from the test set), a one-sentence reason, then the score, and **a verbatim quote** for scores of 1 or 2.
- **Quote check:** every quote is verified automatically against the page. A vote with an invented quote is discarded.
- **Vote:**
  - The tie-breaker is called when the two scores differ or a vote is invalid.
  - The final score is the median of the valid votes; with two valid votes that differ, the lower one is kept.
  - **Strict labels:** relevant means a score of 2. **Lenient labels:** relevant means a score of 1 or more.

**How the judges were chosen** (calibration on items independent of the judges):
- `qwen2.5:3b` scored 0 on almost everything, so it was rejected.
- `gemma3:4b` was set aside because it writes the system's query rewrites.
- `llama3.2:3b` invented quotes on 25 of 325 items.
- Mistral's free account had a zero quota.
- `llama3.1:8b` passed calibration as tie-breaker (14 of 15 known-relevant pages found, 1 invented quote).

**Agreement achieved**
| Measure | Value |
|---|---|
| Cohen's κ, judge 1 vs judge 2, relevant vs not | **0.747** (substantial) |
| Cohen's κ, strict | 0.733 |
| Cohen's κ, all three grades | 0.657 |
| Raw agreement (exact grade / relevant vs not) | 78% / 90.5% |
| Invented quotes discarded | gpt-oss-120b 28 (10%), Qwen 12, Llama 4 of 91 |
| Final grades 0 / 1 / 2 | 76 / 77 / 125 (1 item unresolved) |

### 6.4 Metrics
- **Hit@k** (k = 1, 3, 5, 10): a relevant chunk appears in the top k.
- **MRR@10:** the mean of 1 / rank of the first relevant chunk.
- **Source precision@5:** the share of the top 5 that comes from a relevant document.
- **Threshold calibration:** the top-1 similarity on the out-of-scope queries.
- **Breakdowns:** by hazard type, language and query style.
- **Size of an effect:** with 30 queries, one query moves Hit@k by 3.3 points, so smaller differences are noise.

---

## 7. Retrieval results

Reference runs: `evaluation/results/retrieval_20261017_2039_strict.md` (primary) and `retrieval_20261017_2028_lenient.md`.

### 7.1 The fair comparison: pooled configurations
Every top-3 page of these five configurations was judged.

| Configuration | MRR@10 strict | Hit@1 strict | Hit@5 strict | Hit@10 strict | MRR@10 lenient |
|---|---|---|---|---|---|
| **structure + filter + rerank** | **0.868** | **0.800** | 0.933 | **1.000** | **1.000** |
| structure + filter + fusion (raw + rewrite v3) | 0.835 | 0.767 | 0.933 | 0.967 | 0.978 |
| fixed + filter | 0.803 | 0.733 | 0.933 | 0.933 | 0.950 |
| structure + filter + cap2 | 0.796 | 0.667 | **0.967** | 0.967 | 0.918 |
| structure + filter | 0.781 | 0.667 | 0.900 | 0.933 | 0.906 |

**The ranking is the same under strict and lenient labels**, so the conclusions don't depend on how strictly "relevant" is defined.

### 7.2 Experiment by experiment
| Experiment | Comparison (MRR@10 strict) | Conclusion |
|---|---|---|
| E1 Chunking | Fixed 0.803 vs structure 0.781 (filtered); head-to-head 5 wins / 5 losses / 20 ties | **No significant difference**: our hypothesis that structure-aware chunking retrieves better was not confirmed on this corpus |
| E2 Type filter | Fixed: 0.803 with vs 0.803 without (lenient 0.950 vs 0.921) | Small or no gain on ranking, but cleaner evidence (source precision up). Kept: cheap and safe |
| E3 Contextual header | 0.781 with vs 0.813 without | **No gain**; the effect varied between runs and is not real |
| E4 Query rewrite | Raw 0.781; rewrite alone 0.669; fusion 0.835 | **Rewriting alone hurts; fusing it with the raw query helps** |
| E5 Reranking / cap | Rerank 0.868; cap2 0.796; rerank + cap2 0.850 | **Reranking is the best single improvement**; the cap adds nothing once reranking is on |
| E6 Embedding model | e5-base 0.781 vs e5-small 0.662 | **e5-base clearly better** |

Configurations outside the pool (no header, e5-small, rewrite alone) can return pages that weren't judged and fall back to the keyword labels, so their scores lean pessimistic. Their large gaps (e5-small, rewrite alone) are still meaningful; the no-header result should be read as "no measurable gain".

### 7.3 Breakdowns (MRR@10 strict)
| Configuration | Fire (11) | Flood (10) | Structural (9) | English (22) | French (8) |
|---|---|---|---|---|---|
| fixed + filter | **0.841** | 0.825 | 0.731 | 0.811 | 0.781 |
| structure + filter | 0.828 | 0.800 | 0.704 | 0.811 | 0.701 |
| **structure + filter + rerank** | 0.799 | **0.875** | **0.944** | **0.859** | 0.893 |
| structure + filter + fusion | **0.877** | 0.792 | 0.833 | 0.798 | **0.938** |

- **Reranking** helps structural queries most (0.70 → 0.94), but slightly hurts fire queries (0.83 → 0.80), a known trade-off (RAG-12).
- **Fusion** is best for fire and French queries; with only 8 French queries, that's not enough to justify a per-language rule.

### 7.4 Strict vs lenient labels
With lenient labels, where partly relevant pages count, many configurations reach Hit@5 = 1.0 and reranking reaches MRR = 1.0, so the labels no longer separate the configurations. **Strict labels are the primary result**, and lenient labels an upper bound.

### 7.5 Remaining failures (best configuration, strict)
- **FIRE-Q02:** *"Smoke from a nearby forest fire is filling our neighbourhood and my elderly father has asthma."* The reranker prefers generic health passages.
- **FIRE-Q05 (French):** *"Un incendie de végétation s'est déclaré près des maisons, le vent pousse les flammes vers le village."*

### 7.6 Answering "nothing relevant"
| Score | Range |
|---|---|
| First relevant chunk (relevant queries) | 0.758 – 0.894, median 0.861 |
| Top-1 chunk (out-of-scope queries) | 0.742 – 0.827, median 0.777 |

The two ranges overlap: e5 similarity scores are compressed into a narrow band. The threshold is a trade-off:
- **0.785** (chosen) keeps 83% of relevant hits and rejects 5 of 6 out-of-scope queries.
- **0.830** rejects all 6 but keeps only 71%.

We chose 0.785, which favours recall: in a safety tool, missing relevant guidance is worse than letting one weak passage through, and the verifier agent is the second line of defence. The "locust swarms" question (0.827) can't be rejected without losing many relevant hits.

### 7.7 How our conclusions changed (and why that matters)
| Stage | Labels | What we believed | What changed |
|---|---|---|---|
| First runs (14 docs, 26 queries) | Keyword | The header helps (+0.04 MRR), structure ≈ fixed | Labels incomplete |
| After corpus fixes (18 docs, 34 queries) | Keyword | Reranking best (0.726), header no longer helps, rewrites hurt | Labels still incomplete; absolute scores far too low |
| **Final** (36 queries, EN/FR) | **LLM panel** | Reranking best (0.868), fusion second, chunking tie, no header effect, e5-base > e5-small | – |

Two lessons for the report:
- **Absolute scores were badly underestimated** with keyword labels: MRR 0.70 against 0.87 with the panel labels.
- **Small effects** such as the header **flipped between runs**, while the big ones (reranking, rewrite alone, e5-small) held every time.

---

## 8. Generation: prompt construction, generation and evaluation (steps 5–7)

### 8.1 Why generation is part of the RAG
- **Retrieval alone hands the agents raw passages.** Steps 5 and 6 turn them into a short, cited summary of what the documents say about the incident: "retrieved guidance".
- **The schema keeps this separate from reported facts (incident agent) and AI inference (risk agent).**
- **The knowledge agent returns both the passages and the grounded answer** (`KnowledgeResult.answer`).
- **The system has no verifier agent,** so the generation step has to check itself (8.2).

### 8.2 How it works (`src/rag/generate.py`)
1. **Prompt construction (step 5).**
   - The retrieved passages (top 5 after reranking) are numbered `[S1]…[S5]`. Each is labelled with its citation, document title and section, e.g. `[S1] FLOOD-01 p.2, Be Prepared for a Flood, section: HOW TO STAY SAFE > Survive DURING`.
   - Each passage is capped at 1,800 characters, so the prompt, five passages and the answer fit gemma's 4,096-token context. A typical prompt is about 1,700 tokens.
   - They are inserted with the incident into `prompts/rag_answer/v4.yaml`.
2. **Generation (step 6).** gemma3:4b (local Ollama) returns JSON:
   - `in_scope` (its scope decision);
   - an `answer` (at most 3 sentences);
   - up to 6 `guidance` items, each with a verbatim `quote` first, then a `statement` rephrasing only that quote, and its source tags;
   - a `not_covered` list.

   The output is validated with Pydantic, with one retry on invalid JSON.
3. **Built-in safeguards, in order:**

| Safeguard | When | What it does |
|---|---|---|
| Empty retrieval | Before generation | No passage above the threshold: no LLM call; answer "not covered" |
| **Scope gate** | Before generation | Incident without a hazard type (other/unknown) and no passage ≥ 0.83: no LLM call; answer "outside the scope" |
| **Scope decision** | After generation | The model's `in_scope: false` is enforced in code: no guidance is passed on |
| **Refusal retry** | After generation | Typed incident, a passage ≥ 0.82, but no guidance: retry once with feedback |
| Citation check | After generation | Tags mapped to `SOURCE-ID p.N`; citations to passages not provided removed; statements citing nothing provided dropped |
| **Quote check** (the runtime filter) | After generation | The quote must appear verbatim in a cited passage; otherwise the statement goes to `unverified_guidance` and is not passed on |
| Entailment check (NLI) | Optional, **off by default** | A multilingual NLI model checks that the quote or passage entails the statement. Measured as not worth it (8.4) |

### 8.3 How we evaluated generation (`src/rag/evaluate_generation.py`)
- **Pipeline under test:** the final retrieval configuration, then `rag_answer` v3 and v4, on all 36 test queries.
  - Answers are generated with every statement kept and the scope gate recorded but not applied, so each safeguard's effect can be measured separately.
  - Results are cached per prompt version, so judging can resume after an interruption.
- **Automatic metrics** (no model involved):
  - abstention: out-of-scope queries must get no guidance (with the model's own decision, and with the gate), and relevant ones should get some;
  - JSON validity;
  - citation validity;
  - quote grounding;
  - retries;
  - latency.
- **Judged metrics**, by two models from families independent from the generator (Gemma). These are the same two models as for retrieval: `gpt-oss-120b` (OpenAI) and `qwen3.8-27b` (Alibaba), with prompt `generation_judge` v1.
  - **Faithfulness, claim by claim:** each statement is judged against *its own cited passages*: supported, partial (only part of it, or an added detail) or unsupported. Reported for all statements, and separately for those kept or set aside by the quote check.
  - **Answer relevance:** 0 to 2.
  - **Agreement:** Cohen's κ between the two judges.

### 8.4 Results
Reports: `evaluation/results/generation_v4_20261018_1608.md` (v4) and the v3 report in the same folder.

| Metric | v3 | **v4 (default)** |
|---|---|---|
| Out-of-scope queries refused, model's own decision | 4/6 | **6/6** |
| Out-of-scope queries refused, model + scope gate | – | 6/6 |
| Relevant queries answered with guidance | 28/30 | **29/30** |
| False refusals (passages retrieved, no guidance) | 1 | **0** |
| Refusal retries triggered | – | 0 |
| Statements per answered query | 5.6 | 6.0 |
| Citation validity | 100% (200/200) | 100% (180/180) |
| Quote grounding | 85.4% | 81.0% |
| **All statements:** both judges "supported" / any "unsupported" | 80.0% / 7.9% | 74.7% / 9.8% |
| **Statements passed on (quote verified):** count | 119 | **141** |
| **Statements passed on:** both judges "supported" / any "unsupported" | 87.4% / **1.7%** | 84.4% / **1.4%** |
| Statements set aside: any "unsupported" | 43% | 45% |
| Mean relevance (gpt-oss / Qwen) | 1.85 / 1.89 | 1.83 / 1.62 |
| Judge agreement, κ supported vs not | 0.57 | 0.55 |
| Latency per answer (median) | 70 s | 78 s |

**Reading the results**
- **v4 fixes both abstention failures with the prompt alone.**
  - **Income tax and locusts** are now refused by the model's explicit scope decision.
  - **The French wind-driven wildfire report** gets 6 statements.
  - **The two code safeguards did no work in the end.** The refusal retry was never triggered. The scope gate would have stopped the same two questions, but its 0.83 threshold was calibrated on these same 6 questions, so it's reported as a safety net, not as evidence.
- **The quote check is what makes the output trustworthy.**
  - **Both versions:** of the statements set aside, 43–45% are unsupported; of those passed on, only 1.4–1.7%.
  - **v4:** it passes on more statements (141 vs 119) at the same low unsupported rate.
- **What v4 costs** (GEN-08):
  - **Faithfulness:** raw faithfulness is lower, because quote-first generation makes more statements and more quote attempts that fail verbatim matching. The filter absorbs most of this.
  - **Relevance:** Qwen rates 7 answers less relevant, mostly fire queries where hazard-behaviour statements replace actions. gpt-oss is unchanged.
  - **Latency:** 8 s longer.

**NLI entailment check: a measured negative result** (GEN-07). Applied to the 140 judged v3 statements, on top of the quote check:

| Statements passed on | Count | Both judges "supported" | Any "unsupported" |
|---|---|---|---|
| Quote check only | 119 | 87.4% | 1.7% (2) |
| Quote check + NLI (threshold 0.5) | 87 | 89.7% | 1.1% (1) |
| Removed by NLI on top | 32 | 81% (correct ones lost) | 1 |

- **What it costs:** removing 32 statements, mostly correct ones, to catch a single unsupported one, plus about 60–70 s per answer on CPU.
- **Why:** faithful paraphrases (summaries of two sentences, English rephrasings of French text) are classed as "neutral".
- **So:** a heavier model-based check isn't automatically better than a simple deterministic one. The NLI check stays available, but off.

**Remaining errors**
- **2 unsupported statements still passed on (1.4%).**
  - **A heatwave-monitoring statement in a flood answer:** a passage about another hazard slipped through the hazard-match rule.
  - **One statement attributed to the wrong passage.**
- **A retrieval miss** (FIRE-Q08, burn scar): no passage reached the threshold, so the answer correctly says "not covered", but the documents do contain the guidance.

### 8.5 Assessment of the generation step
- **Scope and refusals now behave as intended:** 6/6 out-of-scope questions refused and no false refusal on the test set.
- **Grounding is strong:** every citation points to a real passage, and of the statements passed on, about 1.4% are unsupported according to at least one of two independent judges.
- **Latency** (about 80 s with gemma3:4b split between CPU and GPU) is fine offline but slow for a live demo. Options: 3 passages instead of 5, fewer statements, or a hosted model for the demo (GEN-06).

---

## 9. Failures and problems encountered

All entries, with cause, attempted fix and outcome, are in `evaluation/FAILURES.md`.

### Fixed
| ID | Problem | Fix |
|---|---|---|
| RAG-02 | Cover and front-matter headings became the parent of every section ("Contents > 2 International USAR…") | Front-matter titles and page-1 headings get the lowest level |
| RAG-03 | Table-of-contents lines matched as headings | Exact match preferred over prefix match |
| RAG-04 | Icon bullets leaked into the text | Private-use characters removed |
| RAG-09 | French guide's lines split across text boxes, mid-word | Split-line merging, only for documents detected as split layouts |
| RAG-05 | Keyword labels missed relevant pages | Relevance labels rebuilt by the LLM panel |
| RAG-06 | Burn-scar + heavy-rain query failed everywhere | Solved by fusion with the v3 rewrite |
| ENV-01 | sentence-transformers blocked by Windows security policy | Re-implemented with transformers |
| GEN-01 | Grounded answer v1 refused a clearly covered flood incident | v2: relevance = applies to this type of situation |
| GEN-02 | v2 answered an out-of-scope cooking question | v3: scope check first |
| GEN-03 | v3 still answered 2 of 6 out-of-scope questions (locusts, income tax) | v4: explicit in_scope field enforced in code; 6/6 refused |
| GEN-05 | v3 refused a French wildfire report | v4: hazard behaviour counts as guidance; no false refusal |

### Mitigated
| ID | Problem | Mitigation |
|---|---|---|
| RAG-07 | French much weaker than English (MRR about 0.5 early on) | More French documents, reranking; now 0.89 strict |
| RAG-08 | Out-of-scope queries score like relevant ones | Calibrated threshold + verifier agent |
| RAG-11 | Large general documents crowd out short targeted sheets | Reranking (and an optional per-document cap) |
| JUDGE-01 | Even gpt-oss-120b invents quotes (10%) | Automatic quote check discards those votes |
| ENV-05 | Groq free tier: 200,000 tokens/day per model; Mistral free account with zero quota | Second Groq key; local tie-breaker |
| GEN-04 | 7.9–9.8% of generated statements not supported by their cited passage | Statements with an unverified quote set aside (1.4% unsupported remain with v4) |
| GEN-08 | v4 trade-offs: lower raw faithfulness, one judge rates relevance lower, +8 s | Accepted: same unsupported rate after the filter, scope and refusal failures fixed |

### Open
| ID | Problem | Impact |
|---|---|---|
| RAG-01 | Arabic PDFs extract with swapped letters | Arabic not supported in documents or evaluation |
| RAG-10 | No official gas-explosion guidance; structural documents partly earthquake-oriented | Some urban emergencies poorly covered |
| RAG-12 | Reranker slightly weaker on fire queries | Two fire queries still fail |
| RAG-14 | Hindi in a legacy font in the NDRF SOP extracts as gibberish | Low: the English part of those pages is intact |
| PROMPT-03 | The query rewrite still invents facts (3/40) | Low: only used through fusion |
| GEN-06 | Generation takes about 70 s per answer on the laptop | Slow for a live demo |

### Prompt-engineering failures, kept as evidence for the prompt library
- **PROMPT-01 to PROMPT-03:** the query rewrite iterations (section 5).
- **PROMPT-04:** choosing judges. Small models default to 0 or invent quotes.
- **GEN-01 to GEN-03, GEN-05, GEN-08:** the grounded-answer iterations v1 → v4 (section 5).
- **GEN-07:** the NLI entailment check, a measured negative result (section 8.4).

---

## 10. Where we stand, and is the result satisfying?

### 10.1 Status
The RAG component is **complete, with all seven steps, and evaluated end to end**.
- **Indexing:** the pipeline is reproducible with one command.
- **Retrieval and generation:** both are integrated in the knowledge agent (best retrieval configuration, `rag_answer` v4 with the built-in safeguards, verified statements only).
- **Evaluation:** retrieval with independent relevance labels (κ = 0.75); generation with automatic checks and claim-level faithfulness from two independent judges, for v3 and v4. Every result file is kept in `evaluation/results/`.
- **Tests:** 53 automated tests cover extraction, chunking, ingestion, retrieval post-processing, metrics, judging, generation safeguards and the knowledge agent.

### 10.2 Verdict
**Yes, the result is satisfying for this project, both as a working component and for the grading criteria.**

**Why**
- **Retrieval quality is high for a prototype.** For 80% of test queries, the first passage is directly relevant; a relevant passage is in the top 5 for 93% and in the top 10 for 100%. Hazard-specific failures are limited to two fire queries.
- **Generation is grounded, checkable and refuses what it should:**
  - every citation points to a provided passage;
  - of the statements passed on, 84% are supported according to both independent judges and 1.4% are judged unsupported by at least one;
  - 6/6 out-of-scope questions are refused, with no false refusal.
- **Every choice is justified, and most are measured:**
  - corpus selection, with exclusions explained;
  - chunk size tied to the model's limit;
  - embedding model chosen by measurement (e5-base vs e5-small);
  - vector store chosen on stated criteria;
  - each retrieval setting tested on and off.
- **The chunking comparison was done**, which the brief values, and reported honestly as a null result.
- **The evaluation goes beyond "a short evaluation":** pooled graded labels from a blinded, multi-family LLM panel with κ = 0.75, two label definitions, and per-hazard and per-language breakdowns.
- **Failures are documented** with cause and fix (32 entries), which the brief explicitly rewards. They include a measured negative result (NLI check).

**Honest limits (to state in the report)**
1. **Small test set:** 30 relevant queries, so small differences, about 3 points or less, aren't meaningful.
2. **The queries were drafted with the help of the same AI assistant that built the system.** The labels are independent of it, but the choice of queries isn't, and no teammate has reviewed them yet.
3. **The labels come from LLMs, not humans.** Their reliability is shown by agreement between independent judges, not by human validation.
4. **Pool bias:** only the five pooled configurations are compared on fully judged results. The others lean pessimistic.
5. **Lenient labels saturate,** so they can't rank the best configurations; strict labels are the primary measure.
6. **Fire queries are the weak spot** under reranking; French has only 8 queries; Arabic isn't supported.
7. **Generation limits:**
   - generation takes about 80 s per answer on the laptop;
   - the two generation judges agree only moderately (κ about 0.55), so faithfulness is best read per judge as well as by consensus;
   - the 6 out-of-scope questions were also used to calibrate the scope gate, so 6/6 refusals shows the prompt works on these cases, not that it generalises;
   - one judge rates v4's answers less relevant (1.62 vs 1.89).
8. **The downstream agents aren't evaluated yet.** Whether the risk assessment and report use the grounded answer faithfully will be evaluated once those agents exist.

---

## 11. What could be improved

Ordered by value for effort:

| Improvement | Expected benefit | Effort |
|---|---|---|
| A teammate reviews and extends the test set (+20–30 queries, more French and report-style) | Removes the query-authorship caveat; makes 3–5-point differences measurable | 1–2 h + one judging run (Groq paid tier, under $1) |
| Human spot-check of 20–30 pooled pages | Reports human-vs-panel agreement and validates the labels | 15 min |
| Fix RAG-12: rerank only the top 10, or blend reranker and cosine scores | Recovers the fire queries without losing the structural gains | 1 h |
| Hybrid retrieval (BM25 + dense) | Exact-term matches for keyword-heavy queries ("placards", "INSARAG marking") | 2–3 h |
| Strengthen the rewrite guardrail (v4: only words from the report, or a check step) | Removes invented facts from fusion queries | 1 h |
| A stronger multilingual reranker (e.g. `bge-reranker-v2-m3`) | Possibly better on fire and French queries; slower on CPU | 1 h + a re-run |
| Fix the Arabic extraction (ligature repair) or use Arabic documents with a clean text layer | Arabic support | Unknown |
| Faster generation for the demo: 3 passages, fewer statements, or a hosted model | Brings about 80 s down to about 20–30 s | 30 min |
| More out-of-scope and near-domain test questions (not used for calibration) | Shows whether the scope decision generalises | 1 h + a run |
| Human spot-check of 20 generated statements | Human-vs-judge agreement for faithfulness | 15 min |
| Faithfulness evaluation of the risk and report agents | Extends the evaluation to the full pipeline | Part of the next phase |

---

## 12. How to reproduce

```bash
# index (about 30 min on CPU for all collections)
.venv/Scripts/python -m src.rag.ingest --strategy all
.venv/Scripts/python -m src.rag.ingest --strategy structure --no-header
.venv/Scripts/python -m src.rag.ingest --strategy structure --model intfloat/multilingual-e5-small

# relevance labels (Groq key in .env as JUDGE_API_KEY; llama3.1:8b pulled in Ollama)
.venv/Scripts/python -m src.rag.evaluate --make-pool --rewrite 3 --pool-depth 3
.venv/Scripts/python -m src.rag.judging prepare
.venv/Scripts/python -m src.rag.judging judge --judge judge1
.venv/Scripts/python -m src.rag.judging judge --judge judge2
.venv/Scripts/python -m src.rag.judging analyse
.venv/Scripts/python -m src.rag.judging judge --judge tiebreaker
.venv/Scripts/python -m src.rag.judging merge

# evaluation
.venv/Scripts/python -m src.rag.evaluate --rewrite 3 --judgments evaluation/retrieval_judgments_strict.csv --tag strict
.venv/Scripts/python -m src.rag.evaluate --rewrite 3 --tag lenient

# generation evaluation (answers with gemma3:4b, then the two Groq judges)
.venv/Scripts/python -m src.rag.evaluate_generation generate --version 4
.venv/Scripts/python -m src.rag.evaluate_generation judge --version 4
.venv/Scripts/python -m src.rag.evaluate_generation report --version 4

# try a query
.venv/Scripts/python -m src.rag.retriever "water is entering houses" --type flood -k 5 --rerank
```

---

## 13. Q&A preparation

- **Why page-level labels?** They're valid for every chunking strategy, so the comparison is fair.
- **What is pooling?** Judging only the union of what the systems retrieve (TREC). It's efficient but favours the pooled systems, which is why we compare those five.
- **What do the LLM judges evaluate?** Offline, two things: retrieval (context relevance of each retrieved page, used to build the answer key) and generation (faithfulness of each statement to its cited passages, and answer relevance).
- **Why claim-level faithfulness?** A whole answer can be mostly right and contain one invented claim; judging each statement against its own citations finds it.
- **Why verify quotes automatically?** It's a cheap, deterministic grounding check, and it predicts the judges' verdicts (2% unsupported when verified, 43% when not), so it can filter statements at runtime without any judge.
- **Why can a grounded generator still be unfaithful?** The model fills gaps from its training ("use an N95 mask") and attaches the nearest citation; grounding instructions reduce but don't eliminate this.
- **How does the RAG work without a verifier agent?** It checks itself:
  - before generation: a scope gate;
  - after generation: an explicit scope decision enforced in code, a refusal retry, citation checks, and the quote check that decides what is passed on.
- **Why not an NLI (entailment) check?** We measured it: it removed 32 statements, 81% of them correct, to catch one unsupported statement, and added about 60–70 s per answer.
- **Why three model families, and not Claude?** Independence from the system's author, different blind spots, κ as a reliability measure, and a tie-breaker instead of human adjudication.
- **Why not fine-tune (LoRA) a judge?** There were no human labels to train on, and training on another model's labels would copy its bias.
- **Why the quote check?** Even strong judges invent evidence (10%); a verbatim requirement makes every judgment checkable.
- **Bi-encoder vs cross-encoder:**
  - Dense retrieval uses a bi-encoder: one vector per text, so it can be precomputed and is fast.
  - The reranker is a cross-encoder: query and passage go through the model together, which is more accurate but needs one pass per pair.
- **Reciprocal rank fusion:** score = Σ 1/(60 + rank). It's rank-based because the similarity scores of different queries aren't comparable.
- **e5 details:** asymmetric `query:` / `passage:` prefixes from contrastive training; mean pooling; cosine similarity on L2-normalised vectors equals the dot product.
- **Why tokens, not characters?** The 512-token limit truncates silently; French and Arabic need more tokens per word.
- **HNSW:** an approximate nearest-neighbour graph index, practically exact at our size. It explains the small run-to-run differences.
- **Why keep structure-aware chunking if it isn't better?** Equal retrieval quality, plus section headings for citations. And we report the null result.
- **Why is the threshold 0.785?** Calibrated on out-of-scope queries, recall-oriented, with the verifier as a second safeguard.
- **Why no fine-tuning of the embedding model?** No training pairs, and a strong multilingual model off the shelf. With a few hundred labelled query–passage pairs, contrastive fine-tuning would be the next step.
