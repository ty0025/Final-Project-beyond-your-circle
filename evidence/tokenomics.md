# Tokenomics: gpt-6-luna

Generated 2026-10-24T21:53:18Z from `runs/usage.jsonl`: **8 runs**, 84 model calls (10.5 per run), 2026-10-24T21:33:17Z to 2026-10-24T21:51:47Z.

## Average run

| Metric | Per run |
|---|---:|
| Input tokens | 21,549 |
| - cached (read from cache) | 14,675 |
| - cache writes | 6,462 |
| - uncached | 412 |
| Output tokens (incl. reasoning) | 3,208 |
| - reasoning | 1,389 |
| Model calls | 10.5 |
| **Cost** | **$0.002600** |

Cost per run: mean $0.002600, p50 $0.002361, p90 $0.003274, max $0.003409. Latency per model call: mean 3,222 ms, p90 6,981 ms.

**Cache hit rate:** 68.1% of input tokens were served from the prompt cache. Without caching the same traffic would have cost $0.0301 instead of $0.0208 (30.8% saved).

## Per agent

| Agent | Calls | Calls/run | Avg input | Avg cached | Avg output | Cache hit | Cost | Share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| researcher | 36 | 4.50 | 2,478 | 1,945 | 249 | 78.5% | $0.007572 | 36.4% |
| coordinator | 24 | 3.00 | 2,133 | 1,419 | 350 | 66.5% | $0.006674 | 32.1% |
| verifier | 16 | 2.00 | 1,808 | 831 | 496 | 46.0% | $0.006052 | 29.1% |
| guard | 8 | 1.00 | 384 | 0 | 48.6 | 0.0% | $0.000502 | 2.4% |

## Projections

Per user per month (30 runs): **$0.0780**.

| Users | Runs / month | Monthly | Yearly |
|---:|---:|---:|---:|
| 1 | 30 | $0.0780 | $0.9360 |
| 100 | 3,000 | $7.80 | $93.60 |
| 10,000 | 300,000 | $779.96 | $9,360 |

Sensitivity (monthly cost by runs per user):

| Runs / user / month | 1 user | 100 users | 10,000 users |
|---:|---:|---:|---:|
| 10 | $0.0260 | $2.60 | $259.99 |
| 30 | $0.0780 | $7.80 | $779.96 |
| 100 | $0.2600 | $26.00 | $2,600 |

## Assumptions

- Model gpt-6-luna through Portkey. Prices per 1M tokens (Lecture 11): input $0.1, cached input $0.01, cache write $0.125, output $0.5.
- Billing: uncached input = input - cached - cache_write, billed at the input rate; cached and cache-write tokens at their own rates; output tokens (reasoning included) at the output rate.
- Each user runs 30 tasks per month (--runs-per-user, default RUNS_PER_USER_PER_MONTH). Yearly = 12 x monthly.
- Cost per run is the mean over the measured runs in the ledger, including the LLM guard call and every agent's model calls. Projections scale linearly: no volume discounts, no hosting or gateway fees.
- Runs blocked before any model call cost $0 and do not appear in the ledger.
- Cache hit rate depends on traffic: a busy app keeps the 30-minute prompt cache warm, a quiet one pays more cache writes.
