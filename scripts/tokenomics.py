"""Turn the usage ledger (real runs) into tokenomics evidence for the report.

Usage (from the repo root):
    python scripts/tokenomics.py                      # runs/usage.jsonl -> evidence/tokenomics.{json,md}
    python scripts/tokenomics.py --runs-per-user 50   # change the usage assumption
    python scripts/tokenomics.py --ledger runs/redteam_usage.jsonl --out-dir evidence/redteam

Outputs per-run averages (input, cached input, cache writes, output, reasoning tokens), cost per
run (mean/p50/p90/max), cache hit rate and savings, a per-agent breakdown, and monthly/yearly
projections for 1, 100 and 10,000 users. All assumptions are written into the outputs.
No model calls are made.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from app.config import MODEL, get_settings  # noqa: E402
from app.ledger import UsageLedger  # noqa: E402
from app.pricing import PRICES_PER_M  # noqa: E402

USAGE_FIELDS = ("input_tokens", "cached_tokens", "cache_write_tokens", "uncached_input_tokens", "output_tokens", "reasoning_tokens")
PROJECTION_USERS = (1, 100, 10_000)


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile; 0.0 when empty."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100.0
    low = math.floor(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def usd(x: float) -> str:
    if x == 0:
        return "$0"
    if x < 0.01:
        return f"${x:.6f}"
    if x < 1:
        return f"${x:.4f}"
    if x < 1000:
        return f"${x:,.2f}"
    return f"${x:,.0f}"


def num(x: float) -> str:
    return f"{x:,.0f}" if abs(x) >= 100 or float(x).is_integer() else f"{x:,.1f}"


def per_agent_breakdown(records: list[dict], n_runs: int) -> list[dict]:
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in records:
        agg = totals[r.get("agent") or "?"]
        agg["calls"] += 1
        agg["cost_usd"] += float(r.get("cost_usd") or 0)
        for field in USAGE_FIELDS:
            agg[field] += int(r.get(field) or 0)
    grand_cost = sum(a["cost_usd"] for a in totals.values()) or 1.0
    rows = []
    for agent, agg in sorted(totals.items(), key=lambda kv: -kv[1]["cost_usd"]):
        calls = agg["calls"]
        rows.append(
            {
                "agent": agent,
                "calls": int(calls),
                "calls_per_run": calls / n_runs if n_runs else 0.0,
                "avg_input_tokens_per_call": agg["input_tokens"] / calls,
                "avg_cached_tokens_per_call": agg["cached_tokens"] / calls,
                "avg_output_tokens_per_call": agg["output_tokens"] / calls,
                "cache_hit_rate": agg["cached_tokens"] / agg["input_tokens"] if agg["input_tokens"] else 0.0,
                "total_cost_usd": agg["cost_usd"],
                "cost_share": agg["cost_usd"] / grand_cost,
            }
        )
    return rows


def cache_effect(records: list[dict], prices: dict[str, float]) -> dict:
    """What the same traffic would have cost with every input token billed at the full input rate."""
    actual = sum(float(r.get("cost_usd") or 0) for r in records)
    no_cache = sum(
        (int(r.get("input_tokens") or 0) * prices["input"] + int(r.get("output_tokens") or 0) * prices["output"]) / 1e6
        for r in records
    )
    saved = no_cache - actual
    return {
        "actual_cost_usd": actual,
        "cost_without_cache_usd": no_cache,
        "saved_usd": saved,
        "saved_pct": saved / no_cache if no_cache else 0.0,
    }


def sensitivity(mean_cost: float, runs_per_user: int) -> list[dict]:
    rows = []
    for k in sorted({10, runs_per_user, 100}):
        rows.append({"runs_per_user_per_month": k, **{str(u): mean_cost * k * u for u in PROJECTION_USERS}})
    return rows


def assumptions_text(k: int, prices: dict[str, float]) -> list[str]:
    return [
        f"Model {MODEL} through Portkey. Prices per 1M tokens (Lecture 11): input ${prices['input']}, "
        f"cached input ${prices['cached_input']}, cache write ${prices['cache_write']}, output ${prices['output']}.",
        "Billing: uncached input = input - cached - cache_write, billed at the input rate; cached and cache-write "
        "tokens at their own rates; output tokens (reasoning included) at the output rate.",
        f"Each user runs {k} tasks per month (--runs-per-user, default RUNS_PER_USER_PER_MONTH). Yearly = 12 x monthly.",
        "Cost per run is the mean over the measured runs in the ledger, including the LLM guard call and every "
        "agent's model calls. Projections scale linearly: no volume discounts, no hosting or gateway fees.",
        "Runs blocked before any model call cost $0 and do not appear in the ledger.",
        "Cache hit rate depends on traffic: a busy app keeps the 30-minute prompt cache warm, a quiet one pays "
        "more cache writes.",
    ]


def build_report(ledger_path: Path, runs_per_user: int) -> dict:
    ledger = UsageLedger(ledger_path)
    records = ledger.records()
    stats = ledger.stats(runs_per_user)
    prices = PRICES_PER_M[MODEL]
    latencies = [float(r.get("latency_ms") or 0) for r in records]
    timestamps = sorted(r.get("ts", "") for r in records if r.get("ts"))
    try:
        source = ledger_path.resolve().relative_to(REPO_DIR).as_posix()
    except ValueError:
        source = str(ledger_path)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "model": MODEL,
        "period": {"first_call": timestamps[0] if timestamps else None, "last_call": timestamps[-1] if timestamps else None},
        "stats": stats,
        "calls_per_run": stats["calls"] / stats["runs"] if stats["runs"] else 0.0,
        "latency_ms": {
            "mean": sum(latencies) / len(latencies) if latencies else 0.0,
            "p50": percentile(latencies, 50),
            "p90": percentile(latencies, 90),
        },
        "per_agent": per_agent_breakdown(records, stats["runs"]),
        "cache": cache_effect(records, prices),
        "sensitivity_monthly_usd": sensitivity(stats["cost_per_run"]["mean"], runs_per_user),
        "runs": ledger.run_summaries(),
        "assumptions": assumptions_text(runs_per_user, prices),
    }


def to_markdown(report: dict) -> str:
    stats = report["stats"]
    avg = stats["avg_per_run"]
    cpr = stats["cost_per_run"]
    k = stats["assumptions"]["runs_per_user_per_month"]
    cache = report["cache"]
    lines = [
        f"# Tokenomics: {report['model']}",
        "",
        f"Generated {report['generated_at']} from `{report['source']}`: **{stats['runs']} runs**, "
        f"{stats['calls']} model calls ({report['calls_per_run']:.1f} per run), "
        f"{report['period']['first_call']} to {report['period']['last_call']}.",
        "",
        "## Average run",
        "",
        "| Metric | Per run |",
        "|---|---:|",
        f"| Input tokens | {num(avg.get('input_tokens', 0))} |",
        f"| - cached (read from cache) | {num(avg.get('cached_tokens', 0))} |",
        f"| - cache writes | {num(avg.get('cache_write_tokens', 0))} |",
        f"| - uncached | {num(avg.get('uncached_input_tokens', 0))} |",
        f"| Output tokens (incl. reasoning) | {num(avg.get('output_tokens', 0))} |",
        f"| - reasoning | {num(avg.get('reasoning_tokens', 0))} |",
        f"| Model calls | {report['calls_per_run']:.1f} |",
        f"| **Cost** | **{usd(avg.get('cost_usd', 0))}** |",
        "",
        f"Cost per run: mean {usd(cpr['mean'])}, p50 {usd(cpr['p50'])}, p90 {usd(cpr['p90'])}, max {usd(cpr['max'])}. "
        f"Latency per model call: mean {report['latency_ms']['mean']:,.0f} ms, p90 {report['latency_ms']['p90']:,.0f} ms.",
        "",
        f"**Cache hit rate:** {stats['cache_hit_rate']:.1%} of input tokens were served from the prompt cache. "
        f"Without caching the same traffic would have cost {usd(cache['cost_without_cache_usd'])} instead of "
        f"{usd(cache['actual_cost_usd'])} ({cache['saved_pct']:.1%} saved).",
        "",
        "## Per agent",
        "",
        "| Agent | Calls | Calls/run | Avg input | Avg cached | Avg output | Cache hit | Cost | Share |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for a in report["per_agent"]:
        lines.append(
            f"| {a['agent']} | {a['calls']} | {a['calls_per_run']:.2f} | {num(a['avg_input_tokens_per_call'])} | "
            f"{num(a['avg_cached_tokens_per_call'])} | {num(a['avg_output_tokens_per_call'])} | "
            f"{a['cache_hit_rate']:.1%} | {usd(a['total_cost_usd'])} | {a['cost_share']:.1%} |"
        )
    lines += [
        "",
        "## Projections",
        "",
        f"Per user per month ({k} runs): **{usd(stats['per_user_month_usd'])}**.",
        "",
        "| Users | Runs / month | Monthly | Yearly |",
        "|---:|---:|---:|---:|",
    ]
    for p in stats["projections"]:
        lines.append(f"| {p['users']:,} | {p['users'] * k:,} | {usd(p['monthly_usd'])} | {usd(p['yearly_usd'])} |")
    lines += [
        "",
        "Sensitivity (monthly cost by runs per user):",
        "",
        "| Runs / user / month | 1 user | 100 users | 10,000 users |",
        "|---:|---:|---:|---:|",
    ]
    for row in report["sensitivity_monthly_usd"]:
        lines.append(
            f"| {row['runs_per_user_per_month']} | {usd(row['1'])} | {usd(row['100'])} | {usd(row['10000'])} |"
        )
    lines += ["", "## Assumptions", ""]
    lines += [f"- {a}" for a in report["assumptions"]]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Ledger -> evidence/tokenomics.{json,md}")
    parser.add_argument(
        "--runs-per-user",
        type=int,
        default=settings.runs_per_user_per_month,
        help=f"runs per user per month (default {settings.runs_per_user_per_month})",
    )
    parser.add_argument("--ledger", default=str(settings.runs_dir / "usage.jsonl"), help="usage ledger (JSONL)")
    parser.add_argument("--out-dir", default=str(REPO_DIR / "evidence"), help="where to write tokenomics.{json,md}")
    args = parser.parse_args(argv)
    if args.runs_per_user < 1:
        parser.error("--runs-per-user must be at least 1")

    ledger_path = Path(args.ledger).resolve()
    report = build_report(ledger_path, args.runs_per_user)
    if report["stats"]["runs"] == 0:
        print(f"No model calls in {ledger_path} yet. Run a few tasks in the app first (python run.py).")
        print("Nothing written, so existing evidence is not overwritten.")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / "tokenomics.json", out_dir / "tokenomics.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown = to_markdown(report)
    md_path.write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"Wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
