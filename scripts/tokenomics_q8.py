"""Problem 8 tokenomics: one cost summary from the committed per-run ledger copies (no model calls, no network).

    python scripts/tokenomics_q8.py   # writes evidence/q08_tokenomics.json and evidence/q08_tokenomics.md

Every live model call this project made up to CUTOFF has a committed copy in evidence/ (13 runs, 46 rows), so the
result is the same on a fresh clone, where runs/ (git-ignored) is empty. Three figures, never mixed:

  (i)   Typical-run sample: every run of the normal app flow in the normal ledger runs/usage.jsonl (Q4-Q6 requests,
        the user's three 8-A searches, the G-12 re-check). Per-run cost and the monthly scenarios come from it. It is
        exactly what the app's Usage tab shows on the development machine once legacy rows are excluded.
  (ii)  Development + safety-testing total: every live row of this project = (i) + Q7 red team + Q8 fresh clone.
  (iii) Historical placeholder records (Harbor Bikes, written before the Q4 metering gate, no "mode" field):
        only counted, from the local runs/ ledgers when present; excluded from (i) and (ii).

If the local ledgers contain live rows that are not listed below (a newer run), the script reports them and does NOT
fold them in: moving the cut-off is a deliberate edit of CUTOFF and GROUPS.
Every row's cost is recomputed from its tokens with the course prices and must equal the ledger.
The prompt-cache figure is a RE-PRICING of the same real tokens, not a separate experiment.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pricing import PRICES_PER_M  # noqa: E402

P = PRICES_PER_M["gpt-6-luna"]
PRICE_SOURCE = ("Lecture 11 slides, https://zlisto.github.io/mgt_409_fa26/lectures/slides/lec11-slides.html, "
                "re-read 2026-10-26: input $0.10, cached $0.01, cache write $0.125, output $0.50 per 1M tokens; "
                "input_tokens = 'total tokens you sent in'; reasoning tokens 'count toward output'.")
RUNS_PER_USER_PER_MONTH = (4, 8, 30)  # scenarios, not measurements (30 = the app's RUNS_PER_USER_PER_MONTH default)
USERS = (1, 100, 10_000)
CUTOFF = "2026-10-25T21:23:30Z"  # last live model call included (r_21eea8b51494, step 3)

# (label, ledger it was written to, evidence folder with the committed copy, run ids, part of the typical sample?)
GROUPS = (
    ("Q4 first real run", "normal", "q04_run", ("r_b79bfbda45ad",), True),
    ("Q5 case runs", "normal", "q05_runs", ("r_8aad4fe5a302", "r_c588d02ea0b5", "r_835194ffb88a"), True),
    ("Q6 end-user flow run", "normal", "q06_run", ("r_ce638df7cf6e",), True),
    ("Q8-A the user's three searches", "normal", "q08a", ("r_80b535e6cc97", "r_b8cd2f215d47", "r_117624a6bd8a"), True),
    ("G-12 fix re-check", "normal", "q08a", ("r_21eea8b51494",), True),
    ("Q7 red team (incl. benign control)", "redteam_q7", "q07_redteam",
     ("r_0c89b3881d73", "r_6dff5fbf9fb4", "r_7c9a61b04778"), False),
    ("Q8-D fresh-clone check", "fresh clone", "q08_clone", ("r_af384cbce5e9",), False),
)
LOCAL_LEDGERS = {"normal": REPO / "runs" / "usage.jsonl", "redteam_q7": REPO / "runs" / "redteam_q7" / "usage.jsonl"}
# Also read if someone archives the Harbor rows there; nothing was moved: they stay in runs/*.jsonl and
# app/ledger.py skips them (rows without a "mode" field).
LEGACY_ARCHIVE = REPO / "runs" / "archive" / "harbor_2026-10-24"
LEGACY_LEDGERS = (REPO / "runs" / "usage.jsonl", REPO / "runs" / "redteam_usage.jsonl",
                  LEGACY_ARCHIVE / "usage.jsonl", LEGACY_ARCHIVE / "redteam_usage.jsonl")
LEGACY_RECORDED = "95 + 38 rows (evidence/q01.md section 3.5)"


def load(path: Path) -> list[dict]:
    """Ledger rows; a half-written or corrupt line (e.g. a write cut off by a crash) is skipped, as app/ledger.py does."""
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def recompute(r: dict) -> float:
    uncached = r["input_tokens"] - r["cached_tokens"] - r["cache_write_tokens"]
    return (uncached * P["input"] + r["cached_tokens"] * P["cached_input"] + r["cache_write_tokens"] * P["cache_write"]
            + r["output_tokens"] * P["output"]) / 1e6


def repriced_without_cache(r: dict) -> float:
    """Same real tokens, every input token at the uncached input price (the counterfactual 'no prompt cache')."""
    return (r["input_tokens"] * P["input"] + r["output_tokens"] * P["output"]) / 1e6


def checks(rows: list[dict]) -> dict:
    return {
        "rows": len(rows),
        "all_live": all(r.get("mode") == "live" for r in rows),
        "all_status_ok": all(r["status"] == "ok" for r in rows),
        "no_missing_usage": all(not r["usage_missing"] for r in rows),
        "served_models": sorted({r["served_model"] for r in rows}),
        "cost_recomputed_equals_ledger": all(abs(recompute(r) - r["cost_usd"]) < 1e-12 for r in rows),
        "cached_plus_write_within_input": all(r["cached_tokens"] + r["cache_write_tokens"] <= r["input_tokens"] for r in rows),
        "reasoning_within_output": all(r["reasoning_tokens"] <= r["output_tokens"] for r in rows),
        "unique_response_ids": len({r["response_id"] for r in rows}) == len(rows),
        "all_at_or_before_cutoff": all(r["ts"] <= CUTOFF for r in rows),
        "min_latency_ms": min(r["latency_ms"] for r in rows) if rows else None,
    }


def totals(rows: list[dict]) -> dict:
    # math.fsum, not sum(): sum() of floats rounds differently from Python 3.12 on; fsum gives the correctly rounded
    # total on every version (Python 3.11 is the minimum).
    return {"runs": len({r["run_id"] for r in rows}), "calls": len(rows),
            "input": sum(r["input_tokens"] for r in rows), "cached": sum(r["cached_tokens"] for r in rows),
            "cache_write": sum(r["cache_write_tokens"] for r in rows), "output": sum(r["output_tokens"] for r in rows),
            "reasoning": sum(r["reasoning_tokens"] for r in rows), "cost_usd": math.fsum(r["cost_usd"] for r in rows)}


def by_run(rows: list[dict]) -> list[dict]:
    # Left-to-right += (not sum()): plain float addition gives the same digits on every Python version. fsum would
    # change the last digit of three per-run figures in the committed evidence, so it is not used here.
    runs: dict[str, dict] = {}
    for r in rows:
        g = runs.setdefault(r["run_id"], {"run_id": r["run_id"], "group": r["_group"], "started": r["ts"], "calls": 0,
                                          "input": 0, "cached": 0, "cache_write": 0, "output": 0, "reasoning": 0,
                                          "cost_usd": 0.0, "guard_cost_usd": 0.0, "repriced_without_cache_usd": 0.0})
        g["started"] = min(g["started"], r["ts"])
        g["calls"] += 1
        for k, f in (("input", "input_tokens"), ("cached", "cached_tokens"), ("cache_write", "cache_write_tokens"),
                     ("output", "output_tokens"), ("reasoning", "reasoning_tokens")):
            g[k] += r[f]
        g["cost_usd"] += r["cost_usd"]
        g["repriced_without_cache_usd"] += repriced_without_cache(r)
        if r["agent"] == "guard":
            g["guard_cost_usd"] += r["cost_usd"]
    return sorted(runs.values(), key=lambda g: g["started"])


def collect() -> tuple[list[dict], list[dict]]:
    """All listed rows (from the committed copies) and one entry per group."""
    rows: list[dict] = []
    groups: list[dict] = []
    for label, ledger, folder, run_ids, typical in GROUPS:
        group_rows: list[dict] = []
        for run_id in run_ids:
            copy = REPO / "evidence" / folder / f"{run_id}.usage.jsonl"
            found = [r for r in load(copy) if r.get("run_id") == run_id]
            if not found:
                raise SystemExit(f"missing committed ledger copy for {run_id}: {copy}")
            group_rows += [{**r, "_group": label, "_ledger": ledger, "_typical": typical} for r in found]
        rows += group_rows
        groups.append({"group": label, "ledger": ledger, "evidence": f"evidence/{folder}/", "typical_sample": typical,
                       "run_ids": list(run_ids), **totals(group_rows)})
    return rows, groups


def local_ledger_check(rows: list[dict]) -> dict:
    """Compare the git-ignored local ledgers (if present) with the committed copies; report anything not counted."""
    out: dict = {}
    for ledger, path in LOCAL_LEDGERS.items():
        local = load(path)
        if not local:
            out[ledger] = "not present in this checkout (runs/ is git-ignored)"
            continue
        listed = {r["run_id"] for r in rows if r["_ledger"] == ledger}
        strip = lambda r: {k: v for k, v in r.items() if not k.startswith("_")}  # noqa: E731
        same = [strip(r) for r in rows if r["_ledger"] == ledger] == [r for r in local if r.get("run_id") in listed]
        live = [r for r in local if r.get("mode") == "live"]
        extra = sorted({r["run_id"] for r in live if r["run_id"] not in listed or r["ts"] > CUTOFF})
        out[ledger] = {"path": path.relative_to(REPO).as_posix(), "listed_rows_identical_to_copies": same,
                       "live_rows": len(live), "live_rows_not_counted": extra}
    return out


def legacy_history() -> dict | None:
    rows = [r for path in LEGACY_LEDGERS for r in load(path) if "mode" not in r]
    if not rows:
        return None
    return {**totals(rows), "per_ledger_rows": {p.relative_to(REPO).as_posix(): sum(1 for r in load(p) if "mode" not in r)
                                                for p in LEGACY_LEDGERS},
            "note": "Harbor Bikes placeholder domain, written before the Q4 metering gate (no mode / served_model / "
                    "status fields; 2 known gateway cache replays). Not this project: excluded from (i) and (ii)."}


def build() -> dict:
    rows, groups = collect()
    typical_rows = [r for r in rows if r["_typical"]]
    runs = by_run(typical_rows)
    costs = [g["cost_usd"] for g in runs]
    tokens = [g["input"] + g["output"] for g in runs]
    mean = statistics.mean(costs)
    t = totals(typical_rows)
    repriced = math.fsum(g["repriced_without_cache_usd"] for g in runs)
    guard = math.fsum(g["guard_cost_usd"] for g in runs)
    typical_label = " + ".join(g["group"] for g in groups if g["typical_sample"])
    return {
        "price_source": PRICE_SOURCE,
        "cutoff_utc": CUTOFF,
        "source": "committed copies evidence/*/<run_id>.usage.jsonl (identical to the ledger rows); no model calls",
        "cost_summary": {
            "i_typical_run_sample": {
                "definition": f"every run of the normal app flow in runs/usage.jsonl: {typical_label}",
                **t,
                "per_run": {"mean_usd": mean, "median_usd": statistics.median(costs), "min_usd": min(costs),
                            "max_usd": max(costs), "mean_calls": statistics.mean(g["calls"] for g in runs),
                            "mean_tokens": statistics.mean(tokens), "min_tokens": min(tokens), "max_tokens": max(tokens)},
                "cache_hit_rate": t["cached"] / t["input"],
            },
            "ii_development_and_safety_testing_total": {
                "definition": "every live model call of this project: (i) + Q7 red team (separate ledger) + Q8 fresh clone (clone's own ledger)", **totals(rows)},
            "iii_historical_placeholder_records": legacy_history() or {"note": f"not present in this checkout (runs/ is git-ignored); recorded: {LEGACY_RECORDED}"},
        },
        "groups": groups,
        "checks_all_project_rows": checks([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]),
        "local_ledger_check": local_ledger_check(rows),
        "typical_runs": runs,
        "comparisons_computed_from_the_same_rows": {
            "prompt_cache_repricing": {
                "recorded_usd": t["cost_usd"], "repriced_all_input_uncached_usd": repriced,
                "difference_pct": (repriced - t["cost_usd"]) / repriced,
                "what_it_is": ("The same real token counts priced twice: as recorded (cached input $0.01, cache write $0.125) "
                               "and with every input token at the uncached $0.10. Not a separate run; quality without "
                               "caching was not measured."),
            },
            "drop_llm_guard": {
                "recorded_usd": t["cost_usd"], "without_guard_calls_usd": t["cost_usd"] - guard, "difference_pct": guard / t["cost_usd"],
                "decision": ("Not adopted: in q07 the guard alone blocked the soft canary attack r_6dff5fbf9fb4; "
                             "matcher answers without the guard were not re-run"),
            },
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
    }


def markdown(d: dict) -> str:
    u = lambda x: f"${x:.6f}"  # noqa: E731
    cs = d["cost_summary"]
    ti, tii, tiii = cs["i_typical_run_sample"], cs["ii_development_and_safety_testing_total"], cs["iii_historical_placeholder_records"]
    pr = ti["per_run"]
    tok = lambda x: f"{x['input']:,} / {x['cached']:,} / {x['cache_write']:,} | {x['output']:,} ({x['reasoning']:,})"  # noqa: E731
    if "calls" in tiii:
        iii_row = (f"| (iii) Historical placeholder records | Harbor Bikes placeholder domain, written before the Q4 metering gate "
                   f"(no `mode` field) | {tiii['runs']} | {tiii['calls']} | {tok(tiii)} | excluded, not this project |")
    else:
        iii_row = f"| (iii) Historical placeholder records | Harbor Bikes placeholder domain | - | - | - | - | excluded; {tiii['note']} |"
    lines = [
        "# Tokenomics (problem 8): one cost summary", "",
        f"Prices: {d['price_source']}", "",
        f"Ledger cut-off: **{d['cutoff_utc']}** (last live model call included). Source: {d['source']}.", "",
        "## Cost summary", "",
        "| Category | Contains | Runs | Model calls | Input / cached / cache-write tokens | Output (reasoning) | Cost |",
        "|---|---|---:|---:|---|---|---:|",
        f"| (i) Typical-run sample | {ti['definition']} | {ti['runs']} | {ti['calls']} | {tok(ti)} | {u(ti['cost_usd'])} total; "
        f"{u(pr['mean_usd'])} per run (range {u(pr['min_usd'])} to {u(pr['max_usd'])}) |",
        f"| (ii) Development + safety-testing total | {tii['definition']} | {tii['runs']} | {tii['calls']} | {tok(tii)} | {u(tii['cost_usd'])} |",
        iii_row, "",
        "(i) is part of (ii). (iii) is listed only so older screenshots that mixed it in can be reconciled; no figure uses it.", "",
        "## Where the calls came from", "",
        "| Workload group | Ledger | Runs | Calls | Cost | In (i)? |", "|---|---|---:|---:|---:|---|",
    ]
    for g in d["groups"]:
        lines.append(f"| {g['group']} (`{g['evidence']}`) | {g['ledger']} | {g['runs']} | {g['calls']} | {u(g['cost_usd'])} | "
                     f"{'yes' if g['typical_sample'] else 'no'} |")
    lines += ["", "## Typical-run sample, per run", "",
              "| run_id | group | calls | input | cached | cache write | output (reasoning) | cost | guard part | re-priced, all input uncached |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for g in d["typical_runs"]:
        lines.append(f"| `{g['run_id']}` | {g['group']} | {g['calls']} | {g['input']:,} | {g['cached']:,} | {g['cache_write']:,} | "
                     f"{g['output']:,} ({g['reasoning']:,}) | {u(g['cost_usd'])} | {u(g['guard_cost_usd'])} | {u(g['repriced_without_cache_usd'])} |")
    lines += ["", f"Per run (n={ti['runs']}): mean {u(pr['mean_usd'])}, median {u(pr['median_usd'])}, min {u(pr['min_usd'])}, "
              f"max {u(pr['max_usd'])}; {pr['mean_calls']:.1f} calls and {pr['mean_tokens']:,.0f} tokens on average "
              f"(range {pr['min_tokens']:,} to {pr['max_tokens']:,}); cache hit rate (cached / input tokens) {ti['cache_hit_rate']:.1%}.", "",
              "## Monthly scenarios (estimate from the typical-run mean; search frequency is assumed, not measured)", "",
              "| runs per user per month (scenario) | 1 user | 100 users | 10,000 users |", "|---:|---:|---:|---:|"]
    for s in d["scaling_scenarios"]:
        lines.append(f"| {s['runs_per_user_per_month']} | {u(s['1_users_per_month_usd'])} | ${s['100_users_per_month_usd']:.2f} | "
                     f"${s['10000_users_per_month_usd']:.2f} |")
    c = d["comparisons_computed_from_the_same_rows"]
    lines += ["", "## Comparisons computed from the same rows (no extra runs)", "",
              f"- Prompt cache, re-pricing: recorded {u(c['prompt_cache_repricing']['recorded_usd'])}; the same tokens with every input "
              f"token at the uncached price {u(c['prompt_cache_repricing']['repriced_all_input_uncached_usd'])} "
              f"({c['prompt_cache_repricing']['difference_pct']:.1%} lower as recorded). {c['prompt_cache_repricing']['what_it_is']}",
              f"- LLM guard: its calls are {c['drop_llm_guard']['difference_pct']:.1%} of the sample cost. {c['drop_llm_guard']['decision']}.",
              "", f"Checks (all {d['checks_all_project_rows']['rows']} project rows): {json.dumps(d['checks_all_project_rows'])}",
              f"Local ledger check: {json.dumps(d['local_ledger_check'])}"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    data = build()
    (REPO / "evidence" / "q08_tokenomics.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (REPO / "evidence" / "q08_tokenomics.md").write_text(markdown(data), encoding="utf-8")
    print(markdown(data))
    pending = [x for v in data["local_ledger_check"].values() if isinstance(v, dict) for x in v["live_rows_not_counted"]]
    if pending:
        print(f"NOTE: live runs after the cut-off or not listed, not counted: {pending}", file=sys.stderr)
