"""Deterministic Discover view: windows, DST, grouping, honesty rules and the HTTP API.

Records built with ``rec(...)`` are SYNTHETIC test records (example.test URLs), used only here to
exercise edge cases the real sample does not contain. Every fixed reference time below is a
labelled test time; the app itself always uses the real clock.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import discover, server
from app.collect.records import Record, Session, finalize
from app.collect.sources import SOURCES
from app.collect.store import SourceResult, load_source, refresh_source
from app.discover import NY, build_discovery, safe_url, when_text, windows_for

REPO_DIR = Path(__file__).resolve().parents[1]
SNAPSHOTS = REPO_DIR / "data" / "snapshots"
_n = 0


def at(y, mo, d, h=12, mi=0) -> datetime:
    """A labelled TEST reference time in New York (real DST rules)."""
    return datetime(y, mo, d, h, mi, tzinfo=NY)


def rec(title="Test item", kind="event", start=None, end=None, sessions=(), url=None, **fields) -> Record:
    global _n
    _n += 1
    return finalize(Record(
        record_id=f"test-{_n}", source_id="test", kind=kind, title=title,
        url=url or f"https://example.test/item/{_n}", publisher="Synthetic test publisher",
        organizer="Synthetic test organizer", collected_at="2026-10-25T01:00:00+00:00",
        start=start.isoformat() if start else None, end=end.isoformat() if end else None,
        sessions=list(sessions), **fields,
    ))


def view(*records: Record, now: datetime, **filters) -> dict:
    return build_discovery([SourceResult("test", "cached", "2026-10-25T01:00:00+00:00", list(records))], now=now, **filters)


def titles(d: dict, section: str) -> list[str]:
    return [c["title"] for c in d["sections"][section]]


# --------------------------------------------------------------------------- windows and time zones


def test_seven_day_window_boundary_is_local_midnight():
    now = at(2026, 10, 24, 21, 49)  # Saturday evening
    d = view(rec("last minute of day 7", start=at(2026, 10, 30, 23, 59)),
             rec("first minute of day 8", start=at(2026, 10, 31, 0, 0)), now=now)
    assert d["windows"]["this_week"]["label"] == "Sat Oct 24 – Fri Oct 30"
    assert titles(d, "this_week") == ["last minute of day 7"]
    assert titles(d, "coming") == ["first minute of day 8"]


def test_window_across_the_fall_dst_change_uses_real_rules():
    now = at(2026, 10, 29, 10)  # EDT; DST ends Sun Nov 1, 2026
    w = windows_for(now)
    assert w.this_week_start.utcoffset().total_seconds() == -4 * 3600
    assert w.this_week_end.utcoffset().total_seconds() == -5 * 3600  # Nov 5 midnight is EST
    assert w.this_week_end.isoformat() == "2026-11-05T00:00:00-05:00"
    d = view(rec("Wed night", start=at(2026, 11, 4, 23, 30)), rec("Thu morning", start=at(2026, 11, 5, 0, 30)), now=now)
    assert titles(d, "this_week") == ["Wed night"] and titles(d, "coming") == ["Thu morning"]


def test_repeated_hour_on_dst_day_keeps_the_right_zone_name():
    first = datetime.fromisoformat("2026-11-01T01:30:00-04:00").astimezone(NY)
    second = datetime.fromisoformat("2026-11-01T01:30:00-05:00").astimezone(NY)
    assert when_text(first, None).endswith("1:30 AM EDT")
    assert when_text(second, None).endswith("1:30 AM EST")


def test_spring_dst_change():
    w = windows_for(at(2027, 3, 5, 9))  # DST starts Sun Mar 14, 2027
    assert w.this_week_end.isoformat() == "2027-03-12T00:00:00-05:00"
    w2 = windows_for(at(2027, 3, 10, 9))
    assert w2.this_week_end.isoformat() == "2027-03-17T00:00:00-04:00"


# --------------------------------------------------------------------------- grouping rules


def test_past_hidden_today_kept_and_undated_never_this_week():
    now = at(2026, 10, 27, 15)
    d = view(
        rec("ended yesterday", start=at(2026, 10, 26, 9), end=at(2026, 10, 26, 10)),
        rec("ended an hour ago", start=at(2026, 10, 27, 13), end=at(2026, 10, 27, 14)),
        rec("this morning, no end time", start=at(2026, 10, 27, 9)),
        rec("no date on the page"),
        now=now,
    )
    assert titles(d, "this_week") == ["this morning, no end time"]
    assert titles(d, "date_unknown") == ["no date on the page"]
    assert d["counts"]["past_hidden"] == 2


def test_program_shows_next_open_session_and_stays_one_card():
    sessions = [
        Session(date_text="s1", start=at(2026, 10, 23, 18).isoformat(), end=at(2026, 10, 23, 21).isoformat(), status_text="Registration closed"),
        Session(date_text="s2", start=at(2026, 10, 30, 18).isoformat(), end=at(2026, 10, 30, 21).isoformat(), status_text="Registration closed"),
        Session(date_text="s3", start=at(2026, 11, 6, 18).isoformat(), end=at(2026, 11, 6, 21).isoformat(), status_text="Register"),
    ]
    d = view(rec("Darkroom series", kind="program", sessions=sessions), now=at(2026, 10, 25))
    assert titles(d, "ongoing") == ["Darkroom series"] and not d["sections"]["this_week"]
    card = d["sections"]["ongoing"][0]
    assert card["next_session"]["start"].startswith("2026-11-06T18:00:00-05:00")  # first OPEN session
    assert len(card["upcoming_sessions"]) == 2


def test_program_with_every_upcoming_session_closed_is_not_available():
    sessions = [Session(date_text="s", start=at(2026, 10, 30, 18).isoformat(), status_text="Registration closed")]
    d = view(rec("Closed series", kind="program", sessions=sessions), now=at(2026, 10, 25))
    assert d["counts"]["not_available"] == 1 and "closed" in d["not_available"][0]["reason"]


def test_program_whose_sessions_all_passed_is_hidden_and_flexible_program_stays():
    past = [Session(date_text="s", start=at(2026, 9, 11, 18).isoformat(), end=at(2026, 9, 11, 21).isoformat())]
    flexible = [Session(date_text="Dates & times are flexible")]
    d = view(rec("Old series", kind="program", sessions=past), rec("Coaching", kind="program", sessions=flexible), now=at(2026, 10, 25))
    assert titles(d, "ongoing") == ["Coaching"] and d["counts"]["past_hidden"] == 1


def test_communities_only():
    d = view(rec("Photo club", kind="community"), now=at(2026, 10, 25))
    assert titles(d, "ongoing") == ["Photo club"]
    assert d["sections"]["this_week"] == [] and d["sections"]["coming"] == []


def test_duplicates_by_url_and_by_title_and_date():
    now = at(2026, 10, 25)
    a = rec("GIS Day 2026", start=at(2026, 11, 16, 8, 30), url="https://example.test/gis/")
    b = rec("GIS Day 2026", start=at(2026, 11, 16, 8, 30), url="https://example.test/gis")  # same page
    c = rec("GIS  day 2026!", start=at(2026, 11, 16, 9), url="https://other.test/gis-day")  # same event elsewhere
    d = view(a, b, c, now=now)
    assert len(d["sections"]["coming"]) == 1 and d["counts"]["duplicates_merged"] == 2
    assert d["sections"]["coming"][0]["also_at"]


def test_mode_filter_hides_known_mismatch_but_keeps_unknown_with_flag():
    now = at(2026, 10, 25)
    d = view(rec("online talk", start=at(2026, 10, 27), format="online"), rec("hybrid talk", start=at(2026, 10, 27), format="hybrid"),
             rec("format unknown", start=at(2026, 10, 27)), now=now, mode="in_person")
    assert sorted(titles(d, "this_week")) == ["format unknown", "hybrid talk"]
    assert next(c for c in d["sections"]["this_week"] if c["title"] == "format unknown")["format_unknown_for_filter"]


def test_interest_terms_match_whole_words_only():
    now = at(2026, 10, 25)
    d = view(rec("Intro to GenAI Promptathon", start=at(2026, 10, 27)), rec("Maintaining said gardens", start=at(2026, 10, 27)),
             now=now, interest="ai")
    assert titles(d, "this_week") == ["Intro to GenAI Promptathon"]


def test_eligibility_open_vs_to_check_and_explicit_exclusion():
    now = at(2026, 10, 25)
    d = view(
        rec("open one", start=at(2026, 10, 27), eligibility_texts=["No coding experience is necessary.", "Attendees are required to bring a laptop."]),
        rec("undergrad one", start=at(2026, 10, 27), eligibility_texts=["Open to Yale undergraduates only."]),
        now=now,
    )
    card = d["sections"]["this_week"][0]
    assert card["eligibility_open"] == ["No coding experience is necessary."]
    assert "Attendees are required to bring a laptop." in card["eligibility_check"]
    assert [n["title"] for n in d["not_available"]] == ["undergrad one"]


def test_registration_deadline_passed_vs_upcoming():
    now = at(2026, 11, 2)
    d = view(rec("late", start=at(2026, 11, 10), registration_text="Please register by Oct 30."),
             rec("early", start=at(2026, 11, 10), registration_text="RSVP by Nov 8"), now=now)
    assert [n["title"] for n in d["not_available"]] == ["late"]
    assert d["sections"]["coming"][0]["deadline_text"] == "RSVP by Nov 8"


def test_only_http_links_are_passed_to_the_page():
    assert safe_url("javascript:alert(1)") is None and safe_url("https://x.test/a") == "https://x.test/a"
    d = view(rec("bad link", start=at(2026, 10, 27), registration_url="javascript:alert(1)"), now=at(2026, 10, 25))
    assert d["sections"]["this_week"][0]["registration_url"] is None


def test_real_snapshot_sample_groups_as_expected_at_a_fixed_test_time():
    results = [load_source(s, runs_dir=Path("/nonexistent-test-dir"), snapshot_dir=SNAPSHOTS) for s in SOURCES]
    d = build_discovery(results, now=at(2026, 10, 25, 9), fixed_now_for_test=True)
    assert d["fixed_now_for_test"] is True
    assert {s["data_mode"] for s in d["sources"]} == {"snapshot"}
    assert [c["title"] for c in d["sections"]["ongoing"]] == ["Open Darkroom Session", "Photography Individual Coaching"]
    assert len(d["sections"]["this_week"]) == 4 and len(d["sections"]["coming"]) == 5
    darkroom = d["sections"]["ongoing"][0]
    assert darkroom["session_this_week"] and darkroom["next_session"]["start"] == "2026-10-30T18:00:00-04:00"
    photo = build_discovery(results, now=at(2026, 10, 25, 9), interest="photography")
    assert {c["title"] for s in photo["sections"].values() for c in s} == {"Open Darkroom Session", "Photography Individual Coaching"}


# --------------------------------------------------------------------------- HTTP API


@pytest.fixture
def client(make_settings, tmp_path):
    clients = []

    def build(**deps):
        server.set_dependencies(settings=make_settings(), **deps)
        c = TestClient(server.app)
        c.__enter__()
        clients.append(c)
        return c

    yield build
    for c in clients:
        c.__exit__(None, None, None)
    server.set_dependencies()


def test_discover_endpoint_serves_snapshot_with_labelled_test_time(client):
    c = client(snapshot_dir=SNAPSHOTS, now=lambda: at(2026, 10, 25, 9))
    d = c.get("/api/discover", params={"when": "ongoing"}).json()
    assert d["fixed_now_for_test"] is True and d["filters"]["when"] == "ongoing"
    assert d["counts"]["ongoing"] == 2 and d["sections"]["this_week"] == []
    assert all(s["data_mode"] == "snapshot" for s in d["sources"])
    assert "Not an AI recommendation" in d["notice"]


def test_refresh_success_then_cooldown_then_simulated_failure_keeps_data(client, make_settings, monkeypatch):
    calls = []

    def simulated_refresh():  # SIMULATED: no network; runs the real store with a mock transport
        calls.append(1)
        settings = server.get_app_settings()
        routes = {"https://geospatial.yale.edu/events": httpx.ConnectError("simulated outage")}
        transport = httpx.MockTransport(lambda req: (_ for _ in ()).throw(routes[str(req.url)]) if str(req.url) in routes else httpx.Response(404))
        return [refresh_source(SOURCES["ycgs-events"], runs_dir=settings.runs_dir, snapshot_dir=SNAPSHOTS,
                               transport=transport, sleep=lambda s: None, simulated=True)]

    c = client(snapshot_dir=SNAPSHOTS, collect_refresh=simulated_refresh)
    first = c.post("/api/refresh")
    assert first.status_code == 200
    result = first.json()["results"][0]
    assert result["outcome"] == "failed" and result["simulated"] and result["errors"] == ["network"]
    assert result["data_mode"] == "snapshot" and result["n_records"] == 9  # nothing erased
    again = c.post("/api/refresh")
    assert again.status_code == 429 and len(calls) == 1  # polite cooldown, no second fetch
    d = c.get("/api/discover").json()
    ycgs = next(s for s in d["sources"] if s["id"] == "ycgs-events")
    assert ycgs["last_outcome"] == "failed" and ycgs["simulated"] and ycgs["n_records"] == 9


def test_discover_page_is_wired_into_the_ui(client):
    c = client()
    html = c.get("/").text
    assert 'id="panel-discover"' in html and "/static/discover.js" in html
    assert c.get("/static/discover.js").status_code == 200
