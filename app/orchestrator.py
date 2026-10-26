"""Wires the Beyond Your Circle domain into the foundation: team, APP_META and run_task().

Pipeline for one request (see evidence/architecture.md):
  screen_user_input (code) -> guard (1 gpt-6-luna call) -> matcher agent (gpt-6-luna, tools
  search_listings / get_listing over stored public records) -> verifier (code, no model call).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.agent import AgentRunResult, AgentRuntime, AgentSpec
from app.budget import BudgetExceeded, RunBudget
from app.config import Settings
from app.domain import (
    ListingSession,
    Recommendations,
    RunOptions,
    effective_understood,
    load_prompt,
    register_domain_tools,
    verify_output,
)
from app.events import RunTrace, clip
from app.ledger import UsageLedger
from app.llm import ContentFilterError, LLMError
from app.safety import Canary, SafetyFinding, llm_guard, redact_secrets, screen_user_input, spotlight
from app.tools import ToolRegistry

log = logging.getLogger(__name__)

ENTRY_AGENT = "matcher"

# Declarative team. One model agent is enough here: retrieval is done by deterministic tools and
# checking by deterministic code, so extra LLM agents would only add calls (see architecture.md).
_TEAM: tuple[dict[str, Any], ...] = (
    {
        "name": "matcher",
        "role": (
            "Turns the request into explicit conditions, searches and reads stored public listings, "
            "and returns picks with exact quotes."
        ),
        "tools": ["search_listings", "get_listing"],
        "sub_agents": [],
        "output_model": Recommendations,
        "max_steps": 4,
    },
)

# Non-agent steps of the pipeline, shown in the UI next to the agent list.
PIPELINE: list[dict[str, str]] = [
    {"name": "screen", "kind": "code", "role": "Length limit and prompt-injection heuristics on the request."},
    {"name": "guard", "kind": "model (1 call)", "role": "gpt-6-luna classifies the request as attack or not."},
    {"name": "matcher", "kind": "model agent", "role": "Understands the request, calls the listing tools, picks and explains."},
    {"name": "verifier", "kind": "code (no model call)",
     "role": "Keeps only listings the matcher actually read and that are still available; checks quotes verbatim; "
             "attaches all facts from the stored record."},
]

APP_META: dict[str, Any] = {
    "title": "Beyond Your Circle",
    "tagline": (
        "Public Yale and New Haven events and classes where you can meet people outside SOM, each with its "
        "source page, dates and who can join, as the page states them."
    ),
    "examples": [
        "I shoot film and want hands-on help getting better, in person. I've never worked in a darkroom.",
        "I'm not technical but want to see how people at Yale actually use AI tools. Online is fine.",
        "I'm curious about drones. Is there a casual meetup where I can meet hobbyists outside SOM?",
        "Any in-person maps or GIS event where I could meet people from other fields?",
    ],
    "entry_agent": ENTRY_AGENT,
    "agents": [
        {"name": a["name"], "role": a["role"], "tools": list(a["tools"]), "sub_agents": list(a["sub_agents"])}
        for a in _TEAM
    ],
    "pipeline": PIPELINE,
}

# Domains the app may legitimately link to; other URLs with query strings are stripped from outputs.
# (Subdomains count: yale.edu covers geospatial.yale.edu.) Card links come from the stored records.
ALLOW_DOMAINS: set[str] = {"yale.edu", "creativeartsworkshop.org"}

BLOCKED_REPLY = (
    "I can't help with that request: it looks like an attempt to change my instructions or to get "
    "protected information. Please describe the kind of event or class you are looking for instead."
)
CONTENT_FILTER_REPLY = (
    "I can't finish this request: the model provider's safety filter rejected it as a possible attempt "
    "to manipulate the assistant. Please rephrase what you are looking for."
)
# Shown when the entry agent stops without answer text.
_NO_ANSWER_REPLIES = {
    "max_steps": "The agents ran out of steps before finishing. Please try a more specific question.",
    "incomplete": (
        "The model stopped before finishing its answer (for example at the output token limit), so there is "
        "no reliable answer to show. Please try a more specific question."
    ),
}


def build_team(
    settings: Settings, session: ListingSession | None = None
) -> tuple[dict[str, AgentSpec], ToolRegistry, str]:
    """Agent specs, a registry with the domain tools, and the entry agent's name.

    The per-run listing session (stored records at the real current time) is kept on
    ``registry.domain_session`` so the verifier can see which listings the agent read.
    """
    registry = ToolRegistry()
    register_domain_tools(registry, settings, session)
    specs = {
        a["name"]: AgentSpec(
            name=a["name"],
            role=a["role"],
            instructions=load_prompt(a["name"]),
            tools=list(a["tools"]),
            sub_agents=list(a["sub_agents"]),
            output_model=a["output_model"],
            max_steps=a.get("max_steps"),
        )
        for a in _TEAM
    }
    return specs, registry, ENTRY_AGENT


def _safe_message(exc: BaseException) -> str:
    """A short error message for users and traces; never contains secrets."""
    text = str(exc) if isinstance(exc, LLMError) else f"{type(exc).__name__}: {exc}"
    return clip(redact_secrets(text)[0], 300)


def _blocked_reply(findings: list[SafetyFinding], settings: Settings, user_input: str) -> str:
    if any(f.kind == "input_too_long" for f in findings):
        return (
            f"Your message is too long ({len(user_input):,} characters; the limit is "
            f"{settings.max_input_chars:,}). Please shorten it and try again."
        )
    return BLOCKED_REPLY


def _budget_reply(exc: BudgetExceeded) -> str:
    detail = str(exc).rstrip(".")
    if exc.scope == "daily_usd" and exc.limit <= 0:
        return ("AI matching is switched off on this server (its daily AI budget is set to $0). "
                "Browsing the listings still works without AI.")
    if exc.scope == "daily_usd":
        return (f"Today's AI budget for this app is used up ({detail}). It resets at 00:00 UTC. "
                "Browsing the listings still works without AI.")
    return (f"This request needed more AI work than one run is allowed ({detail}). "
            "Try a shorter, more specific request.")


async def run_task(
    user_input: str,
    *,
    llm: Any,
    settings: Settings,
    ledger: UsageLedger,
    trace: RunTrace,
    canary: Canary,
    options: RunOptions | None = None,
) -> dict:
    """Screen the input, run the agent team and emit exactly one ``final`` event. Returns its data.

    ``options`` are the conditions the user set with the form (enums only). They reach the model as a
    fixed server-written sentence and are applied in code before the verifier checks conditions.
    """
    started = time.perf_counter()
    budget = RunBudget(settings, ledger, trace.run_id)

    def record(finding: SafetyFinding, agent: str | None = None) -> None:
        trace.emit("safety", agent, **finding.to_dict())

    def finish(*, stopped_reason: str, output: dict | None = None, output_text: str = "", **extra: Any) -> dict:
        event = trace.emit(
            "final",
            None,
            ok=stopped_reason == "final",
            stopped_reason=stopped_reason,
            output=output,
            output_text=output_text,
            usage=budget.usage.to_dict(),
            cost_usd=budget.cost_usd,
            n_model_calls=sum(1 for e in trace.events if e.type == "model_call"),
            n_failed_attempts=budget.n_failed,  # failed/retried attempts: in the ledger too, usage unknown
            safety_findings=sum(1 for e in trace.events if e.type == "safety"),
            duration_ms=int((time.perf_counter() - started) * 1000),
            **extra,
        )
        _save(trace, settings)
        return event.data

    if options is not None and not options.is_set():
        options = None
    started_extra = {"options": options.public()} if options else {}
    trace.emit("run_started", None, input_preview=clip(redact_secrets(user_input)[0], 200), app_title=APP_META["title"],
               **started_extra)

    allowed, input_findings = screen_user_input(user_input, settings)
    for finding in input_findings:
        record(finding)
    if not allowed:
        return finish(stopped_reason="blocked", output_text=_blocked_reply(input_findings, settings, user_input))

    try:
        # Wall-clock limit for the whole run (guard + agent, every attempt): RUN_TIMEOUT_S.
        async with asyncio.timeout(settings.run_timeout_s):
            if settings.llm_guard:
                guard_finding = await llm_guard(
                    llm, user_input, run_id=trace.run_id, ledger=ledger, budget=budget, trace=trace
                )
                if guard_finding is not None:
                    record(guard_finding, "guard")
                    return finish(stopped_reason="blocked", output_text=BLOCKED_REPLY)

            # Flagged (medium/low) input is passed on as spotlighted data, not as raw instructions.
            task = spotlight(user_input, "user") if input_findings else user_input
            if options:
                task += "\n\n" + options.note()  # server-written, outside any spotlight block
            specs, registry, entry_agent = build_team(settings)
            runtime = AgentRuntime(
                llm=llm,
                registry=registry,
                specs=specs,
                settings=settings,
                ledger=ledger,
                trace=trace,
                budget=budget,
                canary=canary,
                allow_domains=ALLOW_DOMAINS,
            )
            result: AgentRunResult = await runtime.run_agent(entry_agent, task)
    except TimeoutError:
        record(SafetyFinding(kind="run_timeout", severity="medium", source="system",
                             detail=f"The run exceeded its {settings.run_timeout_s:g} s time limit and was stopped.",
                             action="stopped"))
        return finish(stopped_reason="timeout", limit_scope="run_seconds",
                      output_text=f"This search was stopped at the {settings.run_timeout_s:g} s time limit; no recommendation is shown. "
                                  "Please try again, ideally with a shorter request.")
    except BudgetExceeded as exc:
        record(SafetyFinding(kind="budget", severity="medium", source="system", detail=str(exc), action="stopped"))
        return finish(stopped_reason="budget", output_text=_budget_reply(exc), budget_scope=exc.scope)
    except ContentFilterError:
        # The provider refused a prompt mid-run (e.g. injected text in a document): stop as blocked.
        record(
            SafetyFinding(
                kind="prompt_injection",
                severity="high",
                source="system",
                detail="The model provider's content filter rejected a request during the run; the run was stopped.",
                action="blocked",
            )
        )
        return finish(stopped_reason="blocked", output_text=CONTENT_FILTER_REPLY)
    except asyncio.CancelledError:
        # The client went away: keep the partial trace as evidence, then let the cancellation through.
        trace.emit("error", None, message="Run cancelled before it finished (the client disconnected).")
        _save(trace, settings)
        raise
    except Exception as exc:  # LLMError and anything unexpected
        if not isinstance(exc, LLMError):
            log.exception("run %s failed", trace.run_id)
        message = _safe_message(exc)
        trace.emit("error", None, message=message)
        return finish(stopped_reason="error", output_text=f"Sorry, something went wrong while answering: {message}")

    output = result.output
    if isinstance(output, dict) and "picks" in output:
        # Conditions are checked against the user's words (as read by the model) plus the form choices.
        output = {**output, "understood": effective_understood(output.get("understood"), user_input, options)}
        output = verify_output(output, registry.domain_session)
        v = output["verification"]
        trace.emit("verification", "verifier", kind="code", **v, dropped_picks=output["dropped"],
                   excluded_picks=[{"record_id": e["record_id"], "reasons": e["reasons"]} for e in output["excluded"]])
    answer = None
    if isinstance(output, dict):
        # A summary emptied by the count check (or only whitespace) falls back to the code-built headline,
        # never to raw JSON.
        summary = output.get("summary")
        answer = (summary.strip() if isinstance(summary, str) else "") or output.get("headline") or output.get("answer")
    output_text = answer if isinstance(answer, str) and answer.strip() else result.output_text
    if not output_text:
        output_text = _NO_ANSWER_REPLIES.get(result.stopped_reason, "")
    return finish(stopped_reason=result.stopped_reason, output=output, output_text=output_text)


def _save(trace: RunTrace, settings: Settings) -> None:
    try:
        trace.save(settings.runs_dir)
    except (OSError, ValueError) as exc:
        log.warning("could not save trace %s: %s", trace.run_id, exc)
