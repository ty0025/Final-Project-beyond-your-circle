# Tokenomics (problem 8): real ledgers only

Prices: Lecture 11 slides, https://zlisto.github.io/mgt_409_fa26/lectures/slides/lec11-slides.html, re-read 2026-10-26: input $0.10, cached $0.01, cache write $0.125, output $0.50 per 1M tokens; input_tokens = 'total tokens you sent in'; reasoning tokens 'count toward output'.

Sample: 5 normal real runs (problems 4-6), 19 model calls; small sample, not a traffic study.

| run_id | calls | input | cached | cache write | output (reasoning) | cost | guard part | cost if no prompt cache |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `r_b79bfbda45ad` | 4 | 8,457 | 4,829 | 3,237 | 868 (471) | $0.000926 | $0.000055 | $0.001280 |
| `r_8aad4fe5a302` | 4 | 10,314 | 5,733 | 4,184 | 631 (276) | $0.000936 | $0.000059 | $0.001347 |
| `r_c588d02ea0b5` | 4 | 10,821 | 8,331 | 2,102 | 1,380 (600) | $0.001075 | $0.000059 | $0.001772 |
| `r_835194ffb88a` | 3 | 5,889 | 4,857 | 643 | 424 (173) | $0.000380 | $0.000057 | $0.000801 |
| `r_ce638df7cf6e` | 4 | 10,748 | 5,898 | 4,464 | 1,306 (620) | $0.001309 | $0.000055 | $0.001728 |

Per run: mean $0.000925, median $0.000936, min $0.000380, max $0.001309; 3.8 calls and 10,168 tokens on average; cache hit rate 64.1%.

| runs per user per month (scenario) | 1 user | 100 users | 10,000 users |
|---:|---:|---:|---:|
| 4 | $0.003700 | $0.37 | $37.00 |
| 8 | $0.007400 | $0.74 | $74.00 |
| 30 | $0.027749 | $2.77 | $277.49 |

Optimisations, computed from the same real rows (not separate A/B runs):
- Prompt cache: actual $0.004625 vs $0.006927 without it (33.2% saved).
- Dropping the LLM guard would save 6.2%; not adopted: matcher input is identical for unflagged requests, so picks would not change; but the guard alone blocked the q07 soft canary attack r_6dff5fbf9fb4 -> not adopted.

Totals: normal $0.004625 (19 rows); red-team $0.002125 (9 rows); all project real calls $0.006750. Excluded Harbor history rows: 95.

Checks (normal): {"rows": 19, "all_status_ok": true, "no_missing_usage": true, "served_models": ["gpt-6-luna-global"], "cost_recomputed_equals_ledger": true, "cached_plus_write_within_input": true, "reasoning_within_output": true, "unique_response_ids": true, "min_latency_ms": 1381}
Checks (red-team): {"rows": 9, "all_status_ok": true, "no_missing_usage": true, "served_models": ["gpt-6-luna-global"], "cost_recomputed_equals_ledger": true, "cached_plus_write_within_input": true, "reasoning_within_output": true, "unique_response_ids": true, "min_latency_ms": 1257}
