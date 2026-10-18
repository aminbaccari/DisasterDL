# Decision rule for the second local vision model

Written 2026-10-18 before any run of the second model on the 12 images.

Candidates: `ollama:qwen3-vl:4b-instruct` (current) and `ollama:gemma3:4b`. Same 12 images (the four of the first batch and the eight of 2026-10-17), same prompts (`vision/v1.md` with the report text, `vision/v2.md` image only), 2 runs each, `scripts/vision_bench.py`, warm model, one model loaded at a time. Measures as defined in that script, ground truth by one reader (`GROUND_TRUTH.json`).

gemma3:4b replaces qwen3-vl:4b-instruct as the first link of `VISION_CHAIN` only if, for the prompt the workflow would use:
1. schema valid in at least as many calls;
2. no more calls with a false observation;
3. no more calls with a missing required category;
4. no more calls that miss the quality flag on the two low-quality images (edge_04, control_01);
5. median latency at most 1.5 times that of the current model.
Otherwise the current model stays and gemma3:4b is reported as a measured alternative. Ties on all five keep the current model (no switch without evidence).

Not scored by any rule here and therefore not a basis for the decision: whether each observation is true beyond the tags (needs a reader), place guessing and absence observations (reported, not decisive). 24 calls per model and prompt cell on 12 images is a small sample; a difference of one call is not a difference.
