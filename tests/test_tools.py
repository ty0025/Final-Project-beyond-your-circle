from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Literal, Optional

import pytest
from pydantic import BaseModel

from app.tools import Tool, ToolRegistry, strict_schema, tool
from tests.conftest import assert_strict_schema


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- decorator + schema


@tool(description="Search the catalog.")
def search_catalog(
    query: str,
    tags: list[str],
    limit: int = 5,
    min_price: float = 0.0,
    include_archived: bool = False,
    category: Literal["bikes", "parts"] = "bikes",
    note: Optional[str] = None,
) -> list[str]:
    return [query]


@tool()
def shout(text: str) -> str:
    """Upper-case the text.

    Longer explanation that is not needed in the summary.
    """
    return text.upper()


def test_decorator_returns_tool_with_strict_schema():
    assert isinstance(search_catalog, Tool)
    schema = search_catalog.schema()
    assert schema["type"] == "function"
    assert schema["name"] == "search_catalog"
    assert schema["description"] == "Search the catalog."
    assert schema["strict"] is True

    params = schema["parameters"]
    assert params["type"] == "object"
    assert set(params["properties"]) == {"query", "tags", "limit", "min_price", "include_archived", "category", "note"}
    assert_strict_schema(params)

    props = params["properties"]
    assert props["query"]["type"] == "string"
    assert props["limit"]["type"] == "integer"
    assert props["min_price"]["type"] == "number"
    assert props["include_archived"]["type"] == "boolean"
    assert props["tags"]["type"] == "array"
    assert props["tags"]["items"]["type"] == "string"
    assert set(props["category"]["enum"]) == {"bikes", "parts"}
    note = props["note"]
    nullable = any(opt.get("type") == "null" for opt in note.get("anyOf", [])) or "null" in (note.get("type") or [])
    assert nullable, f"Optional[str] must allow null: {note}"


def test_description_and_name_defaults():
    assert shout.name == "shout"
    assert shout.description.startswith("Upper-case the text.")
    assert shout.untrusted_output is False

    @tool(name="custom_name", description="d", untrusted_output=True, timeout_s=3.0, max_output_chars=99)
    def anything(x: int) -> int:
        return x

    assert anything.name == "custom_name"
    assert anything.schema()["name"] == "custom_name"
    assert anything.untrusted_output is True
    assert anything.timeout_s == 3.0
    assert anything.max_output_chars == 99


def test_strict_schema_on_nested_models():
    class Citation(BaseModel):
        doc_id: str
        quote: str

    class Answer(BaseModel):
        answer: str
        citations: list[Citation]
        confidence: Literal["high", "medium", "low"] = "medium"
        follow_up: Optional[str] = None

    schema = strict_schema(Answer)
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"answer", "citations", "confidence", "follow_up"}
    assert_strict_schema(schema)


# --------------------------------------------------------------------------- registry + execute


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()

    @tool(description="Add two integers.")
    def add(a: int, b: int) -> int:
        return a + b

    @tool(description="Greet someone.")
    async def greet(name: str) -> str:
        return f"hello {name}"

    @tool(description="Return a dict.")
    def info(key: str) -> dict:
        return {"key": key, "values": [1, 2, 3]}

    @tool(description="Always fails.")
    def boom(x: int) -> str:
        raise ValueError("kaput")

    @tool(description="Too slow.", timeout_s=0.05)
    async def slow(x: int) -> str:
        await asyncio.sleep(2)
        return "late"

    @tool(description="Big output.", max_output_chars=50)
    def big(n: int) -> str:
        return "x" * n

    for t in (add, greet, info, boom, slow, big):
        assert reg.register(t) is t
    return reg


def test_registry_lookup_and_schemas(registry: ToolRegistry):
    assert {"add", "greet", "info", "boom", "slow", "big"} <= set(registry.names())
    assert registry.get("add").name == "add"
    assert registry.get("does_not_exist") is None
    schemas = registry.schemas(["add", "greet"])
    assert [s["name"] for s in schemas] == ["add", "greet"]
    assert registry.schemas([]) == []


def test_execute_sync_tool(registry: ToolRegistry):
    r = run(registry.execute("add", json.dumps({"a": 2, "b": 3})))
    assert r.ok is True
    assert r.output == "5"
    assert r.error is None
    assert r.truncated is False
    assert isinstance(r.duration_ms, int) and r.duration_ms >= 0


def test_execute_async_tool(registry: ToolRegistry):
    r = run(registry.execute("greet", json.dumps({"name": "Ana"})))
    assert r.ok is True
    assert r.output == "hello Ana"


def test_non_string_result_is_json(registry: ToolRegistry):
    r = run(registry.execute("info", json.dumps({"key": "k"})))
    assert r.ok is True
    assert json.loads(r.output) == {"key": "k", "values": [1, 2, 3]}


@pytest.mark.parametrize(
    "arguments",
    [
        json.dumps({"a": "two", "b": 3}),  # wrong type
        json.dumps({"a": 1}),  # missing field
        "{not json",  # malformed JSON
        "",  # empty
    ],
)
def test_validation_errors_return_ok_false(registry: ToolRegistry, arguments: str):
    r = run(registry.execute("add", arguments))
    assert r.ok is False
    assert r.output.startswith("ERROR")


def test_unknown_tool_returns_ok_false(registry: ToolRegistry):
    r = run(registry.execute("rm_rf", "{}"))
    assert r.ok is False
    assert r.output.startswith("ERROR")


def test_exception_in_tool_is_captured(registry: ToolRegistry):
    r = run(registry.execute("boom", json.dumps({"x": 1})))
    assert r.ok is False
    assert r.output.startswith("ERROR")
    assert "ValueError" in r.output
    assert "kaput" in r.output


def test_timeout_returns_ok_false(registry: ToolRegistry):
    started = time.perf_counter()
    r = run(registry.execute("slow", json.dumps({"x": 1})))
    assert r.ok is False
    assert r.output.startswith("ERROR")
    assert time.perf_counter() - started < 1.5


def test_long_output_is_truncated(registry: ToolRegistry):
    r = run(registry.execute("big", json.dumps({"n": 500})))
    assert r.ok is True
    assert r.truncated is True
    assert r.output.startswith("x" * 40)
    assert "truncated" in r.output
    assert len(r.output) <= 50 + 20


def test_output_at_limit_is_not_truncated(registry: ToolRegistry):
    r = run(registry.execute("big", json.dumps({"n": 50})))
    assert r.truncated is False
    assert r.output == "x" * 50

# Domain tools (search_listings, get_listing) are tested in tests/test_domain.py.
