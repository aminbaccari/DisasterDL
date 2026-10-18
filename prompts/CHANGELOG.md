# Prompt changelog

One entry per prompt change. Fill it in when it happens. This is the evidence for the before and after examples.

Template:

## <agent> v<old> to v<new> (YYYY-MM-DD)
- Test input that failed:
- What went wrong (paste the actual output):
- Change made to the prompt:
- Result after the change (paste the actual output):
- Technique involved (role, JSON schema, few-shot, constraint, other):

## Entries

(none yet)

## rag_query synthesis v1 to v2 (2026-10-16)
- Test input that failed: not a model input. Contract check `python scripts/check_contracts.py` on an output shaped as `v1_synthesis.md` documents it (same fields, citation without entry id).
- What went wrong (actual validator output): `relevant_guidance/0/citation : 'entry_id' is a required property`. The v1 citation (chunk_id, source, page) cannot be checked by /validate against retrieved entry ids, and page is always 1 for knowledge base files.
- Change made to the prompt: citation now includes entry_id, taken from the passage's entry_ids list (rule 2 and the output schema). File: prompts/rag_query/v2_synthesis.md.
- Result after the change: the documented v2 shape validates (no errors in the same script). NOT yet run on a model, so it is not known whether the model uses valid entry ids. /validate will check that the entry id is in the cited chunk.
- Technique involved: JSON schema.

## risk v1 to v2 (2026-10-16)
- Test input that failed: same contract check, output shaped as `risk_assessment/v1.md` documents it.
- What went wrong (actual validator output): `considerations/0/citation : 'entry_id' is a required property`.
- Change made to the prompt: considerations copy the knowledge citation unchanged including entry_id. File: prompts/risk_assessment/v2.md.
- Result after the change: the documented v2 shape validates. NOT yet run on a model.
- Technique involved: JSON schema.

## report v1/v2 to v3 (2026-10-16)
- Test input that failed: not a model input. Contract check of a Markdown string (what report v1 and v2 return) against backend/schemas/report.schema.json.
- What went wrong (actual validator output): `(root) : '# Preliminary incident assessment ...' is not of type 'object'`. /validate needs structured recommendations with entry ids, a location field and a no-guidance statement.
- Change made to the prompt: v3 returns one JSON object that includes report_markdown. It also folds in the partial-coverage wording drafted in v2 (rule 6) and adds the rules on location, dispatch and entry, injected text and numbers. File: prompts/report/v3.md.
- Result after the change: the documented v3 shape validates. NOT yet run on a model. v2 stays as an untested draft and is not used by the workflow.
- Technique involved: JSON schema, constraint.

## incident_understanding v1: observed failure, no new version yet (2026-10-16)
- Test input that failed: fire_01 ("Smoke is rising from the hills behind the village and flames are visible near the first houses. A strong wind is blowing toward the village."), real Gemini gemini-3.6-flash through the n8n workflow, execution 25 (eval/results/real_gemini-3.6-flash/n8n_execution_25.json).
- What went wrong (actual output): `"location": {"text": "hills behind the village", "precision": "area"}`. The fixed incident expects the location to be not stated (manual check: "Location is reported as not stated, not invented").
- Change made to the prompt: none. A v2 rule is a candidate (a relative description without a place name gives null), but it could not be tested because the free-tier daily quota was exhausted, and the prompt must not be changed without a before and after run.
- Result after the change: not applicable.
- Technique involved: constraint (candidate).

## Observed on real runs, no new version written yet (2026-10-16)
- report v3, knowledge v2, risk v2 (first real runs, docs/EVIDENCE_LOG.md, batch C): knowledge v2 and risk v2 produced valid outputs with entry ids in the 6 reports that completed. Report v3 was valid in 4 of 6 reports. Two reports from qwen3.8-27b lacked uncertainties, information_needed, disclaimer and report_markdown (status flagged, the repair pass did not help). Candidate change: state that every field of the schema is required and add one complete output example. Not changed: the quota is exhausted, so a before and after run is not possible today.
- incident v1: location still copied as a relative phrase (fire_01: "hills behind the village" in 2 of 2 completed runs), and free text in English for a French incident (edge_01 missing_information). Candidate v2: location null unless a named place appears, free text in the incident language.
- vision v1: one real run (fire_01 image), the output matched its schema and listed only visible things. No failure observed, too few runs to say more.

## incident_understanding v1 to v2 (2026-10-16 evening, written, NOT yet tested)
- Test input that failed: fire_01 through the n8n workflow with real models, `location.text` = "hills behind the village" in the completed runs (docs/EVIDENCE_LOG.md, batch C and n8n execution 25). edge_01 (French): missing_information written in English.
- What went wrong (actual output): `"location": {"text": "hills behind the village", "precision": "area"}`; edge_01 list "Type of incident", "Exact location", ... under a French heading.
- Change made to the prompt: prompts/incident_understanding/v2.md. Rule 4: a location is a named place, relative phrases give null and stay in reported_facts. Rule 6: free-text fields in the report language. The second few-shot example no longer has a location ("downtown" is generic).
- Result after the change: NOT TESTED. Planned: same six incidents, same model, three runs each with v1 and v3-style workflow (`scripts/build_workflow.py --prompt incident=incident_understanding/v1.md`) against v2, count locations that are not named places and free text in the wrong language. Run after the free-tier quota resets.
- Technique involved: constraint.

## report v3 to v4 (2026-10-16 evening, written, NOT yet tested)
- Test input that failed: flood_01 run 1 and fire_01 run 2 (batch C, qwen3.8-27b): report JSON lacked uncertainties, information_needed, disclaimer and report_markdown, status flagged, repair did not fix. edge_02 (both runs): a failed Vision step was reported as "No usable image was provided".
- What went wrong (actual output): `schema: (root): 'uncertainties' is a required property` (and three more); `image_status: unusable` with the image not analysed.
- Change made to the prompt: prompts/report/v4.md adds an <image_status> input with a value analysis_failed (rule: never call the image unusable), a rule that every schema field is required, and one complete format example of an invented incident (checked by tests to satisfy the schema and the guardrails). The workflow now sends image_status and `/validate` checks that the report repeats it.
- Result after the change: NOT TESTED on a model. Planned: the same incidents on the same model, count schema failures and wrong image_status with v3 and v4. Watch for the model copying the example.
- Technique involved: JSON schema, few-shot (one example), constraint.

## Partial test results for incident v2 and report v4 (2026-10-16 night, docs/EVIDENCE_LOG.md)
- incident v1 to v2: in the stopped pipeline test (one round, 3 to 4 runs per variant) the report location was a generic phrase in 2 of 2 completed BEFORE runs ("main road", "farm") and null in 3 of 3 AFTER runs. The French edge_01 early exit listed its missing information in French with v2 (French word share 1.00) and in English with v1 (0.08). One run per cell, so an observation only.
- report v3 to v4: paired test on one model (qwen3.8-27b), inputs identical: v3 answered 9, schema valid 9 of 9, passed /validate 2 of 9 (7 failures on image_status, which v3 does not receive); v4 answered 5, schema valid 5 of 5, passed /validate 5 of 5, did not copy its format example (0 of 5). v4 was lost to rate limits more often (7 of 12 calls against 4 of 13), its prompt is longer. The earlier schema failure of v3 (missing fields) did not recur (0 of 9). Not enough to call v4 better writing; it shows the new input and check work and that the longer prompt costs free-tier tokens.
- Both stay drafts until a run with fresh quotas on more than one provider.

## Observed on real runs: vision v1 with a local model (2026-10-17), no new version written yet
- Model qwen3-vl:4b-instruct, 8 answers on 4 images (eval/results/vision_bench/20261017-132058) and 2 end-to-end runs. Input that failed: edge_02_conflict (report "Flooding on the main road, water is rising quickly", image of a dry backyard under smoke haze), run 2 and the end-to-end run.
- What went wrong (actual output): observation `flood_water medium: "A grassy field in the distance appears to be flooded or waterlogged, with shallow water visible beyond a fence"` and `consistent_with_report: partly`. structural_01 run 1: observation "dust visible ... in the air" (the report says dust). Also observations of absence ("No people are visible") with high confidence, a place comparison with "Nabeul" despite rule 5, and one answer with the category "dust" outside the schema enum.
- Change made to the prompt: none yet. Proposed v2: the incident text is not given to the vision model, the output lists observations, visible text and not_determinable only, the consistency check with the report moves to the text agents (see docs/VISION_ARCHITECTURE.md, "Making a small model reliable").
- Result after the change: not applicable.
- Technique involved: constraint, removing the report from the input.

## vision v1 to v2 and risk v2 to v3 (2026-10-17, written, tested partly, still drafts)
- Test input that failed: edge_02_conflict and structural_01 with the local model qwen3-vl:4b-instruct (docs/EVIDENCE_LOG.md): observations that matched the report text and not the picture ("a field appears flooded", "dust in the air"), the model reasoning about the place named in the report, observations of absence, one answer with a category outside the enum.
- What went wrong (actual output): `flood_water medium: "A grassy field in the distance appears to be flooded or waterlogged"`; `inconsistencies: ["The report mentions Nabeul, but the architecture ... suggest a European town"]`; `people high: "No people are visible in the image."`; category "dust".
- Change made to the prompts: prompts/vision/v2.md (image only, no incident text, no absence observations, no place guessing, fixed categories, at most six observations, no comparison fields) and prompts/risk_assessment/v3.md (rule 3: the Risk agent compares the observations with the reported facts). Schema: the two comparison fields became optional.
- Result after the change (12 calls per prompt, same model, interleaved): schema valid 12 of 12 against 10 of 12, absence observations 2 against 14, place words 0 of 12 against 3 of 12, false observations by tag 0 against 0 (the earlier echoes did not recur, so no effect shown on them). Text side, 3 runs per cell on one model: place-name false alarms on flood_01 0 of 3 against 3 of 3, edge_02 conflict detected 3 of 3 for both, but the true conflict "flames near the first houses, no houses visible" for fire_01 found in 1 of 3 against 2 of 2 answered. Still drafts.
- Technique involved: constraint, removing the report from the vision input, moving the comparison to the text agent.

## vision questions v1 to v2, vision check v1 to v2 (2026-10-17, drafts, tested on 4 images, 3 runs)
- Test input that failed: flood_01 with questions v1 (question "Are blocked roads visible in the image?", check v1): answered no in 3 of 3 runs, evidence "roads are submerged, no visible road surfaces", which creates the false conflict "report: roads are blocked, image: not visible".
- Change made to the prompts: prompts/vision_questions/v2.md (one concrete thing per question, "near" claims split, abstract words such as blocked, rising, spreading banned) and prompts/vision_check/v2.md (a question about a state or trend gets "unclear").
- Result after the change: fire_01 house conflict found 3 of 3 (both versions), edge_02 3 of 3, flood_01 false alarms 3 of 3 with v1 and 2 of 3 with v2 (now "Are roads visible in the image?" answered no because the road is under water). Not fixed. v2 was written after reading the v1 answers on the same images, so it is not an independent result.
- Technique involved: constraint, closed questions.

## incident v2 to v3 (2026-10-17, draft, partly tested, now the workflow default)
- Test input that failed: held-out reports h07 "We live next to a pine forest. What should we do to protect our house before the fire season?" and h08 (French, flood preparation), and n01 "A car crashed into a shop window on the main street and the driver is injured." (model gpt-oss-120b, `eval/results/incident_type_check/20261017-230810`).
- What went wrong (actual output): h07 and h08 typed `unclear` or `other` in 4 of 4 answered runs, so rag_topic was `general` and the knowledge base was not searched; n01 typed `structural_emergency` in 2 of 2 runs.
- Change made to the prompt: `prompts/incident_understanding/v3.md`, type definitions include the time after the event and preparing for it; a broken window or a vehicle hitting a building without reported structural damage is not structural; rule 8 on aftermath and preparation.
- Result after the change (gpt-oss-20b, 2 runs, v2 and v3 interleaved, errors excluded, `eval/results/incident_type_check/20261017-233924`): fresh preparation and aftermath positives h09 to h12 8 of 8 against 3 of 6; h01 to h06 12 of 12 both; all ten negatives 12 of 12 not typed as a disaster against 9 of 12; the six fixed incidents 6 of 6 both. Small counts: 14 of 56 v3 calls and 18 of 56 v2 calls excluded as rate-limit errors.
- Technique involved: constraint (type definitions with boundary cases).
