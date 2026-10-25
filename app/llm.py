"""Model gateway: one async client for gpt-6-luna over the Responses API via Portkey."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import openai
from openai import AsyncOpenAI

from app.config import API_KEY_ENV, MODEL, PORTKEY_BASE_URL, get_api_key, get_settings
from app.pricing import Usage

PROMPT_CACHE_OPTIONS = {"ttl": "30m"}
# The course gateway also has a Portkey *response* cache: an identical request is answered
# from it with the original call's usage replayed, which would double-count tokens in the
# ledger and hide the provider's prompt cache. Always force a real call; the provider-side
# prompt cache (explicit breakpoint, see developer_message) still makes repeated prefixes cheap.
GATEWAY_HEADERS = {"x-portkey-cache-force-refresh": "true"}
_MAX_ERROR_CHARS = 300
_URL_RE = re.compile(r"https?://\S+")


class LLMError(RuntimeError):
    """A model call failed. The message is safe to show: it never contains the key."""

    stopped_reason = "error"  # how the agent runtime reports a run that ends with this error


class ContentFilterError(LLMError):
    """The provider's content filter rejected the request (typically a jailbreak-looking prompt).

    This is a safety signal rather than an outage: callers treat it as a block, not a failure.
    """

    stopped_reason = "blocked"


CONTENT_FILTER_MESSAGE = "The model provider's content filter rejected this request as a likely prompt attack."


@dataclass
class FunctionCall:
    call_id: str
    name: str
    arguments: str  # raw JSON string from the model


@dataclass
class LLMResult:
    response_id: str
    output_text: str  # concatenated text output ("" if only function calls)
    function_calls: list[FunctionCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    # Set when the response is not a usable answer even though the call itself succeeded:
    incomplete_reason: str | None = None  # status "incomplete", e.g. "max_output_tokens" (text may be cut off)
    refusal: str = ""  # the model declined (a "refusal" content part instead of output_text)
    model: str | None = None  # the model the response says served it
    mode: str = "mock"  # only LLMClient (the real gateway) sets "live"; FakeLLM/stubs stay "mock"
    attempt: int = 1  # which attempt produced this result (retries are separate ledger records)


@dataclass
class AttemptFailure:
    """One failed model attempt, reported to the caller so it is ledgered with run context."""

    attempt: int
    kind: str  # timeout | connection | rate_limit | server_error | auth | bad_request | content_filter | failed_response | other
    message: str  # already scrubbed
    latency_ms: int
    usage: Usage | None = None  # only if the provider reported usage for the failed response
    response_id: str | None = None
    model: str | None = None
    mode: str = "live"


# Environment variables the openai SDK reads at construction time. The shared parent .env is
# loaded into os.environ, so they are hidden while the client is built (model routing stays locked).
_SDK_ENV_VARS = (
    "OPENAI_CUSTOM_HEADERS",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "OPENAI_WEBHOOK_SECRET",
    "OPENAI_BASE_URL",
    "OPENAI_ADMIN_KEY",
)


@contextlib.contextmanager
def _without_sdk_env() -> Iterator[None]:
    saved = {name: os.environ.pop(name) for name in _SDK_ENV_VARS if name in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def developer_message(instructions: str) -> dict:
    """The stable prefix, marked with an explicit cache breakpoint."""
    return {
        "role": "developer",
        "content": [
            {
                "type": "input_text",
                "text": instructions,
                "prompt_cache_breakpoint": {"mode": "explicit"},
            }
        ],
    }


def build_request(
    *,
    instructions: str,
    input_items: list[dict],
    tools: list[dict] | None = None,
    text_format: dict | None = None,
    previous_response_id: str | None = None,
    cache_key: str | None = None,
    max_output_tokens: int | None = None,
) -> dict:
    """Keyword arguments for ``client.responses.create`` (pure, so it is testable offline)."""
    if previous_response_id is None:
        items = [developer_message(instructions), *input_items]
    else:
        # The developer message is already part of the chained context.
        items = list(input_items)
    request: dict[str, Any] = {
        "model": MODEL,
        "input": items,
        "prompt_cache_options": dict(PROMPT_CACHE_OPTIONS),
    }
    if previous_response_id is not None:
        request["previous_response_id"] = previous_response_id
    if cache_key:
        request["prompt_cache_key"] = cache_key
    if tools:
        request["tools"] = tools
    if text_format:
        request["text"] = {"format": text_format}
    if max_output_tokens:
        request["max_output_tokens"] = max_output_tokens
    return request


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def parse_response(response: Any, latency_ms: int) -> LLMResult:
    """Collect text, function calls and refusals from a Responses API result (SDK object or dict)."""
    texts: list[str] = []
    refusals: list[str] = []
    calls: list[FunctionCall] = []
    for item in _get(response, "output") or []:
        item_type = _get(item, "type")
        if item_type == "function_call":
            if _get(item, "status") == "incomplete":
                continue  # cut off mid-arguments (output token limit): not a usable call
            arguments = _get(item, "arguments")
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments if arguments is not None else {})
            calls.append(
                FunctionCall(
                    call_id=str(_get(item, "call_id") or ""),
                    name=str(_get(item, "name") or ""),
                    arguments=arguments,
                )
            )
        elif item_type == "message":
            for part in _get(item, "content") or []:
                part_type = _get(part, "type")
                text = _get(part, "text")
                if part_type == "output_text" and text:
                    texts.append(text)
                elif part_type == "refusal":
                    refusals.append(str(_get(part, "refusal") or text or "").strip() or "The model declined to answer.")
    incomplete_reason = None
    if _get(response, "status") == "incomplete":
        incomplete_reason = str(_get(_get(response, "incomplete_details"), "reason") or "unknown")
    return LLMResult(
        response_id=str(_get(response, "id") or ""),
        output_text="".join(texts),
        function_calls=calls,
        usage=Usage.from_api(_get(response, "usage")),
        latency_ms=latency_ms,
        incomplete_reason=incomplete_reason,
        refusal="\n".join(refusals),
        model=(str(_get(response, "model")) if _get(response, "model") else None),
    )


class LLMClient:
    """Thin async wrapper; the model is always ``config.MODEL``."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_s: float | None = None,
        max_retries: int | None = None,
        http_client: Any = None,  # tests pass an httpx.AsyncClient with a mock transport
    ) -> None:
        key = (api_key or get_api_key()).strip()
        settings = get_settings()
        if timeout_s is None:
            timeout_s = settings.request_timeout_s
        self.model = MODEL
        self.timeout_s = timeout_s
        self.max_retries = settings.llm_max_retries if max_retries is None else max_retries
        self.retry_backoff_s = 0.5
        self._secret = key
        with _without_sdk_env():
            self._client = AsyncOpenAI(
                api_key=key,
                base_url=PORTKEY_BASE_URL,
                default_headers={"x-portkey-api-key": key, **GATEWAY_HEADERS},
                timeout=timeout_s,
                max_retries=0,  # retries happen in create(), one ledger record per attempt
                **({"http_client": http_client} if http_client is not None else {}),
            )

    def __repr__(self) -> str:  # never show the key
        return f"LLMClient(model={self.model!r})"

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
        on_attempt: Callable[[AttemptFailure], None] | None = None,
    ) -> LLMResult:
        """One model call with at most ``max_retries`` retries for transient errors.

        Every failed attempt is reported through ``on_attempt`` (so it is ledgered) before the
        next attempt or before the final ``LLMError`` is raised.
        """
        request = build_request(
            instructions=instructions,
            input_items=input_items,
            tools=tools,
            text_format=text_format,
            previous_response_id=previous_response_id,
            cache_key=cache_key,
            max_output_tokens=max_output_tokens,
        )
        attempts = 1 + max(0, self.max_retries)
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                result = await self._attempt(request, started)
                result.attempt = attempt
                return result
            except _AttemptError as failed:
                failed.failure.attempt = attempt
                if on_attempt is not None:
                    on_attempt(failed.failure)
                if not failed.retryable or attempt == attempts:
                    raise failed.error from None
                await asyncio.sleep(self.retry_backoff_s * attempt)
        raise LLMError("Model call failed.")  # unreachable

    async def _attempt(self, request: dict, started: float) -> LLMResult:
        def elapsed() -> int:
            return int(round((time.perf_counter() - started) * 1000))

        try:
            response = await self._client.responses.create(**request)
        except openai.OpenAIError as exc:
            # `from None`: the chained SDK exception carries the request (and its headers).
            if _is_content_filter(exc):
                raise _AttemptError(ContentFilterError(CONTENT_FILTER_MESSAGE), "content_filter",
                                    CONTENT_FILTER_MESSAGE, elapsed(), False) from None
            message = self._describe(exc)
            kind, retryable = _classify(exc)
            raise _AttemptError(LLMError(message), kind, message, elapsed(), retryable) from None
        except Exception as exc:
            message = self._scrub(f"Model call failed: {type(exc).__name__}: {exc}")
            raise _AttemptError(LLMError(message), "other", message, elapsed(), False) from None
        latency_ms = elapsed()

        status = _get(response, "status")
        raw_usage = _get(response, "usage")
        usage = Usage.from_api(raw_usage) if raw_usage is not None else None
        served = str(_get(response, "model")) if _get(response, "model") else None
        response_id = str(_get(response, "id") or "") or None
        if status == "failed":
            error = _get(response, "error")
            if _get(error, "code") == "content_filter":
                raise _AttemptError(ContentFilterError(CONTENT_FILTER_MESSAGE), "content_filter",
                                    CONTENT_FILTER_MESSAGE, latency_ms, False, usage, response_id, served)
            detail = _get(error, "message") or "unknown error"
            message = self._scrub(f"Model response failed: {detail}")
            raise _AttemptError(LLMError(message), "failed_response", message, latency_ms, False,
                                usage, response_id, served)
        if status == "incomplete" and _get(_get(response, "incomplete_details"), "reason") == "content_filter":
            # The provider's output-side filter cut the answer off: a block, like a filtered prompt.
            raise _AttemptError(ContentFilterError(CONTENT_FILTER_MESSAGE), "content_filter",
                                CONTENT_FILTER_MESSAGE, latency_ms, False, usage, response_id, served)
        # Other incomplete responses (e.g. max_output_tokens) come back with incomplete_reason set;
        # the agent runtime accounts for their usage and does not treat them as a final answer.
        result = parse_response(response, latency_ms)
        result.mode = "live"
        return result

    async def aclose(self) -> None:
        await self._client.close()

    def _describe(self, exc: openai.OpenAIError) -> str:
        if isinstance(exc, openai.APITimeoutError):
            return f"The model gateway timed out after {self.timeout_s:g}s. Please try again."
        if isinstance(exc, openai.APIConnectionError):
            return "Could not reach the model gateway (Portkey). Check your internet connection."
        if isinstance(exc, openai.AuthenticationError):
            return f"The model gateway rejected the API key (401). Check {API_KEY_ENV} in your .env file."
        if isinstance(exc, openai.RateLimitError):
            return "The model gateway is rate limiting requests (429). Wait a moment and try again."
        if isinstance(exc, openai.APIStatusError):
            detail = _error_detail(exc.body) or exc.message
            return self._scrub(f"Model gateway error {exc.status_code}: {detail}")
        return self._scrub(f"Model call failed: {type(exc).__name__}: {exc}")

    def _scrub(self, message: str) -> str:
        secrets_to_hide = {self._secret, os.environ.get(API_KEY_ENV, ""), os.environ.get("OPENAI_API_KEY", "")}
        for secret in secrets_to_hide:
            secret = (secret or "").strip()
            if len(secret) >= 4:
                message = message.replace(secret, "[REDACTED]")
        # Provider messages may carry documentation links; they are noise in the UI and would
        # trip the exfiltration-URL check of the red-team report.
        message = _URL_RE.sub("[link removed]", message)
        if len(message) > _MAX_ERROR_CHARS:
            message = message[: _MAX_ERROR_CHARS - 1] + "…"
        return message


SIMULATED_LLM_KINDS = ("timeout", "error")


class SimulatedFailureLLM:
    """Demo/test stand-in for LLMClient (``LLM_SIMULATE=timeout|error``): every call fails after a delay.

    It never touches the network or the API key and never reports an attempt, so it writes no ledger
    rows of any mode. Its messages say "SIMULATED" so screenshots cannot pass for a real outage.
    """

    def __init__(self, kind: str, delay_s: float = 8.0) -> None:
        if kind not in SIMULATED_LLM_KINDS:
            raise ValueError(kind)
        self.kind = kind
        self.delay_s = max(0.0, delay_s)
        self.model = MODEL

    def __repr__(self) -> str:
        return f"SimulatedFailureLLM(kind={self.kind!r})"

    async def create(self, **_: Any) -> LLMResult:
        await asyncio.sleep(self.delay_s)  # cancellable, so Stop can be demonstrated
        if self.kind == "timeout":
            raise LLMError("[SIMULATED, test mode] The model gateway timed out. No real model call was made.")
        raise LLMError("[SIMULATED, test mode] The model gateway returned an error (HTTP 503). No real model call was made.")

    async def aclose(self) -> None:
        return None


class _AttemptError(Exception):
    def __init__(self, error: LLMError, kind: str, message: str, latency_ms: int, retryable: bool,
                 usage: Usage | None = None, response_id: str | None = None, model: str | None = None) -> None:
        super().__init__(message)
        self.error = error
        self.retryable = retryable
        self.failure = AttemptFailure(attempt=0, kind=kind, message=message, latency_ms=latency_ms,
                                      usage=usage, response_id=response_id, model=model)


def _classify(exc: openai.OpenAIError) -> tuple[str, bool]:
    """(error kind, worth retrying)."""
    if isinstance(exc, openai.APITimeoutError):
        return "timeout", True
    if isinstance(exc, openai.APIConnectionError):
        return "connection", True
    if isinstance(exc, openai.RateLimitError):
        return "rate_limit", True
    if isinstance(exc, openai.AuthenticationError):
        return "auth", False
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500 or exc.status_code in (408, 409):
            return "server_error", True
        return "bad_request", False
    return "other", False


def _is_content_filter(exc: openai.OpenAIError) -> bool:
    """Azure/OpenAI content-filter rejections arrive as 400 with code "content_filter"."""
    if not isinstance(exc, openai.BadRequestError):
        return False
    if getattr(exc, "code", None) == "content_filter":
        return True
    body = exc.body if isinstance(exc.body, Mapping) else {}
    error = body.get("error", body)
    return isinstance(error, Mapping) and error.get("code") == "content_filter"


def _error_detail(body: Any) -> str | None:
    """Best-effort human message from an API error body."""
    if isinstance(body, Mapping):
        error = body.get("error", body)
        if isinstance(error, Mapping):
            message = error.get("message")
            if message:
                return str(message)
        elif isinstance(error, str):
            return error
    elif isinstance(body, str) and body.strip():
        return body.strip()
    return None
