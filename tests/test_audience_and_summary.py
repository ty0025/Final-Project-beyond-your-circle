"""G-11 (who may take part) and the summary-count check (deterministic, no model call).

Synthetic one-sentence records are TEST data (not app data); the real committed snapshot is used only to
show that no stored record changes. Summary sentences are copied verbatim from saved real runs.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.collect.records import Record, finalize
from app.domain import load_prompt, verify_output
from app.domain.conditions import _PUBLIC_AUDIENCE, evaluate, verdict
from app.domain.tools import detail
from app.domain.verify import reconcile_summary
from app.events import RunTrace
from app.ledger import UsageLedger
from app.orchestrator import run_task
from app.safety import Canary
from tests.conftest import FakeLLM, call_result, json_result
from tests.test_domain import DARKROOM, pick, session, understood


def synthetic(text: str) -> Record:
    return finalize(Record(record_id="syn-0000000000", source_id="syn", kind="event", title="Synthetic test listing",
                           url="https://example.test/", publisher="test", organizer="test",
                           collected_at="2026-10-25T00:00:00+00:00", eligibility_texts=[text]))


def audience(text: str, identity: str | None) -> list:
    s = session()
    card = next(iter(s.cards.values()))  # only used for time/registration, which these profiles do not set
    conds = evaluate(synthetic(text), card, understood(identity=identity, participation="not_stated"), s.view["windows"])
    return [c for c in conds if c.kind in ("audience", "membership")]


# --------------------------------------------------------------------------- G-11: named groups need the user's words


def test_named_group_is_to_confirm_when_the_user_did_not_say_who_they_are():
    [c] = audience("This talk is open to all Yale students.", None)
    assert c.status == "to_confirm" and c.quote.startswith("open to all Yale students")  # not cut to "open to all"
    [c] = audience("Open to the Yale community.", None)
    assert c.status == "to_confirm"


def test_named_group_is_met_only_when_the_stated_identity_is_in_it():
    assert [c.status for c in audience("Open to Yale students only.", "SOM MBA student")] == ["met"]
    assert [c.status for c in audience("Open to members of the Yale community.", "Yale SOM graduate student")] == ["met"]
    # a stated identity that does not show membership: to confirm, never an exclusion
    conds = audience("Open to Yale students only.", "Yale staff member")
    assert [c.status for c in conds] == ["to_confirm"] and verdict(conds) == "conditional"


def test_graduate_group_is_not_met_for_an_undergraduate():
    text = "Current Yale Graduate Students who have a current PWG Membership"
    grad = {c.kind: c.status for c in audience(text, "SOM student")}
    undergrad = {c.kind: c.status for c in audience(text, "Yale undergraduate")}
    assert grad == {"audience": "met", "membership": "to_confirm"}
    assert undergrad == {"audience": "to_confirm", "membership": "to_confirm"}  # "undergraduate" contains "graduate"


@pytest.mark.parametrize("text", ["Free and open to the public.", "Open to all ages.", "Everyone is welcome."])
def test_truly_open_wording_stays_met_without_an_identity(text):
    assert [c.status for c in audience(text, None)] == ["met"]


# --------------------------------------------------------------------------- G-11: wording no rule models


@pytest.mark.parametrize("text", ["You must be a Yale NetID holder to attend.", "Restricted to Yale affiliates with a valid ID.",
                                  "Participation is by invitation only.", "Eligibility: current MBA students in good standing.",
                                  "You must have a valid Yale ID."])
def test_unrecognised_eligibility_wording_becomes_to_confirm(text):
    [c] = audience(text, "SOM MBA student")
    assert c.status == "to_confirm" and c.quote == text


@pytest.mark.parametrize("text", ["Attendees are also required to bring a laptop.", "Space is limited to 20 participants.",
                                  "Members of the public are welcome.", "Masks must be worn indoors.",
                                  "Participants must have a laptop."])
def test_catch_all_ignores_equipment_capacity_and_public_wording(text):
    assert audience(text, None) == []


def test_catch_all_never_duplicates_a_condition_already_quoted():
    kinds = [c.kind for c in audience("Current Yale Graduate Students who have a current PWG Membership", None)]
    assert kinds == ["audience", "membership"]
    s = session()
    darkroom = evaluate(s.records[DARKROOM], s.cards[DARKROOM], understood(), s.view["windows"])
    assert [c.kind for c in darkroom if c.kind in ("audience", "prerequisite")] == ["prerequisite"]


def test_no_stored_record_gets_audience_met_without_a_stated_identity():
    s = session()
    for rid, card in s.cards.items():
        for c in evaluate(s.records[rid], card, understood(), s.view["windows"]):
            if c.kind == "audience" and c.status == "met":
                assert _PUBLIC_AUDIENCE.search(c.quote or ""), (rid, c)


# --------------------------------------------------------------------------- summary counts vs final cards

C = lambda m, c, e: {"match": m, "conditional": c, "exploratory": e, "excluded": 0, "dropped": 0}  # noqa: E731

REAL_SUMMARIES = [  # (run_id, final card counts, first sentence of the saved summary, should be removed)
    ("r_ce638df7cf6e", C(1, 2, 0), "I found three close matches, all focused on learning or using AI tools.", True),
    ("r_c588d02ea0b5", C(2, 1, 0), "I found 3 close matches and no exploratory picks.", True),
    ("r_af384cbce5e9", C(0, 2, 0), "I found two close matches focused on trying generative AI tools or designing a chatbot.", True),
    ("r_0c89b3881d73", C(0, 1, 0), "I found one close in-person photography match, but the page doesn’t describe opportunities "
                                   "to socialize or specifically mention film photography.", True),
    ("r_21eea8b51494", C(0, 1, 0), "I found one close photography listing and no exploratory picks.", False),
    ("r_835194ffb88a", C(0, 0, 0), "I found no close or exploratory picks: the current stored listings have no volleyball "
                                   "or basketball activities.", False),
]


@pytest.mark.parametrize("run_id,counts,sentence,removed", REAL_SUMMARIES, ids=[r[0] for r in REAL_SUMMARIES])
def test_summary_sentence_with_a_wrong_count_is_removed(run_id, counts, sentence, removed):
    tail = "Two listings are labeled online but also mention in-person attendees, so their format should be confirmed."
    text, gone = reconcile_summary(f"{sentence} {tail}", counts)
    assert gone == ([sentence] if removed else [])
    assert tail in text  # "two listings ..." without a finding verb is a description, not a count claim


def test_consistent_counts_are_kept_word_for_word():
    text = "One conditional match and one exploratory option."
    assert reconcile_summary(text, C(0, 1, 1)) == (text, [])


def test_verifier_reports_code_counts_and_removed_summary_sentences():
    s = session()
    detail(s, DARKROOM)
    out = verify_output({"understood": understood(), "summary": "I found one close match. It recurs.",
                         "picks": [pick(DARKROOM, quotes=["comfortable working independently"])], "follow_up_question": None}, s)
    assert [p["status"] for p in out["picks"]] == ["conditional"]
    assert out["counts"] == C(0, 1, 0) and "1 to check first" in out["headline"]
    assert out["summary"] == "It recurs." and out["verification"]["summary_sentences_removed"] == ["I found one close match."]


def test_emptied_summary_falls_back_to_the_code_headline_not_raw_json(make_settings):
    settings = make_settings()
    llm = FakeLLM([
        call_result(("search_listings", {"interests": ["photography"], "participation": "any", "when": "all", "max_results": 8})),
        call_result(("get_listing", {"record_id": DARKROOM})),
        json_result({"understood": understood(), "summary": "I found two close matches.", "follow_up_question": None,
                     "picks": [pick(DARKROOM, quotes=["comfortable working independently"])]}),
    ])
    import app.orchestrator as orch

    original = orch.build_team
    orch.build_team = lambda st: original(st, session())  # fixed TEST time + committed snapshot
    try:
        final = asyncio.run(run_task("photography in person", llm=llm, settings=settings,
                                     ledger=UsageLedger(settings.runs_dir / "usage.jsonl"), trace=RunTrace(), canary=Canary()))
    finally:
        orch.build_team = original
    assert final["output"]["summary"] == ""
    assert final["output_text"] == final["output"]["headline"] and not final["output_text"].startswith("{")
    assert json.dumps(final)


def test_matcher_prompt_no_longer_asks_the_model_for_counts():
    prompt = load_prompt("matcher")
    assert "how many close and exploratory picks" not in prompt and "Do not state how many picks" in prompt


def test_browse_lists_named_group_wording_under_check_not_open():
    from datetime import datetime

    from app.discover import NY, build_discovery
    from app.collect.store import SourceResult
    rec = finalize(Record(record_id="syn-0000000001", source_id="syn", kind="event", title="Synthetic talk", url="https://example.test/t",
                          publisher="t", organizer="t", collected_at="2026-10-25T00:00:00+00:00", start="2026-10-27T18:00:00-04:00",
                          eligibility_texts=["This talk is open to all Yale students.", "Free and open to the public."]))
    d = build_discovery([SourceResult("syn", "snapshot", "2026-10-25T00:00:00+00:00", [rec], {})], now=datetime(2026, 10, 25, 9, tzinfo=NY))
    card = d["sections"]["this_week"][0]
    assert card["eligibility_open"] == ["Free and open to the public."]
    assert card["eligibility_check"] == ["This talk is open to all Yale students."]


# --------------------------------------------------------------------------- review fixes (issues 1-12, 14)


def synthetic_texts(texts: list[str], **fields) -> Record:
    return finalize(Record(record_id="syn-0000000000", source_id="syn", kind="event", title="Synthetic test listing",
                           url="https://example.test/", publisher="test", organizer="test",
                           collected_at="2026-10-25T00:00:00+00:00", eligibility_texts=list(texts), **fields))


def conditions_for(texts: list[str], identity: str | None, participation: str = "not_stated", **fields) -> list:
    s = session()
    card = next(iter(s.cards.values()))  # only used for time/registration, which these profiles do not set
    return evaluate(synthetic_texts(texts, **fields), card, understood(identity=identity, participation=participation),
                    s.view["windows"])


def browse(texts: list[str]) -> tuple[list[str], list[str]]:
    """Browse tab: (eligibility_open, eligibility_check) of one synthetic dated card."""
    from datetime import datetime

    from app.collect.store import SourceResult
    from app.discover import NY, build_discovery
    rec = finalize(Record(record_id="syn-0000000001", source_id="syn", kind="event", title="Synthetic talk", url="https://example.test/t",
                          publisher="t", organizer="t", collected_at="2026-10-25T00:00:00+00:00", start="2026-10-27T18:00:00-04:00",
                          eligibility_texts=list(texts)))
    d = build_discovery([SourceResult("syn", "snapshot", "2026-10-25T00:00:00+00:00", [rec], {})], now=datetime(2026, 10, 25, 9, tzinfo=NY))
    card = d["sections"]["this_week"][0]
    return card["eligibility_open"], card["eligibility_check"]


def find_open(text: str) -> bool:
    """Find: the page alone (no identity stated) says anyone may take part."""
    return any(c.status == "met" for c in audience(text, None))


# 1. A short quote from another check ("in-person", "open to all", "members of ...") must not hide a restriction.
def test_format_quote_does_not_hide_a_restriction_in_the_same_sentence():
    text = "This in-person workshop is restricted to Yale affiliates."
    conds = conditions_for([text], None, participation="in_person", format="in_person", format_text="in-person")
    assert ("format", "met") in [(c.kind, c.status) for c in conds]
    assert [(c.kind, c.status, c.quote) for c in conds if c.kind == "audience"] == [("audience", "to_confirm", text)]
    assert verdict(conds) == "conditional"


@pytest.mark.parametrize("text,identity", [
    ("Open to all; Yale ID required to enter the building.", None),
    ("Free and open to the public, but attendees must present a valid photo ID.", None),
    ("Open to members of the Yale community; restricted to those with a Yale ID.", "SOM MBA student"),
    ("For members only; must present a valid Yale ID.", None),
])
def test_open_or_group_quote_does_not_hide_a_second_condition_in_the_same_sentence(text, identity):
    conds = audience(text, identity)
    assert any(c.status == "to_confirm" and c.quote == text for c in conds)  # the catch-all still quotes the sentence
    assert verdict(conds) == "conditional"


# 2. A narrower unit (undergraduates, Yale College, one school) needs the identity to name it too.
@pytest.mark.parametrize("text,identity,status", [
    ("Open to all Yale undergraduates.", "Yale SOM graduate student", "to_confirm"),
    ("Open to all Yale undergraduates.", "Yale undergraduate", "met"),
    ("Open to all Yale College students.", "SOM MBA student", "to_confirm"),
    ("Open to all Yale College students.", "Yale College student", "met"),
    ("Open to all Yale Law School students.", "Yale SOM graduate student", "to_confirm"),
    ("Open to all Yale Law School students.", "Yale Law School student", "met"),
    ("Open to all Yale School of Medicine students.", "SOM MBA student", "to_confirm"),
    ("Open to all Yale School of Management students.", "Yale SOM graduate student", "met"),  # SOM = School of Management
    ("Open to all Yale students.", "SOM MBA student", "met"),  # no narrower unit: unchanged
])
def test_narrower_group_is_met_only_when_the_identity_names_it(text, identity, status):
    conds = audience(text, identity)
    assert [c.status for c in conds] == [status]
    assert verdict(conds) != "excluded"  # "open to X" never turns anyone away


# 3. "Open to all <group>" names a group; it is public only when it ends there or goes on with ages, levels, comers, interested.
@pytest.mark.parametrize("text", ["Open to all SOM students.", "Open to all MBA students.", "Open to all PhD students.",
                                  "Open to all first-year students.", "Open to all CAW members.",
                                  "Open to all New Haven residents.", "Open to all women."])
def test_open_to_all_followed_by_a_group_is_not_public(text):
    assert [c.status for c in audience(text, None)] == ["to_confirm"]
    assert browse([text]) == ([], [text])


@pytest.mark.parametrize("text", ["Open to all.", "Free and open to all.", "Open to all ages.", "Open to all levels.",
                                  "Open to all skill levels.", "Open to all experience levels.", "Open to all comers.",
                                  "Open to all interested in drones.", "Open to all, no registration required."])
def test_open_to_all_that_names_nobody_stays_public(text):
    assert find_open(text) and browse([text]) == ([text], [])


# 4. Negated public wording is never read as open.
@pytest.mark.parametrize("text", ["This event is not open to the public.",
                                  "Open to the Yale community only, not the general public.",
                                  "Yale ID required; not open to the public.",
                                  "This event is open to Yale students only and is not open to the public."])
def test_not_open_to_the_public_is_never_read_as_open(text):
    for identity in (None, "SOM MBA student"):
        conds = audience(text, identity)
        assert conds and all(c.status == "to_confirm" for c in conds) and verdict(conds) == "conditional"
    assert browse([text]) == ([], [text])


# 5. Each eligibility text is searched on its own: a quote never runs into the next text.
@pytest.mark.parametrize("texts", [["Open to the Yale community", "Members of the public may watch the livestream"],
                                   ["Free and open to the public.", "Open to Yale students for course credit."]])
def test_each_eligibility_text_is_searched_on_its_own(texts):
    conds = conditions_for(texts, None)
    quotes = [c.quote for c in conds if c.kind == "audience"]
    assert quotes and all(any(q in t for t in texts) for q in quotes)
    assert verdict(conds) == "conditional"  # a named group without an identity stays "to confirm"


# 6. The catch-all ignores credits, sizes in words and affiliation that says nothing about who may come.
@pytest.mark.parametrize("text", ["This session is eligible for 1.5 CME credits.", "Eligible for CME credit.",
                                  "Enrollment is limited to twelve participants.",
                                  "Speakers are affiliated with the Yale School of the Environment.",
                                  "Hosted by the Yale-affiliated Center for Biodiversity; all are welcome."])
def test_catch_all_ignores_credit_size_and_speaker_affiliation(text):
    assert [c for c in audience(text, "Yale SOM graduate student") if c.status == "to_confirm"] == []


@pytest.mark.parametrize("text", ["Yale affiliates only.", "Open to Yale affiliates with a valid ID.",
                                  "Limited to Yale students.", "Eligibility: current MBA students in good standing."])
def test_catch_all_still_flags_real_access_wording(text):
    assert [c.status for c in audience(text, None)] == ["to_confirm"]


# 7. "Undergraduate" is a student identity; Browse and Find read the same audience wording the same way.
def test_an_undergraduate_identity_counts_as_a_student():
    assert [c.status for c in audience("Open to Yale students, faculty, and staff.", "Yale undergraduate")] == ["met"]
    assert [c.status for c in audience("Faculty only.", "Yale undergraduate")] == ["not_met"]


@pytest.mark.parametrize("text,is_open", [
    ("Open to all who are interested.", True), ("Open to all who are interested in drones.", True),
    ("Open to all comers.", True), ("Everyone is welcome.", True), ("Free and open to the public.", True),
    ("Open to all SOM students.", False), ("Open to all Yale students.", False), ("Open to the Yale community.", False),
    ("This event is not open to the public.", False),
])
def test_browse_and_find_agree_on_who_may_come(text, is_open):
    assert find_open(text) is is_open
    assert (text in browse([text])[0]) is is_open


def test_browse_and_find_share_one_open_to_all_pattern():
    from app.discover import _OPEN, OPEN_TO_ALL
    assert OPEN_TO_ALL in _OPEN.pattern and OPEN_TO_ALL in _PUBLIC_AUDIENCE.pattern


# 8. "match" as a verb is not a count; "matches" as a noun still is.
@pytest.mark.parametrize("sentence,counts", [
    ("The two events match your interest in AI.", C(0, 2, 0)),
    ("This one matches what you asked for.", C(0, 1, 0)),
    ("Both match your interest in maps.", C(1, 1, 0)),
    ("Both match.", C(1, 0, 0)),
    ("The two workshops match because both are hands-on.", C(1, 0, 0)),
])
def test_match_used_as_a_verb_is_not_a_count(sentence, counts):
    assert reconcile_summary(sentence, counts) == (sentence, [])


def test_matches_used_as_a_noun_is_still_a_count():
    sentence = "Here are two matches you might like."
    assert reconcile_summary(sentence, C(1, 0, 0)) == ("", [sentence])
    assert reconcile_summary(sentence, C(2, 0, 0)) == (sentence, [])


# 9. The size of the searched pool is not a result count.
@pytest.mark.parametrize("sentence", ["I found one close match among the 11 stored listings.",
                                      "Out of 11 listings, I found one match.", "I found one match after reading 4 listings.",
                                      "I searched 11 listings and found one match."])
def test_size_of_the_searched_pool_is_not_a_result_count(sentence):
    assert reconcile_summary(sentence, C(1, 0, 0)) == (sentence, [])
    assert reconcile_summary(sentence, C(0, 1, 0))[1] == [sentence]  # the real claim ("one match") is still checked


# 10. A wrong count is caught through commas and up to five describing words.
@pytest.mark.parametrize("sentence", ["I found two in-person, beginner-friendly matches.", "I found 2 strong, close matches.",
                                      "I found two hands-on in-person beginner workshop matches."])
def test_wrong_count_with_commas_or_several_describing_words_is_removed(sentence):
    assert reconcile_summary(sentence, C(1, 1, 0)) == ("", [sentence])
    assert reconcile_summary(sentence, C(2, 0, 0)) == (sentence, [])


# 11. The sentence split does not break after common abbreviations.
@pytest.mark.parametrize("first", ["I found three close matches, e.g. the darkroom session.",
                                   "I found three close matches, i.e. both workshops and the session.",
                                   "Dr. Lee and I found three close matches.", "Prof. Lee found three close matches.",
                                   "Mr. Lee found three close matches.", "Ms. Lee found three close matches."])
def test_sentence_split_keeps_abbreviations_inside_the_sentence(first):
    assert reconcile_summary(f"{first} It recurs weekly.", C(1, 2, 0)) == ("It recurs weekly.", [first])


# 12. A summary that is only whitespace falls back to the code-built headline, never to raw JSON.
def test_whitespace_only_summary_falls_back_to_the_code_headline(make_settings, monkeypatch):
    import app.orchestrator as orch

    settings = make_settings()
    llm = FakeLLM([
        call_result(("search_listings", {"interests": ["photography"], "participation": "any", "when": "all", "max_results": 8})),
        call_result(("get_listing", {"record_id": DARKROOM})),
        json_result({"understood": understood(), "summary": "It recurs.", "follow_up_question": None,
                     "picks": [pick(DARKROOM, quotes=["comfortable working independently"])]}),
    ])
    real_verify, original = orch.verify_output, orch.build_team
    # tests the orchestrator's own guard, whatever the verifier returns
    monkeypatch.setattr(orch, "verify_output", lambda output, s: {**real_verify(output, s), "summary": "  \n "})
    monkeypatch.setattr(orch, "build_team", lambda st: original(st, session()))  # fixed TEST time + committed snapshot
    final = asyncio.run(run_task("photography in person", llm=llm, settings=settings,
                                 ledger=UsageLedger(settings.runs_dir / "usage.jsonl"), trace=RunTrace(), canary=Canary()))
    assert final["output_text"] == final["output"]["headline"] and not final["output_text"].lstrip().startswith("{")


# 14. User- and model-facing wording matches the data (events, classes and ongoing programs; no "communities").
def test_wording_says_events_and_classes_not_communities(settings):
    from app.domain.tools import _SECTION_LABEL, register_domain_tools
    from app.orchestrator import BLOCKED_REPLY
    from app.tools import ToolRegistry

    assert "event or class" in BLOCKED_REPLY and "communit" not in BLOCKED_REPLY
    registry = ToolRegistry()
    register_domain_tools(registry, settings, session())
    description = registry.get("search_listings").description
    assert "classes and ongoing programs" in description and "communit" not in description
    assert "communit" not in _SECTION_LABEL["ongoing"]
    role = load_prompt("matcher").split("# Tools")[0]
    assert "events, classes and ongoing programs" in role and "communities" not in role


# --------------------------------------------------------------------------- final check, 2026-10-26 (afternoon)

# "Open to anyone / everyone" followed by a group names that group (regression from the round-3 public wording).
@pytest.mark.parametrize("text", ["Open to anyone with a valid Yale ID.", "Open to anyone affiliated with Yale.",
                                  "Open to anyone at Yale.", "Open to everyone in the Yale community."])
def test_open_to_anyone_followed_by_a_group_is_not_public(text):
    conds = conditions_for([text], None)
    assert conds and verdict(conds) == "conditional"
    assert browse([text]) == ([], [text])


@pytest.mark.parametrize("text", ["Open to anyone.", "Open to everyone!", "Open to anyone interested in maps."])
def test_open_to_anyone_that_names_nobody_stays_public(text):
    assert verdict(conditions_for([text], None)) == "clear"
    assert browse([text]) == ([text], [])


# Group-only wording without "open to" must not leave the card a plain Match.
@pytest.mark.parametrize("text", ["Graduate students only.", "Yale students only.", "Only Yale students may attend.",
                                  "All Yale students are welcome."])
def test_group_only_wording_is_to_confirm(text):
    conds = conditions_for([text], None)
    assert any(c.kind == "audience" and c.status == "to_confirm" for c in conds) and verdict(conds) == "conditional"


@pytest.mark.parametrize("text", ["Must be 21 and over to attend.", "Open to everyone over 21.", "Ages 21 and up."])
def test_age_limits_written_in_words_are_found(text):
    assert any(c.kind == "age" for c in conditions_for([text], None))


# A sentence that states the Check-first count correctly is kept.
@pytest.mark.parametrize("sentence, counts", [("I found one match and two listings to check first.", C(1, 2, 0)),
                                              ("I found two possible matches that you should check first.", C(0, 2, 0))])
def test_correct_check_first_count_is_kept(sentence, counts):
    assert reconcile_summary(sentence, counts) == (sentence, [])


def test_wrong_check_first_count_is_still_removed():
    sentence = "I found two possible matches that you should check first."
    assert reconcile_summary(sentence, C(0, 1, 0)) == ("", [sentence])
