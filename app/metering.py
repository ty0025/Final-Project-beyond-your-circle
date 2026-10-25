"""One place that turns a model attempt into a ledger record, a budget update and a trace event.

Used by the agent loop and the LLM guard, so every attempt (successful, failed or retried) is
counted the same way. Unmeasured usage is written as null (see ``ModelCall.to_record``).
"""

from __future__ import annotations

from typing import Any, Callable

from app.ledger import ModelCall
from app.llm import AttemptFailure, LLMResult
from app.pricing import COST_CRITICAL_FIELDS, USAGE_FIELDS, Usage, cost_usd


def _cost(usage: Usage) -> float | None:
    return None if set(usage.missing) & set(COST_CRITICAL_FIELDS) else cost_usd(usage)


def _finish(res: LLMResult) -> str:
    if res.refusal:
        return "refusal"
    if res.incomplete_reason:
        return f"incomplete:{res.incomplete_reason}"
    return "tool_calls" if res.function_calls else "final"


def record_success(*, res: LLMResult, run_id: str, agent: str, step: int, ledger: Any, budget: Any,
                   trace: Any = None) -> ModelCall:
    call = ModelCall(
        run_id=run_id,
        agent=agent,
        step=step,
        response_id=res.response_id,
        latency_ms=res.latency_ms,
        usage=res.usage,
        cost_usd=_cost(res.usage),
        served_model=res.model,
        mode=res.mode,
        attempt=res.attempt,
        n_function_calls=len(res.function_calls),
        finish=_finish(res),
    )
    ledger.append(call)
    budget.record(call)
    if trace is not None:
        trace.emit(
            "model_call",
            agent,
            step=step,
            attempt=res.attempt,
            mode=res.mode,
            served_model=res.model,
            finish=call.finish,
            usage=res.usage.to_dict(),
            usage_missing=list(res.usage.missing),
            cost_usd=call.cost_usd,
            latency_ms=res.latency_ms,
            n_function_calls=len(res.function_calls),
            run_usage=budget.usage.to_dict(),
            run_cost_usd=budget.cost_usd,
            run_calls=budget.n_calls,
        )
    return call


def failure_recorder(*, run_id: str, agent: str, step: int, ledger: Any, budget: Any,
                     trace: Any = None) -> Callable[[AttemptFailure], None]:
    """Callback for ``LLMClient.create(on_attempt=...)``: ledger one failed attempt."""

    def on_attempt(failure: AttemptFailure) -> None:
        usage = failure.usage or Usage(missing=USAGE_FIELDS)
        call = ModelCall(
            run_id=run_id,
            agent=agent,
            step=step,
            response_id=failure.response_id or "",
            latency_ms=failure.latency_ms,
            usage=usage,
            cost_usd=None,
            served_model=failure.model,
            mode=failure.mode,
            status="error",
            error_kind=failure.kind,
            attempt=failure.attempt,
        )
        ledger.append(call)
        budget.record(call)
        if trace is not None:
            trace.emit(
                "model_call_failed",
                agent,
                step=step,
                attempt=failure.attempt,
                error_kind=failure.kind,
                message=failure.message,
                latency_ms=failure.latency_ms,
                run_calls=budget.n_calls,
            )

    return on_attempt
