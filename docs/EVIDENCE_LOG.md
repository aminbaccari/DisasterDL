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
| 2026-10-16 | fixed | 1, 3, 5 | queries_v2.csv, 18 queries (10 en, 8 fr), written and committed (f56b979) before this run | hit@1 0.44, hit@3 0.78, hit@5 0.78, MRR 0.59 | No topic filter. Match on entry id. Raw: rag/eval/results_queries_v2_fixed_20261016-1524.csv. |
| 2026-10-16 | section | 1, 3, 5 | same 18 | hit@1 0.78, hit@3 0.83, hit@5 0.89, MRR 0.81 | No topic filter. Raw: rag/eval/results_queries_v2_section_20261016-1524.csv. |
| 2026-10-16 | fixed | 1, 3, 5 | same 18 | hit@1 0.56, hit@3 0.83, hit@5 0.89, MRR 0.70 | With --use-topic-filter (n8n passes rag_topic). Raw: results_queries_v2_topic_fixed_20261016-1524.csv. |
| 2026-10-16 | section | 1, 3, 5 | same 18 | hit@1 0.78, hit@3 0.83, hit@5 0.94, MRR 0.82 | With --use-topic-filter. Raw: results_queries_v2_topic_section_20261016-1524.csv. |

Notes on the two query sets. The first set (rag/eval/queries.csv, 20 queries, rows above) was written with the entries in view and committed together with its results, so it is not blind. The second set (queries_v2.csv) was written from entry needs and the fixed incidents and committed before any retrieval was run on it. Model: intfloat/multilingual-e5-small, offline from the local cache. Matching on entry id is lenient for the fixed strategy: a fixed chunk that holds three entries counts for each of them, so the gap in favour of section chunking is, if anything, understated. Eighteen queries is a small sample: one query is 5.6 points.

Misses on queries_v2 (from a one-off script that printed the top 3 entry ids, section and fixed, no topic filter):
- v13 (en, apartment block collapsed, people may be trapped, should neighbours go in), expected ST-05 or ST-17: not in the top 5 for either strategy. Section chunking returns cordon entries (ST-13, ST-09 to ST-11, ST-14, ST-15). ST-05 is titled "Do not enter obviously unsafe buildings; entry rules" but the query words (apartment block, trapped, neighbours) do not match it. A real retrieval weakness for the structural_01 incident.
- v08 (fr, drying a flooded house before mould): rank none in both strategies. French query with the English-only entries FL-19 and FL-20: the French fire entries added on 2026-10-16 (FI-21 to FI-24) are returned instead. Without the topic filter, French queries are pulled to French entries, whatever the topic.
- v12, v16 (fr, flood and structural): same pattern in the fixed strategy (French fire entries outrank the English flood and structural ones).
- v02 (fr, fire: stay or leave) section rank 5: the French entry FI-24 and others exist but after-fire entries (FI-20, FI-26) rank higher.
- v15 (en, who declares a building safe) section rank 3, fixed rank 2: ST-16 and ST-05 come before ST-01.
- Topic filter: raises fixed hit@5 from 0.78 to 0.89 and section from 0.89 to 0.94, so the workflow should always send rag_topic. v13 still misses.
- Not yet tried (ideas, not results): a query rewrite by the RAG query agent, more French flood and structural entries, a rerank by language.

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
