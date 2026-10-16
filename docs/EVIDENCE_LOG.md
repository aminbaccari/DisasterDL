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
| 2026-10-16 | fire_01 (real Gemini gemini-3.6-flash, n8n 2.43.6 test container, text only) | no (no test images exist) | Run 1 (no pacing, raw: eval/results/real_gemini-3.6-flash/n8n_execution_24.json): incident and RAG queries answered, knowledge, risk and report calls failed with 429, status degraded, validation not run. Run 2 (13 s pacing, n8n_execution_25.json): incident, queries and risk (on the retry) answered, knowledge and report failed with 429 (daily free-tier quota of gemini-3.6-flash exhausted), status degraded. No report was produced in any run. | Incident agent put 'hills behind the village' in location.text (precision area). The fixed incident expects location not stated. Manual check failed (see Failure cases). | Not fixed, prompt not changed. |
| 2026-10-16 | all six, MOCK agents (canned), real n8n, real /search and /validate | no | MOCK: 6 of 6 answered HTTP 200, incident type matched the expectation in 6 of 6 (by construction, the mock returns the expected type). Raw: eval/results/n8n_mock/20261016-162058/. | Run on the first 53-node workflow, before the retry nodes were added. | Re-run not done after the retry nodes, see 'Not run'. |
| 2026-10-16 | failure paths, MOCK | no | MOCK, current 78-node workflow, raw eval/results/n8n_mock/failure_paths.json and rag_down.json. Too short text: HTTP 400. Gemini unreachable (7.0 s), HTTP 500 (6.5 s), invalid JSON (0.8 s): one retry, then status degraded with the reason listed. Vague report: needs_more_information, nothing guessed. Report with an invented location: /validate failed, one repair pass fixed it (status ok, repaired true). Report invented every time: status flagged, check location. RAG service stopped: coverage none, validation unavailable, status flagged. | none | n/a |

## Failure cases and fixes

All entries below happened on 2026-10-16 during the build. Prompts were not changed to hide any of them.

- Incident Understanding v1 invents a location (real Gemini gemini-3.6-flash, fire_01, n8n execution 25). Input: 'Smoke is rising from the hills behind the village ...'. Output: location {text: 'hills behind the village', precision: 'area'}. The incident file expects the location to be not stated, and the manual check 'Location is reported as not stated, not invented' fails. The prompt rule 'copies the place as written' allows a relative description. One run only, so frequency is unknown. The /validate location check does not catch it, because the phrase is in the incident text. Candidate fix: a v2 rule that a relative description without a place name is null. Not written, because it cannot be tested while the quota is exhausted.
- Cold start of the embedding model (found with the MOCK workflow): the first three parallel /search calls from n8n timed out after 30 s, the workflow answered in degraded mode and listed three 'RAG search' reasons. Fix: rag/service.py loads the model at startup. Afterwards the same call took 1.6 s. A degraded run is the designed behaviour, the fix only removes the cause.
- Shared Chroma client (found in real run 1): 'Could not connect to tenant default_tenant' on one of three parallel /search calls. Fix: rag/store.py keeps one client under a lock. In run 2 the three searches succeeded (0.67 s). One run, so not proof.
- Vague report retrieved unrelated entries (found by scripts/replay_mock.py): with rag_topic general there is no topic filter, so edge_01 pulled flood and structural entries and the mock marked coverage good. Fix: no retrieval when the topic is general (workflow node 'Topic searchable?'). Not a fix of retrieval quality.
- Gemini availability: gemini-3.8-flash (the .env model) answered 503 'high demand' on 10 of 11 pings over about 10 minutes, gemini-3.7-flash 503 on 3 of 3. gemini-3.6-flash and gemini-3.5-flash answered 200 on a single ping each. Real runs used gemini-3.6-flash, with the team's agreement to try another model.
- Gemini free-tier limits: a burst of 14 single pings gave 6 answers, then HTTP 429 on the 7th call at t=19 s (quota GenerateRequestsPerMinutePerProjectPerModel-FreeTier). A pipeline run makes at least 6 Gemini calls, so scripts and the workflow got a pacing option (build_workflow.py --pace-seconds). Later, during run 2, the quota GenerateRequestsPerDayPerProjectPerModel-FreeTier for gemini-3.6-flash was exhausted (retry after about 29,700 s). All real runs stopped there, as agreed.
- Python TLS on the host: certificate verification failed for huggingface.co and for googleapis.com, while curl and the n8n container worked. Verification was not turned off: the model was loaded from the local cache (HF_HUB_OFFLINE=1) and scripts use the operating system certificate store (truststore).
- Docker Desktop engine stopped during the session (not by a command of ours). It was restarted with 'docker desktop start' with the user's agreement. The container named n8n (port 5678) that ran earlier was not in 'docker ps -a' afterwards, its volume n8n_data is still there. Cause unknown.

## Limitations observed

- No test images exist in vision/test_images/, so the Vision agent was never run on an image, real or mock-with-image. The mock vision answers are canned.
- Real Gemini results exist for the Incident Understanding, RAG query and Risk agents, on one incident (fire_01, text only), from run 2 only. Knowledge synthesis, Report and the whole /validate step on a real report were never run. Pipeline-level claims about LLM quality cannot be made.
- The baseline single prompt (scripts/baseline_single_prompt.py) was not run. Its offline tests pass, the dry run prints the request. No comparison with the pipeline exists.
- Real per-node latency (seconds, from n8n's own execution times, successful calls only, gemini-3.6-flash, one run each): Gemini incident 9.89 and 5.16, Gemini RAG queries 5.96 and 10.23, Gemini risk 5.45 (retry, run 2), RAG search 1.24 and 0.67. Fewer than three samples per node, so no averages. Calls that returned 429 are not latencies of a model answer.
- Retrieval: the query sets are small (18 and 20 queries), written by the same team as the entries. Structural_01 style queries missed (query v13).
- The French fire entries FI-21 to FI-26 are team translations, not reviewed by a French speaker outside the team.
- The OCR-only flood pages were not re-verified (no tesseract on this machine).
- Guardrails are regular expressions: /validate proves only what it tests. It passed every MOCK report, which says nothing about real model reports.
