"""The unified record for public events, programs and communities.

Unknown is explicit: a field is ``None``/empty when the page does not state it, and its name
is listed in ``missing``. ``None`` never means "free", "open to everyone" or "no limit".
Every extracted value keeps the original wording it came from in ``evidence``.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TIMEZONE = "America/New_York"
QUOTE_CHARS = 300

# Fields whose absence matters to a user deciding whether they can take part.
KEY_FIELDS = (
    "organizer",
    "when",
    "format",
    "location_text",
    "eligibility_texts",
    "cost_text",
    "registration",
    "capacity_text",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_Strict):
    field: str
    quote: str = Field(description="Original page wording that supports the field (clipped).")
    basis: str = Field(description="Where on the page it came from, e.g. 'page text', 'time@datetime'.")


class Session(_Strict):
    """One dated session of a program (a course or season), not a separate event."""

    date_text: str
    start: str | None = None  # ISO 8601 with UTC offset, America/New_York
    end: str | None = None
    status_text: str | None = None  # exactly as shown, e.g. "Registration closed"
    register_url: str | None = None  # a link existing does not mean seats are available


class Record(_Strict):
    record_id: str
    source_id: str
    kind: Literal["event", "program", "community"]
    title: str
    url: str  # original detail page
    publisher: str  # site that published the page
    organizer: str | None = None
    collected_at: str  # UTC ISO time the page was fetched
    timezone: str = TIMEZONE
    date_text: str | None = None  # original date/term wording
    start: str | None = None  # single-occurrence events only
    end: str | None = None
    sessions: list[Session] = Field(default_factory=list)  # programs with dated sessions
    format: Literal["in_person", "online", "hybrid"] | None = None
    format_text: str | None = None
    location_text: str | None = None
    eligibility_texts: list[str] = Field(default_factory=list)
    cost_text: str | None = None
    registration_url: str | None = None
    registration_text: str | None = None
    capacity_text: str | None = None
    topics: list[str] = Field(default_factory=list)
    summary: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def clip(text: str, limit: int = QUOTE_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def make_record_id(source_id: str, url: str) -> str:
    return f"{source_id}-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:10]}"


def compute_missing(record: Record) -> list[str]:
    present = {
        "organizer": bool(record.organizer),
        "when": bool(record.start or any(s.start for s in record.sessions)),
        "format": record.format is not None,
        "location_text": bool(record.location_text),
        "eligibility_texts": bool(record.eligibility_texts),
        "cost_text": bool(record.cost_text),
        "registration": bool(record.registration_url or record.registration_text),
        "capacity_text": bool(record.capacity_text),
    }
    return [name for name in KEY_FIELDS if not present[name]]


def finalize(record: Record) -> Record:
    record.missing = compute_missing(record)
    return record
