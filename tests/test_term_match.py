"""G-18: interest words inside compound words ("GeoAI", "GenAI", "ArcGIS"), deterministic, no model call.

Found by the user's post-fix retest r_e29a8b37a60c: the code dropped "Save the Date: GIS Day 2026" for the
interest "AI" although the page says "GeoAI workshops". The page text below is the real stored record.
"""

from __future__ import annotations

import pytest

from app.collect.sources import SOURCES
from app.collect.store import load_source
from app.discover import build_discovery, term_in
from app.domain.conditions import topic_matches
from app.domain.tools import search
from tests.test_domain import SNAPSHOTS, TEST_NOW, pick, run_verify, session

GIS_DAY = "ycgs-events-29f5227779"  # "Save the Date: GIS Day 2026" ("... geospatial talks, GeoAI workshops, ...")


@pytest.mark.parametrize("term, text", [
    ("ai", "a day of geospatial talks, GeoAI workshops, a poster session"),
    ("ai", "Hands-on GenAI tools for beginners"), ("AI", "Built with OpenAI models"),
    ("ai", "AI-powered maps"), ("ai", "An intro to AI."), ("gis", "Mapping in ArcGIS Pro"),
    ("ml", "No-code AutoML demo"), ("genai", "GenAI office hours"),
])
def test_term_found_as_a_word_or_as_the_end_of_a_compound(term, text):
    assert term_in(term, text)


@pytest.mark.parametrize("term, text", [
    ("ai", "Please maintain your workspace."), ("ai", "She said it was free."), ("ai", "Thai food after the talk"),
    ("ai", "Held in Dubai"), ("ai", "SAID IN CAPITALS"), ("ai", "AIDS awareness week"), ("ai", "MAIN HALL"),
    ("gis", "Logistics for the trip"), ("ml", "Write the page in HTML"), ("bot", "Botany walk"),
    ("artificial intelligence", "ArtificialIntelligence"),  # multi-word terms keep the whole-word rule only
])
def test_ordinary_words_never_match_a_short_term(term, text):
    assert not term_in(term, text)


def test_the_real_gis_day_listing_is_relevant_to_ai():
    record = session().records[GIS_DAY]
    assert "GeoAI" in record.summary
    assert topic_matches(["ai"], record) == [{"term": "ai", "field": "summary"}]


def test_search_tool_and_browse_now_find_gis_day_for_ai():
    r = search(session(), ["ai"], "any", "all", 12)
    assert GIS_DAY in [x["record_id"] for x in r["results"] if "ai" in x["matched_terms"]]
    results = [load_source(s, runs_dir=SNAPSHOTS.parent / "nonexistent", snapshot_dir=SNAPSHOTS) for s in SOURCES]
    ids = [c["id"] for items in build_discovery(results, now=TEST_NOW, interest="ai")["sections"].values() for c in items]
    assert GIS_DAY in ids


def test_the_verifier_keeps_gis_day_for_an_ai_request():
    out = run_verify([pick(GIS_DAY)], interests=["AI"], purpose=None, purpose_type="not_stated", participation="either")
    assert [p["record_id"] for p in out["picks"]] == [GIS_DAY]
    assert out["dropped"] == []
