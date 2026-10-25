"""Shared fixtures for the offline test suite.

Isolation rules:
- No test ever needs or reads the real PORTKEY_API_KEY. Dummy keys are put into the
  environment *before* any ``app`` module is imported, so ``load_dotenv(override=False)``
  at import time can never replace them with real values.
- Every test runs with a clean copy of ``os.environ`` (restored afterwards), no settings
  overrides, ``RUNS_DIR`` pointing at ``tmp_path`` and a fresh ``get_settings`` cache.
- The model is replaced by ``FakeLLM``: scripted ``LLMResult``s, no network.
"""

from __future__ import annotations

import copy
import itertools
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

DUMMY_KEY = "test-key-1234567890"
DUMMY_OPENAI_KEY = "test-openai-key-0987654321"

# Must happen before the first ``import app.config`` (which loads .env files).
os.environ["PORTKEY_API_KEY"] = DUMMY_KEY
os.environ["OPENAI_API_KEY"] = DUMMY_OPENAI_KEY

SETTINGS_ENV_VARS = (
    "RUN_BUDGET_USD",
    "RUN_TOKEN_CAP",
    "DAILY_BUDGET_USD",
    "MAX_STEPS_PER_AGENT",
    "MAX_TOOL_CALLS_PER_RUN",
    "MAX_AGENT_DEPTH",
    "MAX_OUTPUT_TOKENS",
    "MAX_INPUT_CHARS",
    "RATE_LIMIT_RUNS",
    "RATE_LIMIT_WINDOW_S",
    "SAFETY_LLM_GUARD",
    "RUNS_PER_USER_PER_MONTH",
    "DATA_DIR",
    "RUNS_DIR",
    "LLM_TIMEOUT_S",
    "RUN_TIMEOUT_S",
    "MAX_MODEL_CALLS_PER_RUN",
    "LLM_MAX_RETRIES",
    "LLM_SIMULATE",
)


# --------------------------------------------------------------------------- environment


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path):
    """Clean, restorable environment with dummy keys and runs_dir under tmp_path."""
    from app.config import get_settings

    saved = dict(os.environ)
    for name in SETTINGS_ENV_VARS:
        os.environ.pop(name, None)
    os.environ["PORTKEY_API_KEY"] = DUMMY_KEY
    os.environ["OPENAI_API_KEY"] = DUMMY_OPENAI_KEY
    os.environ["RUNS_DIR"] = str(tmp_path / "runs")
    get_settings.cache_clear()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """The public-source collector must never reach the network in the offline suite."""
    import app.collect.fetch as fetch

    def blocked():
        raise RuntimeError("real network is disabled in tests; pass transport=httpx.MockTransport(...)")

    monkeypatch.setattr(fetch, "_real_transport", blocked)


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Any]:
    """Settings factory: runs_dir under tmp_path, LLM guard off unless asked for."""
    from app.config import Settings

    def factory(**overrides: Any):
        values: dict[str, Any] = {"runs_dir": tmp_path / "runs", "llm_guard": False}
        values.update(overrides)
        return Settings(**values)

    return factory


@pytest.fixture
def settings(make_settings):
    return make_settings()


@pytest.fixture
def ledger(settings):
    from app.ledger import UsageLedger

    return UsageLedger(settings.runs_dir / "usage.jsonl")


# --------------------------------------------------------------------------- fake model

_response_ids = itertools.count(1)
_call_ids = itertools.count(1)


def make_usage(
    input_tokens: int = 1200,
    cached_tokens: int = 1000,
    output_tokens: int = 60,
    cache_write_tokens: int = 0,
    reasoning_tokens: int = 0,
):
    from app.pricing import Usage

    return Usage(
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        cache_write_tokens=cache_write_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
    )


def text_result(text: str, *, usage=None):
    """A final answer (no function calls)."""
    from app.llm import LLMResult

    return LLMResult(
        response_id=f"resp_{next(_response_ids)}",
        output_text=text,
        function_calls=[],
        usage=usage if usage is not None else make_usage(),
        latency_ms=5,
    )


def json_result(obj: Any, *, usage=None):
    return text_result(json.dumps(obj), usage=usage)


def call_result(*calls: tuple[str, dict], usage=None):
    """A model turn that requests one or more function calls: call_result(("name", {args}), ...)."""
    from app.llm import FunctionCall, LLMResult

    return LLMResult(
        response_id=f"resp_{next(_response_ids)}",
        output_text="",
        function_calls=[
            FunctionCall(call_id=f"call_{next(_call_ids)}", name=name, arguments=json.dumps(args))
            for name, args in calls
        ],
        usage=usage if usage is not None else make_usage(),
        latency_ms=5,
    )


class FakeLLM:
    """Drop-in replacement for ``LLMClient`` with the same ``create`` signature.

    ``script`` items are consumed in call order. Each item is an ``LLMResult``, an
    exception instance (raised), or a callable ``(request) -> LLMResult``. When the script
    is empty, ``default`` (same kinds) is used; without a default the call fails loudly.
    Every request is recorded in ``self.requests`` as a dict of the keyword arguments.
    """

    def __init__(self, script=(), *, default=None) -> None:
        self.script = list(script)
        self.default = default
        self.requests: list[dict[str, Any]] = []

    async def create(
        self,
        *,
        instructions: str,
        input_items: list[dict],
        tools: list[dict] | None = None,
        text_format: dict | None = None,
        previous_response_id: str | None = None,
        cache_key: str | None = None,
        max_output_tokens: int | None = None,
        on_attempt=None,  # FakeLLM never fails an attempt silently; scripted exceptions are raised
    ):
        request = {
            "instructions": instructions,
            "input_items": copy.deepcopy(input_items),
            "tools": copy.deepcopy(tools),
            "text_format": copy.deepcopy(text_format),
            "previous_response_id": previous_response_id,
            "cache_key": cache_key,
            "max_output_tokens": max_output_tokens,
        }
        self.requests.append(request)
        if self.script:
            item = self.script.pop(0)
        elif self.default is not None:
            item = self.default
        else:
            raise AssertionError(f"FakeLLM script exhausted at call #{len(self.requests)}")
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            item = item(request)
        return item


# --------------------------------------------------------------------------- helpers


def event_types(trace) -> list[str]:
    return [e.type for e in trace.events]


def events_of(trace, type_: str) -> list:
    return [e for e in trace.events if e.type == type_]


def tool_outputs(request: dict) -> list[str]:
    """The function_call_output strings sent in a FakeLLM request."""
    return [item["output"] for item in request["input_items"] if item.get("type") == "function_call_output"]


def assert_strict_schema(schema: dict) -> None:
    """Strict function/structured-output schema rules: closed objects, all keys required, no defaults."""

    def walk(node: Any, path: str) -> None:
        if isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")
            return
        if not isinstance(node, dict):
            return
        assert "default" not in node, f"'default' key at {path}"
        if node.get("type") == "object" or "properties" in node:
            props = node.get("properties", {})
            assert node.get("additionalProperties") is False, f"additionalProperties must be false at {path}"
            assert sorted(node.get("required", [])) == sorted(props), f"all properties must be required at {path}"
        for key, value in node.items():
            if key == "properties":
                for name, sub in value.items():
                    walk(sub, f"{path}.{name}")
            elif isinstance(value, (dict, list)):
                walk(value, f"{path}.{key}")

    walk(schema, "$")

    refs: list[str] = []

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("$ref"), str):
                refs.append(node["$ref"])
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(schema)
    defs = schema.get("$defs", {})
    for ref in refs:
        assert ref.startswith("#/$defs/") and ref.split("/")[-1] in defs, f"unresolvable $ref {ref}"
