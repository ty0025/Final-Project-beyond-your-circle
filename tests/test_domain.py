"""Beyond Your Circle domain: listing tools, output contract and the deterministic verifier.

Uses the committed REAL snapshot (data/snapshots) at a fixed, labelled TEST time; model turns are
scripted with FakeLLM (MOCK: proves interfaces only, not model quality).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from app.collect.sources import SOURCES
from app.collect.store import load_source
from app.discover import NY
from app.domain import ListingSession, Recommendations, verify_output
from app.domain.tools import detail, search
from app.events import RunTrace
from app.ledger import UsageLedger
from app.orchestrator import ALLOW_DOMAINS, APP_META, build_team, run_task
from app.safety import Canary
from app.tools import strict_schema
from tests.conftest import FakeLLM, assert_strict_schema, call_result, json_result

SNAPSHOTS = Path(__file__).resolve().parents[1] / "data" / "snapshots"
TEST_NOW = datetime(2026, 10, 25, 9, 0, tzinfo=NY)  # labelled TEST reference time
DARKROOM = "caw-photo-dc1d381afb"
COACHING = "caw-photo-d1411fc392"
BOT = "ycgs-events-9d7a535869"
PROMPTATHON = "ycgs-events-5971125a69"


def session() -> ListingSession:
    results = [load_source(s, runs_dir=Path("/nonexistent-test-dir"), snapshot_dir=SNAPSHOTS) for s in SOURCES]
    return ListingSession.from_results(results, now=TEST_NOW)


def understood(**overrides) -> dict:
    base = {"interests": ["photography"], "purpose": "meet people", "purpose_type": "meet_people_or_join_community",
            "participation": "in_person", "play_or_watch": "not_applicable", "experience_level": None,
            "identity": None, "time_window": "not_stated", "time_preference": None, "location_preference": None,
            "not_stated": ["experience_level", "identity", "time_window", "location_preference"]}
    return base | overrides


def pick(rid, fit="close", quotes=(), why="Fits your purpose.", interaction="not described on the page",
         interaction_quote=None, link=None, link_quote=None) -> dict:
    return {"record_id": rid, "fit": fit, "why": why, "interaction": interaction, "interaction_quote": interaction_quote,
            "exploration_link": link, "link_quote": link_quote, "evidence_quotes": list(quotes)}


def run_verify(picks, s=None, **u) -> dict:
    s = s or session()
    for p in picks:
        if p["record_id"] in s.records and p["record_id"] in s.cards:
            detail(s, p["record_id"])
    return verify_output({"understood": understood(**u), "picks": picks, "summary": "x", "follow_up_question": None}, s)


# --------------------------------------------------------------------------- tools


def test_search_ranks_keyword_matches_and_records_seen_ids():
    s = session()
    out = search(s, ["photography", "darkroom", "film"], "any", "all", 8)
    ids = [r["record_id"] for r in out["results"]]
    assert set(ids[:2]) == {DARKROOM, COACHING}
    assert out["n_matching"] == 2 and out["results"][0]["matched_terms"]
    assert out["results"][2]["matched_terms"] == []  # a few non-matching items, labelled as such
    assert set(ids) <= s.seen_ids and s.read_ids == set() and {"photography", "darkroom"} <= s.search_terms
    assert out["now"].startswith("Sun Oct 25")


def test_search_respects_participation():
    ids = [r["record_id"] for r in search(session(), ["photography", "darkroom"], "online", "all", 8)["results"]]
    assert DARKROOM not in ids and COACHING in ids  # known in-person item excluded; unknown format kept


def test_get_listing_reads_real_record_and_rejects_unknown_ids():
    s = session()
    d = detail(s, DARKROOM)
    assert d["title"] == "Open Darkroom Session" and d["cost"] == "Sessions are $30 each."
    assert d["upcoming_sessions"][0].startswith("Fri Oct 30, 2026 · 6:00 PM–9:00 PM EDT")
    with pytest.raises(ValueError):
        detail(s, "caw-photo-0000000000")
    with pytest.raises(ValueError):
        detail(s, "../../app/config.py")


def test_tools_are_registered_untrusted_with_strict_schemas(make_settings):
    specs, registry, entry = build_team(make_settings(), session())
    assert entry == "matcher" and specs["matcher"].tools == ["search_listings", "get_listing"]
    assert specs["matcher"].sub_agents == [] and specs["matcher"].max_steps == 4
    for name in ("search_listings", "get_listing"):
        assert registry.get(name).untrusted_output
        assert_strict_schema(next(s for s in registry.schemas([name]))["parameters"])
    assert_strict_schema(strict_schema(Recommendations))
    assert {a["name"] for a in APP_META["pipeline"]} == {"screen", "guard", "matcher", "verifier"}
    assert "yale.edu" in ALLOW_DOMAINS and not any("harbor" in d for d in ALLOW_DOMAINS)


# --------------------------------------------------------------------------- verifier: IDs, quotes, facts


def test_verifier_drops_fabricated_unread_and_duplicate_picks():
    s = session()
    detail(s, DARKROOM)
    out = verify_output({"understood": understood(), "summary": "x", "follow_up_question": None, "picks": [
        pick(DARKROOM, quotes=["comfortable working independently"]),
        pick("caw-photo-ffffffffff"),  # fabricated
        pick("ycgs-events-be4bf73baf"),  # real but never read with get_listing
        pick(DARKROOM),  # duplicate
    ]}, s)
    reasons = [d["reason"] for d in out["dropped"]]
    assert [p["record_id"] for p in out["picks"]] == [DARKROOM]
    assert any("does not exist" in r for r in reasons) and any("did not read" in r for r in reasons)
    assert "duplicate pick" in reasons


def test_reasoning_and_facts_are_kept_apart_with_provenance():
    out = run_verify([pick(DARKROOM, quotes=["comfortable working independently", "free lunch for everyone"])])
    p = out["picks"][0]
    assert p["reasoning"]["verified_quotes"] == ["comfortable working independently"]
    assert p["reasoning"]["unverified_quotes"] == ["free lunch for everyone"]
    cost = next(f for f in p["facts"] if f["field"] == "cost")
    assert cost["value"] == "Sessions are $30 each." and cost["page_wording"] == "Sessions are $30 each."
    assert cost["source_url"].startswith("https://creativeartsworkshop.org/") and cost["collected_at"]
    capacity = next(f for f in p["facts"] if f["field"] == "capacity")
    assert capacity["value"] is None and capacity["basis"] == "not stated on the page"


def test_verifier_rejects_details_the_page_does_not_contain():
    out = run_verify([pick(DARKROOM, quotes=["comfortable working independently"],
                           why="Drop in on Fridays for $5 at 7pm; details at https://evil.example/x.")])
    r = out["picks"][0]["reasoning"]
    kinds = {d.split(" -> ")[1].split(":")[0] for d in r["rejected_details"]}
    assert {"price", "clock_time", "url"} <= kinds
    assert "$5" not in r["why"] and "evil.example" not in r["why"] and "Fridays" in r["why"]  # Friday is on the page
    assert out["verification"]["details_redacted"] >= 3


def test_interaction_is_only_claimed_with_a_verified_quote():
    good = run_verify([pick(DARKROOM, quotes=["comfortable working independently"], interaction="a practice session",
                            interaction_quote="This darkroom practice session")])["picks"][0]["reasoning"]
    bad = run_verify([pick(DARKROOM, quotes=["comfortable working independently"], interaction="you will meet pro photographers",
                           interaction_quote="meet professional photographers")])["picks"][0]["reasoning"]
    assert good["interaction_grounded"] and good["interaction"] == "a practice session"
    assert not bad["interaction_grounded"] and "not guaranteed" in bad["interaction"]
    assert "meet professional photographers" in bad["unverified_quotes"]


def test_exploratory_needs_a_verified_link_and_is_capped():
    s = session()
    picks = [
        pick(BOT, fit="exploratory", link="hands-on building", link_quote="design their own tailored chatbot"),
        pick(COACHING, fit="exploratory", link="made up", link_quote="a quote that is not on the page"),
        pick(PROMPTATHON, fit="exploratory", link="hands-on", link_quote="Intro to GenAI Promptathon"),
        pick("ycgs-events-357e37a349", fit="exploratory", link="hobby meetup", link_quote="YCGS Drone Hobbyist Gathering II"),
    ]
    out = run_verify(picks, s, participation="either", interests=["chatbots"])
    assert [p["status"] for p in out["picks"]] == ["exploratory", "exploratory"]
    reasons = {d["record_id"]: d["reason"] for d in out["dropped"]}
    assert "without a verified quote" in reasons[COACHING] and "more than 2 exploratory" in reasons["ycgs-events-357e37a349"]


# --------------------------------------------------------------------------- verifier: conditions decide the status


def test_known_unmet_prerequisite_excludes_and_unknown_makes_conditional():
    beginner = run_verify([pick(DARKROOM, quotes=["comfortable working independently"])], experience_level="never taken a darkroom class")
    assert beginner["picks"] == [] and "prerequisite" in beginner["excluded"][0]["reasons"][0]
    unknown = run_verify([pick(DARKROOM, quotes=["comfortable working independently"])])
    p = unknown["picks"][0]
    assert p["status"] == "conditional"
    assert any(c["kind"] == "prerequisite" and c["status"] == "to_confirm" for c in p["conditions"])
    assert any("Confirm before you plan on it" in step for step in p["next_steps"])


def test_format_mismatch_excludes_even_a_close_pick():
    out = run_verify([pick(DARKROOM, quotes=["comfortable working independently"])], participation="online")
    assert out["picks"] == [] and "online" in out["excluded"][0]["reasons"][0]


def test_clear_match_when_no_hard_condition_is_open():
    out = run_verify([pick(PROMPTATHON, quotes=["Intro to GenAI Promptathon"])], interests=["ai"], participation="online",
                     purpose_type="learn_or_discuss_topic", experience_level="not technical")
    p = out["picks"][0]
    assert p["status"] == "match", p["conditions"]
    assert any(c["kind"] == "prerequisite" and c["status"] == "met" for c in p["conditions"])


def test_time_window_is_checked_with_real_dates():
    out = run_verify([pick(BOT, quotes=["Build A Bot Workshop"])], interests=["bot"], participation="either", time_window="this_week")
    assert out["picks"] == [] and "this week" in out["excluded"][0]["reasons"][0]  # Nov 20 is not in Oct 25-31


# --------------------------------------------------------------------------- whole pipeline (MOCK model)


def test_run_task_end_to_end_with_mock_model(make_settings):
    settings = make_settings()
    ledger = UsageLedger(settings.runs_dir / "usage.jsonl")
    trace = RunTrace()
    llm = FakeLLM([
        call_result(("search_listings", {"interests": ["photography", "darkroom", "film"], "participation": "in_person",
                                         "when": "all", "max_results": 8})),
        call_result(("get_listing", {"record_id": DARKROOM}), ("get_listing", {"record_id": COACHING})),
        json_result({
            "understood": understood(),
            "picks": [pick(DARKROOM, quotes=["comfortable working independently"], interaction="a practice session",
                           interaction_quote="This darkroom practice session"),
                      pick(COACHING, fit="exploratory", link="one-on-one help", link_quote="personalized one-on-one coaching")],
            "summary": "One conditional match and one exploratory option.",
            "follow_up_question": "Have you taken a darkroom class before?",
        }),
    ])

    import app.orchestrator as orch

    original = orch.build_team
    orch.build_team = lambda s: original(s, session())  # fixed TEST time + committed snapshot
    try:
        final = asyncio.run(run_task("I shoot film and want to meet photographers in person.", llm=llm,
                                     settings=settings, ledger=ledger, trace=trace, canary=Canary()))
    finally:
        orch.build_team = original

    assert final["stopped_reason"] == "final" and final["output_text"] == "One conditional match and one exploratory option."
    picks = final["output"]["picks"]
    assert [(p["record_id"], p["status"]) for p in picks] == [(DARKROOM, "conditional"), (COACHING, "exploratory")]
    types = [e.type for e in trace.events]
    assert types.count("model_call") == 3 and "verification" in types
    verification = next(e for e in trace.events if e.type == "verification")
    assert verification.agent == "verifier" and verification.data["kind"] == "code"
    assert {r["mode"] for r in ledger.records()} == {"mock"}  # FakeLLM calls are never labelled live
    assert json.dumps(final)
