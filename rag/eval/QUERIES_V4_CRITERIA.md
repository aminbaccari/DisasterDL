# Pass criteria for the D12 fix on queries_v4.csv

Written 2026-10-17 after the BASELINE on queries_v4 had been run (hit@5 8 of 19 without the fix) and BEFORE any run with the fix. The queries themselves were committed before the baseline (commit 26fb76f); these criteria were not, which is a gap in the pre-registration.

Setting: section chunking, topic filter, k = 5, `--balance-languages` against the same without it.

1. Group A (12 French queries whose answer is only in an English entry): hit@5 improves by at least 2 queries.
2. Groups C and E (7 controls with a French translation or in English): hit@5 loses at most 1 query.
3. Group E (3 English queries): no loss at all.

If 2 or 3 fail, the fix is not adopted into the workflow whatever it does on 1. The 24 queries of v3, the 18 of v2 and the 12 cases of incident_cases_v1 are re-run afterwards but were seen before the fix, so they are a regression check, not evidence of improvement.
