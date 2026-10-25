"""Public-source collector: parsers on trimmed REAL pages, fetch limits and fallback on SIMULATED failures.

Fixtures in tests/fixtures/collect/ are trimmed copies of real pages fetched on 2026-10-25
(each file's first line names its URL). Every network failure below is simulated with
httpx.MockTransport; nothing here touches the network (see the no_real_network fixture).
"""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.collect.fetch import BoundedFetcher, FetchError, Page
from app.collect.records import Record
from app.collect.sources import CAW_PHOTO, SOURCES, YCGS_EVENTS
from app.collect.store import load_source, refresh_source, save_snapshot

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "collect"
REPO_DIR = Path(__file__).resolve().parents[1]

CAW_LISTING = "https://creativeartsworkshop.org/courses/department/photography/"
DARKROOM = "https://creativeartsworkshop.org/courses/no-term/open-darkroom-session/"
COACHING = "https://creativeartsworkshop.org/courses/no-term/photography-individual-coaching/"
YCGS_LISTING = "https://geospatial.yale.edu/events"
BOT = "https://geospatial.yale.edu/events/2026-11-20-build-a-bot-workshop"
PART2 = "https://geospatial.yale.edu/events/2026-10-28-telling-stories-with-maps-part-ii-hands-on-map-making-in-person"
DRONE = "https://geospatial.yale.edu/events/2026-11-09-ycgs-drone-hobbyist-gathering-ii"

FIXTURE_FOR = {
    CAW_LISTING: "caw_listing.html",
    DARKROOM: "caw_open_darkroom.html",
    COACHING: "caw_coaching.html",
    YCGS_LISTING: "ycgs_listing.html",
    BOT: "ycgs_build_a_bot.html",
    PART2: "ycgs_part2.html",
    DRONE: "ycgs_drone.html",
}


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def page(url: str) -> Page:
    return Page(url=url, requested_url=url, status=200, content_type="text/html", text=fixture_text(FIXTURE_FOR[url]),
                n_bytes=0, fetched_at="2026-10-25T01:30:00+00:00")


def no_sleep(_: float) -> None:
    pass


def site(routes: dict[str, httpx.Response | Exception], seen: list[httpx.Request] | None = None) -> httpx.MockTransport:
    """Simulated web: robots.txt allows everything unless routed; unknown URLs return 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        url = str(request.url)
        if url in routes:
            item = routes[url]
            if isinstance(item, Exception):
                raise item
            return item
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow:\n")
        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler)


def html(url: str) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html; charset=UTF-8"}, text=fixture_text(FIXTURE_FOR[url]))


# --------------------------------------------------------------------------- parsers on real pages


def test_caw_listing_finds_both_course_pages():
    urls, _ = CAW_PHOTO.parse_listing(page(CAW_LISTING), date(2026, 10, 24))
    assert set(urls) == {DARKROOM, COACHING}


def test_open_darkroom_is_one_program_with_dated_sessions_not_separate_events():
    r = CAW_PHOTO.parse_detail(page(DARKROOM), CAW_PHOTO)
    assert r.kind == "program" and r.start is None and r.end is None
    assert len(r.sessions) == 10
    by_day = {s.start[:10]: s for s in r.sessions}
    assert by_day["2026-10-30"].start == "2026-10-30T18:00:00-04:00"
    assert by_day["2026-11-06"].start == "2026-11-06T18:00:00-05:00"  # after the DST change
    assert by_day["2026-10-23"].status_text == "Registration closed"
    assert by_day["2026-10-30"].status_text == "Register" and by_day["2026-10-30"].register_url
    assert any("taken darkroom classes at CAW before" in t for t in r.eligibility_texts)
    assert "Suggested Ages: 18+" in r.eligibility_texts
    assert r.cost_text == "Sessions are $30 each."
    assert r.format == "in_person" and r.format_text == "In person"
    assert r.capacity_text is None and "capacity_text" in r.missing  # unknown, not "unlimited"
    assert any("Fall 2026" in w for w in r.warnings)  # the year is inferred from the term line


def test_flexible_coaching_is_not_turned_into_a_dated_session():
    r = CAW_PHOTO.parse_detail(page(COACHING), CAW_PHOTO)
    assert r.kind == "program"
    assert all(s.start is None for s in r.sessions)
    assert "when" in r.missing
    assert r.capacity_text == "Capacity: 1"
    assert any("flexible" in w for w in r.warnings)


def test_ycgs_listing_keeps_dated_window_in_order():
    urls, notes = YCGS_EVENTS.parse_listing(page(YCGS_LISTING), date(2026, 10, 24))
    days = [re.search(r"/events/(\d{4}-\d{2}-\d{2})", u).group(1) for u in urls]
    assert len(urls) == 9 and days == sorted(days) and days[0] == "2026-10-27"
    later, _ = YCGS_EVENTS.parse_listing(page(YCGS_LISTING), date(2026, 12, 1))
    assert [u.rsplit("/", 1)[1][:10] for u in later] == ["2026-12-04", "2026-12-15"]
    assert re.match(r"\d+ event link\(s\) on the listing; 9 dated", notes[0])


def test_build_a_bot_fields_and_unknowns():
    r = YCGS_EVENTS.parse_detail(page(BOT), YCGS_EVENTS)
    assert r.kind == "event"
    assert (r.start, r.end) == ("2026-11-20T12:00:00-05:00", "2026-11-20T13:00:00-05:00")
    assert r.format == "online"
    assert any("in-person attendees" in w for w in r.warnings)  # page contradicts its own label
    assert r.capacity_text == "Attendance will be capped at 50 people."
    assert "No coding experience is necessary." in r.eligibility_texts
    assert r.registration_url == "https://cglink.me/2dA/r2333101"
    assert r.cost_text is None and "cost_text" in r.missing  # not stated -> unknown, never "free"
    assert r.location_text is None and "location_text" in r.missing


def test_place_audience_and_cohost_come_only_from_page_text():
    part2 = YCGS_EVENTS.parse_detail(page(PART2), YCGS_EVENTS)
    assert part2.format == "in_person" and part2.location_text == "DH Lab, Sterling Memorial Library"
    assert part2.organizer.startswith("Co-hosted by the Yale Library")
    assert any("designed for instructors" in t for t in part2.eligibility_texts)
    assert part2.warnings == []  # '(Virtual)' refers to Part I, not this session
    drone = YCGS_EVENTS.parse_detail(page(DRONE), YCGS_EVENTS)
    assert drone.location_text == "East Rock Brewery, New Haven, CT"
    assert any("+21 only" in t for t in drone.eligibility_texts)
    assert drone.format is None and "format" in drone.missing  # no label on the page


@pytest.mark.parametrize("url", [DARKROOM, COACHING, BOT, PART2, DRONE])
def test_every_text_quote_appears_on_the_page(url):
    source = CAW_PHOTO if "creativeartsworkshop" in url else YCGS_EVENTS
    r = source.parse_detail(page(url), source)
    from app.collect.htmltree import parse_html

    text = " ".join(parse_html(fixture_text(FIXTURE_FOR[url])).text().split())
    for ev in r.evidence:
        if ev.basis in ("time@datetime", "'Add to Calendar' iCal data on the page") or ev.field in ("registration_url", "organizer"):
            continue
        quote = " ".join(ev.quote.rstrip("…").split())
        if ev.basis.startswith("site footer"):
            assert all(part.strip() in text for part in quote.split(","))
        elif ev.basis.startswith("first of"):
            assert quote.split(" $")[0] in text
        else:
            assert quote in text, (ev.field, quote)


# --------------------------------------------------------------------------- fetch limits (simulated)


def test_only_https_allowlisted_urls_are_requested():
    seen: list[httpx.Request] = []
    with BoundedFetcher({"geospatial.yale.edu"}, 5, transport=site({}, seen), sleep=no_sleep) as f:
        for bad in ("http://geospatial.yale.edu/events", "https://evil.example/x", "https://user@geospatial.yale.edu/"):
            with pytest.raises(FetchError) as exc:
                f.get(bad)
            assert exc.value.kind == "not_allowed"
    assert seen == []


def test_redirect_off_the_allowlist_is_blocked_and_allowed_redirect_followed():
    routes = {
        "https://geospatial.yale.edu/a": httpx.Response(302, headers={"location": "https://evil.example/steal"}),
        "https://geospatial.yale.edu/b": httpx.Response(301, headers={"location": "/events"}),
        YCGS_LISTING: html(YCGS_LISTING),
    }
    with BoundedFetcher({"geospatial.yale.edu"}, 5, transport=site(routes), sleep=no_sleep) as f:
        with pytest.raises(FetchError) as exc:
            f.get("https://geospatial.yale.edu/a")
        assert exc.value.kind == "redirect_blocked"
        got = f.get("https://geospatial.yale.edu/b")
        assert got.url == YCGS_LISTING and got.redirects == [YCGS_LISTING]


def test_size_page_and_content_type_caps():
    from app.collect.fetch import FetchLimits

    routes = {
        "https://geospatial.yale.edu/big": httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 5000),
        "https://geospatial.yale.edu/pdf": httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF"),
    }
    with BoundedFetcher({"geospatial.yale.edu"}, 2, limits=FetchLimits(max_bytes=1000), transport=site(routes), sleep=no_sleep) as f:
        with pytest.raises(FetchError) as exc:
            f.get("https://geospatial.yale.edu/big")
        assert exc.value.kind == "too_large"
        with pytest.raises(FetchError) as exc:
            f.get("https://geospatial.yale.edu/pdf")
        assert exc.value.kind == "bad_content_type"
        with pytest.raises(FetchError) as exc:
            f.get("https://geospatial.yale.edu/third")
        assert exc.value.kind == "page_cap"


@pytest.mark.parametrize(
    ("robots", "allowed"),
    [
        (httpx.Response(200, text="User-agent: *\nDisallow: /\n"), False),  # like events.yale.edu
        (httpx.Response(404), True),
        (httpx.Response(503), False),
    ],
)
def test_robots_txt_is_obeyed(robots, allowed):
    routes = {"https://geospatial.yale.edu/robots.txt": robots, YCGS_LISTING: html(YCGS_LISTING)}
    with BoundedFetcher({"geospatial.yale.edu"}, 3, transport=site(routes), sleep=no_sleep) as f:
        if allowed:
            assert f.get(YCGS_LISTING).status == 200
        else:
            with pytest.raises(FetchError) as exc:
                f.get(YCGS_LISTING)
            assert exc.value.kind == "robots_disallow"


def test_requests_carry_no_api_key_and_honour_crawl_delay():
    import os

    seen: list[httpx.Request] = []
    sleeps: list[float] = []
    routes = {
        "https://creativeartsworkshop.org/robots.txt": httpx.Response(200, text="User-agent: *\nCrawl-delay: 10\nDisallow:\n"),
        CAW_LISTING: html(CAW_LISTING),
        DARKROOM: html(DARKROOM),
    }
    with BoundedFetcher({"creativeartsworkshop.org"}, 3, min_delay_s=1.0, transport=site(routes, seen), sleep=sleeps.append) as f:
        f.get(CAW_LISTING)
        f.get(DARKROOM)
    key = os.environ["PORTKEY_API_KEY"]
    for req in seen:
        dumped = json.dumps(dict(req.headers))
        assert key not in dumped and "authorization" not in dumped.lower() and "portkey" not in dumped.lower()
        assert req.headers["user-agent"].startswith("BeyondYourCircle/")
    assert sleeps and max(sleeps) > 9  # waited ~10 s between same-host requests


# --------------------------------------------------------------------------- persistence and fallback (simulated failures)

TWO_PAGE_SOURCE = dataclasses.replace(
    YCGS_EVENTS, id="ycgs-test", parse_listing=lambda page, today: ([BOT, DRONE], ["test listing"])
)


def ok_routes() -> dict:
    return {YCGS_LISTING: html(YCGS_LISTING), BOT: html(BOT), DRONE: html(DRONE)}


def test_network_failure_keeps_and_serves_last_success(tmp_path):
    first = refresh_source(TWO_PAGE_SOURCE, runs_dir=tmp_path, snapshot_dir=tmp_path / "snap", transport=site(ok_routes()), sleep=no_sleep)
    assert first.data_mode == "live" and len(first.records) == 2 and first.status["last_outcome"] == "ok"
    cache_file = tmp_path / "collect" / "ycgs-test.json"
    before = cache_file.read_text(encoding="utf-8")

    down = site({YCGS_LISTING: httpx.ConnectError("simulated outage"), "https://geospatial.yale.edu/robots.txt": httpx.Response(404)})
    second = refresh_source(TWO_PAGE_SOURCE, runs_dir=tmp_path, snapshot_dir=tmp_path / "snap", transport=down, sleep=no_sleep)
    assert second.data_mode == "cached"
    assert second.collected_at == first.collected_at  # dated fallback, not relabelled as new
    assert [r.title for r in second.records] == [r.title for r in first.records]
    assert second.status["last_outcome"] == "failed" and second.status["errors"][0]["kind"] == "network"
    assert cache_file.read_text(encoding="utf-8") == before  # failure did not erase the last success


def test_partial_failure_carries_previous_record_forward(tmp_path):
    first = refresh_source(TWO_PAGE_SOURCE, runs_dir=tmp_path, transport=site(ok_routes()), sleep=no_sleep)
    routes = ok_routes() | {DRONE: httpx.Response(503)}
    again = refresh_source(TWO_PAGE_SOURCE, runs_dir=tmp_path, transport=site(routes), sleep=no_sleep)
    assert again.data_mode == "live" and again.status["last_outcome"] == "partial"
    assert again.status["carried_forward"] == 1 and again.status["errors"][0]["kind"] == "http_status"
    old_drone = next(r for r in first.records if r.url == DRONE)
    drone = next(r for r in again.records if r.url == DRONE)
    assert drone == old_drone  # the previous record, unchanged, including its own collected_at


def test_empty_listing_does_not_erase_previous_records(tmp_path):
    refresh_source(TWO_PAGE_SOURCE, runs_dir=tmp_path, transport=site(ok_routes()), sleep=no_sleep)
    empty_source = dataclasses.replace(TWO_PAGE_SOURCE, parse_listing=lambda page, today: ([], ["no items"]))
    result = refresh_source(empty_source, runs_dir=tmp_path, transport=site(ok_routes()), sleep=no_sleep)
    assert result.status["last_outcome"] == "empty"
    assert result.data_mode == "cached" and len(result.records) == 2


def test_without_cache_falls_back_to_committed_snapshot_then_unavailable(tmp_path):
    work, fresh, snap = tmp_path / "work", tmp_path / "fresh", tmp_path / "snap"
    refresh_source(TWO_PAGE_SOURCE, runs_dir=work, transport=site(ok_routes()), sleep=no_sleep)
    save_snapshot("ycgs-test", runs_dir=work, snapshot_dir=snap)
    down = site({YCGS_LISTING: httpx.ConnectTimeout("simulated timeout")})
    result = refresh_source(TWO_PAGE_SOURCE, runs_dir=fresh, snapshot_dir=snap, transport=down, sleep=no_sleep)
    assert result.data_mode == "snapshot" and len(result.records) == 2 and result.collected_at
    nothing = refresh_source(TWO_PAGE_SOURCE, runs_dir=tmp_path / "x", snapshot_dir=tmp_path / "none", transport=down, sleep=no_sleep)
    assert nothing.data_mode == "unavailable" and nothing.records == []
    assert nothing.status["last_outcome"] == "failed"  # "no data", not "no events"


# --------------------------------------------------------------------------- the committed real sample


@pytest.mark.parametrize("source_id", sorted(SOURCES))
def test_committed_snapshot_is_valid_real_sample(source_id, tmp_path):
    payload = json.loads((REPO_DIR / "data" / "snapshots" / f"{source_id}.json").read_text(encoding="utf-8"))
    assert payload["snapshot_note"] and payload["collected_at"] and payload["records"]
    hosts = SOURCES[source_id].allowed_hosts
    for raw in payload["records"]:
        r = Record.model_validate(raw)
        assert r.collected_at and r.url.split("/")[2] in hosts
        if r.kind == "event" and (m := re.search(r"/events/(\d{4}-\d{2}-\d{2})-", r.url)):
            assert r.start and r.start.startswith(m.group(1))
    loaded = load_source(source_id, runs_dir=tmp_path, snapshot_dir=REPO_DIR / "data" / "snapshots")
    assert loaded.data_mode == "snapshot"
