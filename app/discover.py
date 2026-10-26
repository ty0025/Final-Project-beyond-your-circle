"""Deterministic browsing of collected public records (no model calls).

Sections (America/New_York, real IANA rules via zoneinfo; never a fixed UTC offset):
- ``this_week``: single-date events starting before midnight at the end of day 7 (today + 6).
- ``coming``: single-date events after that.
- ``ongoing``: programs (courses/series; their dated sessions stay inside them) and communities.
- ``date_unknown``: events whose page gives no machine-readable date (never shown as "this week").

This is a keyword filter, not an AI recommendation. Unknown stays unknown: a missing field is
shown as "not stated", and only explicit page text moves an item to "known not available".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from app.collect.records import Record
from app.collect.sources import NOT_CONNECTED, SOURCES
from app.collect.store import SourceResult

NY = ZoneInfo("America/New_York")
THIS_WEEK_DAYS = 7
SECTIONS = ("this_week", "coming", "ongoing", "date_unknown")
MODES = ("any", "in_person", "online")
WHENS = ("all", "this_week", "coming", "ongoing")

# Quick-pick interests (the test interests); free-text search works for any other interest.
INTERESTS: dict[str, dict[str, Any]] = {
    "photography": {
        "label": "Photography",
        "terms": ["photo", "photos", "photography", "photographer", "camera", "cameras", "darkroom", "film", "lens"],
    },
    "sports": {
        "label": "Sports & games",
        "terms": ["sport", "sports", "intramural", "intramurals", "league", "tournament", "pickup", "soccer",
                  "basketball", "volleyball", "tennis", "pickleball", "running", "climbing", "fitness",
                  "watch party", "game day"],
    },
    "ai": {
        "label": "AI for non-technical people",
        "terms": ["ai", "artificial intelligence", "genai", "generative ai", "chatbot", "chatbots", "bot",
                  "prompt", "promptathon", "machine learning", "llm"],
    },
}

KIND_LABELS = {"event": "Event", "program": "Program / series", "community": "Community"}
PUBLISHER_LABELS = {"official_yale": "Official Yale", "community_nonprofit": "Community nonprofit"}
MODE_LABELS = {"in_person": "In person", "online": "Online", "hybrid": "Hybrid"}
MISSING_LABELS = {
    "organizer": "organizer",
    "when": "date/time",
    "format": "in person or online",
    "location_text": "location",
    "eligibility_texts": "who can join",
    "cost_text": "cost",
    "registration": "how to register",
    "capacity_text": "capacity",
}
REGISTRATION_NOTE = "A registration link does not guarantee a spot. Registration happens on the organizer's site."

_CLOSED = re.compile(r"\b(registration (is )?closed|sold out|fully booked|at capacity|event is full|waitlist only)\b", re.I)
# "Open to all" names nobody only when the phrase ends there or goes on with ages, levels, comers or "(who are)
# interested": "open to all SOM students / New Haven residents" names a group. Shared with the Find checks
# (app/domain/conditions.py), so Browse and Find read the same wording the same way.
OPEN_TO_ALL = (r"open to all(?=\s*(?:[.,;:!?)–—-]|$)|\s+(?:ages|levels|skill levels|experience levels|comers)\b|"
               r"\s+(?:who are )?interested(?:\s+in\b|\s*(?:[.,;:!?)]|$)))")
# "Open to everyone / anyone" names nobody only when it ends there or goes on with "interested", ages or
# "regardless": "open to anyone with a valid Yale ID / affiliated with Yale / at Yale" names a group.
OPEN_TO_ANYONE = (r"open to (?:everyone|anyone)(?=\s*(?:[.,;:!?)–—-]|$)|"
                  r"\s+(?:who (?:is |are )?)?interested\b|\s+(?:of all ages|regardless)\b)")
# Wording that turns the public away ("not open to the public", "..., not the general public"): never read as open.
NOT_OPEN = r"\bnot (?:be )?open to\b|\bclosed to the public\b|\bnot (?:to |for )?the (?:general )?public\b"
_OPEN = re.compile(
    r"\b(no [a-z ]*experience (is )?(necessary|needed|required)|all (experience|skill) levels|beginners? (are )?welcome|"
    rf"{OPEN_TO_ALL}|{OPEN_TO_ANYONE}|open to the public|"
    r"everyone is welcome|all are welcome|free and open to the public)\b",
    re.I,
)
_NOT_OPEN = re.compile(NOT_OPEN, re.I)
# Explicit restrictions that rule out a Yale SOM graduate student.
_EXCLUDES = re.compile(
    r"\b(undergraduates? only|undergraduate students only|for undergraduates only|faculty only|staff only|"
    r"faculty and staff only|employees only|high school students only|children only|kids only)\b",
    re.I,
)
_DEADLINE = re.compile(
    r"\b(?:register|registration|rsvp|sign up|apply)\w*\s+(?:by|before|closes|deadline:?|due)\s+"
    r"(?:(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(?P<day>\d{1,2})|(?P<m>\d{1,2})/(?P<d>\d{1,2}))",
    re.I,
)
# "Registration Dates: September 2nd - September 16th" -> the end of the range is the deadline.
_DEADLINE_RANGE = re.compile(
    r"\bregistration dates?:?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?"
    r"\s*[–-]\s*(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?",
    re.I,
)
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# --------------------------------------------------------------------------- time helpers


def now_ny() -> datetime:
    return datetime.now(NY)


def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return dt.astimezone(NY) if dt.tzinfo else None  # naive times are not trusted


def ny_midnight(day: date) -> datetime:
    """Local midnight in New York for ``day`` (offset chosen by the real DST rules)."""
    return datetime.combine(day, time(0), tzinfo=NY)


def term_in(term: str, text: str) -> bool:
    """True if an interest word occurs in ``text`` (shared by Browse, the search tool and the verifier).

    A whole word, any case ("AI", "ai"). A short acronym (2-4 letters) also counts as the capitalised end
    of a compound word: "GeoAI", "GenAI", "OpenAI", "ArcGIS", "AutoML" (G-18). That second check is
    case-sensitive, so ordinary words such as "maintain", "said" or "Thai" never match "ai".
    """
    if re.search(rf"\b{re.escape(term)}\b", text, re.I):
        return True
    return bool(re.fullmatch(r"[A-Za-z]{2,4}", term)) and re.search(rf"(?<=[a-z]){term.upper()}\b", text) is not None


@dataclass(frozen=True)
class Windows:
    now: datetime
    this_week_start: datetime
    this_week_end: datetime  # exclusive: midnight starting day 8

    def to_dict(self) -> dict:
        last_day = (self.this_week_end - timedelta(days=1)).date()
        return {
            "now": self.now.isoformat(timespec="seconds"),
            "now_text": f"{_day(self.now.date())}, {_clock(self.now)} {self.now.tzname()}",
            "timezone": "America/New_York",
            "this_week": {
                "start": self.this_week_start.isoformat(),
                "end": self.this_week_end.isoformat(),
                "label": f"{_day(self.this_week_start.date())} – {_day(last_day)}",
            },
            "coming": {"start": self.this_week_end.isoformat(), "label": f"From {_day(self.this_week_end.date())}"},
        }


def windows_for(now: datetime) -> Windows:
    now = now.astimezone(NY)
    today = now.date()
    return Windows(now, ny_midnight(today), ny_midnight(today + timedelta(days=THIS_WEEK_DAYS)))


def _day(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def _clock(dt: datetime) -> str:
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def when_text(start: datetime | None, end: datetime | None) -> str | None:
    if start is None:
        return None
    text = f"{_day(start.date())}, {start.year} · {_clock(start)}"
    if end is not None:
        text += f"–{_clock(end)}" if end.date() == start.date() else f" – {_day(end.date())} {_clock(end)}"
    return f"{text} {start.tzname()}"  # EDT or EST from the real rules


def et_stamp(iso: str | None) -> str | None:
    dt = _parse(iso)
    return f"{_day(dt.date())}, {_clock(dt)} {dt.tzname()}" if dt else None


# --------------------------------------------------------------------------- record helpers


def safe_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    return url.strip() if parts.scheme in ("http", "https") and parts.netloc else None


def canonical_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _is_past(start: datetime | None, end: datetime | None, now: datetime) -> bool:
    if end is not None:
        return end < now
    if start is not None:
        return start.date() < now.date()  # no end time: keep it through its own day
    return False


def _match_terms(record: Record, q: str, interest: str | None) -> tuple[bool, list[str]]:
    haystack = " ".join([record.title, " ".join(record.topics), record.summary or "", " ".join(record.eligibility_texts)])
    terms: list[str] = []
    if interest and interest in INTERESTS:
        terms += INTERESTS[interest]["terms"]
    words = [w for w in re.split(r"[\s,;]+", q.strip()) if len(w) >= 2]
    if not terms and not words:
        return True, []
    hits = [t for t in terms + words if term_in(t, haystack)]
    interest_ok = not terms or any(t in hits for t in terms)  # any term of the chosen interest
    words_ok = all(w in hits for w in words)  # every typed word
    return interest_ok and words_ok, sorted(set(hits), key=str.lower)


def _deadline(record: Record, ref_year: int) -> tuple[str | None, datetime | None]:
    text = " ".join([record.registration_text or "", *record.eligibility_texts, record.summary or ""])
    m = _DEADLINE.search(text) or _DEADLINE_RANGE.search(text)
    if not m:
        return None, None
    if m.group("mon"):
        month, day = _MONTHS[m.group("mon")[:3].lower()], int(m.group("day"))
    else:
        month, day = int(m.group("m")), int(m.group("d"))
    try:
        due = datetime.combine(date(ref_year, month, day), time(23, 59), tzinfo=NY)
    except ValueError:
        return m.group(0), None
    return m.group(0), due


@dataclass
class _Item:
    record: Record
    source_id: str
    data_mode: str
    also_at: list[dict]


def _dedupe(items: list[_Item]) -> tuple[list[_Item], int]:
    by_url: dict[tuple[str, str], _Item] = {}
    for it in items:
        # One page can hold several listings (e.g. one league page, many sports): URL + title.
        key = (canonical_url(it.record.url), _norm_title(it.record.title))
        if key not in by_url or it.record.collected_at > by_url[key].record.collected_at:
            by_url[key] = it
    merged = 0
    by_event: dict[tuple[str, str], _Item] = {}
    out: list[_Item] = []
    for it in by_url.values():
        start = _parse(it.record.start)
        if it.record.kind != "event" or start is None:
            out.append(it)
            continue
        key = (_norm_title(it.record.title), start.date().isoformat())
        if key in by_event:
            keep = by_event[key]
            if len(it.record.missing) < len(keep.record.missing):
                keep, it = it, keep
                by_event[key] = keep
                out[out.index(it)] = keep
            keep.also_at.append({"source_id": it.source_id, "url": safe_url(it.record.url)})
            merged += 1
        else:
            by_event[key] = it
            out.append(it)
    return out, merged + (len(items) - len(by_url))


# --------------------------------------------------------------------------- main entry


def build_discovery(
    results: Iterable[SourceResult],
    *,
    now: datetime,
    q: str = "",
    interest: str | None = None,
    mode: str = "any",
    when: str = "all",
    fixed_now_for_test: bool = False,
) -> dict:
    """Group, filter and explain stored records. ``now`` is the real current time in the app."""
    mode = mode if mode in MODES else "any"
    when = when if when in WHENS else "all"
    interest = interest if interest in INTERESTS else None
    q = (q or "")[:100]
    win = windows_for(now)
    results = list(results)

    items = [_Item(r, res.source_id, res.data_mode, []) for res in results for r in res.records]
    items, n_duplicates = _dedupe(items)

    sections: dict[str, list[dict]] = {s: [] for s in SECTIONS}
    hidden: list[dict] = []
    n_past = n_filtered = 0
    for it in items:
        r = it.record
        start, end = _parse(r.start), _parse(r.end)
        card = _card(it, win)

        # 1) past items are hidden (counted)
        if r.kind == "event" and _is_past(start, end, win.now):
            n_past += 1
            continue
        if r.kind == "program" and r.sessions and card["next_session"] is None and not card["undated_sessions"]:
            n_past += 1
            continue

        # 2) explicit page facts that rule the item out
        reason = _known_unavailable(r, card, win)
        if reason:
            hidden.append({"id": r.record_id, "title": r.title, "url": card["url"], "reason": reason})
            continue

        # 3) user filters (unknown values stay visible with a flag; known mismatches are hidden)
        if mode != "any" and r.format is not None and r.format not in (mode, "hybrid"):
            n_filtered += 1
            continue
        ok, hits = _match_terms(r, q, interest)
        if not ok:
            n_filtered += 1
            continue
        card["matched_terms"] = hits
        card["format_unknown_for_filter"] = mode != "any" and r.format is None

        if r.kind == "event":
            section = "date_unknown" if start is None else ("this_week" if start < win.this_week_end else "coming")
        else:
            section = "ongoing"
        if when != "all" and section != when:
            n_filtered += 1
            continue
        sections[section].append(card)

    for name in ("this_week", "coming"):
        sections[name].sort(key=lambda c: c["start"] or "")
    sections["ongoing"].sort(key=lambda c: (c["next_session"] or {}).get("start") or "9999")

    return {
        "now": win.now.isoformat(timespec="seconds"),
        "fixed_now_for_test": fixed_now_for_test,
        "windows": win.to_dict(),
        "filters": {"q": q, "interest": interest, "mode": mode, "when": when},
        "interests": {k: v["label"] for k, v in INTERESTS.items()},
        "sections": sections,
        "counts": {
            **{s: len(v) for s, v in sections.items()},
            "past_hidden": n_past,
            "not_available": len(hidden),
            "filtered_out": n_filtered,
            "duplicates_merged": n_duplicates,
        },
        "not_available": hidden,
        "sources": [_source_summary(res) for res in results],
        "not_connected": [{"url": u, "reason": why} for u, why in NOT_CONNECTED.items()],
        "notice": "Deterministic browsing of collected public pages (keyword filters). Not an AI recommendation.",
    }


def _known_unavailable(r: Record, card: dict, win: Windows) -> str | None:
    if _EXCLUDES.search(" ".join(r.eligibility_texts)):
        return f"Restricted audience stated on the page: “{_EXCLUDES.search(' '.join(r.eligibility_texts)).group(0)}”"
    if r.kind == "program" and card["upcoming_sessions"] and all(_CLOSED.search(s.get("status_text") or "") for s in card["upcoming_sessions"]):
        return "Registration closed for every upcoming session listed"
    if r.kind == "event" and _CLOSED.search(" ".join([r.registration_text or "", *r.warnings, r.summary or ""])):
        return "The page says registration is closed or full"
    if card["deadline_at"] and _parse(card["deadline_at"]) < win.now:
        return f"Registration deadline passed ({card['deadline_text']})"
    return None


def _card(it: _Item, win: Windows) -> dict:
    r = it.record
    start, end = _parse(r.start), _parse(r.end)
    upcoming: list[dict] = []
    undated = 0
    for s in r.sessions:
        s_start, s_end = _parse(s.start), _parse(s.end)
        if s_start is None:
            undated += 1
            continue
        if not _is_past(s_start, s_end, win.now):
            upcoming.append({
                "start": s_start.isoformat(),
                "when_text": when_text(s_start, s_end),
                "status_text": s.status_text,
                "register_url": safe_url(s.register_url),
                "this_week": s_start < win.this_week_end,
            })
    actionable = [s for s in upcoming if not _CLOSED.search(s["status_text"] or "")]
    next_session = (actionable or upcoming or [None])[0]

    # The deadline's year comes from the item's own date (a January deadline belongs to a January season).
    ref = start or _parse((next_session or {}).get("start")) or win.now
    deadline_text, deadline_at = _deadline(r, ref.year)

    open_signals = [t for t in r.eligibility_texts if _OPEN.search(t) and not _NOT_OPEN.search(t)]
    to_check = [t for t in r.eligibility_texts if t not in open_signals]
    if r.capacity_text:
        to_check.append(r.capacity_text)

    location = r.location_text
    if location and any("organizer's address" in w for w in r.warnings):
        location += " (organizer's address)"
    if not location and r.format == "online":
        location = "Online"

    source = SOURCES.get(it.source_id)
    return {
        "id": r.record_id,
        "kind": r.kind,
        "kind_label": KIND_LABELS[r.kind],
        "title": r.title,
        "url": safe_url(r.url),
        "source_id": it.source_id,
        "source_name": source.name if source else it.source_id,
        "publisher": r.publisher,
        "publisher_type": PUBLISHER_LABELS.get(source.publisher_type, "") if source else "",
        "organizer": r.organizer,
        "data_mode": it.data_mode,
        "collected_at": r.collected_at,
        "collected_at_text": et_stamp(r.collected_at),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "when_text": when_text(start, end),
        "date_text": r.date_text,
        "next_session": next_session,
        "upcoming_sessions": upcoming,
        "undated_sessions": undated,
        "session_this_week": bool(next_session and next_session["this_week"]),
        "format_label": MODE_LABELS.get(r.format or "", None),
        "location_label": location,
        "cost_label": r.cost_text,
        "registration_url": safe_url(r.registration_url) or (next_session or {}).get("register_url"),
        "registration_text": r.registration_text,
        "registration_note": REGISTRATION_NOTE,
        "deadline_text": deadline_text,
        "deadline_at": deadline_at.isoformat() if deadline_at else None,
        "eligibility_open": open_signals,
        "eligibility_check": to_check,
        "not_stated": [MISSING_LABELS[m] for m in r.missing if not (m == "location_text" and r.format == "online")],
        "warnings": list(r.warnings),
        "summary": r.summary,
        "topics": list(r.topics),
        "also_at": it.also_at,
        "matched_terms": [],
    }


def _source_summary(res: SourceResult) -> dict:
    source = SOURCES.get(res.source_id)
    st = res.status or {}
    return {
        "id": res.source_id,
        "name": source.name if source else res.source_id,
        "publisher_type": PUBLISHER_LABELS.get(source.publisher_type, "") if source else "",
        "listing_url": source.listing_url if source else None,
        "coverage": source.coverage if source else None,
        "data_mode": res.data_mode,
        "collected_at": res.collected_at,
        "collected_at_text": et_stamp(res.collected_at),
        "n_records": len(res.records),
        "last_attempt_at": st.get("last_attempt_at"),
        "last_attempt_text": et_stamp(st.get("last_attempt_at")),
        "last_outcome": st.get("last_outcome"),
        "last_errors": sorted({e.get("kind", "?") for e in st.get("errors", [])}),
        "simulated": bool(st.get("simulated")),
    }
