"""Deterministic verifier (code, no model call) for the matcher's structured output.

For every pick it keeps two things strictly apart:
- ``reasoning``: what the model wrote (purpose fit, interaction, exploration link), with each quote
  checked word for word and any price/time/date/link the page does not contain redacted;
- ``facts``: date, place, organizer, cost, conditions, registration, restored by the server from the
  stored record, each with the page wording and where it came from.

Status per pick (server decides, the model cannot override it):
- ``excluded``: a hard condition is known NOT to be met (moved out of the picks, with reasons);
- ``conditional``: a hard condition is unknown -> "check first";
- ``match`` / ``exploratory``: no hard condition is open. Exploratory picks need a verified link quote.
A pick is dropped if its record_id was not read with get_listing in this run, does not exist, or is
no longer available.
"""

from __future__ import annotations

import re
from typing import Any

from app.collect.records import Record
from app.domain.conditions import (
    Condition,
    evaluate,
    norm,
    page_text,
    redact_details,
    topic_matches,
    unsupported_details,
    verdict,
)
from app.domain.tools import ListingSession

MAX_PICKS = 6
MAX_EXPLORATORY = 2
NO_INTERACTION = ("The page does not describe how attendees interact or who attends, so meeting particular "
                  "people or speakers is not guaranteed.")
_FACT_FIELDS = {  # Record.evidence field -> fact label
    "start": "when", "end": "when", "sessions": "when", "date_text": "when",
    "format": "format", "location_text": "location", "organizer": "organizer", "cost_text": "cost",
    "eligibility_texts": "conditions", "registration_text": "registration", "registration_url": "registration",
    "capacity_text": "capacity",
}


_NUMBERS = {"one": 1, "a single": 1, "two": 2, "both": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10}
# "<number> [up to 5 describing words, commas allowed] <result noun>", e.g. "three close matches",
# "two in-person, beginner-friendly matches", "1 exploratory option". "match" as a verb ("the two events
# match your interest", "this one matches what you asked") is not a count: it is followed by its object
# (lookahead below) or disagrees in number with the count (checked in reconcile_summary).
_COUNT_CLAIM = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|both|a single)\s+"
    r"((?:(?!(?:the|a|an|and|or|but|of|to|that|which|who|is|are|was|were|be|on|in|for|with|from|them|these|those)\s)"
    r"[\w’'-]+,?\s+){0,5}?)"
    r"(match(?:es)?(?!\s+(?:your|what|my|the|it|them|well|closely|exactly|perfectly|best)\b)|"
    r"picks?|options?|listings?|results?|recommendations?)\b", re.I)
# Generic nouns ("two listings are labeled online") only count as a claim within 3 words after a finding verb.
_FOUND_BEFORE = re.compile(r"\b(found|find|there (are|is)|here (are|is)|returned|recommend\w*|picked|identified)\b"
                           r"(\W+\w+){0,3}\W*$", re.I)
# A number after these words is the pool that was searched, not a result: "among the 11 stored listings".
_POOL_BEFORE = re.compile(r"\b(among|of|from|out of|after reading)\s+((all )?the\s+|all\s+)?$", re.I)
# Split after . ! ? but not after "e.g.", "i.e.", "Dr.", "Mr.", "Mrs.", "Ms.", "Prof.".
# "two listings to check first", "two possible matches that need checking": a Check-first count.
_TO_CHECK_AFTER = re.compile(r"\s+(?:that\s+|which\s+)?(?:(?:you\s+)?(?:should|need to|must)\s+|to\s+)"
                             r"(?:check|confirm)\b|\s+(?:that\s+|which\s+)?needs?\s+(?:checking|confirming|a check)\b", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?])(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bDr\.)(?<!\bMr\.)(?<!\bMrs\.)(?<!\bMs\.)(?<!\bProf\.)\s+",
                           re.I)


def code_counts(kept: list[dict], excluded: list[dict], dropped: list[dict]) -> dict:
    """Counts of the FINAL cards (after the checks): the only numbers the result page should state."""
    n = {s: sum(1 for p in kept if p["status"] == s) for s in ("match", "conditional", "exploratory")}
    return {**n, "excluded": len(excluded), "dropped": len(dropped)}


def headline(counts: dict) -> str:
    if not counts["match"] + counts["conditional"] + counts["exploratory"]:
        return "No verified match in the stored listings."
    m = counts["match"]
    return (f"After the code checks: {m} {'match' if m == 1 else 'matches'}, {counts['conditional']} to check first, "
            f"{counts['exploratory']} exploratory.")


def reconcile_summary(summary: str, counts: dict) -> tuple[str, list[str]]:
    """Drop AI summary sentences whose stated count disagrees with the final cards.

    The model writes its summary BEFORE the code checks, so "I found three close matches" can sit above
    1 Match + 2 Check first. "match(es)" is compared with the Match count, "exploratory ..." with the
    Exploratory count, "conditional ..." with Check first, "close <listing/pick>" with Match + Check
    first, and other result nouns with all cards shown. "No ..." statements are kept (cards can only be
    removed by the checks, never added). Returns (kept text, removed sentences).
    """
    total = counts["match"] + counts["conditional"] + counts["exploratory"]
    text = (summary or "").strip()
    kept, removed = [], []
    for sentence in _SENTENCE_END.split(text):
        wrong = False
        for m in _COUNT_CLAIM.finditer(sentence):
            raw, quals, noun = m.group(1).lower(), m.group(2).lower(), m.group(3).lower()
            said = int(raw) if raw.isdigit() else _NUMBERS[raw]
            before = sentence[:m.start()]
            if noun.startswith("match") and (said == 1) != (noun == "match"):
                continue  # a verb: "this one matches ...", "both match ...", "the two workshops match because ..."
            if _POOL_BEFORE.search(before):
                continue
            if not noun.startswith("match") and "exploratory" not in quals and not _FOUND_BEFORE.search(before):
                continue
            if "exploratory" not in quals and _TO_CHECK_AFTER.match(sentence[m.end():]):
                expected = counts["conditional"]
            elif "exploratory" in quals:
                expected = counts["exploratory"]
            elif "conditional" in quals:
                expected = counts["conditional"]
            elif noun.startswith("match"):
                expected = counts["match"]
            elif "close" in quals:
                expected = counts["match"] + counts["conditional"]
            else:
                expected = total
            wrong = wrong or said != expected
        (removed if wrong else kept).append(sentence)
    if not removed:
        return text, []
    return " ".join(s for s in kept if s), removed


def quotable_text(record: Record) -> str:
    return norm(page_text(record))


def _check_quote(quote: Any, haystack: str) -> tuple[str | None, bool]:
    text = str(quote or "").strip().strip('"').strip()
    if not text:
        return None, False
    return text, norm(text.rstrip(".…")) in haystack


def _facts(record: Record, card: dict) -> list[dict]:
    """Field-level provenance: value shown to the user + the page wording it came from."""
    seen: set[tuple[str, str]] = set()
    facts = []
    values = {
        "when": card.get("when_text") or (card.get("next_session") or {}).get("when_text") or record.date_text,
        "format": record.format_text, "location": card.get("location_label"), "organizer": record.organizer,
        "cost": record.cost_text, "registration": record.registration_text or card.get("registration_url"),
        "capacity": record.capacity_text,
    }
    for ev in record.evidence:
        label = _FACT_FIELDS.get(ev.field)
        if not label or (label, ev.quote) in seen:
            continue
        seen.add((label, ev.quote))
        value = "; ".join(record.eligibility_texts) if label == "conditions" else values.get(label)
        facts.append({"field": label, "value": value, "page_wording": ev.quote, "basis": ev.basis,
                      "source_url": record.url, "collected_at": record.collected_at})
    for label in ("cost", "capacity", "location", "format"):
        if not values.get(label) and not any(f["field"] == label for f in facts):
            facts.append({"field": label, "value": None, "page_wording": None, "basis": "not stated on the page",
                          "source_url": record.url, "collected_at": record.collected_at})
    return facts


def _next_steps(record: Record, card: dict, conditions: list[Condition]) -> list[str]:
    steps = [f"Read the original page: {card['url']}"]
    checks = [c.text for c in conditions if c.status == "to_confirm"]
    if checks:
        steps.append("Confirm before you plan on it: " + " ".join(checks))
    if card.get("not_stated"):
        steps.append("Not stated on the page (ask the organizer if it matters): " + ", ".join(card["not_stated"]) + ".")
    if card.get("registration_url"):
        steps.append(f"Registration is on the organizer's site ({card['registration_url']}); a link does not guarantee a spot.")
    elif record.registration_text:
        steps.append(f"How to register, as written: “{record.registration_text}”")
    return steps


def _context(session: ListingSession) -> dict:
    """What was searched and when: the date windows used for grouping and each source's data state."""
    view = session.view  # type: ignore[attr-defined]
    sources = [{k: s.get(k) for k in ("name", "data_mode", "collected_at_text", "n_records", "last_outcome",
                                      "last_attempt_text", "simulated")} for s in view["sources"]]
    return {"windows": view["windows"], "sources": sources, "n_listings": len(session.cards)}


def _when_label(card: dict) -> str | None:
    return card.get("when_text") or (card.get("next_session") or {}).get("when_text") or card.get("date_text")


def _empty(note: str, session: ListingSession | None = None) -> dict:
    return {"picks": [], "excluded": [], "dropped": [], "also_read": [], "understood": None, "summary": "",
            "follow_up_question": None, **(_context(session) if session is not None else {}),
            "verification": {"checked": 0, "kept": 0, "excluded": 0, "dropped": 0, "quotes_total": 0,
                             "quotes_verified": 0, "details_redacted": 0, "note": note}}


def verify_output(output: Any, session: ListingSession) -> dict:
    """Return the verified result shown to the user, plus a summary of what was checked."""
    if not isinstance(output, dict):
        return _empty("No structured output to verify.", session)
    understood = output.get("understood") if isinstance(output.get("understood"), dict) else {}
    windows = session.view["windows"]  # type: ignore[attr-defined]
    terms = sorted({t for t in session.search_terms} | {w.lower() for i in understood.get("interests", []) for w in str(i).split() if len(w) >= 2})
    kept: list[dict] = []
    excluded: list[dict] = []
    dropped: list[dict] = []
    quotes_total = quotes_ok = redacted = exploratory = 0
    seen: set[str] = set()
    for pick in output.get("picks") or []:
        if not isinstance(pick, dict):
            continue
        rid = str(pick.get("record_id", "")).strip()
        reason = None
        if rid in seen:
            reason = "duplicate pick"
        elif rid not in session.records:
            reason = "record_id does not exist in the stored listings (possible fabrication)"
        elif rid not in session.read_ids:
            reason = "the agent did not read this listing with get_listing in this run"
        elif rid not in session.cards:
            reason = "listing is no longer available: " + session.unavailable.get(rid, "it is in the past")
        elif not session.cards[rid].get("url"):
            reason = "the stored record has no openable http(s) source link"
        if reason:
            dropped.append({"record_id": rid, "reason": reason})
            continue
        seen.add(rid)
        record, card = session.records[rid], session.cards[rid]
        haystack = quotable_text(record)

        # --- reasoning (model text), checked word for word
        verified, unverified = [], []
        for quote in (pick.get("evidence_quotes") or [])[:3]:
            text, ok = _check_quote(quote, haystack)
            if text is None:
                continue
            quotes_total += 1
            (verified if ok else unverified).append(text)
            quotes_ok += ok
        interaction_quote, interaction_ok = _check_quote(pick.get("interaction_quote"), haystack)
        link_quote, link_ok = _check_quote(pick.get("link_quote"), haystack)
        free_text = {k: str(pick.get(k) or "") for k in ("why", "interaction", "exploration_link")}
        rejected: list[str] = []
        for key, text in free_text.items():
            bad = unsupported_details(text, record)
            if bad:
                rejected += [f"{key} -> {b}" for b in bad]
                free_text[key] = redact_details(text, bad)
        redacted += len(rejected)
        reasoning = {
            "why": free_text["why"],
            "interaction": free_text["interaction"] if interaction_ok else NO_INTERACTION,
            "interaction_quote": interaction_quote if interaction_ok else None,
            "interaction_grounded": interaction_ok,
            "exploration_link": free_text["exploration_link"] or None,
            "link_quote": link_quote if link_ok else None,
            "verified_quotes": verified,
            "unverified_quotes": unverified + ([interaction_quote] if interaction_quote and not interaction_ok else [])
                                 + ([link_quote] if link_quote and not link_ok else []),
            "rejected_details": rejected,
            "author": "gpt-6-luna (matcher); quotes checked by code",
        }

        # --- relevance, conditions and status (code)
        relevance = topic_matches(terms, record)
        conditions = evaluate(record, card, understood, windows)
        model_fit = pick.get("fit")
        status_conditions = verdict(conditions)
        if status_conditions == "excluded":
            excluded.append({"record_id": rid, "title": record.title, "url": card["url"],
                             "section": session.sections.get(rid), "when": _when_label(card),
                             "reasons": [c.text for c in conditions if c.status == "not_met"],
                             "conditions": [c.to_dict() for c in conditions]})
            continue
        # A real, available listing removed by a check stays openable (title + server link), so anything
        # the AI summary mentions can still be opened.
        listing = {"title": record.title, "url": card["url"], "section": session.sections.get(rid), "when": _when_label(card)}
        if model_fit == "exploratory" or not relevance:
            if not link_ok:
                dropped.append({"record_id": rid, "reason": "exploratory pick without a verified quote showing the connection"
                                if model_fit == "exploratory" else "none of your interest words appear on the page and no verified link was given",
                                **listing})
                continue
            if exploratory >= MAX_EXPLORATORY:
                dropped.append({"record_id": rid, "reason": f"more than {MAX_EXPLORATORY} exploratory picks", **listing})
                continue
            exploratory += 1
            status = "exploratory"
        else:
            status = "conditional" if status_conditions == "conditional" else "match"
        if len(kept) >= MAX_PICKS:
            dropped.append({"record_id": rid, "reason": f"more than {MAX_PICKS} picks", **listing})
            continue
        kept.append({
            "record_id": rid,
            "status": status,
            "section": session.sections.get(rid),
            "model_fit": model_fit,
            "reasoning": reasoning,
            "relevance": relevance,
            "conditions": [c.to_dict() for c in conditions],
            "next_steps": _next_steps(record, card, conditions),
            "facts": _facts(record, card),
            "grounded": bool(verified),
            "card": card,
        })
    order = {"match": 0, "conditional": 1, "exploratory": 2}
    kept.sort(key=lambda p: order[p["status"]])

    # Listings the matcher read but did not recommend, with the code's own verdict and a source link,
    # so anything the AI summary mentions can still be opened (and known-unmet ones say so).
    handled = {p["record_id"] for p in kept} | {e["record_id"] for e in excluded} | {d["record_id"] for d in dropped}
    also_read = []
    for rid in sorted(session.read_ids - handled):
        if rid not in session.cards or not session.cards[rid].get("url"):
            continue
        record, card = session.records[rid], session.cards[rid]
        conditions = evaluate(record, card, understood, windows)
        v = verdict(conditions)
        also_read.append({
            "record_id": rid, "title": record.title, "url": card["url"], "section": session.sections.get(rid),
            "when": _when_label(card), "verdict": {"excluded": "not_a_fit", "conditional": "check_first"}.get(v, "no_open_condition"),
            "reasons": [c.text for c in conditions if c.status == ("not_met" if v == "excluded" else "to_confirm")],
        })
    counts = code_counts(kept, excluded, dropped)
    summary, summary_removed = reconcile_summary(str(output.get("summary") or ""), counts)
    return {
        "understood": output.get("understood"),
        "summary": summary,
        "headline": headline(counts),
        "counts": counts,
        "follow_up_question": output.get("follow_up_question"),
        "picks": kept,
        "excluded": excluded,
        "dropped": dropped,
        "also_read": also_read,
        **_context(session),
        "verification": {
            "checked": len(kept) + len(excluded) + len(dropped),
            "kept": len(kept),
            "excluded": len(excluded),
            "dropped": len(dropped),
            "quotes_total": quotes_total,
            "quotes_verified": quotes_ok,
            "details_redacted": redacted,
            "summary_sentences_removed": summary_removed,
            "listings_read": sorted(session.read_ids),
            "note": "Deterministic check by code (no model call): IDs, availability, verbatim quotes, "
                    "unsupported details, participation conditions against what you said, and counts "
                    "stated in the AI summary against the final cards.",
        },
    }
