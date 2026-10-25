"""Deterministic participation checks and grounding rules (code, no model call).

Four things are kept apart for every listing:
- topic relevance: which of the user's interest words appear on the page;
- purpose fit: the model's explanation (stored as reasoning, never as fact);
- hard conditions: format, time window, audience, prerequisite, age, registration, play-vs-watch,
  each judged against what the USER SAID: met / not_met / to_confirm (unknown) / info;
- unknowns: important things the page does not state (cost, capacity, ...).

A known not_met condition removes the listing from "you can take part"; any to_confirm hard
condition makes it a conditional match. Nothing is inferred about the user beyond their words.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from app.collect.records import Record
from app.discover import ny_midnight
from app.domain.models import SOM_IDENTITY

NY_TZ = "America/New_York"

_ONLY_RESTRICTION = re.compile(
    r"\b(undergraduates? only|undergraduate students only|faculty only|staff only|faculty and staff only|"
    r"employees only|members only|high school students only|children only|kids only)\b", re.I)
_OPEN_AUDIENCE = re.compile(
    r"\b(open to (all|everyone|the public|the yale community|all yale|yale students|graduate students)|"
    r"everyone is welcome|all are welcome|free and open to the public|current yale graduate students)\b", re.I)
_DESIGNED_FOR = re.compile(r"\b(designed for|intended for|geared toward[s]?|open to)\s+([^.;:]{3,80})", re.I)
_PREREQ = re.compile(
    r"\b(for students who have taken|prerequisite|must have (taken|completed)|previous experience required|"
    r"prior experience required|have taken [a-z ]*class(es)? [a-z ]*before|attendance or viewing the recording is required|"
    r"is required\))", re.I)
_NO_EXPERIENCE = re.compile(
    r"\b(no [a-z ]*experience (is )?(necessary|needed|required)|all (experience|skill) levels|beginners? (are )?welcome|"
    r"level of skill may vary)\b", re.I)
_AGE = re.compile(r"(\+\s*(18|21)\b|\b(18|21)\s*\+|\bages?\s*\d+\s*\+|\b(18|21) (years|and older|or older))", re.I)
_SUGGESTED_AGE = re.compile(r"suggested ages?", re.I)
_MEMBERSHIP = re.compile(r"\b(current [A-Z]{2,5} (household )?membership|membership required|members only|must be a member|"
                         r"have a current [a-z ]*membership)\b", re.I)
_EQUIPMENT = re.compile(r"\b(bring (a|your) [a-z ]{2,30})", re.I)
_PLAY = re.compile(r"\b(league|leagues|team|teams|tournament|pickup|play|players|scrimmage|intramurals?)\b", re.I)
_WATCH = re.compile(r"\b(watch party|watch parties|viewing party|screening|spectat\w*|game[- ]watching|cheer)\b", re.I)
_BEGINNER = re.compile(r"\b(beginner|new to|never|no experience|first time|just started|just starting|novice)\b", re.I)
_STUDENT_IDENTITY = re.compile(r"\b(student|mba|som|graduate|grad|phd|master'?s)\b", re.I)
_UNDERGRAD_IDENTITY = re.compile(r"\bundergrad", re.I)

# Facts the model must not introduce in free text unless the page states them.
FACT_PATTERNS = {
    "price": re.compile(r"\$\s?\d[\d,]*(?:\.\d\d)?|\bfree\b", re.I),
    "clock_time": re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b", re.I),
    "date": re.compile(
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?\b|\b\d{1,2}/\d{1,2}\b", re.I),
    "weekday": re.compile(r"\b(?:mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?)\b", re.I),
    "url": re.compile(r"https?://\S+|\bwww\.\S+", re.I),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone": re.compile(r"\(?\b\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b"),
}


@dataclass
class Condition:
    kind: str  # format | time | audience | prerequisite | age | membership | registration | activity | equipment | capacity
    status: str  # met | not_met | to_confirm | info
    text: str  # plain-language explanation
    quote: str | None = None  # page wording behind it

    def to_dict(self) -> dict:
        return asdict(self)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("’", "'").replace("“", '"').replace("”", '"')).strip().casefold()


def interaction_text(record: Record) -> str:
    """Text that can describe the activity itself (not the organizer's name or address)."""
    return " | ".join(p for p in [record.title, record.summary or "", record.date_text or "",
                                  " ".join(record.eligibility_texts)] if p)


def page_text(record: Record) -> str:
    parts = [record.title, record.summary or "", record.date_text or "", record.format_text or "",
             record.location_text or "", record.cost_text or "", record.registration_text or "",
             record.capacity_text or "", record.organizer or "", " ".join(record.topics),
             " ".join(record.eligibility_texts), " ".join(s.date_text for s in record.sessions),
             " ".join(s.status_text or "" for s in record.sessions)]
    return " | ".join(p for p in parts if p)


def _said(value: Any) -> bool:
    return value not in (None, "", "not_stated", "either", "not_applicable")


_WORD = re.compile(r"[a-z]{3,}")
_STOPWORDS = {"the", "and", "not", "for", "with", "who", "are", "was", "has", "have", "but", "you", "your", "want",
              "like", "into", "about", "just", "some", "other", "any", "all", "this", "that", "very", "really"}
_OTHER_AUDIENCE = re.compile(r"faculty|staff|employees|high school|children|kids", re.I)


def _supported_by_text(name: str, value: str, user_text: str, interests: Any = ()) -> bool:
    """True if the user's own words support this identity / experience reading.

    A content word of the reading (not a stopword, not the user's interest itself) must occur in the
    text, and any pattern that drives a decision (beginner; student / undergrad / staff ...) must be
    in the user's words too, so "new to darkroom" is not kept just because the user wrote "darkroom".
    """
    text = (user_text or "").casefold()
    topic = {w for t in (interests or []) for w in _WORD.findall(str(t).casefold())}
    words = set(_WORD.findall(str(value).casefold())) - _STOPWORDS - topic
    if not any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
        return False
    deciding = [_BEGINNER] if name == "experience_level" else [_STUDENT_IDENTITY, _UNDERGRAD_IDENTITY, _OTHER_AUDIENCE]
    return all(p.search(text) for p in deciding if p.search(str(value)))


def effective_understood(understood: dict | None, user_text: str, options: Any = None) -> dict:
    """The request the code checks: the model's reading of the user's words plus the form choices.

    - Form choices (``RunOptions``) override the model's reading of those fields: the user set them.
    - ``identity`` / ``experience_level`` that no word of the user's text supports are dropped, so the
      checks never act on an inferred identity or experience.
    ``provenance`` records, per affected field, whether it came from the form (and what the AI had
    read) or was dropped, so the UI can say where each condition came from.
    """
    u = dict(understood or {})
    not_stated = list(u.get("not_stated") or [])
    form = options.public() if options is not None else {}
    provenance: dict[str, dict] = {}
    for name in ("identity", "experience_level"):
        value = u.get(name)
        if value and not _supported_by_text(name, value, user_text, u.get("interests")):
            provenance[name] = {"source": "dropped", "ai_reading": value}
            u[name] = None
            if name not in not_stated:
                not_stated.append(name)
    overrides = {}
    if form.get("som_student"):
        overrides["identity"] = SOM_IDENTITY
    for name in ("participation", "time_window"):
        if name in form:
            overrides[name] = form[name]
    for name, value in overrides.items():
        before = u.get(name)  # a dropped AI guess is None here: it is never shown as the user's words
        entry = {"source": "form", "value": value}
        if before not in (None, "", "not_stated", value):
            entry["ai_reading"] = before
        provenance[name] = entry
        u[name] = value
        if name in not_stated:
            not_stated.remove(name)
    u["not_stated"] = not_stated
    u["provenance"] = provenance
    return u


def evaluate(record: Record, card: dict, understood: dict | None, windows: dict) -> list[Condition]:
    """Hard conditions for one listing, judged only against what the user said."""
    u = understood or {}
    out: list[Condition] = []
    texts = list(record.eligibility_texts)
    joined = " ".join(texts)

    # format (in person / online)
    want = u.get("participation")
    conflict = any("format to be confirmed" in w for w in record.warnings)
    if want in ("in_person", "online"):
        label = {"in_person": "in person", "online": "online"}[want]
        if record.format is None:
            out.append(Condition("format", "to_confirm", f"You asked for {label}; the page does not say whether it is in person or online."))
        elif conflict:
            out.append(Condition("format", "to_confirm", f"You asked for {label}; the page is contradictory about the format.", record.format_text))
        elif record.format in (want, "hybrid"):
            out.append(Condition("format", "met", f"You asked for {label}; the page says {record.format_text}.", record.format_text))
        else:
            out.append(Condition("format", "not_met", f"You asked for {label}; the page says {record.format_text}.", record.format_text))

    # time window
    tw = u.get("time_window")
    if tw in ("this_week", "next_few_weeks"):
        label = "this week" if tw == "this_week" else "in the next few weeks"
        this_week_end = datetime.fromisoformat(windows["this_week"]["end"])
        horizon = ny_midnight(this_week_end.date() + timedelta(days=21))  # real DST rules
        start = card.get("start") or (card.get("next_session") or {}).get("start")
        if not start:
            out.append(Condition("time", "to_confirm", f"You asked for something {label}; the page gives no date."))
        else:
            dt = datetime.fromisoformat(start)
            limit = this_week_end if tw == "this_week" else horizon
            status = "met" if dt < limit else "not_met"
            what = "next session" if card.get("next_session") and not card.get("start") else "date"
            out.append(Condition("time", status, f"You asked for something {label}; the {what} is {(card.get('next_session') or {}).get('when_text') or card.get('when_text')}."))

    # audience / identity
    identity = u.get("identity") or ""
    only = _ONLY_RESTRICTION.search(joined)
    if only:
        phrase = only.group(0)
        if not identity:
            out.append(Condition("audience", "to_confirm", f"The page limits who can join (“{phrase}”); you did not say who you are.", phrase))
        elif _UNDERGRAD_IDENTITY.search(phrase) and _STUDENT_IDENTITY.search(identity) and not _UNDERGRAD_IDENTITY.search(identity):
            out.append(Condition("audience", "not_met", f"The page says “{phrase}”; you told us “{identity}”.", phrase))
        elif re.search(r"faculty|staff|employees|high school|children|kids", phrase, re.I) and _STUDENT_IDENTITY.search(identity):
            out.append(Condition("audience", "not_met", f"The page says “{phrase}”; you told us “{identity}”.", phrase))
        else:
            out.append(Condition("audience", "to_confirm", f"The page says “{phrase}”; check that this includes you.", phrase))
    else:
        designed = _DESIGNED_FOR.search(joined)
        open_aud = _OPEN_AUDIENCE.search(joined)
        if open_aud and re.search(r"graduate", open_aud.group(0), re.I):
            status = "met" if re.search(r"graduate|mba|som|phd|master", identity, re.I) else "to_confirm"
            out.append(Condition("audience", status, f"The page says it is open to “{open_aud.group(0)}”.", open_aud.group(0)))
        elif open_aud:
            out.append(Condition("audience", "met", f"The page says “{open_aud.group(0)}”.", open_aud.group(0)))
        elif designed:
            out.append(Condition("audience", "to_confirm", f"Audience as written: “{designed.group(0).strip()}”. Check that it suits you.", designed.group(0).strip()))

    # prior experience / prerequisites
    experience = u.get("experience_level") or ""
    prereq = next((t for t in texts if _PREREQ.search(t)), None)
    if prereq:
        if experience and _BEGINNER.search(experience):
            out.append(Condition("prerequisite", "not_met", f"The page sets a prerequisite; you said “{experience}”.", prereq))
        else:
            asked = f"you said “{experience}”, which does not show whether you meet it" if experience else "you did not say whether you meet it"
            out.append(Condition("prerequisite", "to_confirm", f"The page sets a prerequisite; {asked}.", prereq))
    else:
        open_exp = next((t for t in texts if _NO_EXPERIENCE.search(t)), None)
        if open_exp:
            out.append(Condition("prerequisite", "met", "The page says no particular experience is needed.", open_exp))

    # membership
    member = _MEMBERSHIP.search(joined)
    if member:
        out.append(Condition("membership", "to_confirm", f"The page requires a membership (“{member.group(0)}”).", member.group(0)))

    # age
    age_text = next((t for t in texts if _AGE.search(t)), None)
    if age_text:
        if _SUGGESTED_AGE.search(age_text):
            out.append(Condition("age", "info", f"Suggested age on the page: {age_text}.", age_text))
        else:
            out.append(Condition("age", "to_confirm", "The page sets an age limit; you did not state your age.", age_text))

    # play or watch
    pw = u.get("play_or_watch")
    if pw in ("play", "watch"):
        page = page_text(record)
        plays, watches = bool(_PLAY.search(page)), bool(_WATCH.search(page))
        if pw == "watch" and plays and not watches:
            out.append(Condition("activity", "not_met", "You want to watch; this listing is for playing."))
        elif pw == "play" and watches and not plays:
            out.append(Condition("activity", "not_met", "You want to play; this listing is for watching."))
        elif (pw == "watch" and watches) or (pw == "play" and plays):
            out.append(Condition("activity", "met", f"You want to {pw}; the page fits that."))
        else:
            out.append(Condition("activity", "to_confirm", f"You want to {pw}; the page does not make clear whether that is possible."))

    # registration and capacity (availability is never confirmed by this app)
    if card.get("next_session") and card["next_session"].get("status_text"):
        out.append(Condition("registration", "info", f"Next session status on the page: “{card['next_session']['status_text']}”. A link does not guarantee a spot.",
                             card["next_session"]["status_text"]))
    elif record.registration_text or card.get("registration_url"):
        out.append(Condition("registration", "info", "Registration happens on the organizer's site; a link does not guarantee a spot.",
                             record.registration_text))
    if record.capacity_text:
        out.append(Condition("capacity", "to_confirm", "Places are limited; availability is not shown here.", record.capacity_text))

    # equipment the user must bring
    equip = _EQUIPMENT.search(joined)
    if equip:
        out.append(Condition("equipment", "info", f"You need to {equip.group(0).lower()}.", equip.group(0)))
    return out


def topic_matches(terms: list[str], record: Record) -> list[dict]:
    """Which interest words appear where on the page (deterministic relevance evidence)."""
    fields = {"title": record.title, "topics": " ".join(record.topics), "summary": record.summary or "",
              "conditions": " ".join(record.eligibility_texts)}
    found = []
    for term in terms:
        for name, text in fields.items():
            if re.search(rf"\b{re.escape(term)}\b", text, re.I):
                found.append({"term": term, "field": name})
                break
    return found


def unsupported_details(text: str, record: Record) -> list[str]:
    """Factual tokens (prices, times, dates, weekdays, links, emails, phones) in model text that the page does not contain."""
    haystack = norm(page_text(record))
    bad = []
    for kind, pattern in FACT_PATTERNS.items():
        for m in pattern.finditer(text or ""):
            token = m.group(0)
            candidates = {norm(token), norm(token).rstrip("s")}  # "Fridays" is supported by "Friday"
            if not any(c and c in haystack for c in candidates):
                bad.append(f"{kind}: {token}")
    return bad


def redact_details(text: str, bad: list[str]) -> str:
    for item in bad:
        token = item.split(": ", 1)[1]
        text = text.replace(token, "[detail not on the page]")
    return text


def verdict(conditions: list[Condition]) -> str:
    if any(c.status == "not_met" for c in conditions):
        return "excluded"
    if any(c.status == "to_confirm" for c in conditions):
        return "conditional"
    return "clear"
