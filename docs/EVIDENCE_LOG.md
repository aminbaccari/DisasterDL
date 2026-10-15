# Evidence log

Real results only. Date every entry and say who ran it. Nothing here may be invented or estimated.

## Decisions (what we chose and why, one sentence each)

- 2026-10-15: LLM and vision = Gemini Flash free tier (one key for text and images). Tunisia is on the Gemini API supported countries list. Exact model and free-tier limits to be confirmed in Google AI Studio (docs list gemini-3.8-flash as stable; gemini-2.5-flash is limited to past users).
- 2026-10-15: Embeddings = local multilingual-e5 (English and French corpus, reproducible, no rate limits).
- 2026-10-15: Vector store = ChromaDB (local, simple).
- 2026-10-15: RAG as a FastAPI service called from n8n (keeps chunking and evaluation in Python).
- 2026-10-15: n8n self-hosted with Docker.
- 2026-10-15: Prompt library v1 drafted for 5 agents (6 prompts). Not yet run on any input.

## RAG experiments

| Date | Chunking strategy | Top-k | Test queries | Hits | Notes |
|------|-------------------|-------|--------------|------|-------|

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
