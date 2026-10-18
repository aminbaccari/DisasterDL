# Relevance judging: agreement between the two LLM judges

- Items: 325 pooled (query, document, page) pairs; scored by both judges: 325
- Judge A (Claude subagents) score distribution: {0: 106, 1: 117, 2: 102}
- Judge B (llama3.2:3b) score distribution: {0: 106, 1: 112, 2: 107}
- Quotes not found in the page: Judge A 0, Judge B 25
- Cohen's kappa, 3 levels: 0.377
- Cohen's kappa, binary lenient (score >= 1): 0.482
- Cohen's kappa, binary strict (score = 2): 0.471
- Raw agreement, binary lenient: 77.2%
- Disputed (lenient disagreement, invalid quote or missing score): 95
- Adjudication sheet: 125 items (95 disputed + 30 random agreed)
