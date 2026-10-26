"""Domain tools over the stored public records: search_listings and get_listing.

The tools read only what the collector stored (cached refresh, else the committed snapshot);
they never touch the network. A per-run ``ListingSession`` remembers which record IDs the model
actually received, so the verifier can reject IDs the model did not retrieve.
Page text is external content: both tools are ``untrusted_output`` (scanned and spotlighted).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Callable, Literal

from pydantic import Field

from app.collect.records import Record
from app.collect.sources import SOURCES
from app.collect.store import SourceResult, load_source
from app.config import Settings
from app.discover import build_discovery, now_ny, term_in
from app.tools import ToolRegistry, tool

MAX_TERMS = 10
MAX_RESULTS = 12
_ID_RE = re.compile(r"^[a-z0-9-]{3,80}$")
_SECTION_ORDER = {"this_week": 0, "coming": 1, "ongoing": 2, "date_unknown": 3}
_SECTION_LABEL = {"this_week": "this week", "coming": "coming weeks", "ongoing": "ongoing program or class",
                  "date_unknown": "date not stated"}


@dataclass
class ListingSession:
    """Stored records and the discovery view for one run (real current time)."""

    now: datetime
    results: list[SourceResult]
    records: dict[str, Record]
    cards: dict[str, dict]  # available (not past, not ruled out) records -> discover card
    sections: dict[str, str]  # record_id -> section
    unavailable: dict[str, str]  # record_id -> reason (ruled out by the page)
    seen_ids: set[str] = field(default_factory=set)  # returned by any tool this run
    read_ids: set[str] = field(default_factory=set)  # returned by get_listing this run
    search_terms: set[str] = field(default_factory=set)  # interest keywords the agent searched with
    data_note: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, settings: Settings, *, now: datetime | None = None, snapshot_dir: Path | None = None) -> "ListingSession":
        results = [load_source(sid, runs_dir=settings.runs_dir, snapshot_dir=snapshot_dir) for sid in SOURCES]
        return cls.from_results(results, now=now or now_ny())

    @classmethod
    def from_results(cls, results: list[SourceResult], *, now: datetime) -> "ListingSession":
        view = build_discovery(results, now=now)
        cards: dict[str, dict] = {}
        sections: dict[str, str] = {}
        for name, items in view["sections"].items():
            for card in items:
                cards[card["id"]] = card
                sections[card["id"]] = name
        records = {r.record_id: r for res in results for r in res.records}
        unavailable = {n["id"]: n["reason"] for n in view["not_available"]}
        data_note = [
            {"source": s["name"], "data": s["data_mode"], "collected": s["collected_at_text"]} for s in view["sources"]
        ]
        session = cls(now, results, records, cards, sections, unavailable, data_note=data_note)
        session.view = view  # type: ignore[attr-defined]
        return session


def _haystack(card: dict) -> str:
    return " ".join([card["title"], " ".join(card["topics"]), card["summary"] or "",
                     " ".join(card["eligibility_open"]), " ".join(card["eligibility_check"])])


def _matches(terms: list[str], text: str) -> list[str]:
    return [t for t in terms if term_in(t, text)]


def _when(card: dict) -> str | None:
    if card["when_text"]:
        return card["when_text"]
    if card["next_session"]:
        more = len(card["upcoming_sessions"]) - 1
        return f"next session {card['next_session']['when_text']}" + (f" (+{more} more listed)" if more > 0 else "")
    return card["date_text"] or None


def search(session: ListingSession, interests: list[str], participation: str, when: str, max_results: int) -> dict:
    terms = []
    for raw in interests[:MAX_TERMS]:
        term = " ".join(str(raw).split())[:40].strip().lower()
        if len(term) >= 2 and term not in terms:
            terms.append(term)
    session.search_terms.update(terms)
    # A time window must not hide ongoing programs and classes: their sessions are checked against the
    # window later by code (conditions.evaluate). Single-date events outside the window stay out (G-12).
    view = build_discovery(session.results, now=session.now, mode=participation, when="all")
    keep = {"this_week": {"this_week", "ongoing"}, "coming": {"coming", "ongoing"}, "ongoing": {"ongoing"}}.get(when)
    scored = []
    for name, items in view["sections"].items():
        if keep is not None and name not in keep:
            continue
        for card in items:
            hits = _matches(terms, _haystack(card))
            scored.append((-len(hits), _SECTION_ORDER[name], card["start"] or "", name, card, hits))
    scored.sort(key=lambda x: x[:3])
    limit = max(1, min(int(max_results), MAX_RESULTS))
    matched = [s for s in scored if s[5]]
    nearby = [s for s in scored if not s[5]][:3]  # a few non-matching items, for honest exploration
    chosen = (matched + nearby)[:limit]
    out = []
    for _, _, _, name, card, hits in chosen:
        session.seen_ids.add(card["id"])
        out.append({
            "record_id": card["id"],
            "title": card["title"],
            "kind": card["kind"],
            "section": _SECTION_LABEL[name],
            "when": _when(card),
            "format": card["format_label"] or "not stated",
            "matched_terms": hits,
            "summary": (card["summary"] or "")[:240],
        })
    return {
        "now": view["windows"]["now_text"],
        "this_week_window": view["windows"]["this_week"]["label"],
        "data_sources": session.data_note,
        "filters_used": {"interests": terms, "participation": participation, "when": when},
        "results": out,
        "n_matching": len(matched),
        "n_available_total": sum(len(v) for v in view["sections"].values()),
        "ruled_out_by_page": [{"title": n["title"], "reason": n["reason"]} for n in view["not_available"][:3]],
        "note": "Only these stored public listings exist. Call get_listing before recommending any record_id.",
    }


def detail(session: ListingSession, record_id: str) -> dict:
    record_id = record_id.strip()
    if not _ID_RE.fullmatch(record_id) or record_id not in session.records:
        raise ValueError("no listing with that record_id; use a record_id returned by search_listings")
    if record_id not in session.cards:
        reason = session.unavailable.get(record_id, "it is in the past")
        raise ValueError(f"this listing is not available ({reason}); do not recommend it")
    session.seen_ids.add(record_id)
    session.read_ids.add(record_id)
    r, card = session.records[record_id], session.cards[record_id]
    return {
        "record_id": record_id,
        "title": r.title,
        "kind": r.kind,
        "section": _SECTION_LABEL[session.sections[record_id]],
        "when": _when(card),
        "upcoming_sessions": [s["when_text"] + (f" ({s['status_text']})" if s["status_text"] else "")
                              for s in card["upcoming_sessions"][:4]],
        "date_text": r.date_text,
        "format": r.format_text or "not stated",
        "location": r.location_text or "not stated",
        "organizer": r.organizer,
        "cost": r.cost_text or "not stated",
        "registration": r.registration_text or ("registration link on the page" if card["registration_url"] else "not stated"),
        "capacity": r.capacity_text or "not stated",
        "conditions_stated": r.eligibility_texts,
        "not_stated": card["not_stated"],
        "warnings": r.warnings,
        "topics": r.topics,
        "summary": r.summary,
        "source": f"{card['source_name']} ({card['publisher_type']}), collected {card['collected_at_text']}",
        "page": card["url"],
    }


def register_domain_tools(registry: ToolRegistry, settings: Settings, session: ListingSession | None = None) -> list[str]:
    """Register search_listings and get_listing; the session is kept on ``registry.domain_session``."""
    session = session or ListingSession.load(settings)
    registry.domain_session = session  # type: ignore[attr-defined]

    @tool(
        name="search_listings",
        description=(
            "Search the stored public listings (Yale and New Haven events, classes and ongoing programs). "
            "Returns up to max_results items, best keyword matches first, then a few non-matching nearby items. "
            "interests: short lowercase keywords and close synonyms, e.g. ['photography', 'photo', 'darkroom', 'film']. "
            "participation: 'in_person', 'online' or 'any' (items whose page does not say stay included). "
            "when: 'this_week' (next 7 days), 'coming' (later single-date events), 'ongoing' (recurring "
            "programs and classes) or 'all'; 'this_week' and 'coming' also return ongoing programs and classes, whose "
            "sessions the app checks against the window. Times are America/New_York."
        ),
        untrusted_output=True,
        max_output_chars=7000,
    )
    def search_listings(
        interests: Annotated[list[str], Field(description="Keywords and close synonyms (max 10).")],
        participation: Literal["any", "in_person", "online"],
        when: Literal["all", "this_week", "coming", "ongoing"],
        max_results: Annotated[int, Field(description="1-12; 8 is usually enough.")],
    ) -> str:
        return json.dumps(search(session, interests, participation, when, max_results), ensure_ascii=False)

    @tool(
        name="get_listing",
        description=(
            "Full details of one stored listing by record_id (as returned by search_listings): dates in "
            "America/New_York, format, location, cost, registration, capacity, stated conditions, what the page "
            "does not state, warnings and source. Quote from this text when you explain a match."
        ),
        untrusted_output=True,
        max_output_chars=6000,
    )
    def get_listing(record_id: str) -> str:
        return json.dumps(detail(session, record_id), ensure_ascii=False)

    tools: tuple[Callable[..., Any], ...] = (search_listings, get_listing)
    for item in tools:
        registry.register(item)
    return [item.name for item in tools]
