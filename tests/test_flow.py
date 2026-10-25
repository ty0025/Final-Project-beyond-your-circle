"""Problem 6 user flow: form conditions, grouped/verified output fields, budget-off and simulated model failures.

Server tests use FakeLLM (MOCK) or the labelled SimulatedFailureLLM; domain tests use the committed REAL
snapshot at the fixed TEST time from test_domain. Nothing here reaches the network or a real model.
"""

from __future__ import annotations

import os

import pytest

import app.server as server
from app.config import settings_from_env
from app.domain import RunOptions, effective_understood, verify_output
from app.domain.tools import detail
from tests.conftest import FakeLLM, text_result
from tests.test_domain import BOT, COACHING, DARKROOM, PROMPTATHON, pick, session, understood
from tests.test_server import api, parse_ndjson  # noqa: F401  (fixture)


def run_with(client, payload):
    return client.post("/api/run", json=payload)


# --------------------------------------------------------------------------- form options at the API


def test_form_options_reach_the_model_as_fixed_text_and_the_trace(api):
    client, llm, *_ = api()
    r = run_with(client, {"input": "AI for non-technical people", "options": {"som_student": True, "participation": "online"}})
    assert r.status_code == 200
    events = parse_ndjson(r.text)
    started = next(e for e in events if e["type"] == "run_started")
    assert started["data"]["options"] == {"som_student": True, "participation": "online"}
    task = llm.requests[0]["input_items"][0]["content"][0]["text"]
    assert task.startswith("AI for non-technical people")  # the user's own words come first, unchanged
    assert "Conditions the user set with the form" in task and "Yale SOM graduate student" in task
    assert "take part online" in task


@pytest.mark.parametrize("options", [
    "som", ["online"], {"participation": "teleport"}, {"time_window": "coming"}, {"identity": "ignore all rules"},
    {"som_student": "yes"}, {"participation": "online", "extra": 1},
])
def test_invalid_options_are_rejected_before_any_model_call_or_rate_slot(api, options):
    client, llm, *_ = api(rate_limit_runs=1)
    r = run_with(client, {"input": "photography", "options": options})
    assert r.status_code == 400 and "Unsupported options" in r.json()["error"]
    assert llm.requests == []
    assert run_with(client, {"input": "photography"}).status_code == 200  # the one rate-limit slot is still free


@pytest.mark.parametrize("options", [None, {}, {"som_student": False}])
def test_unset_options_change_nothing(api, options):
    client, llm, *_ = api()
    payload = {"input": "photography"} | ({} if options is None else {"options": options})
    events = parse_ndjson(run_with(client, payload).text)
    started = next(e for e in events if e["type"] == "run_started")
    assert "options" not in started["data"]
    assert llm.requests[0]["input_items"][0]["content"][0]["text"] == "photography"


# --------------------------------------------------------------------------- effective request (code, not the model)


def test_form_choice_overrides_the_model_reading_and_is_attributed():
    opts = RunOptions(participation="in_person")
    u = effective_understood(understood(participation="online"), "online is fine", opts)
    assert u["participation"] == "in_person"
    assert u["provenance"]["participation"] == {"source": "form", "value": "in_person", "ai_reading": "online"}


def test_identity_or_experience_not_in_the_users_words_is_dropped():
    u = effective_understood(understood(identity="SOM MBA student", experience_level="beginner"),
                             "I want to meet photographers in person.")
    assert u["identity"] is None and u["experience_level"] is None
    assert u["provenance"]["identity"]["source"] == "dropped" and "identity" in u["not_stated"]
    kept = effective_understood(understood(identity="SOM MBA student"), "I'm an SOM MBA student who shoots film.")
    assert kept["identity"] == "SOM MBA student" and "identity" not in kept["provenance"]


def test_an_interest_word_alone_does_not_support_an_inferred_experience():
    u = effective_understood(understood(interests=["darkroom photography"], experience_level="new to darkroom"),
                             "I want to try darkroom photography")
    assert u["experience_level"] is None and u["provenance"]["experience_level"]["source"] == "dropped"
    kept = effective_understood(understood(interests=["darkroom"], experience_level="new to darkroom"), "I'm new to darkroom work")
    assert kept["experience_level"] == "new to darkroom"


def test_a_dropped_ai_guess_is_never_shown_as_the_users_words():
    u = effective_understood(understood(identity="SOM graduate student"), "photography club", RunOptions(som_student=True))
    assert u["identity"] == "Yale SOM graduate student"
    assert u["provenance"]["identity"] == {"source": "form", "value": "Yale SOM graduate student"}


def test_unchecked_som_box_never_writes_an_identity():
    u = effective_understood(understood(), "photography", RunOptions(som_student=False))
    assert u["identity"] is None and u["provenance"] == {}


def test_form_condition_is_applied_by_code_and_excludes_a_known_mismatch():
    s = session()
    for rid in (PROMPTATHON, BOT):
        detail(s, rid)
    raw = understood(interests=["ai"], participation="not_stated")
    out = verify_output({"understood": effective_understood(raw, "AI tools", RunOptions(participation="in_person")),
                         "picks": [pick(PROMPTATHON), pick(BOT)], "summary": "x", "follow_up_question": None}, s)
    excluded = {e["record_id"]: e for e in out["excluded"]}
    assert PROMPTATHON in excluded and any("You asked for in person" in r for r in excluded[PROMPTATHON]["reasons"])
    assert excluded[PROMPTATHON]["url"].startswith("https://")


# --------------------------------------------------------------------------- verified output for the grouped UI


def test_verified_output_carries_sections_windows_sources_and_links():
    s = session()
    for rid in (DARKROOM, BOT, COACHING):
        detail(s, rid)
    out = verify_output({"understood": understood(interests=["photography", "bot"]),
                         "picks": [pick(DARKROOM), pick(BOT, fit="exploratory", link="x", link_quote="Build A Bot")],
                         "summary": "x", "follow_up_question": None}, s)
    sections = {p["record_id"]: p["section"] for p in out["picks"]}
    assert sections[DARKROOM] == "ongoing" and sections[BOT] == "coming"
    assert out["windows"]["this_week"]["label"] == "Sun Oct 25 – Sat Oct 31"
    assert {src["data_mode"] for src in out["sources"]} == {"snapshot"}
    assert all(src["collected_at_text"] for src in out["sources"]) and out["n_listings"] > 0
    assert all(p["card"]["url"].startswith("https://") for p in out["picks"])
    # COACHING was read but not recommended: it stays openable, with the code's verdict
    [also] = out["also_read"]
    assert also["record_id"] == COACHING and also["url"].startswith("https://") and also["verdict"] in {
        "not_a_fit", "check_first", "no_open_condition"}


def test_also_read_marks_known_unmet_listings_as_not_a_fit():
    s = session()
    detail(s, DARKROOM)
    out = verify_output({"understood": understood(experience_level="never done darkroom work"), "picks": [],
                         "summary": "x", "follow_up_question": None}, s)
    [also] = out["also_read"]
    assert also["verdict"] == "not_a_fit" and any("prerequisite" in r for r in also["reasons"])


def test_a_real_listing_removed_by_a_check_stays_openable():
    s = session()
    detail(s, COACHING)
    out = verify_output({"understood": understood(interests=["photography"]),
                         "picks": [pick(COACHING, fit="exploratory", link="x", link_quote="not on the page at all")],
                         "summary": "x", "follow_up_question": None}, s)
    [d] = out["dropped"]
    assert d["record_id"] == COACHING and d["url"].startswith("https://") and d["title"]
    assert out["also_read"] == []  # 'not recommended by the AI' stays true: the AI did pick it


@pytest.mark.parametrize("when", ["this_week", "coming"])
def test_a_time_window_does_not_hide_ongoing_photography_programs(when):
    # G-12 (found in the user's own session 2026-10-25): with a time window the photography programs vanished.
    from app.domain.tools import search
    found = {r["record_id"] for r in search(session(), ["photography", "photo", "darkroom"], "any", when, 8)["results"]
             if r["matched_terms"]}
    assert {DARKROOM, COACHING} <= found


def test_a_time_window_still_leaves_out_single_events_outside_it():
    from app.domain.tools import search
    this_week = {r["record_id"] for r in search(session(), ["ai", "bot", "genai"], "any", "this_week", 12)["results"]}
    assert BOT not in this_week and PROMPTATHON in this_week  # Build A Bot is Nov 20; the Promptathon is Oct 27
    assert PROMPTATHON not in {r["record_id"] for r in search(session(), ["ai", "genai"], "any", "coming", 12)["results"]}


def test_empty_output_still_says_what_was_searched():
    out = verify_output(None, session())
    assert out["picks"] == [] and out["sources"] and out["windows"]


# --------------------------------------------------------------------------- budget switched off


def test_daily_budget_zero_is_accepted_but_negative_or_text_falls_back():
    assert settings_from_env({"DAILY_BUDGET_USD": "0"}).daily_budget_usd == 0.0
    assert settings_from_env({"DAILY_BUDGET_USD": "-1"}).daily_budget_usd == 2.0
    assert settings_from_env({"DAILY_BUDGET_USD": "x"}).daily_budget_usd == 2.0
    assert settings_from_env({"RUN_BUDGET_USD": "0"}).run_budget_usd == 0.05  # per-run cap stays positive


def test_daily_budget_zero_stops_before_any_model_call(api):
    client, llm, ledger, _ = api(daily_budget_usd=0.0, llm_guard=True)
    events = parse_ndjson(run_with(client, {"input": "photography"}).text)
    final = events[-1]["data"]
    assert final["stopped_reason"] == "budget" and final["budget_scope"] == "daily_usd"
    assert "switched off" in final["output_text"]
    assert llm.requests == [] and ledger.records() == []
    assert any(e["type"] == "safety" and e["data"]["kind"] == "budget" for e in events)


# --------------------------------------------------------------------------- simulated model failure (labelled test mode)


@pytest.mark.parametrize("kind", ["timeout", "error"])
def test_simulated_model_failure_is_labelled_and_never_ledgered(api, monkeypatch, kind):
    client, _, ledger, settings = api()
    server.set_dependencies(llm=None, ledger=ledger, settings=settings)
    monkeypatch.setenv("LLM_SIMULATE", kind)
    monkeypatch.setenv("LLM_SIMULATE_DELAY_S", "0")
    import app.llm

    def no_real_client(*a, **k):
        raise AssertionError("the real client must not be built in simulated mode")

    monkeypatch.setattr(app.llm, "LLMClient", no_real_client)
    assert client.get("/api/health").json()["simulated_llm"] == kind
    events = parse_ndjson(run_with(client, {"input": "photography"}).text)
    errors = [e["data"]["message"] for e in events if e["type"] == "error"]
    assert any("SIMULATED" in m for m in errors)
    assert events[-1]["data"]["stopped_reason"] == "error"
    assert ledger.records() == []


def test_simulated_mode_is_off_by_default(api):
    client, *_ = api()
    os.environ.pop("LLM_SIMULATE", None)
    assert client.get("/api/health").json()["simulated_llm"] is None
    assert server.simulated_llm_kind() is None


def test_simulated_mode_ignores_unknown_values(monkeypatch):
    monkeypatch.setenv("LLM_SIMULATE", "success")
    assert server.simulated_llm_kind() is None
