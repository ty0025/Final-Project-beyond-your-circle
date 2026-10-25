"""Connected public sources and their deterministic parsers.

Only sources verified as public, programmatically readable and robots.txt-permitted are
connected. Candidates that were checked but not connected are listed in ``NOT_CONNECTED``
with the reason, so the app and the report can state coverage honestly.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable
from urllib.parse import unquote, urljoin
from zoneinfo import ZoneInfo

from app.collect.fetch import Page
from app.collect.htmltree import Node, meta_content, parse_html, sentences
from app.collect.records import TIMEZONE, Evidence, Record, Session, clip, finalize, make_record_id

NY = ZoneInfo(TIMEZONE)


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    publisher: str
    publisher_type: str  # "official_yale" | "community_nonprofit"
    listing_url: str
    allowed_hosts: frozenset[str]
    max_detail_pages: int
    min_delay_s: float
    coverage: str
    parse_listing: Callable[[Page, date], tuple[list[str], list[str]]]  # -> (detail urls, notes)
    parse_detail: Callable[[Page, "Source"], Record]


# --------------------------------------------------------------------------- shared helpers

_TIME_RANGE = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[–—-]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE
)
_MONTH_DAY = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_YEAR = re.compile(r"\b(20\d\d)\b")

_ELIGIBILITY = re.compile(
    r"(\bfor students who|\bopen to\b|\bonly for\b|\bmembers only\b|\bmust\b|\brequired\b|\brequires\b|\bprerequisite|"
    r"\bexperience (is )?(necessary|required|needed)|\bno [a-z ]*experience|\bcomfortable\b|\bages?\b|"
    r"\b(18|21)\s*\+|\+\s*(18|21)\b|\bdesigned for\b|\bintended for\b|\bgeared toward|"
    r"\ball (experience|skill) levels\b|\bbeginners? (are )?welcome\b|\bbring (a|your) laptop|\baffiliat)",
    re.IGNORECASE,
)
_LOCATION_LINE = re.compile(r"(?:📍|\b(?:location|where|venue)\s*:)\s*([^\n]{3,160})", re.IGNORECASE)
_HOSTED_BY = re.compile(r"\b(co-hosted|hosted|organized|presented|sponsored) by\b", re.IGNORECASE)
_CAPACITY = re.compile(r"\b(capped at|capacity|limited to \d+|seats? (are|is) limited|space is limited|max(imum)? of \d+)", re.IGNORECASE)
_COST = re.compile(
    r"(\$\s?\d|\bfree (of charge|to attend|and open|admission|event|workshop)\b|"
    r"\b(admission|attendance|registration|entry|the event|this event|the workshop|this workshop|it) (is|are) free\b|"
    r"\bno (cost|charge|fee)\b|\btuition\b|\bregistration fee\b)",
    re.IGNORECASE,
)
_CAPACITY_LINE = re.compile(r"\bCapacity:\s*(\d+)", re.IGNORECASE)
_FLEXIBLE = re.compile(r"\b(flexible|by appointment|to be arranged|TBA|TBD)\b", re.IGNORECASE)
_REGISTRATION = re.compile(r"\b(reserve|register|registration|rsvp|sign up|enroll)\b", re.IGNORECASE)
_POLICY = re.compile(r"\b(withdraw|refund|cancell?ation polic)", re.IGNORECASE)
_IN_PERSON = re.compile(r"\bin[ -]person\b", re.IGNORECASE)
_ONLINE = re.compile(r"\b(zoom|online|virtual)\b", re.IGNORECASE)


def _hour24(hour: int, minute: int, ampm: str) -> tuple[int, int]:
    hour %= 12
    if ampm.lower() == "pm":
        hour += 12
    return hour, minute


def parse_time_range(text: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """'6–9 pm' -> ((18, 0), (21, 0)); a start without am/pm takes the end's unless that is impossible."""
    m = _TIME_RANGE.search(text)
    if not m:
        return None
    h1, m1, ap1, h2, m2, ap2 = m.groups()
    end = _hour24(int(h2), int(m2 or 0), ap2)
    if ap1:
        start = _hour24(int(h1), int(m1 or 0), ap1)
    else:
        start = _hour24(int(h1), int(m1 or 0), ap2)
        if start > end:  # e.g. '11–1 pm' -> 11 am
            start = _hour24(int(h1), int(m1 or 0), "am")
    return start, end


def ny_iso(day: date, hm: tuple[int, int]) -> str:
    return datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=NY).isoformat()


def _format_from_label(label: str | None) -> str | None:
    if not label:
        return None
    text = label.lower()
    online = "online" in text or "virtual" in text
    in_person = "in person" in text or "in-person" in text
    if "hybrid" in text or (online and in_person):
        return "hybrid"
    if online:
        return "online"
    if in_person:
        return "in_person"
    return None


def _format_conflict_warning(fmt: str | None, description: str) -> str | None:
    if fmt == "online" and _IN_PERSON.search(description):
        return "The page labels the format 'Online' but the description mentions in-person attendees; format to be confirmed."
    if fmt == "in_person" and re.search(
        r"\bzoom\b|\bjoin (us )?virtually\b|\bvirtual option\b|\bonline option\b|\blive-?stream", description, re.IGNORECASE
    ):
        return "The page labels the format 'In person' but the description mentions a virtual option; format to be confirmed."
    return None


def _pick(sents: list[str], pattern: re.Pattern[str], *, exclude: re.Pattern[str] | None = None) -> list[str]:
    return [s for s in sents if pattern.search(s) and not (exclude and exclude.search(s))]


# --------------------------------------------------------------------------- Creative Arts Workshop

_CAW_COURSE = re.compile(r"^https://creativeartsworkshop\.org/courses/(?!department/|type/)[a-z0-9-]+/[a-z0-9-]+/$")


def caw_parse_listing(page: Page, today: date) -> tuple[list[str], list[str]]:
    root = parse_html(page.text)
    urls: list[str] = []
    for a in root.find_all("a"):
        href = urljoin(page.url, a.attrs.get("href", ""))
        if _CAW_COURSE.match(href) and href not in urls:
            urls.append(href)
    return urls, [f"{len(urls)} course page link(s) on the photography department listing"]


def _caw_footer_location(root: Node) -> str | None:
    for section in root.find_all("section"):
        heading = section.find("h4")
        if heading is not None and heading.text().strip().lower() == "location":
            body = section.find("div", cls="textwidget")
            if body is None:
                return None
            lines = [ln for ln in body.text().split("\n") if ln and ln.lower() != "directions" and not re.match(r"^\(?\d{3}\)?[ -]\d{3}-\d{4}$", ln)]
            return ", ".join(lines) or None
    return None


def caw_parse_detail(page: Page, source: Source) -> Record:
    root = parse_html(page.text)
    article = root.find("article", cls="course") or root
    evidence: list[Evidence] = []
    warnings: list[str] = []

    title_node = article.find("h1", cls="entry-title") or root.find("h1")
    title = title_node.text() if title_node else (meta_content(root, "og:title") or page.url)
    publisher = source.publisher

    format_node = article.find("div", cls="location-types")
    format_text = (format_node.text() or None) if format_node else None
    fmt = _format_from_label(format_text)
    if format_text:
        evidence.append(Evidence(field="format", quote=clip(format_text), basis="course header label"))

    topics: list[str] = []
    categories = article.find("div", cls="categories")
    if categories is not None:
        dept = categories.find("a", cls="department")
        if dept is not None:
            topics.append(dept.text())
        evidence.append(Evidence(field="topics", quote=clip(categories.text()), basis="course category line"))

    content = article.find("div", cls="entry-content")
    sessions_nodes = content.find_all("div", cls="session") if content else []
    # Paragraph text only (sessions are parsed separately).
    para_text = "\n".join(p.text() for p in (content.find_all("p") if content else []))
    sents = sentences(para_text)

    term = next((m.group(1).strip() for s in sents if (m := re.match(r"Term:\s*(.+)", s))), None)
    ages = next((m.group(1).strip() for s in sents if (m := re.match(r"Suggested Ages:\s*(.+)", s))), None)
    year_match = _YEAR.search(term or "")
    year = int(year_match.group(1)) if year_match else None
    if term:
        evidence.append(Evidence(field="date_text", quote=f"Term: {term}", basis="page text"))

    sessions: list[Session] = []
    capacity_quotes: list[str] = []
    for node in sessions_nodes:
        lines = node.text().split("\n")
        date_text = lines[0] if lines else node.text()
        status_node = node.find("em") or node.find("a", cls="register-button")
        status_text = status_node.text() if status_node else None
        link = node.find("a", cls="register-button")
        if (cap := _CAPACITY_LINE.search(node.text())) and cap.group(0) not in capacity_quotes:
            capacity_quotes.append(cap.group(0))
        start = end = None
        md = _MONTH_DAY.search(date_text)
        times = parse_time_range(date_text)
        if _FLEXIBLE.search(date_text):
            warnings.append(f"Session timing is flexible ('{clip(date_text, 90)}'); not treated as a dated session.")
        elif md and times:
            sess_year = int(md.group(3)) if md.group(3) else year
            if sess_year is not None and sess_year < 100:
                sess_year += 2000
            if sess_year is not None:
                day = date(sess_year, int(md.group(1)), int(md.group(2)))
                start, end = ny_iso(day, times[0]), ny_iso(day, times[1])
        if start is None and not _FLEXIBLE.search(date_text):
            warnings.append(f"Could not date session '{clip(date_text, 80)}'; kept as text only.")
        sessions.append(
            Session(
                date_text=clip(" ".join(lines[:2]), 160),
                start=start,
                end=end,
                status_text=status_text,
                register_url=link.attrs.get("href") if link is not None else None,
            )
        )
    if sessions:
        evidence.append(
            Evidence(field="sessions", quote=clip(sessions_nodes[0].text()), basis=f"first of {len(sessions)} session blocks")
        )
        if any(s.start for s in sessions) and not any(
            (m := _MONTH_DAY.search(s.date_text)) and m.group(3) for s in sessions
        ):
            warnings.append(f"Session dates show month/day only; the year {year} comes from the page's term line ('{term}').")

    eligibility = _pick(sents, _ELIGIBILITY, exclude=_POLICY)
    eligibility = [s for s in eligibility if not s.startswith(("Term:", "Suggested Ages:"))]
    if ages:
        eligibility.append(f"Suggested Ages: {ages}")
    for text in eligibility:
        evidence.append(Evidence(field="eligibility_texts", quote=clip(text), basis="page text"))

    cost_sents = _pick(sents, _COST, exclude=_POLICY)
    cost_text = cost_sents[0] if cost_sents else None
    if cost_text:
        evidence.append(Evidence(field="cost_text", quote=clip(cost_text), basis="page text"))

    reg_sents = _pick(sents, _REGISTRATION, exclude=_POLICY)
    registration_text = " ".join(reg_sents) or None
    open_links = [s.register_url for s in sessions if s.register_url]
    registration_url = open_links[0] if open_links else None
    if registration_text:
        evidence.append(Evidence(field="registration_text", quote=clip(registration_text), basis="page text"))
    if registration_url:
        evidence.append(Evidence(field="registration_url", quote=registration_url, basis="session 'Register' link"))

    capacity = _pick(sents, _CAPACITY) + capacity_quotes
    capacity_text = capacity[0] if capacity else None
    if capacity_text:
        evidence.append(Evidence(field="capacity_text", quote=clip(capacity_text), basis="page text / session block"))

    location_text = _caw_footer_location(root)
    if location_text:
        evidence.append(Evidence(field="location_text", quote=clip(location_text), basis="site footer 'Location' (organizer address)"))
        warnings.append("Location is the organizer's address from the site footer; the page does not name a course-specific room.")

    summary = next((s for s in para_text.split("\n") if s and not s.startswith(("Term:", "Suggested Ages:"))), None)
    evidence.append(Evidence(field="organizer", quote=publisher, basis="publishing site (organizer's own course page)"))

    record = Record(
        record_id=make_record_id(source.id, page.url),
        source_id=source.id,
        kind="program",  # a course/practice series; its dated sessions stay inside it
        title=title,
        url=page.url,
        publisher=publisher,
        organizer=publisher,
        collected_at=page.fetched_at,
        date_text=f"Term: {term}" if term else None,
        sessions=sessions,
        format=fmt,
        format_text=format_text,
        location_text=location_text,
        eligibility_texts=[clip(t) for t in eligibility],
        cost_text=clip(cost_text) if cost_text else None,
        registration_url=registration_url,
        registration_text=clip(registration_text) if registration_text else None,
        capacity_text=clip(capacity_text) if capacity_text else None,
        topics=topics,
        summary=clip(summary, 600) if summary else None,
        evidence=evidence,
        warnings=warnings,
    )
    return finalize(record)


# --------------------------------------------------------------------------- Yale Center for Geospatial Solutions

_YCGS_EVENT = re.compile(r"^/events/(\d{4}-\d{2}-\d{2})-[a-z0-9-]+$")
YCGS_WINDOW_DAYS = 75


def ycgs_parse_listing(page: Page, today: date) -> tuple[list[str], list[str]]:
    root = parse_html(page.text)
    dated: dict[str, date] = {}
    for a in root.find_all("a"):
        href = a.attrs.get("href", "")
        m = _YCGS_EVENT.match(href)
        if m:
            dated[urljoin(page.url, href)] = date.fromisoformat(m.group(1))
    last = today + timedelta(days=YCGS_WINDOW_DAYS)
    upcoming = sorted((d, u) for u, d in dated.items() if today <= d <= last)
    notes = [
        f"{len(dated)} event link(s) on the listing; {len(upcoming)} dated {today.isoformat()}..{last.isoformat()} "
        f"(date taken from the URL slug, America/New_York)"
    ]
    return [u for _, u in upcoming], notes


def _ical_end(root: Node) -> tuple[str | None, str | None]:
    for a in root.find_all("a"):
        href = a.attrs.get("href", "")
        if href.startswith("data:text/calendar") and "base64," in href:
            try:
                ical = base64.b64decode(unquote(href.split("base64,", 1)[1])).decode("utf-8", "replace")
            except ValueError:
                return None, None
            m = re.search(r"DTEND:(\d{8}T\d{6})Z", ical)
            if m:
                end = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).astimezone(NY)
                return end.isoformat(), f"DTEND:{m.group(1)}Z"
    return None, None


def ycgs_parse_detail(page: Page, source: Source) -> Record:
    root = parse_html(page.text)
    evidence: list[Evidence] = []
    warnings: list[str] = []

    heading = root.find("h1", cls="page-title__heading") or root.find("h1")
    title = heading.text() if heading else (meta_content(root, "og:title") or page.url)
    publisher = meta_content(root, "og:site_name") or source.publisher

    format_node = root.find(cls="event-meta__format")
    format_text = format_node.text() if format_node else None
    fmt = _format_from_label(format_text)
    if format_text:
        evidence.append(Evidence(field="format", quote=format_text, basis="event format label"))

    time_node = root.find("time")
    start = date_text = None
    if time_node is not None:
        date_text = time_node.text() or None
        raw = time_node.attrs.get("datetime")
        if raw:
            try:
                start = datetime.fromisoformat(raw).astimezone(NY).isoformat()
                evidence.append(Evidence(field="start", quote=f'datetime="{raw}"; text "{date_text}"', basis="time@datetime"))
            except ValueError:
                warnings.append(f"Unreadable start time '{raw}'.")
    end, end_quote = _ical_end(root)
    if end:
        evidence.append(Evidence(field="end", quote=end_quote, basis="'Add to Calendar' iCal data on the page"))
    elif start and date_text and (times := parse_time_range(date_text)):
        end = ny_iso(datetime.fromisoformat(start).date(), times[1])
        evidence.append(Evidence(field="end", quote=date_text, basis="page date text"))

    cta = root.find("a", cls="event-meta__cta")
    registration_url = cta.attrs.get("href") if cta is not None else None
    registration_text = cta.text() if cta is not None else None
    if registration_url:
        evidence.append(Evidence(field="registration_url", quote=f"{registration_text}: {registration_url}", basis="event website / register button"))

    desc_node = root.find("div", cls="event-meta__description")
    description = desc_node.text() if desc_node else ""
    sents = sentences(description)

    # These pages have no structured venue field; a place is only known if the description states one.
    location_text = None
    if m := _LOCATION_LINE.search(description):
        location_text = m.group(1).strip(" .;")
        evidence.append(Evidence(field="location_text", quote=clip(m.group(0)), basis="event description"))
    organizer = publisher
    hosted = [s for s in sents if _HOSTED_BY.search(s)]
    if hosted:
        organizer = clip(hosted[0], 200)
        evidence.append(Evidence(field="organizer", quote=clip(hosted[0]), basis="event description"))
    eligibility = _pick(sents, _ELIGIBILITY)
    capacity = _pick(sents, _CAPACITY)
    cost = _pick(sents, _COST)
    for text in eligibility:
        evidence.append(Evidence(field="eligibility_texts", quote=clip(text), basis="event description"))
    if capacity:
        evidence.append(Evidence(field="capacity_text", quote=clip(capacity[0]), basis="event description"))
    if cost:
        evidence.append(Evidence(field="cost_text", quote=clip(cost[0]), basis="event description"))
    conflict = _format_conflict_warning(fmt, description)
    if conflict:
        warnings.append(conflict)
    if not hosted:
        evidence.append(Evidence(field="organizer", quote=publisher, basis="og:site_name (publishing site)"))

    summary = meta_content(root, "og:description") or (sents[0] if sents else None)
    record = Record(
        record_id=make_record_id(source.id, page.url),
        source_id=source.id,
        kind="event",
        title=title,
        url=page.url,
        publisher=publisher,
        organizer=organizer,
        collected_at=page.fetched_at,
        date_text=date_text,
        start=start,
        end=end,
        format=fmt,
        format_text=format_text,
        location_text=location_text,
        eligibility_texts=[clip(t) for t in eligibility],
        cost_text=clip(cost[0]) if cost else None,
        registration_url=registration_url,
        registration_text=registration_text,
        capacity_text=clip(capacity[0]) if capacity else None,
        summary=clip(summary, 600) if summary else None,
        evidence=evidence,
        warnings=warnings,
    )
    if not start:
        record.warnings.append("No machine-readable date on the page; this item cannot be placed in a date window.")
    return finalize(record)


# --------------------------------------------------------------------------- registry

CAW_PHOTO = Source(
    id="caw-photo",
    name="Creative Arts Workshop: photography classes",
    publisher="Creative Arts Workshop",
    publisher_type="community_nonprofit",
    listing_url="https://creativeartsworkshop.org/courses/department/photography/",
    allowed_hosts=frozenset({"creativeartsworkshop.org"}),
    max_detail_pages=4,
    min_delay_s=10.0,  # robots.txt asks for Crawl-delay: 10
    coverage="Photography department listing (first page only) and up to 4 linked course pages.",
    parse_listing=caw_parse_listing,
    parse_detail=caw_parse_detail,
)

YCGS_EVENTS = Source(
    id="ycgs-events",
    name="Yale Center for Geospatial Solutions: events",
    publisher="Yale Center for Geospatial Solutions",
    publisher_type="official_yale",
    listing_url="https://geospatial.yale.edu/events",
    allowed_hosts=frozenset({"geospatial.yale.edu"}),
    max_detail_pages=10,
    min_delay_s=1.0,
    coverage=f"Events listing (first page only); event pages dated today..+{YCGS_WINDOW_DAYS} days by URL slug, at most 10.",
    parse_listing=ycgs_parse_listing,
    parse_detail=ycgs_parse_detail,
)

SOURCES: dict[str, Source] = {s.id: s for s in (CAW_PHOTO, YCGS_EVENTS)}

# Checked on 2026-10-25 and deliberately NOT connected (see evidence/q02.md).
NOT_CONNECTED: dict[str, str] = {
    "https://events.yale.edu/": "Public Localist JSON API answers (HTTP 200), but robots.txt is 'User-agent: * / Disallow: /'; not auto-collected.",
    "https://yaleconnect.yale.edu/ycyalephotographysociety/home/": "Page is a template shell ('[CONTENT-EVENTS_NAME_FEATURED]', 'There are no upcoming events'); undergraduate society.",
    "https://recreation.yale.edu/gradproims": "Readable and robots-permitted; deferred until the two-source path has evidence.",
    "https://nhccphotoblog.blogspot.com/": "Readable (Atom feed) and robots-permitted; deferred until the two-source path has evidence.",
    "https://poorvucenter.yale.edu/": "Home page only; no event listing identified in the probe; deferred.",
}
