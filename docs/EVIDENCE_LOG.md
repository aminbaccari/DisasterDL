# Evidence log

Real results only. Date every entry and say who ran it. Nothing here may be invented or estimated.

## Decisions (what we chose and why, one sentence each)

- 2026-10-15: LLM and vision = Gemini Flash free tier (one key for text and images). Tunisia is on the Gemini API supported countries list. Exact model and free-tier limits to be confirmed in Google AI Studio (docs list gemini-3.8-flash as stable; gemini-2.5-flash is limited to past users).
- 2026-10-15: Embeddings = local multilingual-e5 (English and French corpus, reproducible, no rate limits).
- 2026-10-15: Vector store = ChromaDB (local, simple).
- 2026-10-15: RAG as a FastAPI service called from n8n (keeps chunking and evaluation in Python).
- 2026-10-15: n8n self-hosted with Docker.
- 2026-10-15: Prompt library v1 drafted for 5 agents (6 prompts). Not yet run on any input.
- 2026-10-16: Fire corpus extended with FEMA V-1013, a French ministry page and a La Presse report of an ONPC communique (FI-09 to FI-20), plus French translations of key entries (FI-21 to FI-26) so French queries reach the FEMA guidance. QA report in rag/knowledge_base/QA_REPORT.md.
- 2026-10-16: Default chunking strategy = section (see RAG experiments). RAG service port moved from 8000 to 8010 because 8000 was in use on the dev machine.
- 2026-10-16: prompts/report/v2.md written as an untested draft (partial coverage wording). TODO: compare with v1 on edge_01_vague and fire_01 once the n8n workflow runs, then record in prompts/CHANGELOG.md.

## RAG experiments

| Date | Chunking strategy | Top-k | Test queries | Hits | Notes |
|------|-------------------|-------|--------------|------|-------|
| 2026-10-16 | fixed (300 words, overlap 40) | 5 | 20 (rag/eval/queries.csv: 12 en, 8 fr; fire 14, flood 4, structural 2) | hit@1 0.55, hit@3 0.85, hit@5 1.00, MRR 0.71 (fr: hit@1 0.25, MRR 0.51) | No topic filter. Model intfloat/multilingual-e5-small. Hit = chunk contains the expected entry id. Queries written by the same person who prepared the entries, so optimistic. |
| 2026-10-16 | section | 5 | same 20 | hit@1 0.90, hit@3 1.00, hit@5 1.00, MRR 0.95 (fr: hit@1 1.00) | No topic filter. |
| 2026-10-16 | fixed | 5 | same 20 | hit@1 0.60, hit@3 0.90, hit@5 1.00, MRR 0.76 | With --use-topic-filter. |
| 2026-10-16 | section | 5 | same 20 | hit@1 0.90, hit@3 1.00, hit@5 1.00, MRR 0.95 | With --use-topic-filter. Section chosen as default: one chunk is one entry. |

## Vision tests

| Date | Image | Disaster type | Expected | Observed | Correct? |
|------|-------|---------------|----------|----------|----------|

## End-to-end tests

| Date | Incident id | Image? | Result | Failure or issue | Fix |
|------|-------------|--------|--------|------------------|-----|

## Failure cases and fixes

(none yet)

## Limitations observed

(none yet)
