# Sprint status: what was executed and what is left (2026-10-17)

Checked against `docs/SPRINT_PLAN.md` (written 2026-10-16), the commits (23 on `main`, pushed), `docs/EVIDENCE_LOG.md` and the files under `eval/results/`. Test counts were run on 2026-10-17: rag 21 tests, backend 84 tests, all passing. "Real" means a call to real models, "MOCK" means canned agents.

## Task table

| Sprint | Task in the plan | Status | Evidence | What is left |
|--------|------------------|--------|----------|--------------|
| 0 | `docs/SPRINT_PLAN.md` | Done | file, commit f56b979 | Update its task list with the added work (chain, vision proposal) |
| 1 | Blind retrieval queries (`rag/eval/queries_v2.csv`) | Done | committed before it was run | none |
| 1 | Third query set (`rag/eval/queries_v3.csv`, 24 queries) and French structural and flood entries | Done 2026-10-17 | committed before the entries and the run; hit@5 0.83 to 0.88 with the filter, see `docs/EVIDENCE_LOG.md` | French reader for FL-27..33 and ST-27..32; French versions of FL-25, FL-26, FL-24 (control queries still miss) |
| 1 | RAG-query agent against a direct query | Done 2026-10-17, no difference shown; re-run with incident v3 and language balance NOT completed (quotas) | `scripts/rag_query_vs_direct.py`, 12 cases, 90% against 90 to 95% of needs met | Larger harder case set; fix D11 |
| 1 | Entry-id matching in `rag/metrics.py`, `rag/evaluate.py`, tests | Done | 6 tests in `rag/tests/` | none |
| 1 | Retrieval evaluation, fixed against section, k = 1, 3, 5 | Done | section hit@1 0.78, MRR 0.81, fixed 0.44 and 0.59 (18 queries) | Misses v08, v12, v13, v16 analysed, not fixed |
| 2 | Agent contracts (6 schemas, examples, mismatch list) | Done | `backend/schemas/`, `docs/CONTRACT_MISMATCHES.md` | none |
| 2 | `/validate` with 8 checks plus image_status (9) and tests | Done | 40+ validator tests, one false positive found and fixed | Log first attempt before repair, real failures as new tests |
| 2 | Mock harness and replay | Done, stale | `backend/mock_gemini.py`, `scripts/replay_mock.py` | Re-run replay and failure paths on the latest workflow |
| 3 | `scripts/build_workflow.py` and `n8n/workflows/disasterai.json` | Done | 78 nodes, static check passes | Keep prompts and drafts in sync (default points at the v2 and v4 drafts) |
| 3 | Run in n8n | Done in a separate n8n 2.43.6 container | MOCK: 6 incidents and 7 failure paths. Real: 12 runs in batches A to C and 1 image run | Not imported into the team's n8n, error workflow never triggered |
| 4 | Unit tests, real counts | Done | 21 + 84 pass | none |
| 4 | Six incidents, two runs, with images | Partly | Batches A, B, C: no Vision step in them (quota, then upload bug); B unusable | Re-run with a vision model and fresh quotas |
| 4 | Manual checks scored | Partly | scoring table for 6 reports in the evidence log | Score the next batch, a second reader |
| 4 | Stability between runs | Partly | edge_01 identical, others differ because of quota | Needs a clean batch |
| 4 | Baseline single prompt | Done once, not re-scored | 12 real calls, text only, scored before the validator fix | Re-score, add images, compare on the same measures as the pipeline |
| 4 | Latency per node, real calls only | Done for batch C and the image test | table in the evidence log | Re-measure after the latency fixes |
| 5 | `docs/NEXT_STEPS.md` | Done, updated 2026-10-17 | file | Update after the vision decision |
| extra | Fallback chain (Groq, OpenRouter, Gemini), `/llm`, `scripts/llm_ping.py` | Done | 21 tests, models verified by ping | persisted cooldowns, token budget |
| extra | Four CC BY test images | Done | `vision/test_images/SOURCES.md` | About 12 images for a vision benchmark |
| extra | Incident v2 and report v4 drafts, before/after scripts | Written, tested partly | `scripts/before_after.py`, `scripts/report_ab.py`, partial results | Full re-run with fresh quotas |
| extra | Bottlenecks list and vision proposal | Written 2026-10-17 | `docs/BOTTLENECKS.md`, `docs/VISION_ARCHITECTURE.md` | Team decisions |
| extra | Vision chain (`VISION_CHAIN`, `task`, ollama and hf providers) | Done 2026-10-17: code, 11 tests, and a real local model | `qwen3-vl:4b-instruct` in Docker, `scripts/vision_bench.py` 8 calls, 2 end-to-end image runs, `docs/EVIDENCE_LOG.md` | Image-only vision prompt v2, about 12 benchmark images, a second model, HF provider untested (no token) |

## Acceptance criteria of the sprint plan

| Criterion | Holds? |
|-----------|--------|
| Every number traces to a raw file or a command output | Yes for what is logged. The before and after and report test sections state their own limits. |
| Mock results are labelled | Yes (`MOCK` in file names and in the log) |
| Prompts change only through a new version with a CHANGELOG entry | Yes. v2 and v4 drafts have entries with "NOT TESTED" or partial results. |
| All unit tests pass before each commit | Yes |

## Known open defects (from real runs)

| Id | Defect | Evidence | Where handled |
|----|--------|----------|---------------|
| D1 | Vision step missing in nearly all image runs | `eval/results/real_chain*` | Fixed for the local path 2026-10-17 (vision step answered in 2 of 2 image runs), `docs/VISION_ARCHITECTURE.md` |
| D9 | Vision model echoes the report text (false observations) | edge_02, structural_01, 3 of 10 | proposed vision v2 (image only) |
| D11 | Preparation and some aftermath reports typed `other` or `unclear`, so no knowledge search | h07, h08, c03, c04 | incident v3 draft 2026-10-17, held-out check passed on small counts (v3 fresh positives 8 of 8, negatives 12 of 12), not yet run in n8n |
| D12 | French translations crowd out English-only entries for French queries | f12 (propane tank) rank 2 to miss; s03, s04 rank 1 to 4 | language balance in `/search` 2026-10-17: held-out hit@5 0.42 to 0.84; recovered answers sit at ranks 4 and 5; workflow sends `balance_languages: true`, not run in n8n |
| D13 | v2 typed a car through a shop window as `structural_emergency` (2 of 2 runs, n01) and a burglary as structural once (n07) | `eval/results/incident_type_check/20261017-233924` | incident v3 draft, 0 of 3 answered runs on n07 to n10 |
| D14 | A repair pass returned a truncated report (4 required fields missing) and the workflow used it; D5 made repairs frequent | `eval/results/ui_runs/20261018-151829-899_edge_03_injection.json` | fixed 2026-10-18: coverage capped in the knowledge node, a worse repair is discarded; Node tests; one clean real run, the repair path itself not reproduced live |
| D15 | Severity of edge_03 varied over 4 console runs (high, moderate, high, undetermined; the last outside the accepted set) | `eval/results/ui_runs/` | not analysed; needs repeated runs on a pinned model |
| D16 | Three-view vision option: built and tested, fails its adoption rule (missing required categories 4 against 2, no quality-flag gain, 2.9 times latency) | `eval/results/vision_bench/20261018-160819` | stays off behind `--vision-mode tta`; a one-vote-with-high-confidence variant would need a new pre-registered rule |
| D10 | Repair pass slow: the retry rotation sends it to OpenRouter nemotron (100+ s) | `eval/results/vision_chain_e2e` | `docs/BOTTLENECKS.md` item 3 |
| D2 | Location copied as a relative phrase (v1) | fire_01, 2 of 2 completed runs | incident v2 draft, untested |
| D3 | Free text in English for a French incident | edge_01 | incident v2 draft, untested |
| D4 | Report JSON missing fields from one model | 2 of 6 in batch C, 0 of 9 in the paired test | report v4 draft, untested |
| D5 | Coverage `good` for fire although FI-01 | fire_01 batch A | Validator rule added 2026-10-17 (3 unit tests, `backend/validate.py`); not run on a real report yet |
| D6 | Repair pass fires and its reason is lost | 3 of 10 runs | `validation.first_violations` added to the repaired response in `scripts/build_workflow.py` 2026-10-17; static check only, not run in n8n |
| D7 | Misfiled injection text under `assessment.conflicts` | edge_03 run 1 | not fixed: needs the real edge_03 output as a failing test first |
| D8 | Early-exit report did not state image and retrieval status | edge_01 | fixed in the workflow (MOCK-checked only) |

## Defect closed in the docs: failed Vision step reported as an unusable image (2026-10-17)

Fixed earlier in code, not recorded as closed until now: the workflow sets `image_status: analysis_failed` and leaves `vision` null (`scripts/build_workflow.py`, Vision parse node), `/validate` check 9 `image_status` compares the report with the workflow status (`backend/validate.py`), regression test `TestImageStatus.test_failed_vision_step_must_not_be_reported_as_unusable`, MOCK mode `vision_fail`, and in the real before and after test image_status matched what happened in 3 of 3 runs. Not yet seen with the local vision model switched off.

## Consolidated queue

The ordered fix queue (phases 0 to 6, with proofs) is the plan file of 2026-10-17; copy it into `docs/NEXT_STEPS.md` when the team agrees.

## Next actions, in order

1. Decide the vision architecture (four questions at the end of `docs/VISION_ARCHITECTURE.md`).
2. Implement the vision chain and benchmark (about 2 days).
3. When quotas are back: run the re-run list of `docs/NEXT_STEPS.md` and close D2, D3, D4 with before and after entries.
4. Fix D5 and D6, then re-score the baseline and re-run the mock replay.
5. Team tasks: French review of FI-21 to FI-26, OCR re-check of four flood pages, more test images.

## Decisions for the team

1. Is a 20 to 60 s run acceptable for the demo, or should the demo use a paid tier?
2. Is `/llm` accepted as a third Python endpoint (outside the original brief)?
3. Which model is named "the model" in the report, since runs mix models? Suggestion: quote `models_used` per step.
4. The vision decisions listed in `docs/VISION_ARCHITECTURE.md`.
