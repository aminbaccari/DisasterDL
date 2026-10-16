# Fixed test incidents

Six incidents used for every end-to-end test, so results are comparable across prompt and workflow versions.

| id | language | image | what it tests |
|----|----------|-------|---------------|
| fire_01 | en | yes | basic forest fire, no location stated |
| flood_01 | fr | yes | French flow end to end, stated location |
| structural_01 | en | yes | second-hand information, possible trapped people |
| edge_01_vague | fr | no | vague report, system must not guess |
| edge_02_conflict | en | yes (mismatched) | report and image disagree |
| edge_03_injection | en | no | instruction hidden in the incident text |

## Rules

1. The expected values in each file are drafts written before any run. The team confirms them before the first run. Do not change them after seeing outputs in order to make results look better. If an expectation was wrong, change it, say why in docs/EVIDENCE_LOG.md, and re-run.
2. Do not reuse the few-shot examples from the prompts as test incidents. The two examples in prompts/incident_understanding/v1.md are excluded for that reason.
3. The expected severity is a set of acceptable values, not one value, because the scale is our own working scale and several levels can be defensible.
4. Automatic checks cover incident type and severity only. The manual_checks lists are for a human to read the report and score each item.

## Which incident tests "no guidance available"

Use edge_01_vague (vague French report, rag_topic general) for the empty or partial retrieval case, and an off-topic query sent to /search with topic general. Do not use fire_01 for this: since the wildfire sources were added on 2026-10-16 it retrieves real guidance, so it is a normal run. Record what /search actually returns for edge_01_vague in docs/EVIDENCE_LOG.md before claiming coverage none. With prompts/report/v2.md (untested draft) check that the report says "no guidance available, follow the authorities" and does not invent steps, and compare with v1.

## Images

The images are not included. Collect them into vision/test_images/ with the file names given in each incident file.

- Use photos you took yourselves or openly licensed images. Record the source, author and licence in vision/test_images/SOURCES.md.
- Avoid images with identifiable people.
- edge_02_conflict needs an image that contradicts the text (smoke or fire for a flood report). Say in SOURCES.md that it was chosen on purpose to mismatch.
- If an image is missing, scripts/run_incidents.py skips that incident and says so, unless you pass --allow-missing-images, in which case it runs text only and marks the run.

## Running

python scripts/run_incidents.py --url <webhook url> --runs 2

Each run is saved as raw JSON in eval/results/<timestamp>/, with a summary.csv. Run each incident at least twice and compare, since the model may not give the same answer every time. Keep the raw outputs, they are the evidence for the evaluation section.

## Scoring sheet

Copy the summary.csv rows into docs/EVIDENCE_LOG.md (end-to-end tests table) and add your manual score for each manual_checks item.
