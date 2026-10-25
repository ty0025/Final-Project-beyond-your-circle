from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.budget import BudgetExceeded, RunBudget
from app.config import MODEL
from app.ledger import ModelCall, UsageLedger
from app.pricing import PRICES_PER_M, Usage, cost_usd

RECORD_KEYS = {
    "ts",
    "run_id",
    "agent",
    "step",
    "model",
    "response_id",
    "latency_ms",
    "input_tokens",
    "cached_tokens",
    "cache_write_tokens",
    "uncached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "cost_usd",
    # metering gate (problem 4): every attempt, served model, live/mock, unmeasured fields
    "attempt",
    "status",
    "error_kind",
    "mode",
    "served_model",
    "model_mismatch",
    "n_function_calls",
    "finish",
    "usage_missing",
}

APPROX = {"rel": 1e-2, "abs": 1e-9}  # tolerant of rounding in reported stats


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_call(
    run_id: str = "r_aaaaaaaaaaaa",
    *,
    agent: str = "researcher",
    step: int = 1,
    usage: Usage | None = None,
    cost: float | None = None,
    ts: str | None = None,
) -> ModelCall:
    usage = usage or Usage(input_tokens=1000, cached_tokens=600, cache_write_tokens=100, output_tokens=200, reasoning_tokens=50)
    kwargs = dict(
        run_id=run_id,
        agent=agent,
        step=step,
        response_id=f"resp_{run_id}_{step}",
        latency_ms=1200,
        usage=usage,
        cost_usd=cost_usd(usage) if cost is None else cost,
    )
    if ts is not None:
        kwargs["ts"] = ts
    return ModelCall(**kwargs)


# --------------------------------------------------------------------------- ModelCall


def test_model_call_record_shape():
    call = make_call()
    record = call.to_record()
    assert set(record) == RECORD_KEYS
    assert record["model"] == MODEL
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["ts"])
    assert record["input_tokens"] == 1000
    assert record["cached_tokens"] == 600
    assert record["cache_write_tokens"] == 100
    assert record["uncached_input_tokens"] == 300
    assert record["output_tokens"] == 200
    assert record["reasoning_tokens"] == 50
    assert record["total_tokens"] == 1200
    assert record["cost_usd"] == pytest.approx(call.cost_usd)
    json.dumps(record)  # must be JSON-serialisable


# --------------------------------------------------------------------------- UsageLedger


def test_append_and_reload(tmp_path: Path):
    path = tmp_path / "nested" / "usage.jsonl"
    ledger = UsageLedger(path)
    assert path.parent.is_dir()
    ledger.append(make_call("r_aaaaaaaaaaaa", step=1))
    ledger.append(make_call("r_aaaaaaaaaaaa", step=2))
    ledger.append(make_call("r_bbbbbbbbbbbb", agent="coordinator"))

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 3
    assert all(set(json.loads(line)) == RECORD_KEYS for line in lines)

    reloaded = UsageLedger(path)
    assert len(reloaded.records()) == 3
    assert [r["step"] for r in reloaded.records("r_aaaaaaaaaaaa")] == [1, 2]
    assert [r["agent"] for r in reloaded.records("r_bbbbbbbbbbbb")] == ["coordinator"]
    assert reloaded.records("r_cccccccccccc") == []


def test_corrupt_lines_are_skipped(tmp_path: Path):
    path = tmp_path / "usage.jsonl"
    good = json.dumps(make_call("r_aaaaaaaaaaaa").to_record())
    path.write_text(f"{good}\nthis is not json{{\n\n[1, 2, 3]\n{good}\n", encoding="utf-8")

    ledger = UsageLedger(path)
    assert len(ledger.records()) == 2

    ledger.append(make_call("r_bbbbbbbbbbbb"))
    assert len(UsageLedger(path).records()) == 3


def test_today_cost_counts_only_the_current_utc_day(tmp_path: Path):
    ledger = UsageLedger(tmp_path / "usage.jsonl")
    old = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger.append(make_call("r_aaaaaaaaaaaa", cost=1.25, ts=old))
    ledger.append(make_call("r_bbbbbbbbbbbb", cost=0.02, ts=utc_now_iso()))
    ledger.append(make_call("r_bbbbbbbbbbbb", step=2, cost=0.03))  # default ts = now
    assert ledger.today_cost_usd() == pytest.approx(0.05)


def test_run_summaries_newest_first(tmp_path: Path):
    ledger = UsageLedger(tmp_path / "usage.jsonl")
    u = Usage(input_tokens=100, output_tokens=10)
    ledger.append(make_call("r_aaaaaaaaaaaa", agent="coordinator", step=1, usage=u, ts="2026-10-01T10:00:00Z"))
    ledger.append(make_call("r_aaaaaaaaaaaa", agent="researcher", step=1, usage=u, ts="2026-10-01T10:00:05Z"))
    ledger.append(make_call("r_bbbbbbbbbbbb", agent="coordinator", step=1, usage=u, ts="2026-10-02T09:00:00Z"))

    summaries = ledger.run_summaries()
    assert [s["run_id"] for s in summaries] == ["r_bbbbbbbbbbbb", "r_aaaaaaaaaaaa"]
    older = summaries[1]
    assert {"run_id", "started_at", "n_calls", "agents", "usage", "cost_usd"} <= set(older)
    assert older["n_calls"] == 2
    assert set(older["agents"]) == {"coordinator", "researcher"}
    assert older["usage"]["input_tokens"] == 200
    assert older["usage"]["total_tokens"] == 220
    assert older["cost_usd"] == pytest.approx(2 * cost_usd(u))
    assert older["started_at"].startswith("2026-10-01T10:00:00")

    assert len(ledger.run_summaries(limit=1)) == 1


def test_stats_math_and_projections(tmp_path: Path):
    ledger = UsageLedger(tmp_path / "usage.jsonl")
    runs = {
        "r_aaaaaaaaaaaa": [Usage(input_tokens=50_000, cached_tokens=0, output_tokens=10_000)],
        "r_bbbbbbbbbbbb": [
            Usage(input_tokens=80_000, cached_tokens=60_000, cache_write_tokens=5_000, output_tokens=20_000),
            Usage(input_tokens=40_000, cached_tokens=30_000, output_tokens=15_000, reasoning_tokens=5_000),
        ],
        "r_cccccccccccc": [Usage(input_tokens=200_000, cached_tokens=150_000, output_tokens=60_000)],
    }
    for run_id, usages in runs.items():
        for step, usage in enumerate(usages, start=1):
            ledger.append(make_call(run_id, step=step, usage=usage))

    k = 20
    stats = ledger.stats(runs_per_user_per_month=k)

    run_costs = sorted(sum(cost_usd(u) for u in usages) for usages in runs.values())
    mean_cost = statistics.mean(run_costs)
    all_usage = [u for usages in runs.values() for u in usages]
    total_input = sum(u.input_tokens for u in all_usage)
    total_cached = sum(u.cached_tokens for u in all_usage)

    assert stats["runs"] == 3
    assert stats["calls"] == 4

    avg = stats["avg_per_run"]
    assert avg["input_tokens"] == pytest.approx(total_input / 3, **APPROX)
    assert avg["cached_tokens"] == pytest.approx(total_cached / 3, **APPROX)
    assert avg["output_tokens"] == pytest.approx(sum(u.output_tokens for u in all_usage) / 3, **APPROX)
    assert avg["cost_usd"] == pytest.approx(mean_cost, **APPROX)

    cpr = stats["cost_per_run"]
    assert cpr["mean"] == pytest.approx(mean_cost, **APPROX)
    assert cpr["p50"] == pytest.approx(run_costs[1], **APPROX)
    assert cpr["max"] == pytest.approx(run_costs[2], **APPROX)
    assert run_costs[1] * 0.99 <= cpr["p90"] <= run_costs[2] * 1.01

    assert stats["cache_hit_rate"] == pytest.approx(total_cached / total_input, **APPROX)

    per_user = mean_cost * k
    assert stats["per_user_month_usd"] == pytest.approx(per_user, **APPROX)

    projections = {p["users"]: p for p in stats["projections"]}
    assert set(projections) == {1, 100, 10_000}
    for users, p in projections.items():
        assert p["monthly_usd"] == pytest.approx(per_user * users, **APPROX)
        assert p["yearly_usd"] == pytest.approx(per_user * users * 12, **APPROX)

    assert stats["assumptions"]["runs_per_user_per_month"] == k
    assert stats["assumptions"]["prices_per_m"] == PRICES_PER_M[MODEL]


def test_stats_on_empty_ledger_are_zeros(tmp_path: Path):
    stats = UsageLedger(tmp_path / "usage.jsonl").stats(runs_per_user_per_month=30)
    assert stats["runs"] == 0
    assert stats["calls"] == 0
    assert stats["cache_hit_rate"] == 0
    assert stats["per_user_month_usd"] == 0
    assert all(v == 0 for v in stats["cost_per_run"].values())
    assert stats["avg_per_run"]["cost_usd"] == 0
    assert sorted(p["users"] for p in stats["projections"]) == [1, 100, 10_000]
    assert all(p["monthly_usd"] == 0 and p["yearly_usd"] == 0 for p in stats["projections"])
    assert UsageLedger(tmp_path / "usage.jsonl").run_summaries() == []


# --------------------------------------------------------------------------- RunBudget


def test_budget_accumulates_usage_and_cost(make_settings, ledger):
    budget = RunBudget(make_settings(), ledger, "r_aaaaaaaaaaaa")
    a, b = make_call(step=1), make_call(step=2)
    budget.record(a)
    budget.record(b)
    assert budget.usage == a.usage + b.usage
    assert budget.cost_usd == pytest.approx(a.cost_usd + b.cost_usd)
    budget.check_before_call()  # well under every cap


def test_run_token_cap_trips(make_settings, ledger):
    budget = RunBudget(make_settings(run_token_cap=1000), ledger, "r_aaaaaaaaaaaa")
    budget.check_before_call()
    budget.record(make_call(usage=Usage(input_tokens=900, output_tokens=100)))
    with pytest.raises(BudgetExceeded) as exc_info:
        budget.check_before_call()
    assert exc_info.value.scope == "run_tokens"
    assert exc_info.value.limit == 1000
    assert exc_info.value.spent >= 1000


def test_run_usd_cap_trips(make_settings, ledger):
    budget = RunBudget(make_settings(run_budget_usd=0.001), ledger, "r_aaaaaaaaaaaa")
    budget.record(make_call(usage=Usage(output_tokens=10_000)))  # $0.005
    with pytest.raises(BudgetExceeded) as exc_info:
        budget.check_before_call()
    assert exc_info.value.scope == "run_usd"
    assert exc_info.value.limit == pytest.approx(0.001)
    assert exc_info.value.spent == pytest.approx(0.005)


def test_daily_cap_trips_from_ledger(make_settings, ledger):
    ledger.append(make_call("r_bbbbbbbbbbbb", cost=0.03))
    budget = RunBudget(make_settings(daily_budget_usd=0.02), ledger, "r_aaaaaaaaaaaa")
    with pytest.raises(BudgetExceeded) as exc_info:
        budget.check_before_call()
    assert exc_info.value.scope == "daily_usd"
    assert exc_info.value.spent == pytest.approx(0.03)


def test_daily_cap_ignores_previous_days(make_settings, ledger):
    ledger.append(make_call("r_bbbbbbbbbbbb", cost=5.0, ts="2020-01-01T00:00:00Z"))
    RunBudget(make_settings(daily_budget_usd=0.02), ledger, "r_aaaaaaaaaaaa").check_before_call()


def test_budget_exceeded_is_an_exception():
    exc = BudgetExceeded("run_usd", 0.05, 0.06)
    assert isinstance(exc, Exception)
    assert (exc.scope, exc.limit, exc.spent) == ("run_usd", 0.05, 0.06)
