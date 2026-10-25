"""FastAPI app: JSON API, NDJSON run streaming and the static web UI (one process, same origin)."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import config, discover
from app.collect.fetch import SimulatedOutageTransport
from app.collect.sources import SOURCES
from app.collect.store import load_source, refresh_all
from app.config import MODEL, REPO_DIR, ConfigError, Settings
from app.domain import RunOptions
from app.events import Event, RunTrace
from app.ledger import UsageLedger
from app.orchestrator import APP_META, run_task
from app.pricing import Usage
from app.safety import Canary, SafetyFinding, redact_data, redact_secrets

log = logging.getLogger(__name__)

VERSION = "0.1.0"
WEB_DIR = REPO_DIR / "web"
NDJSON = "application/x-ndjson"
_DISCONNECT_POLL_S = 1.0
_DONE = object()  # queue sentinel: the run task has finished

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # img-src/connect-src 'self' also stops a manipulated answer from leaking data via external images.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
}


# --------------------------------------------------------------------------- rate limiting


class RateLimiter:
    """In-memory sliding window: at most ``limit`` hits per ``window_s`` seconds per key."""

    _MAX_KEYS = 10_000

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_s: float) -> tuple[bool, int]:
        """Record a hit if allowed. Returns (allowed, retry_after_seconds)."""
        if limit <= 0:
            return True, 0
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > self._MAX_KEYS:
                self._prune(now, window_s)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= window_s:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(1, int(window_s - (now - hits[0])) + 1)
            hits.append(now)
            return True, 0

    def _prune(self, now: float, window_s: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= window_s]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# --------------------------------------------------------------------------- dependencies


class _Deps:
    """Lazily created singletons; tests replace them with ``set_dependencies``."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.limiter = RateLimiter()
        self.llm: Any = None
        self.ledger: UsageLedger | None = None
        self.settings: Settings | None = None
        self.canary: Canary | None = None
        # public-source browsing (deterministic, no model calls)
        self.collect_refresh: Any = None  # tests inject a simulated refresh
        self.snapshot_dir: Any = None  # None = committed data/snapshots/
        self.now: Any = None  # tests inject a fixed, labelled reference time
        self.refresh_running = False
        self.last_refresh_mono: float | None = None
        self.last_refresh_at: str | None = None


_deps = _Deps()


def set_dependencies(
    llm: Any = None,
    ledger: UsageLedger | None = None,
    settings: Settings | None = None,
    canary: Canary | None = None,
    collect_refresh: Any = None,
    snapshot_dir: Any = None,
    now: Any = None,
) -> None:
    """Replace the singletons (None = create lazily from the environment again) and reset the rate limiter."""
    with _deps.lock:
        _deps.llm = llm
        _deps.ledger = ledger
        _deps.settings = settings
        _deps.canary = canary
        _deps.collect_refresh = collect_refresh
        _deps.snapshot_dir = snapshot_dir
        _deps.now = now
        _deps.refresh_running = False
        _deps.last_refresh_mono = None
        _deps.last_refresh_at = None
    _deps.limiter.reset()


def get_app_settings() -> Settings:
    return _deps.settings or config.get_settings()


def get_ledger() -> UsageLedger:
    with _deps.lock:
        if _deps.ledger is None:
            _deps.ledger = UsageLedger(get_app_settings().runs_dir / "usage.jsonl")
        return _deps.ledger


def get_canary() -> Canary:
    with _deps.lock:
        if _deps.canary is None:
            _deps.canary = Canary()
        return _deps.canary


def simulated_llm_kind() -> str | None:
    """``LLM_SIMULATE=timeout|error``: labelled demo mode in which every model call fails without a network call."""
    from app.llm import SIMULATED_LLM_KINDS

    kind = os.environ.get("LLM_SIMULATE", "").strip().lower()
    return kind if kind in SIMULATED_LLM_KINDS else None


def get_llm() -> Any:
    """The model client; raises ConfigError (with a fix-it message) when the key is missing."""
    kind = simulated_llm_kind()
    if kind:  # checked before the real client is built: no key, no network, no ledger rows
        from app.llm import SimulatedFailureLLM

        raw = os.environ.get("LLM_SIMULATE_DELAY_S", "").strip()
        try:
            delay = float(raw) if raw else 8.0
        except ValueError:
            delay = 8.0
        return SimulatedFailureLLM(kind, delay if 0 <= delay <= 120 else 8.0)
    with _deps.lock:
        if _deps.llm is None:
            from app.llm import LLMClient

            _deps.llm = LLMClient(timeout_s=get_app_settings().request_timeout_s)
        return _deps.llm


# --------------------------------------------------------------------------- app


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (does not buffer or interfere with streaming responses)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


app = FastAPI(title=APP_META["title"], version=VERSION, docs_url=None, redoc_url=None)
app.add_middleware(SecurityHeadersMiddleware)


def _error(message: str, status_code: int, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status_code)


@app.get("/", include_in_schema=False)
async def index() -> Any:
    page = WEB_DIR / "index.html"
    if page.is_file():
        return FileResponse(page, headers={"Cache-Control": "no-cache"})
    return HTMLResponse("<!doctype html><title>UI missing</title><p>web/index.html was not found.</p>", status_code=503)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "model": MODEL,
        "key_configured": config.key_configured(),
        "env_files": config.env_files_loaded(),
        "version": VERSION,
        "simulated_llm": simulated_llm_kind(),
    }


def _today_cost() -> float:
    try:
        return get_ledger().today_cost_usd()
    except OSError:
        return 0.0


@app.get("/api/meta")
async def meta() -> dict:
    settings = get_app_settings()
    data = copy.deepcopy(APP_META)
    data["model"] = MODEL
    data["limits"] = {
        "run_budget_usd": settings.run_budget_usd,
        "daily_budget_usd": settings.daily_budget_usd,
        "max_input_chars": settings.max_input_chars,
        "max_steps_per_agent": settings.max_steps_per_agent,
    }
    data["today_cost_usd"] = _today_cost()
    return data


@app.get("/api/runs")
async def runs() -> dict:
    return {"runs": get_ledger().run_summaries(limit=50)}


@app.get("/api/runs/{run_id}")
async def run_detail(run_id: str) -> Any:
    trace = RunTrace.load(get_app_settings().runs_dir, run_id)
    if trace is None:
        return _error("Run not found.", 404)
    # Events are redacted when emitted; this also covers traces written by older versions.
    return redact_data(trace)


@app.get("/api/stats")
async def stats() -> dict:
    settings = get_app_settings()
    data = get_ledger().stats(settings.runs_per_user_per_month)
    data["today_cost_usd"] = _today_cost()
    data["daily_budget_usd"] = settings.daily_budget_usd
    return data


# --------------------------------------------------------------------------- public-source browsing


def _refresh_cooldown_s() -> int:
    raw = os.environ.get("REFRESH_COOLDOWN_S", "").strip()
    return int(raw) if raw.isdigit() else 300  # be polite to the source sites


def _refresh_state() -> dict:
    wait = 0
    if _deps.last_refresh_mono is not None:
        wait = max(0, int(_refresh_cooldown_s() - (time.monotonic() - _deps.last_refresh_mono)))
    return {
        "running": _deps.refresh_running,
        "last_refresh_at": _deps.last_refresh_at,
        "last_refresh_text": discover.et_stamp(_deps.last_refresh_at),
        "next_allowed_in_s": wait,
        "simulated_outage_mode": _simulate_outage(),
    }


def _simulate_outage() -> bool:
    return os.environ.get("COLLECT_SIMULATE_OUTAGE", "").strip().lower() in ("1", "true", "yes")


def _stored_results() -> list:
    runs_dir = get_app_settings().runs_dir
    return [load_source(sid, runs_dir=runs_dir, snapshot_dir=_deps.snapshot_dir) for sid in SOURCES]


def _default_refresh() -> list:
    simulate = _simulate_outage()
    return refresh_all(
        runs_dir=get_app_settings().runs_dir,
        snapshot_dir=_deps.snapshot_dir,
        transport=SimulatedOutageTransport() if simulate else None,
        simulated=simulate,
    )


@app.get("/api/discover")
async def discover_view(q: str = "", interest: str = "", mode: str = "any", when: str = "all") -> dict:
    """Stored public records grouped into this week / coming / ongoing. No network, no model calls."""
    now = _deps.now() if _deps.now else discover.now_ny()
    data = discover.build_discovery(
        _stored_results(), now=now, q=q, interest=interest or None, mode=mode, when=when,
        fixed_now_for_test=_deps.now is not None,
    )
    data["refresh"] = _refresh_state()
    return data


@app.get("/api/sources")
async def sources() -> dict:
    data = discover.build_discovery(_stored_results(), now=_deps.now() if _deps.now else discover.now_ny())
    return {"sources": data["sources"], "not_connected": data["not_connected"], "refresh": _refresh_state()}


@app.post("/api/refresh")
async def refresh_sources() -> Any:
    """Bounded re-collection from the connected public sources (about a minute; polite delays)."""
    if _deps.refresh_running:
        return _error("A refresh is already running. Please wait for it to finish.", 409, refresh=_refresh_state())
    state = _refresh_state()
    if state["next_allowed_in_s"] > 0:
        return _error(
            f"Sources were refreshed at {state['last_refresh_text']}. To be polite to the source sites, "
            f"the next refresh is possible in {state['next_allowed_in_s']} s.",
            429,
            refresh=state,
        )
    _deps.refresh_running = True
    try:
        results = await asyncio.to_thread(_deps.collect_refresh or _default_refresh)
    finally:
        _deps.refresh_running = False
        _deps.last_refresh_mono = time.monotonic()
        _deps.last_refresh_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary = [
        {
            "source_id": r.source_id,
            "data_mode": r.data_mode,
            "outcome": (r.status or {}).get("last_outcome"),
            "collected_at": r.collected_at,
            "collected_at_text": discover.et_stamp(r.collected_at),
            "n_records": len(r.records),
            "errors": sorted({e.get("kind", "?") for e in (r.status or {}).get("errors", [])}),
            "simulated": bool((r.status or {}).get("simulated")),
        }
        for r in results
    ]
    return {"results": summary, "refresh": _refresh_state()}


def max_body_bytes(settings: Settings) -> int:
    """Largest accepted /api/run body: room for a max-length question even if every character
    is JSON-escaped (``\\u0000`` is 6 bytes), plus slack. Larger bodies are refused unread."""
    return settings.max_input_chars * 6 + 4096


async def _read_body(request: Request, limit: int) -> bytes | None:
    """The request body, or None as soon as it is (or declares to be) larger than ``limit`` bytes."""
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                return None
        except ValueError:
            return None
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/api/run")
async def run(request: Request) -> Any:
    settings = get_app_settings()
    raw = await _read_body(request, max_body_bytes(settings))
    if raw is None:
        return _error(f"Request too large. Questions are limited to {settings.max_input_chars:,} characters.", 413)
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return _error('Send a JSON body like {"input": "your question"}.', 400)
    text = body.get("input") if isinstance(body, dict) else None
    if not isinstance(text, str) or not text.strip():
        return _error("Please type a question first.", 400)
    text = text.strip()
    # Optional form conditions: enums only, validated before any model call or rate-limit slot.
    raw_options = body.get("options")
    options: RunOptions | None = None
    if raw_options not in (None, {}):
        try:
            if not isinstance(raw_options, dict):
                raise ValueError("options must be an object")
            options = RunOptions.model_validate(raw_options)
        except (ValueError, ValidationError):
            return _error("Unsupported options. Allowed: som_student (true), participation (in_person, online, "
                          "either), time_window (this_week, next_few_weeks).", 400)
        if not options.is_set():
            options = None

    try:
        llm = get_llm()
    except ConfigError as exc:  # the UI still works and shows the setup hint
        return _single_error_stream(redact_secrets(str(exc))[0])

    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = _deps.limiter.check(client_ip, settings.rate_limit_runs, settings.rate_limit_window_s)
    if not allowed:
        finding = SafetyFinding(
            kind="rate_limited",
            severity="medium",
            source="system",
            detail=f"More than {settings.rate_limit_runs} runs in {settings.rate_limit_window_s}s from one client.",
            action="blocked",
        )
        log.warning("safety finding: %s", json.dumps(finding.to_dict()))
        response = _error(
            f"Too many runs from your address. Please wait {retry_after} s and try again.",
            429,
            retry_after_s=retry_after,
            finding=finding.to_dict(),
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    trace = RunTrace()
    queue: asyncio.Queue = asyncio.Queue()
    trace.queue = queue
    extra = {"options": options} if options else {}  # only when set: older run_task stubs keep working
    task = asyncio.create_task(
        run_task(text, llm=llm, settings=settings, ledger=get_ledger(), trace=trace, canary=get_canary(), **extra)
    )

    def on_done(t: asyncio.Task) -> None:
        queue.put_nowait(_DONE)
        if not t.cancelled() and t.exception() is not None:
            log.error("run %s crashed", trace.run_id, exc_info=t.exception())

    task.add_done_callback(on_done)
    return StreamingResponse(
        _stream_run(request, trace, queue, task, settings),
        media_type=NDJSON,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Run-Id": trace.run_id},
    )


# --------------------------------------------------------------------------- streaming helpers


def _elapsed_ms(trace: RunTrace) -> int:
    try:
        started = datetime.fromisoformat(trace.started_at.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((datetime.now(timezone.utc) - started).total_seconds() * 1000))


def _encode(item: Any) -> str:
    if isinstance(item, Event):
        line = item.to_json()
    elif isinstance(item, dict):
        line = json.dumps(item, ensure_ascii=False, default=str)
    else:
        line = str(item)
    return redact_secrets(line)[0] + "\n"  # defense in depth: no key ever leaves the server


async def _stream_run(
    request: Request, trace: RunTrace, queue: asyncio.Queue, task: asyncio.Task, settings: Settings
) -> AsyncIterator[str]:
    """Yield events until ``final``. Cancels the run if the client disconnects; always ends the stream."""
    finished = False
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_DISCONNECT_POLL_S)
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    log.info("client disconnected; cancelling run %s", trace.run_id)
                    return
                continue
            if item is _DONE:
                break
            yield _encode(item)
            if getattr(item, "type", None) == "final":
                finished = True
                return

        # The task ended without a final event: report it so the stream still terminates cleanly.
        finished = True
        exc = None if task.cancelled() else task.exception()
        reason = type(exc).__name__ if exc else "cancelled"
        yield _encode(trace.emit("error", None, message=f"The run stopped unexpectedly ({reason})."))
        # Totals so far come from the last model_call event's running figures.
        last_call = next((e.data for e in reversed(trace.events) if e.type == "model_call"), {})
        yield _encode(
            trace.emit(
                "final",
                None,
                ok=False,
                stopped_reason="error",
                output=None,
                output_text="Sorry, the run stopped unexpectedly. Please try again.",
                usage=last_call.get("run_usage") or Usage().to_dict(),
                cost_usd=last_call.get("run_cost_usd") or 0.0,
                n_model_calls=sum(1 for e in trace.events if e.type == "model_call"),
                safety_findings=sum(1 for e in trace.events if e.type == "safety"),
                duration_ms=_elapsed_ms(trace),
            )
        )
        try:
            trace.save(settings.runs_dir)
        except (OSError, ValueError):
            pass
    finally:
        if not finished and not task.done():
            task.cancel()


def _single_error_stream(message: str) -> StreamingResponse:
    event = RunTrace().emit("error", None, message=message)

    async def body() -> AsyncIterator[str]:
        yield _encode(event)

    return StreamingResponse(body(), media_type=NDJSON, headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=WEB_DIR, check_dir=False), name="static")
