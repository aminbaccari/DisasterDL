# Sprint status and proposed fixes (2026-10-16, evening)

Evidence: `docs/EVIDENCE_LOG.md`, raw files under `eval/results/` (`baseline/20261016-195033`, `real_chain/20261016-200357`, `real_chain_img_test/`). Real = a call to a real model through the chain. Counts below are from those files.

## What the real runs showed

| # | Finding | Evidence |
|---|---------|----------|
| F1 | **The image never reached the Vision branch in the 12-run batch.** n8n 2.43 delivered the JPEG as a garbled text field (`body.image`) because `run_incidents.py` sent the part without a Content-Type. Every image incident ran text only and the report said `image_status: not_provided`. | `real_chain/*`: 0 of 8 image runs have a vision step. After adding the Content-Type, fire_01 run: vision answered by nemotron-3.5-super-vl, `image_status: analysed`, and it flagged "no houses visible". |
| F2 | **Very slow runs.** 87 to 348 s per incident. Groq answers in 1 to 7 s, but after a Groq 429 the chain falls to OpenRouter nemotron (reasoning model, 40 to 208 s per call). Two runs hit the 180 s client timeout. | `models_used` seconds: nemotron report 208.5 s, risk 48 to 86 s, knowledge 39 to 70 s. Groq steps 1.4 to 8 s. |
| F3 | **Incident prompt v1 puts a relative description in `location`** ("hills behind the village", "the village"). fire_01 expects "not stated". `/validate` cannot catch it because the words are in the text. | Execution 25 (Gemini), fire_01 report `location: the village` in the image run. |
| F4 | **The repair pass fired often and its reason is lost.** `repaired: true` in 3 of 10 completed runs (fire_01 twice, flood_01 once). The response keeps only the final verdict. | `real_chain` summary, `validation.repaired`. |
| F5 | **Coverage is optimistic on fire.** Knowledge agent said `good` for fire_01 in both runs although FI-01 says nothing covers flames reaching a house. Retrieved evacuation entries satisfy `/validate`. | `knowledge_coverage: good`, fire_01 runs 1 and 2. |
| F6 | **Baseline single prompt:** guessed severity `high` on the vague report in both runs (expected undetermined), 6 of 12 reports with partial coverage had no "no guidance" sentence, 1 of 12 failed the schema. Two false positives came from a validator bug (fixed). | `baseline/20261016-195033/`. Baseline had no image either. |
| F7 | **Validator false positive** on `Location: ** Not specified`. Fixed, with a test. | commit below |
| F8 | Gemini free tier exhausted (daily) for 3.6 and 3.5 flash, 503 on 3.8 and 3.7. The chain absorbed this: no run ended without a model. | `failed_attempts` in `models_used`. |

## Proposed fixes, in order

1. **Latency (F2), 1 hour.** Reorder the chain so the three Groq models come before OpenRouter nemotron (they are separate per-model limits), give each model a call timeout of 45 s in `llm_chain.complete` (so a slow model falls through), and raise the n8n webhook client timeout to 400 s. Re-measure on six incidents. Expect: if Groq limits are per minute, runs of 20 to 40 s. Not proven until re-run.
2. **Image handling (F1), done in part.** `run_incidents.py` now sends the Content-Type. The workflow now says so in `degraded_steps` when an image arrives as text (regenerated, static check passes, not re-run in n8n). Still to do: re-run the four image incidents twice and score Vision.
3. **Incident prompt v2 (F3), 1 hour.** Rule: location is null unless a named place appears; relative phrases ("behind the village") go to reported facts. Test as an agent-level before and after on the six incidents, three runs each, on the same model, with a CHANGELOG entry. Add a guardrail check that `location` is a proper name (starts with a capital) as a second net.
4. **Log the first validation attempt (F4), 30 min.** Return `validation.first_violations` in the response and in `models_used` so the repair reason is visible. Then read the 3 repaired runs to see which check fired.
5. **Coverage honesty (F5), 1 to 2 hours.** Make `/validate` compare the report's `knowledge.coverage` with the retrieval: a fire report that says `good` while FI-01 is among the retrieved entries and the incident text mentions flames near houses is flagged. Or change the synthesis prompt to v3 (cannot mark `good` when FI-01 is retrieved). The second needs a CHANGELOG entry and a test run.
6. **Baseline fairness (F6), 30 min.** Re-score the 12 baseline rows with the fixed validator (`scripts/baseline_single_prompt.py --rescore`, to be written) and run the baseline with the images (needs a vision-capable model in the single prompt). Disclose that the validator was fixed after the first scoring.
7. **Manual checks.** Read the reports of the 10 completed runs against `manual_checks` in each incident file and score honestly. Not done yet.

## What is left from `docs/SPRINT_PLAN.md`

| Sprint | Task | Status | Left |
|--------|------|--------|------|
| 1 | Blind queries, entry-id matching, evaluation | Done | Nothing. A third query set with more structural and French flood cases would help (misses v13, v08). |
| 2 | Schemas, guardrails, mock harness | Done | `report` prompt v3, knowledge v2 and risk v2 are now run by real models (10 reports), so their CHANGELOG entries need the real before and after. Not written. |
| 3 | Workflow generator, n8n run | Done with MOCK and real chain | Re-run after the F1 fix. Error workflow never triggered. Not imported into the team's n8n. |
| 4 | Unit tests | Counted on 2026-10-16 evening: rag 21, backend 64 (all pass) | Update the totals in the evidence log. |
| 4 | Six incidents x 2 runs, real | 10 of 12 answered, text only, no manual scoring | Re-run with images after fix 1, score manual checks, compare run 1 vs run 2 stability. |
| 4 | Baseline | 12 real calls, text only, scored before the validator fix | Re-score, add images, compare with the pipeline on the same measures. |
| 4 | Latency per node | Real values in `models_used` (x_llm seconds) for 10 runs | Summarise per node and per model in the log, after fix 1 changes the mix. |
| 5 | `docs/NEXT_STEPS.md` | Written before the chain and images existed | Stale: update. |
| any | Evidence log and CHANGELOG | Chain, images, validator fix, upload bug not logged yet | Log them. |
| any | Mock replay after the retry and chain changes | Not re-run | Re-run `scripts/replay_mock.py` and `scripts/failure_paths_mock.py` (needs `GEMINI_BASE_URL` pointing at the mock). |

Acceptance criteria check: "every number traces to a raw file" holds for what is logged, but the new runs are not logged yet. "Mock results labelled" holds. "No prompt edited to pass tests" holds, v2 prompts exist only for the contract mismatches.

## Decisions for the team

1. Is a 20 to 60 s run acceptable for the demo, or should the demo use a paid tier?
2. Accept `/llm` as a third Python endpoint (it is outside the original brief)?
3. Which model should be quoted as "the model" in the report, given that each run mixes Groq gpt-oss-120b and OpenRouter nemotron? Suggestion: quote the per-step `models_used` table.
