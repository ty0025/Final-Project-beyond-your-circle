"""Problem-5 functional cases (fixed TEST time; real snapshot + manually verified case records)."""

from __future__ import annotations

import pytest

from tests.fixtures.cases.specs import CASES, case_session, run_case

_SESSION = None


def outcome(case_id: str) -> dict[str, dict]:
    global _SESSION
    _SESSION = _SESSION or case_session()
    result = run_case(next(c for c in CASES if c["id"] == case_id), _SESSION)
    return {row["title"]: row for row in result["rows"]}


def test_c1_beginner_in_person_photography():
    o = outcome("C1")
    assert o["Open Darkroom Session"]["status"] == "excluded"  # prerequisite vs "never done darkroom work"
    assert "prerequisite" in o["Open Darkroom Session"]["reasons"][0]
    assert o["New Haven Camera Club"]["status"] == "excluded"  # on Zoom vs in person
    assert o["Photography Individual Coaching"]["status"] == "conditional"  # format not stated


def test_c2_club_online_fine():
    o = outcome("C2")
    assert o["New Haven Camera Club"]["status"] == "match" and o["New Haven Camera Club"]["interaction"]
    assert o["Open Darkroom Session"]["status"] == "conditional"  # prerequisite unknown, not assumed


def test_c3_play_closed_and_future_registration():
    o = outcome("C3")
    volley = o["Grad/Pro Intramurals: Fall Volleyball"]
    assert volley["status"] == "excluded" and "Registration deadline passed" in volley["reasons"][0]  # season still running
    hoops = o["Grad/Pro Intramurals: Winter Basketball"]
    assert hoops["status"] == "conditional"
    assert any("membership" in t for t in hoops["to_confirm"]) and any("limited" in t for t in hoops["to_confirm"])


def test_c4_watching_is_not_playing():
    o = outcome("C4")
    assert o["Grad/Pro Intramurals: Winter Basketball"]["status"] == "excluded"
    assert "watch" in o["Grad/Pro Intramurals: Winter Basketball"]["reasons"][0]


def test_c5_ai_intro_for_non_technical():
    o = outcome("C5")
    assert o["Intro to GenAI Promptathon"]["status"] == "match"
    assert o["Build A Bot Workshop"]["status"] == "conditional"  # capacity capped at 50


def test_c6_this_week_in_person_uses_real_dates():
    o = outcome("C6")
    assert o["Build A Bot Workshop"]["status"] == "excluded" and "this week" in o["Build A Bot Workshop"]["reasons"][0]
    assert o["Intro to GenAI Promptathon"]["status"] == "excluded"  # online vs in person
    part2 = next(v for k, v in o.items() if k.startswith("Telling Stories with Maps - Part II"))
    assert part2["status"] == "conditional"  # audience "designed for instructors" + Part I required


def test_c7_unknown_age_rule_is_conditional():
    assert outcome("C7")["YCGS Drone Hobbyist Gathering II"]["status"] == "conditional"


def test_c8_empty_result_is_empty():
    assert outcome("C8") == {}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_every_excluded_item_has_a_reason(case):
    for row in run_case(case, case_session())["rows"]:
        if row["status"] == "excluded":
            assert row["reasons"]
