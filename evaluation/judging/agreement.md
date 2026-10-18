# Relevance judging: LLM panel

- Items: 279 pooled (query, document, page) pairs, prompt relevance_judge v3
- judge1 = openai/gpt-oss-120b; judge2 = qwen/qwen3.8-27b; tie-breaker = llama3.1:8b
- judge1 raw score distribution: {0: 56, 1: 90, 2: 133}; invalid votes (failed or invented quote): 28
- judge2 raw score distribution: {0: 69, 1: 82, 2: 128}; invalid votes: 12
- Items with two valid votes: 241
- Cohen's kappa judge1 vs judge2, 3 levels: 0.657
- Cohen's kappa, binary lenient (score >= 1): 0.747
- Cohen's kappa, binary strict (score = 2): 0.733
- Raw agreement: exact score 78.0%, lenient 90.5%
- Disputed items sent to the tie-breaker: 91

## Final labels

- Tie-breaker valid votes: 87/91; it sided with judge1 on 26 and with judge2 on 41 items
- Final score distribution: {0: 76, 1: 77, 2: 125}; unresolved (no valid vote): 1
- Relevant items: lenient (score >= 1) 202, strict (score = 2) 125
- Agreement of the earlier keyword labels with the final lenient labels: 53.6% (kappa 0.206)
