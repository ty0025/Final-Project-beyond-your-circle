"""Problem 8 tokenomics from the REAL ledgers only (no model calls, no network).

    python scripts/tokenomics_q8.py   # writes evidence/q08_tokenomics.json and evidence/q08_tokenomics.md

- Normal use: runs/usage.jsonl rows with mode == "live". Rows without a mode field are the old Harbor Bikes
  placeholder history (before the metering fixes) and are excluded and only counted.
- Safety tests: runs/redteam_q7/usage.jsonl (kept separate, shown in the totals).
- Every row's cost is recomputed from its tokens with the course prices and must equal the ledger.
- The optimisation comparisons are COMPUTED from the same real rows (not separate A/B runs).
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pricing import PRICES_PER_M  # noqa: E402

P = PRICES_PER_M["gpt-6-luna"]
PRICE_SOURCE = ("Lecture 11 slides, https://zlisto.github.io/mgt_409_fa26/lectures/slides/lec11-slides.html, "
                "re-read 2026-10-26: input $0.10, cached $0.01, cache write $0.125, output $0.50 per 1M tokens; "
                "input_tokens = 'total tokens you sent in'; reasoning tokens 'count toward output'.")
RUNS_PER_USER_PER_MONTH = (4, 8, 30)  # scenarios, not measurements
USERS = (1, 100, 10_000)


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def recompute(r: dict) -> float:
    uncached = r["input_tokens"] - r["cached_tokens"] - r["cache_write_tokens"]
    return (uncached * P["input"] + r["cached_tokens"] * P["cached_input"] + r["cache_write_tokens"] * P["cache_write"]
            + r["output_tokens"] * P["output"]) / 1e6


def no_cache_cost(r: dict) -> float:
    return (r["input_tokens"] * P["input"] + r["output_tokens"] * P["output"]) / 1e6


def checks(rows: list[dict]) -> dict:
    return {
        "rows": len(rows),
        "all_status_ok": all(r["status"] == "ok" for r in rows),
        "no_missing_usage": all(not r["usage_missing"] for r in rows),
        "served_models": sorted({r["served_model"] for r in rows}),
        "cost_recomputed_equals_ledger": all(abs(recompute(r) - r["cost_usd"]) < 1e-12 for r in rows),
        "cached_plus_write_within_input": all(r["cached_tokens"] + r["cache_write_tokens"] <= r["input_tokens"] for r in rows),
        "reasoning_within_output": all(r["reasoning_tokens"] <= r["output_tokens"] for r in rows),
        "unique_response_ids": len({r["response_id"] for r in rows}) == len(rows),
        "min_latency_ms": min(r["latency_ms"] for r in rows) if rows else None,
    }


def by_run(rows: list[dict]) -> list[dict]:
    runs: dict[str, dict] = {}
    for r in rows:
        g = runs.setdefault(r["run_id"], {"run_id": r["run_id"], "started": r["ts"], "calls": 0, "input": 0, "cached": 0,
                                          "cache_write": 0, "output": 0, "reasoning": 0, "cost_usd": 0.0,
                                          "guard_cost_usd": 0.0, "no_cache_cost_usd": 0.0})
        g["calls"] += 1
        for k, f in (("input", "input_tokens"), ("cached", "cached_tokens"), ("cache_write", "cache_write_tokens"),
                     ("output", "output_tokens"), ("reasoning", "reasoning_tokens")):
            g[k] += r[f]
        g["cost_usd"] += r["cost_usd"]
        g["no_cache_cost_usd"] += no_cache_cost(r)
        if r["agent"] == "guard":
            g["guard_cost_usd"] += r["cost_usd"]
    return sorted(runs.values(), key=lambda g: g["started"])


def build() -> dict:
    main = load(REPO / "runs" / "usage.jsonl")
    live = [r for r in main if r.get("mode") == "live"]
    history = [r for r in main if "mode" not in r]
    red = [r for r in load(REPO / "runs" / "redteam_q7" / "usage.jsonl") if r.get("mode") == "live"]
    runs = by_run(live)
    costs = [g["cost_usd"] for g in runs]
    mean = statistics.mean(costs)
    actual = sum(costs)
    no_cache = sum(g["no_cache_cost_usd"] for g in runs)
    guard = sum(g["guard_cost_usd"] for g in runs)
    agents: dict[str, list[float]] = defaultdict(list)
    for r in live:
        agents[r["agent"]].append(r["cost_usd"])
    return {
        "price_source": PRICE_SOURCE,
        "sample": f"{len(runs)} normal real runs (problems 4-6), {len(live)} model calls; small sample, not a traffic study",
        "checks_normal": checks(live),
        "checks_redteam": checks(red),
        "runs": runs,
        "per_run": {"mean_usd": mean, "median_usd": statistics.median(costs), "min_usd": min(costs), "max_usd": max(costs),
                    "mean_calls": statistics.mean(g["calls"] for g in runs),
                    "mean_tokens": statistics.mean(g["input"] + g["output"] for g in runs),
                    "cache_hit_rate": sum(g["cached"] for g in runs) / sum(g["input"] for g in runs)},
        "per_agent_mean_cost_per_call_usd": {a: statistics.mean(v) for a, v in agents.items()},
        "optimisations_computed_from_same_rows": {
            "prompt_cache": {"actual_usd": actual, "if_no_prompt_cache_usd": no_cache, "saving_pct": (no_cache - actual) / no_cache,
                             "quality": "same rows; caching does not change the tokens the model sees"},
            "drop_llm_guard": {"actual_usd": actual, "without_guard_usd": actual - guard, "saving_pct": guard / actual,
                               "quality": ("matcher input is identical for unflagged requests, so picks would not change; "
                                           "but the guard alone blocked the q07 soft canary attack r_6dff5fbf9fb4 -> not adopted")},
        },
        "scaling_scenarios": [
            {"runs_per_user_per_month": k, **{f"{u}_users_per_month_usd": mean * k * u for u in USERS}}
            for k in RUNS_PER_USER_PER_MONTH
        ],
        "shared_costs": {
            "source_refresh": "collector makes 0 model calls (deterministic parsing): $0 model cost per refresh, shared by all users",
            "verification": "code only, $0",
            "retries_failed_attempts": "0 in these runs; failed attempts are ledgered with cost unknown (null)",
            "not_included": "hosting, bandwidth, Portkey plan fees, developer time, real browser/user time",
        },
        "totals": {
            "normal_live": {"rows": len(live), "cost_usd": actual},
            "redteam_q7": {"rows": len(red), "cost_usd": sum(r["cost_usd"] for r in red)},
            "project_real_calls_total_usd": actual + sum(r["cost_usd"] for r in red),
            "harbor_history_excluded": {"rows": len(history), "note": "placeholder domain before the metering fixes; not used"},
        },
    }


def markdown(d: dict) -> str:
    u = lambda x: f"${x:.6f}"  # noqa: E731
    lines = ["# Tokenomics (problem 8): real ledgers only", "", f"Prices: {d['price_source']}", "", f"Sample: {d['sample']}.", "",
             "| run_id | calls | input | cached | cache write | output (reasoning) | cost | guard part | cost if no prompt cache |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for g in d["runs"]:
        lines.append(f"| `{g['run_id']}` | {g['calls']} | {g['input']:,} | {g['cached']:,} | {g['cache_write']:,} | "
                     f"{g['output']:,} ({g['reasoning']:,}) | {u(g['cost_usd'])} | {u(g['guard_cost_usd'])} | {u(g['no_cache_cost_usd'])} |")
    pr = d["per_run"]
    lines += ["", f"Per run: mean {u(pr['mean_usd'])}, median {u(pr['median_usd'])}, min {u(pr['min_usd'])}, max {u(pr['max_usd'])}; "
              f"{pr['mean_calls']:.1f} calls and {pr['mean_tokens']:,.0f} tokens on average; cache hit rate {pr['cache_hit_rate']:.1%}.", "",
              "| runs per user per month (scenario) | 1 user | 100 users | 10,000 users |", "|---:|---:|---:|---:|"]
    for s in d["scaling_scenarios"]:
        lines.append(f"| {s['runs_per_user_per_month']} | {u(s['1_users_per_month_usd'])} | ${s['100_users_per_month_usd']:.2f} | ${s['10000_users_per_month_usd']:.2f} |")
    o = d["optimisations_computed_from_same_rows"]
    lines += ["", "Optimisations, computed from the same real rows (not separate A/B runs):",
              f"- Prompt cache: actual {u(o['prompt_cache']['actual_usd'])} vs {u(o['prompt_cache']['if_no_prompt_cache_usd'])} without it "
              f"({o['prompt_cache']['saving_pct']:.1%} saved).",
              f"- Dropping the LLM guard would save {o['drop_llm_guard']['saving_pct']:.1%}; not adopted: {o['drop_llm_guard']['quality']}.",
              "", f"Totals: normal {u(d['totals']['normal_live']['cost_usd'])} ({d['totals']['normal_live']['rows']} rows); red-team "
              f"{u(d['totals']['redteam_q7']['cost_usd'])} ({d['totals']['redteam_q7']['rows']} rows); all project real calls "
              f"{u(d['totals']['project_real_calls_total_usd'])}. Excluded Harbor history rows: {d['totals']['harbor_history_excluded']['rows']}.",
              "", f"Checks (normal): {json.dumps(d['checks_normal'])}", f"Checks (red-team): {json.dumps(d['checks_redteam'])}"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    data = build()
    (REPO / "evidence" / "q08_tokenomics.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (REPO / "evidence" / "q08_tokenomics.md").write_text(markdown(data), encoding="utf-8")
    print(markdown(data))
