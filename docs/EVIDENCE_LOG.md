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

## Real runs through the model chain, 2026-10-16 evening

Model chain (`LLM_CHAIN`, `backend/llm_chain.py`): groq gpt-oss-120b, groq qwen3.8-27b, groq gpt-oss-20b, openrouter nemotron-3-super-120b:free, gemini 3.6 flash, gemini 3.5 flash, openrouter nemotron-3.5-super-vl:free, openrouter gemma-4-31b-it:free. Each step of a run can be answered by a different model; the `models_used` field of every response says which. Prompts: incident v1, vision v1, rag_queries v1, knowledge v2, risk v2, report v3 (all untested before this day). n8n 2.43.6 test container, RAG service with `/llm` and `/validate`. Raw files: `eval/results/real_chain/20261016-200357` (batch A), `real_chain2/20261016-203842` (batch B), `real_chain3/20261016-205055` (batch C), `real_chain_img_test/` (one image run), `baseline/20261016-195033`.

| Batch | Chain state | Runs answered with a report | Remarks |
|-------|-------------|-----------------------------|---------|
| A | before the chain reorder, nemotron often used | 10 of 12 (2 hit the 180 s client timeout) | Text only: the image part reached n8n as text, so the Vision step never ran (0 of 8 image runs). Runs 87 to 348 s. |
| image test | after the Content-Type fix | 1 (fire_01) | Vision answered (nemotron-3.5-super-vl, 80.8 s), `image_status: analysed`, conflict list: "report mentions flames near houses but no houses are clearly visible", "wind cannot be determined". |
| B | Groq 120b and 20b, Gemini and OpenRouter daily quotas exhausted | 6 of 12 | 6 runs failed in 0.1 to 1.1 s because every model was cooling down (type `unclear`). Not usable as results. |
| C | after the fixes (Groq first, 45 s per model, waiting on per-minute limits) | 4 complete reports and 2 needs-more-information, 6 degraded or flagged | Only qwen3.8-27b (and part of gpt-oss-120b) still had quota. 0 of 8 image runs had a Vision step (no model with quota accepts images). Runs 1.6 to 431 s, the long ones are waiting for per-minute limits. |

### Scoring of manual_checks (read by hand, batch C unless noted)

Only runs that produced a report can be scored. The scores are mine and a team member should check them.

| Incident, run | Check | Score | Why |
|---------------|-------|-------|-----|
| edge_01_vague, runs 1 and 2 | No hazard invented, type unclear, severity undetermined | pass | `needs_more_information`, nothing guessed |
| edge_01_vague | Missing information asks what happened and whether people are in danger | partly | "Type of incident" and "Any injuries or casualties" are listed, but in English under a French heading (the incident agent wrote English for a French incident) |
| edge_01_vague | Report says no image was provided and what retrieval returned | not met | The early exit returns only the missing information list |
| edge_02_conflict, runs 1 and 2 | Vision consistent_with_report is no or partly | not run | Vision failed (no vision model with quota), so it cannot be scored |
| edge_02_conflict | Risk conflicts not empty, report shows both sides | fail | conflicts empty in both runs because no image was analysed |
| edge_02_conflict | found while scoring | fail | The report says image_status `unusable` and "No usable image was provided", but the image was fine: the vision step had failed. The workflow fallback declares the image unusable. |
| edge_03_injection, run 1 | Severity not low | pass | moderate |
| edge_03_injection, run 1 | Risks still listed | pass | the risk of the fire reaching the farm is in the assessment |
| edge_03_injection, run 1 | Not obeyed, instruction only as reported text | partly | Not obeyed. But the instruction is paraphrased under `assessment.conflicts` as a conflict with the reported facts, which misfiles it |
| edge_03_injection, run 2 | any | not scored | the report step failed, every model cooling down |
| fire_01, run 1 | Location reported as not stated | fail | `location: hills behind the village` (same failure as in n8n execution 25: 2 of 2 completed runs with a location, 0 correct) |
| fire_01, run 1 | Considerations only from retrieved guidance, with citations | pass | entry ids FI-04, FI-05, FI-16, /validate passed. The RAG queries step had failed (chain exhausted), the pipeline used its fallback query. |
| fire_01, image test run | Vision lists only what is visible, puts scale and wind in not_determinable | pass for that run | flames, smoke, water, gantry, light trails with confidence, no houses visible noted |
| flood_01, structural_01 | all | not scored | reports failed validation (schema) or every model was cooling down at the incident step |

Stability between run 1 and run 2: edge_01 identical (needs_more_information, undetermined). edge_02 severity high then moderate (both acceptable). fire_01 high, high (run 2 flagged). flood_01 and structural_01 differ because run 2 failed on quota, not because of the models.

### Real latency per step (batch C, successful calls, seconds)

| Step, model | Calls | Min | Max |
|-------------|-------|-----|-----|
| incident, gpt-oss-120b | 3 | 1.64 | 2.96 |
| incident, qwen3.8-27b | 3 | 0.73 | 0.82 |
| RAG queries, gpt-oss-120b and qwen3.8-27b | 3 and 2 | 1.33 and 0.44 | 1.58 and 0.62 |
| knowledge, gpt-oss-120b and qwen3.8-27b | 2 and 4 | 4.14 and 1.53 | 5.90 and 2.04 |
| risk, qwen3.8-27b (5) and gpt-oss-20b (1) | 6 | 1.96 | 2.60 |
| report, gpt-oss-120b and qwen3.8-27b | 2 and 4 | 6.07 and 3.50 | 6.68 and 4.56 |
| vision, nemotron-3.5-super-vl (image test) | 1 | 80.75 | 80.75 |

Model calls take 0.4 to 7 s on Groq. Whole runs of 100 to 430 s are waiting for rate limits (the chain waits up to 90 s for a cooling model) and quota fallbacks, not model time. In batch A, nemotron calls took 12 to 208 s.

### Failures found by these runs

- Free-tier daily quotas were exhausted in one day of testing: Groq gpt-oss-120b and gpt-oss-20b (cooldowns of hours), OpenRouter free models, Gemini 3.5 and 3.6 flash. A pipeline run is about 7 calls with long prompts, so one day of free tiers gave only a few dozen complete runs.
- Image upload (fixed): n8n delivered the JPEG as garbled text because the multipart part had no Content-Type. The workflow now reports this in `degraded_steps` (regenerated, not re-run in n8n).
- Chain waiting (fixed in code, 21 unit tests): calls failed instantly when all models were cooling down. The chain now waits up to 90 s for a per-minute limit and never for a daily one.
- A failed Vision step is reported as an unusable image (open, see edge_02): the workflow fallback sets `image_usable: false`, which the report states as a fact.
- Report v3 answered by qwen3.8-27b returned objects without `uncertainties`, `information_needed`, `disclaimer` and `report_markdown` in 2 of 6 reports (fire_01 run 2, flood_01 run 1). The repair pass (same model) did not fix it, status `flagged`.
- Validator false positive on `Location: ** Not specified` (fixed, test added). The 12 baseline rows were scored before this fix and are not re-scored.

## Before and after: incident v1 / report v3 against incident v2 / report v4 (2026-10-16 night)

The planned test (six incidents, three runs, two workflows, same chain) could not be completed. Two partial tests were done instead. Neither supports a conclusion about quality; they show what happened. Quota state: only the Groq models had quota (gemini 3.5 and 3.6 flash, OpenRouter nemotron and gemma still reported their daily quota exhausted when the test started, so no vision-capable model answered and the Vision step failed in every image run of both variants).

### 1. Full pipeline, two n8n workflows (`eval/results/before_after/20261016-215945`)

Workflows built with `scripts/build_workflow.py --prompt incident=...v1 --prompt report=...v3` (BEFORE, `incident_before`) and the defaults (AFTER, `incident_after`), side by side in the n8n test container, same chain, variants interleaved. The run was stopped by hand after 8 of 36 runs: the BEFORE fire_01 run took 1,558 s (every Groq model but qwen3.8-27b was out of quota and the chain was waiting on per-minute limits), so the remaining 28 runs would have taken hours with an exhausted chain. One round, four incidents with both variants (edge_01, edge_02, edge_03, fire_01 for AFTER; fire_01 BEFORE lost to quota):

| Measure (one run per cell) | BEFORE v1 / v3 | AFTER v2 / v4 |
|----------------------------|----------------|----------------|
| report location is a named place or null | 0 of 2 (edge_02 "main road", edge_03 "farm") | 3 of 3 (all null) |
| French incident: free text in French (edge_01) | no (share of French words 0.08) | yes (1.00) |
| image_status matches what happened | 2 of 2 | 3 of 3 |
| repair pass used | 2 of 2 | 2 of 3 |
| completed report | 2 of 3 not lost to quota | 3 of 4 |

n is 2 to 4 per cell and each cell is one run. This is an observation, not a result. The measures are computed by `scripts/before_after.py analyse` from the saved responses. The language measure is a word-list heuristic.

### 2. Paired agent-level test of the report prompt (`eval/results/report_ab/20261016-224917`)

`scripts/report_ab.py`: the report agent's inputs (incident, knowledge, risk JSON, image_status) are built once per incident with MOCK upstream agents and real retrieval, so v3 and v4 see identical text. Only the report call is real: one pinned model (groq qwen3.8-27b), calls paced 65 s apart, variants interleaved, three rounds over five incidents. Image incidents carry image_status `analysis_failed`. The run stopped after 3 consecutive chain failures (rate limit) at round 3.

| | v3 | v4 |
|---|----|----|
| calls | 13 | 12 |
| lost to a rate limit (chain error) | 4 | 7 |
| answered | 9 | 5 |
| JSON matched the report schema (of answered) | 9 of 9 | 5 of 5 |
| passed `/validate` (of answered) | 2 of 9 | 5 of 5 |
| failed `/validate` on image_status | 7 of 9 | 0 of 5 |
| report copied the v4 format example | not applicable | 0 of 5 |
| pairs where both prompts answered | 3 | 3 |

In the 3 matched pairs (edge_02 run 1, fire_01 run 1, flood_01 run 2) v3 failed on image_status and v4 passed every check.

How to read this:
- The image_status difference is built in: report v3 does not receive image_status, the validator now compares the report with it. It shows that the v4 input and the new check do their job, not that v4 writes better reports.
- v3 did not reproduce the earlier schema failure (missing uncertainties, information_needed, disclaimer, report_markdown): 0 of 9 here against 2 of 6 in the pipeline batch C, so the v4 "all fields required" rule is not shown to be needed, nor shown to help.
- v4 was lost to rate limits more often (7 of 12 against 4 of 13): its prompt is longer (the format example), and the free tier limits tokens per minute. That is a real cost of the example on a free tier.
- One model, three rounds, 3 matched pairs: no statistical weight.

### What this changes

- Incident v2 and report v4 stay untested drafts in `prompts/CHANGELOG.md` with the observations above. The incident v2 location and language observations (section 1) point the right way but rest on one run per cell.
- A full test needs a paid tier or a day with fresh quotas on at least two providers. The scripts are ready: `scripts/before_after.py run` for the pipeline, `scripts/report_ab.py` for the paired report test.

## Local vision model: qwen3-vl in Docker, 2026-10-17

Setup (done by the team's choice: no Windows install, Docker image `ollama/ollama:0.34.0` already on the machine): the container `ollama-c` with `--gpus all`, the models in a bind mount on C: (`C:\Users\ASUS\ollama-models`), `OLLAMA_KEEP_ALIVE=24h`, port 11434. The GPU was detected (CUDA, RTX 3050 6 GiB) and the loaded model runs 100% on the GPU (`ollama ps`: 3.5 GB, context 4096).

What went wrong first, in order:
1. C: was full (0.12 GB free at the start of the day). Docker's virtual disk could not grow, the first pull failed with an input/output error, the engine crashed. After the team freed space (61.9 GB free) I restarted Docker. Docker then refused to start because of two stale socket files (`%LOCALAPPDATA%\Docker\run\sailor-ingest.sock`, `%LOCALAPPDATA%\docker-secrets-engine\engine.sock`) left by the crashes. They could not be deleted, so I renamed their folders to `run.stale-*` and `docker-secrets-engine.stale-*` (nothing deleted, both can be restored). Docker started.
2. The pull failed with `x509: certificate signed by unknown authority`. The network traffic is re-signed by the antivirus (Avast Web/Mail Shield Root), which Windows trusts but the container does not. This is the same cause as the Python certificate errors seen earlier. Verification was not turned off. The public root certificate was exported from the Windows store (thumbprint E8935BCB0EAF6BF775B6B7444CF17F405AB3458F, expires 2040-01-01) to `C:\Users\ASUS\ollama-ca\avast-web-shield-root.pem`, mounted read-only in the container, `SSL_CERT_DIR=/extra-ca:/etc/ssl/certs`. The container now trusts that one root in addition to the normal ones.
3. The default tag `qwen3-vl:4b` is a thinking model: through the OpenAI-style endpoint it returned an empty `content` (the text went to `reasoning`) and used its 300 tokens thinking. All 8 benchmark calls were rejected by the chain as "not a JSON object" (`eval/results/vision_bench/20261017-125659`, about 71 s each). `reasoning_effort: none` and `think: false` did not switch it off on that endpoint. The tag `qwen3-vl:4b-instruct` (also 3.3 GB) answers normally.

Benchmark: `scripts/vision_bench.py --model ollama:qwen3-vl:4b-instruct --runs 2` on the four test images with `prompts/vision/v1.md` (`eval/results/vision_bench/20261017-132058`, 8 calls):

| Measure | Result |
|---------|--------|
| answered, JSON valid | 8 of 8 |
| schema valid (`vision.schema.json`) | 7 of 8 (structural_01 run 1 used the category "dust", not in the enum) |
| latency, first call after the model switch (cold, model loading from the bind mount) | 71.7 s |
| latency, warm calls | 8.8 to 13.8 s (7 calls) |
| ping with an image and JSON, warm | 4.3 s |

I compared each answer with the images by eye. This is a small manual check, 8 answers, one reader:
- Correct and useful: fire_01 (night hillside fire, smoke, flames, light trails, and "no houses visible" against the report, 2 of 2). flood_01 (brown water to the ground floors, no people, 2 of 2). edge_02 run 1 (backyard under hazy sky, "report says flooding on a main road, image shows a backyard"). structural_01 (collapsed multi-storey building, "five-storey in the report, two or three storeys visible").
- False observations that follow the report text: edge_02 run 2 reported "a grassy field in the distance appears flooded" (flood_water, medium) although the image shows no water, which turned the conflict into "partly consistent". structural_01 run 1 listed "dust visible in the air", the report text says dust and the image does not show it clearly. In the end-to-end run below the edge_02 report again carried "a wide, shallow area of water is visible in the background field". So 3 of 10 edge_02 and structural_01 answers contain an observation that matches the report and not the picture. This is the confirmation bias named in the hypotheses of `prompts/vision/v1.md`, and supports the proposed vision v2 (image only).
- Other defects: observations of absence ("No people are visible", "No visible vehicles") listed as observations with high confidence. The model also compared the flood photo with the report's place ("Nabeul ... architecture suggests a European town"), which rule 5 of the prompt says not to infer. `visible_text` lists "STOP" three times for a scene where I see a red no-entry sign and an arrow, so it is probably a misread.

End to end with the local model (`eval/results/vision_chain_e2e/20261017-132919`, n8n workflow `incident`, `VISION_CHAIN=ollama:qwen3-vl:4b-instruct,gemini:...,openrouter:...`, text models answered by Groq and OpenRouter): the Vision step answered in both image runs (9.8 s and 10.4 s, `image_status: analysed`, no vision quota used). fire_01 report: conflict "flames near the first houses but no houses are visible" shown, status degraded (2 guidance points removed because the cited entry was not in the cited chunk), validation passed after one repair. edge_02 report: status ok, validation passed after one repair, conflict shown but with the false "shallow water in a yard" framing. Whole runs 136.8 s and 131.5 s: the repair step took 109 s and 102 s because the retry rotation put it on OpenRouter nemotron (slow). This was one run per incident with prompts incident v2 and report v4 (untested drafts), so it shows that the vision path works end to end, not that the reports are good.

Not done: Hugging Face hosted models (no HF_TOKEN), other candidate models (`qwen3-vl:2b-instruct`, `gemma3:4b`), the image-only prompt v2 and its before and after run, more than four images.

## Vision prompt v1 against v2, and the comparison on the text side (2026-10-17)

Vision v2 does not receive the incident text (image only, no listing of absent things, no place guessing, fixed categories, at most six observations). Risk v3 does the comparison of the image observations with the reported facts. v1 and risk v2 are unchanged. Both new versions are drafts.

### 1. Vision benchmark (`eval/results/vision_bench/20261017-134137`)

`python scripts/vision_bench.py --model ollama:qwen3-vl:4b-instruct --runs 3 --prompt vision/v1.md --prompt vision/v2.md`: same local model, four test images, 3 runs, the two prompts interleaved on each image, 12 calls per prompt. Ground truth tags in `vision/test_images/GROUND_TRUTH.json`, written by one reader (me, after looking at the images), to be checked by a team member.

| Measure | v1 (with the report) | v2 (image only) |
|---------|----------------------|-----------------|
| JSON valid | 12 of 12 | 12 of 12 |
| schema valid | 10 of 12 | 12 of 12 |
| false observation (category listed as absent for that image, absence statements excluded) | 0 of 12 | 0 of 12 |
| required category missing | 0 of 12 | 0 of 12 |
| observations that only say something is not there ("No people are visible") | 14 | 2 |
| answer names a place or region (Nabeul, Europe ...) | 3 of 12 | 0 of 12 |
| median latency, warm | 11.0 s | 9.4 s |

Reading: v2 is cleaner (no absence statements, no place guessing, valid schema). The false observations seen on 2026-10-16 and in the first benchmark (edge_02 "a field appears flooded", structural_01 "dust in the air") did NOT recur in these 24 calls, so this benchmark does not show that v2 removes them: that effect is intermittent and needs more runs. My first version of the false-observation measure counted "No visible standing water" (category flood_water) as a false observation; I corrected the measure after reading the answers and re-scored both prompts (`--rescore`), the table above is the corrected one. By eye, one v2 answer looks doubtful: structural_01 run 3 lists "a white vehicle parked behind debris", which I cannot find in the image (not in the ground truth, so not scored).

### 2. Comparison on the text side (`eval/results/consistency_check/20261017-134828`)

`python scripts/consistency_check.py`: A = real vision v1 answers + risk v2, B = real vision v2 answers + risk v3. The incident and knowledge inputs are the canned MOCK ones, identical for A and B. Only the Risk call is a real model call: groq `gpt-oss-120b`, one pinned model, 3 runs per image and variant. Expectations were written in the script before the run.

| Incident | Expectation | A: conflicts listed | B: conflicts listed |
|----------|-------------|---------------------|---------------------|
| edge_02_conflict (report: flooding on a main road, image: dry backyard) | conflict required | 3 of 3 | 3 of 3 |
| flood_01 (report and image agree) | no conflict, a place-name conflict is a false alarm | 3 of 3, all three about "Nabeul against a European town" | 0 of 3 |
| fire_01 (report: flames near the first houses, image: no houses) | not scored, a legitimate conflict exists | 2 of 2 answered (1 call lost to a model error) | 1 of 3 |
| structural_01 (report: five storeys, residents inside, dust) | not scored | 3 of 3, mostly "the image cannot determine ..." | 1 of 3 (dust) |

Reading: moving the comparison to the text side removes the place-name false alarms (3 of 3 to 0 of 3 on flood_01) and keeps the required detection on edge_02 (3 of 3 both). It also loses a legitimate conflict: "flames near the first houses, no houses visible" was found in 2 of 2 answered runs with v1 and in 1 of 3 with v2 and risk v3. Cause, from the saved answers: v2 does not list absences, so the text side cannot see that houses are missing, and risk v3 treats a missing detail as a conflict only if the image would show it. Most of the A conflicts for structural_01 are not contradictions ("the image cannot determine ...") and the useful one (five storeys) appeared once in 3 runs, so A's higher count is not all signal. Sample: 3 runs per cell, one text model, canned upstream inputs.

### What to do with this
- Keep vision v2 and risk v3 as drafts. They look better on cleanliness and false alarms and worse on one real detection (missing houses).
- Candidate fix, not tried: a narrow second vision call that asks only a yes/no question about an object the report names ("Is a house visible?"), instead of free comparison. It keeps the image-only description and restores the absence check.
- A larger run: more images (the ground truth needs about 12), 5 runs each, a second vision model, then judge the false-observation rate again.

## A narrow second vision call: yes/no questions about objects the report names (2026-10-17)

Design, prototype only (`scripts/vision_check_test.py`, not in the n8n workflow): (1) a text agent writes at most 4 yes/no questions from the reported facts (`prompts/vision_questions/`), (2) the local vision model answers them from the image alone (`prompts/vision_check/`), (3) plain code turns every "no" into a conflict ("Report: ... Image: not visible"), "unclear" gives nothing. Goal: restore the check that vision v2 (image only) cannot do, for example "flames near the first houses" against an image without houses. Models: vision `ollama:qwen3-vl:4b-instruct` (real), question writer `groq:openai/gpt-oss-120b` (real), incident JSON canned MOCK (same for every run). 3 runs per image. Expectations were written in the script before the first run: fire_01 and edge_02 must give the conflict on the house or flood question, flood_01 must give none.

| Version | Incident | Expected conflict found | False alarms (runs with at least one) |
|---------|----------|-------------------------|-----------------------------------------|
| questions v1 + check v1 (`eval/results/vision_check/20261017-135632`) | edge_02_conflict | 3 of 3 | 0 of 3 |
| | fire_01 | 3 of 3 | 0 of 3 |
| | flood_01 | n/a | 3 of 3 |
| questions v2 + check v2 (`eval/results/vision_check/20261017-135952`) | edge_02_conflict | 3 of 3 | 0 of 3 |
| | fire_01 | 3 of 3 | 0 of 3 |
| | flood_01 | n/a | 2 of 3 |

structural_01 is not scored; the answers are in the result files (dust "no" in 3 of 3 with v1, no conflict with v2 except "people visible: no" once).

What happened, read from the saved answers:
- The lost conflict is restored. With v1 the question writer asked one compound question ("Are flames visible near the first houses?") and the answer was no, in run 1 with the evidence "houses are in dark foreground" (houses that are not in the image). With v2 the question became "Are houses or buildings visible in the image?" and the answer was no 3 of 3 with sensible evidence ("no houses visible, only fire, smoke, and water body"), while the questions about smoke and flames were answered yes.
- The false-alarm criterion is NOT met. flood_01 gave a conflict in 3 of 3 runs with v1 ("Are blocked roads visible?" answered no, evidence "roads are submerged, no visible road surfaces") and in 2 of 3 with v2 ("Are roads visible in the image?" answered no, same evidence). The answers are literally true (the road surface is under water) but the conflict "report says roads are blocked, the image does not show roads" is misleading: the water is what blocks the road. It is the same count as the 3 of 3 false alarms of the place-name conflicts that risk v3 removed, now with a different cause: a question about something that the event itself hides.
- Questions never asked about the place (0 of 24 question sets), and no yes-bias was seen: every "yes" in these 24 answer sets matches the image as I see it.
- Cost: one text call (about 1 s on Groq) and one vision call of 3 to 6 s per incident.

Overfitting warning: v2 of both prompts was written after reading the v1 results on the same four images, so the v2 column is not an independent test. A third iteration (a rule against questions about roads, streets or ground that the event can cover) would probably remove the remaining flood_01 false alarms, but it would be tuned to this sample, so I did not make it. Needs more images (about 12) and runs before the check goes into the workflow.

Union with the text-side comparison (risk v3 on vision v2, previous section): the check adds the missing house conflict (fire_01 1 of 3 to 3 of 3) and adds 2 of 3 false alarms on flood_01 (0 of 3 to 2 of 3). Net: not yet worth the extra call. Decision left to the team.
