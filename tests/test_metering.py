"""Metering gate before real model calls (gaps F-01..F-08 from evidence/q01.md §3.4).

The real LLMClient is exercised against httpx.MockTransport (SIMULATED gateway responses);
nothing here reaches the network.
"""

from __future__ import annotations

import asyncio
import copy
import os
from pathlib import Path

import httpx
import pytest

from app import config
from app.budget import BudgetExceeded, RunBudget
from app.config import MODEL
from app.ledger import UsageLedger
from app.llm import ContentFilterError, LLMClient, LLMError
from app.metering import failure_recorder, record_success
from app.pricing import Usage
from tests.conftest import DUMMY_KEY, text_result
from tests.test_llm import RESPONSE, USER_ITEM


def client_for(handler, *, seen: list | None = None) -> LLMClient:
    def recording(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return handler(request)

    llm = LLMClient(api_key=DUMMY_KEY, timeout_s=5, max_retries=1,
                    http_client=httpx.AsyncClient(transport=httpx.MockTransport(recording)))
    llm.retry_backoff_s = 0
    return llm


def sequence(*responses):
    items = list(responses)
    return lambda request: items.pop(0)


def run_create(llm, ledger, budget):
    return asyncio.run(llm.create(
        instructions="SYS", input_items=[USER_ITEM],
        on_attempt=failure_recorder(run_id="r_test", agent="matcher", step=1, ledger=ledger, budget=budget),
    ))


@pytest.fixture
def meter(settings, ledger):
    return ledger, RunBudget(settings, ledger, "r_test")


# --------------------------------------------------------------------------- F-01 missing usage


def test_missing_usage_is_null_not_zero(meter):
    ledger, budget = meter
    usage = Usage.from_api(None)
    assert set(usage.missing) == {"input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens"}
    res = text_result("ok", usage=usage)
    call = record_success(res=res, run_id="r_test", agent="matcher", step=1, ledger=ledger, budget=budget)
    rec = ledger.records()[0]
    assert call.cost_usd is None and rec["cost_usd"] is None
    assert rec["input_tokens"] is None and rec["output_tokens"] is None and rec["total_tokens"] is None
    assert budget.usage_missing and ledger.stats(30)["calls_usage_missing"] == 1


def test_partly_missing_usage_keeps_measured_fields():
    usage = Usage.from_api({"input_tokens": 100, "input_tokens_details": {"cached_tokens": 40}, "output_tokens": 10})
    assert set(usage.missing) == {"cache_write_tokens", "reasoning_tokens"}
    from app.ledger import ModelCall

    rec = ModelCall(run_id="r", agent="a", step=1, response_id="x", latency_ms=1, usage=usage, cost_usd=0.0).to_record()
    assert rec["input_tokens"] == 100 and rec["cached_tokens"] == 40
    assert rec["cache_write_tokens"] is None and rec["uncached_input_tokens"] is None
    assert rec["usage_missing"] == ["cache_write_tokens", "reasoning_tokens"]


# --------------------------------------------------------------------------- F-02 / F-03 failures and retries


def test_transient_failure_is_retried_once_and_both_attempts_are_ledgered(meter):
    ledger, budget = meter
    llm = client_for(sequence(httpx.Response(500, json={"error": {"message": "upstream"}}), httpx.Response(200, json=RESPONSE)))
    res = run_create(llm, ledger, budget)
    assert res.attempt == 2 and res.mode == "live"
    failed = ledger.records()
    assert len(failed) == 1 and failed[0]["status"] == "error" and failed[0]["error_kind"] == "server_error"
    assert failed[0]["attempt"] == 1 and failed[0]["cost_usd"] is None and failed[0]["input_tokens"] is None
    assert budget.n_calls == 1 and budget.n_failed == 1


def test_retry_is_bounded_and_final_failure_raises(meter):
    ledger, budget = meter
    llm = client_for(sequence(httpx.Response(503), httpx.Response(503), httpx.Response(200, json=RESPONSE)))
    with pytest.raises(LLMError):
        run_create(llm, ledger, budget)
    assert [r["attempt"] for r in ledger.records()] == [1, 2]  # max_retries=1 -> 2 attempts, never 3
    assert budget.n_calls == 2


@pytest.mark.parametrize(
    ("response", "kind", "error"),
    [
        (httpx.Response(401, json={"error": {"message": "bad key"}}), "auth", LLMError),
        (httpx.Response(400, json={"error": {"code": "content_filter", "message": "filtered"}}), "content_filter", ContentFilterError),
    ],
)
def test_non_transient_failures_are_not_retried(meter, response, kind, error):
    ledger, budget = meter
    llm = client_for(sequence(response, httpx.Response(200, json=RESPONSE)))
    with pytest.raises(error):
        run_create(llm, ledger, budget)
    assert [r["error_kind"] for r in ledger.records()] == [kind]


# --------------------------------------------------------------------------- F-04 call cap


def test_model_call_cap_counts_every_attempt(make_settings, ledger):
    budget = RunBudget(make_settings(max_model_calls_per_run=2), ledger, "r_cap")
    llm = client_for(sequence(httpx.Response(500), httpx.Response(500)))
    with pytest.raises(LLMError):
        asyncio.run(llm.create(instructions="S", input_items=[USER_ITEM],
                               on_attempt=failure_recorder(run_id="r_cap", agent="a", step=1, ledger=ledger, budget=budget)))
    with pytest.raises(BudgetExceeded) as exc:
        budget.check_before_call()
    assert exc.value.scope == "run_calls"


# --------------------------------------------------------------------------- F-05 / F-06 served model, live vs mock


def test_served_model_and_live_mode_are_recorded(meter):
    ledger, budget = meter
    other = copy.deepcopy(RESPONSE) | {"model": "some-other-model"}
    llm = client_for(sequence(httpx.Response(200, json=other)))
    res = run_create(llm, ledger, budget)
    record_success(res=res, run_id="r_test", agent="matcher", step=1, ledger=ledger, budget=budget)
    rec = ledger.records()[-1]
    assert rec["mode"] == "live" and rec["served_model"] == "some-other-model" and rec["model_mismatch"] is True
    assert rec["model"] == MODEL


def test_fake_results_are_marked_mock(meter):
    ledger, budget = meter
    record_success(res=text_result("ok"), run_id="r_test", agent="matcher", step=1, ledger=ledger, budget=budget)
    assert ledger.records()[0]["mode"] == "mock" and ledger.stats(30)["calls_mock"] == 1


# --------------------------------------------------------------------------- F-07 / F-08 environment


def test_openai_sdk_env_vars_cannot_add_headers_or_reroute(monkeypatch):
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "x-injected: yes")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://evil.example/v1")
    monkeypatch.setenv("OPENAI_ORG_ID", "org-injected")
    seen: list[httpx.Request] = []
    llm = client_for(lambda r: httpx.Response(200, json=RESPONSE), seen=seen)
    asyncio.run(llm.create(instructions="S", input_items=[USER_ITEM]))
    req = seen[0]
    assert req.url.host == "api.portkey.ai"
    assert "x-injected" not in req.headers and "openai-organization" not in req.headers
    assert os.environ["OPENAI_CUSTOM_HEADERS"] == "x-injected: yes"  # restored after construction


def test_whitespace_key_in_repo_env_does_not_hide_parent_key(tmp_path: Path, monkeypatch):
    repo = tmp_path / "course" / "repo"
    repo.mkdir(parents=True)
    (repo / ".env").write_text('PORTKEY_API_KEY="   "\n', encoding="utf-8")
    (repo.parent / ".env").write_text("PORTKEY_API_KEY=parent-key-1234567890\n", encoding="utf-8")
    monkeypatch.delenv("PORTKEY_API_KEY", raising=False)
    config.load_env(repo)
    assert config.get_api_key() == "parent-key-1234567890"
