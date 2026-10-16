# Next steps (2026-10-16)

Everything here comes from `docs/EVIDENCE_LOG.md`, `docs/CONTRACT_MISMATCHES.md` and the commits of 2026-10-16. "Real" means a call to Gemini or to the local index that actually ran. "MOCK" means canned agent answers.

## What works, and how we know

| Item | Evidence |
|------|----------|
| Knowledge base: 78 entries in `rag/corpus/{en,fr}`, rebuilt by `rag/knowledge_base/tools` | QA T1 to T9 passed on 2026-10-16, 14 of 14 runnable self-tests caught. The 4 OCR-only flood pages were not re-verified (no tesseract). |
| Retrieval, section chunking | Real, 18 pre-registered queries (`rag/eval/queries_v2.csv`): hit@1 0.78, hit@3 0.83, hit@5 0.89, MRR 0.81. Fixed chunking: hit@1 0.44, MRR 0.59. With the topic filter section reaches hit@5 0.94. |
| `/validate` (8 checks) | 29 unit tests, one passing and one failing case per check. Also failed on all 5 known-bad MOCK reports. |
| Agent contracts | 6 JSON schemas, 7 tests, `python scripts/check_contracts.py`. |
| n8n workflow structure | 78 nodes generated from the prompt files, static check passed, imported and run in n8n 2.43.6 with the MOCK Gemini: 6 incidents answered, 7 failure paths behaved as designed (400, retry then degraded, needs more information, repair, flagged, RAG down). |
| Real Gemini, partial | gemini-3.6-flash answered the incident, RAG query and risk steps for fire_01 (text only). Latencies in the evidence log. |
| Unit tests | rag 21, backend 49, all passing on 2026-10-16. |

## What is untested

- Knowledge synthesis, Report (JSON) and the repair pass with a real model. Prompts knowledge v2, risk v2 and report v3 have never produced a report.
- Vision on any image (no images in `vision/test_images/`). The multipart image upload and base64 step are untested.
- The six incidents end to end with real Gemini, two runs each, and manual checks. Stability between runs.
- The baseline single prompt against the pipeline (`scripts/baseline_single_prompt.py`, offline tests only).
- The error workflow (imported, never triggered). Execution on the team's own n8n.
- Cross-language retrieval quality for French queries on English-only entries (3 of 4 cross-language queries missed).

## Known weaknesses, with evidence

1. Incident prompt v1 put "hills behind the village" in `location` for fire_01 (n8n execution 25). The guardrail cannot catch it because the phrase is in the text.
2. Retrieval miss: structural_01 style query v13 (people possibly trapped, may neighbours go in) missed ST-05 in the top 5 for both strategies.
3. Without a topic filter French queries drift to French fire entries (queries v08, v12, v16). The workflow always sends a topic, but a wrong incident type means wrong filter.
4. `fire.md` covers nothing for flames already reaching a house (entry FI-01). A fire incident normally gets coverage partial, so the "no guidance" sentence depends on the report prompt and `/validate`, not on empty retrieval. Tunisian guidance is one news report (FI-12).
5. Free tier of Gemini: 429 after 6 requests in 19 s, then the daily quota. 503 "high demand" on the team model gemini-3.8-flash. A demo on the free tier needs pacing (`--pace-seconds 13`) and a fallback model.
6. Guardrails are regular expressions. They passed every MOCK report, which proves nothing about real reports.

## Ranked backlog

1. Get a working Gemini route for a full run (quota reset, a second key, a paid tier, or another model) and run `scripts/run_incidents.py --runs 2` on the six incidents, then score `manual_checks` (incident file lists). Owner idea: n8n and integration.
2. Collect test images (fire, flood, structural, one mismatched) with licences in `vision/test_images/SOURCES.md`, then test Vision and the upload path. Multimodality.
3. Run `scripts/baseline_single_prompt.py` on the same incidents and compare (type, acceptable severity, citations, invented location, manual checks). Multi-agent justification.
4. Test prompts knowledge v2, risk v2 and report v3 on real output. For each failure write the before and after in `prompts/CHANGELOG.md`. Decide on an incident prompt v2 for the location rule. Prompt engineering.
5. Fire sources: official ONPC page, a wildfire evacuation document for Tunisia, French flood and structural entries. RAG.
6. Retrieval: more French flood and structural entries, a second blind query set, test the RAG query agent against a single direct query (comparison named in `prompts/rag_query/v1.md`). RAG.
7. Import the workflow into the team's n8n (credential "Gemini key", port 8010 service), trigger the error workflow once, screenshot the canvas and one execution per failure. n8n and integration.
8. Re-run `rag/knowledge_base/tools/qa_kb.py` where tesseract exists. Architecture and coordination.
9. Arabic, a UI, deployment: not started, out of version 1 scope.

## Who could take what (6 roles, 4 people, to be agreed)

Roles named in README.md: architecture and coordination, RAG, multi-agent system, prompt engineering, multimodality, n8n and integration. Suggested split: person 1 items 1 and 7; person 2 items 5, 6 and 8; person 3 items 4 and 3; person 4 item 2 plus the screenshots and the evidence log. Everyone must be able to explain the n8n canvas, `/validate` and the retrieval numbers.

## Presentation sections

The professor's list of 8 sections is not in the repository, so no full mapping is claimed. What the repo documents: prompt iteration evidence is section 3 (`prompts/CHANGELOG.md`), error handling is section 7 (`degraded_steps`, the failure-path results), the multi-agent justification is the baseline comparison (item 3), retrieval is `docs/EVIDENCE_LOG.md` RAG experiments. The team should paste the 8 titles here and map each to its file.

## Questions the team must answer before the demo

1. Which Gemini model and plan will the demo use, and what is the fallback when it answers 503 or 429?
2. Is the report JSON (prompt v3) accepted, or does the team want Markdown only and weaker checks?
3. Who reads the French text (FI-21 to FI-26 and the French entries) before the demo?
4. Which images are used, and are their licences recorded?
5. Does the demo run on the team's n8n instance? The container named `n8n` that ran before the Docker restart was missing afterwards, its volume `n8n_data` exists.
6. Should the `.env.example` file come back? README and CLAUDE.md still tell people to copy it.
7. Is the severity scale (our own working scale) described as such in the slides?

## Update 2026-10-17: re-run list for when free-tier quotas are back

Decision of the team: incident prompt v2 and report prompt v4 stay untested drafts (`prompts/CHANGELOG.md`). The default workflow built by `scripts/build_workflow.py` still points at those drafts; to run the tested prompts use `--prompt incident=incident_understanding/v1.md --prompt report=report/v3.md`.

1. Check the models first: `python scripts/llm_ping.py --json` and `python scripts/llm_ping.py --model gemini:gemini-3.6-flash --image`. A useful run needs at least two providers with quota and one vision-capable model.
2. Full pipeline before and after: build both workflows with different `--workflow-id` and `--path`, import them (`n8n import:workflow`, `publish:workflow`, restart), then `python scripts/before_after.py run --before-url .../webhook/incident_before --after-url .../webhook/incident_after --runs 3` and `python scripts/before_after.py analyse <folder>`.
3. Paired report test on one pinned model: `python scripts/report_ab.py --runs 3 --chain <provider:model> --pace-seconds 65` (the pause is for tokens-per-minute limits).
4. Score the manual checks of the new runs with `scripts/show_run.py`, log in `docs/EVIDENCE_LOG.md`, and turn the CHANGELOG "NOT TESTED" lines into before and after entries.
5. Still open from `docs/SPRINT_STATUS.md`: log the first validation attempt before the repair pass, coverage honesty for fire (F5), re-score the baseline with the fixed validator, update the mock replay after the latest workflow changes.
