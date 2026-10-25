"""LLMClient over a mocked HTTP transport: request shape, gateway headers, parsing, error scrubbing."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.config import MODEL
from app.llm import ContentFilterError, LLMClient, LLMError
from tests.conftest import DUMMY_KEY

USER_ITEM = {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}

RESPONSE = {
    "id": "resp_1",
    "object": "response",
    "created_at": 0,
    "status": "completed",
    "model": MODEL,
    "output": [
        {
            "type": "function_call",
            "id": "fc_1",
            "call_id": "call_1",
            "name": "search_docs",
            "arguments": '{"query": "refund"}',
            "status": "completed",
        },
        {
            "type": "message",
            "id": "msg_1",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "hello", "annotations": []}],
        },
    ],
    "parallel_tool_calls": True,
    "tool_choice": "auto",
    "tools": [],
    "usage": {
        "input_tokens": 4036,
        "input_tokens_details": {"cached_tokens": 4014, "cache_write_tokens": 19},
        "output_tokens": 22,
        "output_tokens_details": {"reasoning_tokens": 5},
        "total_tokens": 4058,
    },
}


def mocked_client(handler) -> LLMClient:
    llm = LLMClient(api_key=DUMMY_KEY, timeout_s=5)
    # with_options keeps the constructor's base_url and default headers.
    llm._client = llm._client.with_options(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), max_retries=0
    )
    return llm


def test_first_turn_sends_cached_developer_prefix_and_gateway_headers():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=RESPONSE)

    llm = mocked_client(handler)
    result = asyncio.run(
        llm.create(instructions="SYS", input_items=[USER_ITEM], cache_key="mgt409-final-test", max_output_tokens=100)
    )

    assert seen["url"].startswith("https://api.portkey.ai/v1/")
    assert seen["headers"]["x-portkey-api-key"] == DUMMY_KEY
    # The Portkey response cache would replay old usage; every call must be real.
    assert seen["headers"]["x-portkey-cache-force-refresh"] == "true"
    body = seen["body"]
    assert body["model"] == MODEL
    assert body["prompt_cache_options"] == {"ttl": "30m"}
    assert body["prompt_cache_key"] == "mgt409-final-test"
    assert body["max_output_tokens"] == 100
    assert "previous_response_id" not in body and "tools" not in body and "text" not in body
    developer, user = body["input"]
    assert developer["role"] == "developer"
    assert developer["content"][0] == {
        "type": "input_text",
        "text": "SYS",
        "prompt_cache_breakpoint": {"mode": "explicit"},
    }
    assert user == USER_ITEM

    assert result.response_id == "resp_1"
    assert result.output_text == "hello"
    assert [(c.call_id, c.name, c.arguments) for c in result.function_calls] == [
        ("call_1", "search_docs", '{"query": "refund"}')
    ]
    assert (result.usage.input_tokens, result.usage.cached_tokens, result.usage.cache_write_tokens) == (4036, 4014, 19)
    assert (result.usage.output_tokens, result.usage.reasoning_tokens) == (22, 5)
    assert result.latency_ms >= 0


def test_chained_turn_sends_only_new_items():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=RESPONSE)

    output_item = {"type": "function_call_output", "call_id": "call_1", "output": "3"}
    text_format = {"type": "json_schema", "name": "A", "strict": True, "schema": {"type": "object"}}
    asyncio.run(
        mocked_client(handler).create(
            instructions="SYS", input_items=[output_item], previous_response_id="resp_1", text_format=text_format
        )
    )
    body = seen["body"]
    assert body["previous_response_id"] == "resp_1"
    assert body["input"] == [output_item]
    assert body["text"] == {"format": text_format}


@pytest.mark.parametrize(
    ("status", "expected"),
    [(400, "Model gateway error 400"), (401, "rejected the API key"), (429, "rate limiting")],
)
def test_api_errors_become_llm_errors_without_the_key(status, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": f"bad request for key {DUMMY_KEY}"}})

    with pytest.raises(LLMError) as info:
        asyncio.run(mocked_client(handler).create(instructions="SYS", input_items=[USER_ITEM]))
    message = str(info.value)
    assert expected in message
    assert DUMMY_KEY not in message
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_repr_never_shows_the_key():
    assert DUMMY_KEY not in repr(LLMClient(api_key=DUMMY_KEY, timeout_s=5))


def test_provider_content_filter_becomes_content_filter_error():
    body = {
        "error": {
            "message": "azure-openai error: The response was filtered due to the prompt triggering Azure OpenAI's "
            "content management policy. https://go.microsoft.com/fwlink/?linkid=2198766",
            "type": "invalid_request_error",
            "param": "prompt",
            "code": "content_filter",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    with pytest.raises(ContentFilterError) as info:
        asyncio.run(mocked_client(handler).create(instructions="SYS", input_items=[USER_ITEM]))
    assert isinstance(info.value, LLMError)
    assert info.value.stopped_reason == "blocked"
    assert "http" not in str(info.value)


def test_error_messages_drop_links():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad input, see https://example.com/doc?x=1"}})

    with pytest.raises(LLMError) as info:
        asyncio.run(mocked_client(handler).create(instructions="SYS", input_items=[USER_ITEM]))
    assert not isinstance(info.value, ContentFilterError)
    assert "https://" not in str(info.value)


# --------------------------------------------------------------------------- incomplete / refused responses


def respond_with(body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**RESPONSE, **body})

    return mocked_client(handler)


def test_incomplete_response_is_not_reported_as_a_complete_answer():
    # max_output_tokens includes reasoning: the model ran out before writing any text.
    llm = respond_with(
        {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [{"type": "reasoning", "id": "rs_1", "summary": []}],
        }
    )
    result = asyncio.run(llm.create(instructions="SYS", input_items=[USER_ITEM]))
    assert result.incomplete_reason == "max_output_tokens"
    assert result.output_text == "" and result.function_calls == []
    assert result.usage.input_tokens == 4036, "the call was billed, so its usage is still reported"


def test_truncated_function_call_is_dropped():
    llm = respond_with(
        {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [
                {**RESPONSE["output"][0], "call_id": "call_ok"},
                {**RESPONSE["output"][0], "call_id": "call_cut", "arguments": '{"query": "ref', "status": "incomplete"},
            ],
        }
    )
    result = asyncio.run(llm.create(instructions="SYS", input_items=[USER_ITEM]))
    assert [c.call_id for c in result.function_calls] == ["call_ok"]


def test_output_side_content_filter_is_a_block():
    llm = respond_with(
        {
            "status": "incomplete",
            "incomplete_details": {"reason": "content_filter"},
            "output": [RESPONSE["output"][1]],
        }
    )
    with pytest.raises(ContentFilterError):
        asyncio.run(llm.create(instructions="SYS", input_items=[USER_ITEM]))


def test_refusal_content_part_is_captured():
    refusal_message = {
        "type": "message",
        "id": "msg_2",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "refusal", "refusal": "I can't help with that."}],
    }
    result = asyncio.run(respond_with({"output": [refusal_message]}).create(instructions="SYS", input_items=[USER_ITEM]))
    assert result.refusal == "I can't help with that."
    assert result.output_text == ""
    assert result.incomplete_reason is None


def test_completed_response_has_no_incomplete_reason_or_refusal():
    result = asyncio.run(respond_with({}).create(instructions="SYS", input_items=[USER_ITEM]))
    assert result.incomplete_reason is None and result.refusal == ""
