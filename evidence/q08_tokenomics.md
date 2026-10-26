# Tokenomics (problem 8): one cost summary

Prices: Lecture 11 slides, https://zlisto.github.io/mgt_409_fa26/lectures/slides/lec11-slides.html, re-read 2026-10-26: input $0.10, cached $0.01, cache write $0.125, output $0.50 per 1M tokens; input_tokens = 'total tokens you sent in'; reasoning tokens 'count toward output'.

Ledger cut-off: **2026-10-25T21:23:30Z** (last live model call included). Source: committed copies evidence/*/<run_id>.usage.jsonl (identical to the ledger rows); no model calls.

## Cost summary

| Category | Contains | Runs | Model calls | Input / cached / cache-write tokens | Output (reasoning) | Cost |
|---|---|---:|---:|---|---|---:|
| (i) Typical-run sample | every run of the normal app flow in runs/usage.jsonl: Q4 first real run + Q5 case runs + Q6 end-user flow run + Q8-A the user's three searches + G-12 fix re-check | 9 | 33 | 78,247 / 50,985 / 23,797 | 7,814 (4,152) | $0.007738 total; $0.000860 per run (range $0.000380 to $0.001389) |
| (ii) Development + safety-testing total | every live model call of this project: (i) + Q7 red team (separate ledger) + Q8 fresh clone (clone's own ledger) | 13 | 46 | 109,734 / 68,491 / 36,233 | 11,335 (6,158) | $0.011383 |
| (iii) Historical placeholder records | Harbor Bikes placeholder domain, written before the Q4 metering gate (no `mode` field) | 15 | 133 | 256,156 / 172,179 / 77,829 | 35,186 (13,916) | excluded, not this project |

(i) is part of (ii). (iii) is listed only so older screenshots that mixed it in can be reconciled; no figure uses it.

## Where the calls came from

| Workload group | Ledger | Runs | Calls | Cost | In (i)? |
|---|---|---:|---:|---:|---|
| Q4 first real run (`evidence/q04_run/`) | normal | 1 | 4 | $0.000926 | yes |
| Q5 case runs (`evidence/q05_runs/`) | normal | 3 | 11 | $0.002390 | yes |
| Q6 end-user flow run (`evidence/q06_run/`) | normal | 1 | 4 | $0.001309 | yes |
| Q8-A the user's three searches (`evidence/q08a/`) | normal | 3 | 10 | $0.001724 | yes |
| G-12 fix re-check (`evidence/q08a/`) | normal | 1 | 4 | $0.001389 | yes |
| Q7 red team (incl. benign control) (`evidence/q07_redteam/`) | redteam_q7 | 3 | 9 | $0.002125 | no |
| Q8-D fresh-clone check (`evidence/q08_clone/`) | fresh clone | 1 | 4 | $0.001519 | no |

## Typical-run sample, per run

| run_id | group | calls | input | cached | cache write | output (reasoning) | cost | guard part | re-priced, all input uncached |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `r_b79bfbda45ad` | Q4 first real run | 4 | 8,457 | 4,829 | 3,237 | 868 (471) | $0.000926 | $0.000055 | $0.001280 |
| `r_8aad4fe5a302` | Q5 case runs | 4 | 10,314 | 5,733 | 4,184 | 631 (276) | $0.000936 | $0.000059 | $0.001347 |
| `r_c588d02ea0b5` | Q5 case runs | 4 | 10,821 | 8,331 | 2,102 | 1,380 (600) | $0.001075 | $0.000059 | $0.001772 |
| `r_835194ffb88a` | Q5 case runs | 3 | 5,889 | 4,857 | 643 | 424 (173) | $0.000380 | $0.000057 | $0.000801 |
| `r_ce638df7cf6e` | Q6 end-user flow run | 4 | 10,748 | 5,898 | 4,464 | 1,306 (620) | $0.001309 | $0.000055 | $0.001728 |
| `r_80b535e6cc97` | Q8-A the user's three searches | 3 | 5,966 | 2,481 | 3,107 | 499 (269) | $0.000700 | $0.000055 | $0.000846 |
| `r_b8cd2f215d47` | Q8-A the user's three searches | 3 | 5,963 | 4,898 | 689 | 479 (242) | $0.000412 | $0.000056 | $0.000836 |
| `r_117624a6bd8a` | Q8-A the user's three searches | 4 | 9,613 | 8,018 | 1,214 | 683 (409) | $0.000612 | $0.000056 | $0.001303 |
| `r_21eea8b51494` | G-12 fix re-check | 4 | 10,476 | 5,940 | 4,157 | 1,544 (1,092) | $0.001389 | $0.000056 | $0.001820 |

Per run (n=9): mean $0.000860, median $0.000926, min $0.000380, max $0.001389; 3.7 calls and 9,562 tokens on average (range 6,313 to 12,201); cache hit rate (cached / input tokens) 65.2%.

## Monthly scenarios (estimate from the typical-run mean; search frequency is assumed, not measured)

| runs per user per month (scenario) | 1 user | 100 users | 10,000 users |
|---:|---:|---:|---:|
| 4 | $0.003439 | $0.34 | $34.39 |
| 8 | $0.006878 | $0.69 | $68.78 |
| 30 | $0.025793 | $2.58 | $257.93 |

## Comparisons computed from the same rows (no extra runs)

- Prompt cache, re-pricing: recorded $0.007738; the same tokens with every input token at the uncached price $0.011732 (34.0% lower as recorded). The same real token counts priced twice: as recorded (cached input $0.01, cache write $0.125) and with every input token at the uncached $0.10. Not a separate run; quality without caching was not measured.
- LLM guard: its calls are 6.5% of the sample cost. Not adopted: in q07 the guard alone blocked the soft canary attack r_6dff5fbf9fb4; matcher answers without the guard were not re-run.

Checks (all 46 project rows): {"rows": 46, "all_live": true, "all_status_ok": true, "no_missing_usage": true, "served_models": ["gpt-6-luna-global"], "cost_recomputed_equals_ledger": true, "cached_plus_write_within_input": true, "reasoning_within_output": true, "unique_response_ids": true, "all_at_or_before_cutoff": true, "min_latency_ms": 1257}
Local ledger check: {"normal": {"path": "runs/usage.jsonl", "listed_rows_identical_to_copies": true, "live_rows": 33, "live_rows_not_counted": []}, "redteam_q7": {"path": "runs/redteam_q7/usage.jsonl", "listed_rows_identical_to_copies": true, "live_rows": 9, "live_rows_not_counted": []}}
