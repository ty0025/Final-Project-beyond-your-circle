"""Append-only JSONL ledger of every model call, plus run summaries and cost projections."""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import MODEL
from app.pricing import PRICES_PER_M, USAGE_FIELDS, Usage

PROJECTION_USERS = (1, 100, 10_000)
_USAGE_FIELDS = USAGE_FIELDS


def utc_now_seconds() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _usage_of(record: dict) -> Usage:
    return Usage(**{name: _int(record.get(name)) for name in _USAGE_FIELDS})


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (same as numpy's default); 0.0 when empty."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100.0
    low = math.floor(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


@dataclass
class ModelCall:
    """One model ATTEMPT (successful or failed). Unmeasured values are written as null."""

    run_id: str
    agent: str
    step: int
    response_id: str
    latency_ms: int
    usage: Usage
    cost_usd: float | None  # None = cannot be computed from measured usage
    model: str = MODEL  # requested (locked) model, used for pricing
    served_model: str | None = None  # the model the response says served it
    mode: str = "live"  # "live" = real gateway call; "mock" = FakeLLM/stub (tests, demos)
    status: str = "ok"  # "ok" | "error"
    error_kind: str | None = None
    attempt: int = 1
    n_function_calls: int = 0
    finish: str | None = None  # final | tool_calls | incomplete:<reason> | refusal
    ts: str = field(default_factory=utc_now_seconds)

    def to_record(self) -> dict:
        usage = self.usage
        missing = set(USAGE_FIELDS) if self.status != "ok" else set(usage.missing)

        def measured(name: str, value: int) -> int | None:
            return None if name in missing else value

        served = self.served_model
        return {
            "ts": self.ts,
            "run_id": self.run_id,
            "agent": self.agent,
            "step": self.step,
            "attempt": self.attempt,
            "status": self.status,
            "error_kind": self.error_kind,
            "mode": self.mode,
            "model": self.model,
            "served_model": served,
            "model_mismatch": bool(served) and not served.startswith(self.model),
            "response_id": self.response_id or None,
            "latency_ms": self.latency_ms,
            "n_function_calls": self.n_function_calls,
            "finish": self.finish,
            "input_tokens": measured("input_tokens", usage.input_tokens),
            "cached_tokens": measured("cached_tokens", usage.cached_tokens),
            "cache_write_tokens": measured("cache_write_tokens", usage.cache_write_tokens),
            "uncached_input_tokens": (
                None if missing & {"input_tokens", "cached_tokens", "cache_write_tokens"} else usage.uncached_input_tokens
            ),
            "output_tokens": measured("output_tokens", usage.output_tokens),
            "reasoning_tokens": measured("reasoning_tokens", usage.reasoning_tokens),
            "total_tokens": None if missing & {"input_tokens", "output_tokens"} else usage.total_tokens,
            "usage_missing": sorted(missing),
            "cost_usd": None if self.cost_usd is None else round(self.cost_usd, 12),  # strips float noise only
        }


class UsageLedger:
    """Thread-safe JSONL ledger. Records are kept in memory after the initial load."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._records: list[dict] = []
        self._needs_newline = False
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        content = self.path.read_text(encoding="utf-8", errors="replace")
        # A crash mid-write can leave a partial last line; never glue the next record onto it.
        self._needs_newline = bool(content) and not content.endswith("\n")
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue  # corrupt line
            if isinstance(record, dict) and isinstance(record.get("run_id"), str):
                self._records.append(record)

    def append(self, call: ModelCall) -> None:
        record = call.to_record()
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                if self._needs_newline:
                    fh.write("\n")
                    self._needs_newline = False
                fh.write(line)
                fh.flush()
            self._records.append(record)

    def _snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._records)

    def today_cost_usd(self) -> float:
        """Spend on the current UTC calendar day, across all runs."""
        today = _utc_today()
        return sum(
            _float(record.get("cost_usd"))
            for record in self._snapshot()
            if str(record.get("ts", "")).startswith(today)
        )

    def records(self, run_id: str | None = None) -> list[dict]:
        return [dict(r) for r in self._snapshot() if run_id is None or r.get("run_id") == run_id]

    def run_summaries(self, limit: int | None = None) -> list[dict]:
        """One summary per run, newest first."""
        summaries = _summarize(self._snapshot())
        return summaries if limit is None else summaries[: max(0, limit)]

    def stats(self, runs_per_user_per_month: int) -> dict:
        records = self._snapshot()
        summaries = _summarize(records)
        n_runs = len(summaries)
        total = sum((_usage_of(r) for r in records), Usage())
        run_costs = [s["cost_usd"] for s in summaries]
        mean_cost = sum(run_costs) / n_runs if n_runs else 0.0

        avg_per_run: dict[str, float] = {
            key: (value / n_runs if n_runs else 0.0) for key, value in total.to_dict().items()
        }
        avg_per_run["cost_usd"] = mean_cost
        per_user_month = mean_cost * runs_per_user_per_month

        return {
            "runs": n_runs,
            "calls": len(records),
            "calls_failed": sum(1 for r in records if r.get("status", "ok") != "ok"),
            "calls_usage_missing": sum(1 for r in records if r.get("usage_missing")),
            "calls_mock": sum(1 for r in records if r.get("mode") == "mock"),
            "avg_per_run": avg_per_run,
            "cost_per_run": {
                "mean": mean_cost,
                "p50": _percentile(run_costs, 50),
                "p90": _percentile(run_costs, 90),
                "max": max(run_costs, default=0.0),
            },
            "cache_hit_rate": total.cached_tokens / total.input_tokens if total.input_tokens else 0.0,
            "per_user_month_usd": per_user_month,
            "projections": [
                {"users": users, "monthly_usd": per_user_month * users, "yearly_usd": per_user_month * users * 12}
                for users in PROJECTION_USERS
            ],
            "assumptions": {
                "runs_per_user_per_month": runs_per_user_per_month,
                "prices_per_m": dict(PRICES_PER_M[MODEL]),
            },
        }


def _summarize(records: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for record in records:
        run_id = record["run_id"]
        group = groups.get(run_id)
        if group is None:
            group = groups[run_id] = {
                "run_id": run_id,
                "started_at": str(record.get("ts", "")),
                "n_calls": 0,
                "n_failed": 0,
                "agents": [],
                "usage": Usage(),
                "cost_usd": 0.0,
                "_order": len(groups),
            }
        ts = str(record.get("ts", ""))
        if ts and (not group["started_at"] or ts < group["started_at"]):
            group["started_at"] = ts
        group["n_calls"] += 1
        if record.get("status", "ok") != "ok":
            group["n_failed"] += 1
        agent = record.get("agent")
        if agent and agent not in group["agents"]:
            group["agents"].append(agent)
        group["usage"] = group["usage"] + _usage_of(record)
        group["cost_usd"] += _float(record.get("cost_usd"))

    ordered = sorted(groups.values(), key=lambda g: (g["started_at"], g["_order"]), reverse=True)
    return [
        {
            "run_id": g["run_id"],
            "started_at": g["started_at"],
            "n_calls": g["n_calls"],
            "n_failed": g["n_failed"],
            "agents": g["agents"],
            "usage": g["usage"].to_dict(),
            "cost_usd": g["cost_usd"],
        }
        for g in ordered
    ]
