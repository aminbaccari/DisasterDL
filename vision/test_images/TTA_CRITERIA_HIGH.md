# Rule for the "keep a single-view observation when it is high" variant of the three-view path

Written 2026-10-18 after the first three-view benchmark (`TTA_CRITERIA.md`, `eval/results/vision_bench/20261018-160819`) had failed its rule 3, and BEFORE the variant exists in code and before any run of it.

## What changes
Only the merge policy. Today (`majority`): a category is kept when at least two of the views saw it. Variant (`keep_high`): a category seen by only one view is ALSO kept when that view's confidence for it is `high`; its confidence is then capped at `medium` and it is listed in `reliability.unstable_categories` with support 1. Single-view observations with `medium` or `low` confidence are dropped as before. Nothing else changes (same three views, same prompt `vision/v2.md`, same calls).

## Why this is a weak test, stated in advance
The variant is designed after seeing which true observation the majority rule lost (smoke on `edge_02_conflict`, seen by one view). The 12 images are therefore a development set for this idea, not a fresh test. A pass here means "not rejected on this data", never "shown to generalise". The ground truth is one reader's.

## Design of the run
`scripts/vision_bench.py --runs 3 --prompt vision/v2.md --prompt tta:vision/v2.md --prompt tta+high:vision/v2.md`, `qwen3-vl:4b-instruct` warm, the 12 images, 3 runs. The two three-view conditions share the SAME three model answers per image and run and only differ in the merge (paired, so the difference is the policy and nothing else); their latency is the same three calls. 36 single calls and 108 view calls.

## Rule (same five points as `TTA_CRITERIA.md`, compared with the single call in the same session)
The variant (`tta+high`) is recommended as a SWITCHABLE OPTION, never as the default, only if ALL hold:
1. schema valid in at least as many calls as the single call;
2. no more calls with a false observation than the single call (this is the risk of keeping single-view observations);
3. no more calls with a missing required category than the single call;
4. the quality flag on the two low-quality images at least as often as the single call (flag: image_usable false, quality_issues listed, or category_agreement_score below 0.5);
5. median latency at most 3.5 times the single call's.

A BENEFIT is reported only if, in addition, the quality flag is strictly higher than the single call's OR the number of calls with a missing required category is strictly lower, while rule 2 holds.

## After the run
- If the variant fails rule 2 or rule 3: the three-view path stays off and I stop here. No further merge variants are tried on these images (to avoid searching until something passes).
- If it passes 1 to 5 without a benefit: "no evidence of benefit for three times the cost"; the option stays documented and off.
- If it passes with a benefit: it is documented as an option that deserves a test on new images (to be approved and downloaded separately) before any use.
- The plain `majority` condition is reported again next to it for continuity, with the same rule applied to it.

Limits: 12 images, 3 runs, one model, one reader. A difference of one call is not a difference.
