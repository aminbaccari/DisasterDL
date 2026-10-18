# Adoption rule for the three-view (TTA) vision path

Written 2026-10-18 before any code for it existed and before any run.

What is compared: the single-call vision path (prompt `vision/v2.md`, image only) against the three-view path (the same prompt on three views of the image: original, mirrored, contrast-adjusted; observations kept only when at least two views agree; reliability block). Same local model (`ollama:qwen3-vl:4b-instruct`), warm, the 12 test images, 2 runs each, the two conditions interleaved in one session, `scripts/vision_bench.py` (`tta:vision/v2.md` is the three-view condition). 24 calls per condition for single, 72 model calls for the three-view one. Ground truth by one reader (`GROUND_TRUTH.json`).

The three-view path is recommended as a SWITCHABLE OPTION (never the default, the workflow keeps the single call as the default either way) only if ALL of these hold:
1. schema valid in at least as many calls as the single path;
2. no more calls with a false observation than the single path;
3. no more calls with a missing required category than the single path (keeping only agreed observations can lose true ones, this is the risk);
4. on the two low-quality images (edge_04, control_01; 4 calls each condition) the quality flag is raised at least as often as with the single path, where the flag for the three-view path is: image_usable false, OR quality_issues listed, OR category_agreement_score below 0.5 (the threshold is fixed here, before the run);
5. median latency at most 3.5 times the single path's.

It is reported as showing a BENEFIT only if, in addition, the quality flag on the low-quality images is strictly higher than the single path's. If 1 to 5 hold without a benefit, the result is "no evidence of benefit for three times the cost" and the option stays documented and off. If any of 1 to 3 fails, it stays off.

Also reported, not decisive: mean category agreement on the ten ordinary images against the two low-quality ones, absence statements, place words, calls where fewer than three views answered.

Limits stated in advance: 12 images, 2 runs, one model, one reader's ground truth. A difference of one call is not a difference.
