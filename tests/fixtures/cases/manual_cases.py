"""Manually verified case records (problem 5 functional cases).

These are NOT collected by the app's collector and are NOT shown in the app. They were transcribed by
hand from public pages that were read once on 2026-10-25 (~01:05Z, during the problem-2 source probe),
to cover cases the two connected sources do not contain: a sports league with a CLOSED registration,
a sports league whose registration opens later, and an ongoing community (camera club).
Every text field below is copied from the page; values the page does not state are left empty.
Use them only with the fixed TEST time ``CASE_NOW``.
"""

from __future__ import annotations

from datetime import datetime

from app.collect.records import Evidence, Record, Session, finalize
from app.collect.store import SourceResult
from app.discover import NY

CASE_NOW = datetime(2026, 10, 25, 9, 0, tzinfo=NY)  # fixed TEST reference time (Sunday morning, EDT)
CHECKED_AT = "2026-10-25T01:05:00+00:00"  # when the pages were read
REC_URL = "https://recreation.yale.edu/gradproims"
NHCC_URL = "https://nhccphotoblog.blogspot.com/"

_REC_ELIGIBILITY = [
    "Current Yale Graduate Students who have a current PWG Membership",
    "Within the recreational division the level of skill may vary, but participants will be able to enjoy playing in a fun, social atmosphere.",
]
_REC_SUMMARY = ("The Graduate & Professional Intramural (Grad/Pro IM) Program provides an opportunity for Yale Graduate "
                "Students, Yale Faculty/Staff, and their Spouses to engage in recreational sports.")
_REC_CAPACITY = "Note that there are a limited number of team slots for each league."
_BASIS = "manual reading of the public page (problem 5 case)"


def _ev(field: str, quote: str) -> Evidence:
    return Evidence(field=field, quote=quote, basis=_BASIS)


def _rec_league(rid: str, title: str, registration: str, season_text: str, sessions: list[Session], location: str) -> Record:
    return finalize(Record(
        record_id=rid, source_id="case-manual", kind="program", title=title, url=REC_URL,
        publisher="Yale Campus Recreation", organizer="Yale Campus Recreation", collected_at=CHECKED_AT,
        date_text=season_text, sessions=sessions, location_text=location,
        eligibility_texts=list(_REC_ELIGIBILITY),
        registration_text=f"Registration Dates: {registration}. To register a team, a participant will need to "
                          "identify themselves as a team captain and register their team via the Fusion Play Mobile App.",
        capacity_text=_REC_CAPACITY, topics=["Intramural sports"], summary=_REC_SUMMARY,
        evidence=[_ev("date_text", season_text), _ev("location_text", location),
                  _ev("eligibility_texts", _REC_ELIGIBILITY[0]), _ev("registration_text", f"Registration Dates {registration}"),
                  _ev("capacity_text", _REC_CAPACITY), _ev("organizer", "Yale Campus Recreation")],
        warnings=["Manually transcribed case record (not collected by the app)."],
    ))


def manual_records() -> list[Record]:
    volleyball = _rec_league(
        "case-rec-volleyball-fall", "Grad/Pro Intramurals: Fall Volleyball", "September 2nd - September 16th",
        "Fall Volleyball. Sundays. Regular Season: September 27th - November 1st. Playoffs & Championships: November 8th. "
        "Games played between 10am-3pm",
        [Session(date_text="Regular Season: September 27th - November 1st (Sundays, games played between 10am-3pm)",
                 start="2026-11-01T10:00:00-05:00", end="2026-11-01T15:00:00-05:00"),
         Session(date_text="Playoffs & Championships: November 8th",
                 start="2026-11-08T10:00:00-05:00", end="2026-11-08T15:00:00-05:00")],
        "Payne Whitney Gymnasium, Lanman Center Courts 1&2",
    )
    basketball = _rec_league(
        "case-rec-basketball-winter", "Grad/Pro Intramurals: Winter Basketball", "January 4th - January 19th",
        "Winter Basketball. Sundays. Regular Season: January 24th - February 21st. Playoffs & Championships: February 28th. "
        "Games played between 12pm-4pm",
        [Session(date_text="Regular Season: January 24th - February 21st (Sundays, games played between 12pm-4pm)",
                 start="2027-01-24T12:00:00-05:00", end="2027-01-24T16:00:00-05:00")],
        "Payne Whitney Gymnasium, Lanman Center Courts 3&4",
    )
    meetings = ("Program and competition meetings are held on the 2nd & 4th Mondays at 7pm EST, at 6:45pm (Sept-May) on Zoom.")
    activities = "We are an active club with programs, photo competitions, workshops, group field trips, photo challenges, etc."
    club = finalize(Record(
        record_id="case-nhcc-club", source_id="case-manual", kind="community", title="New Haven Camera Club",
        url=NHCC_URL, publisher="NHCC Photo Blog", organizer="New Haven Camera Club", collected_at=CHECKED_AT,
        date_text=meetings, format="online", format_text="on Zoom", summary=activities,
        registration_text="APPLICATION FOR NHCC MEMBERSHIP", topics=["Photography", "Camera club"],
        evidence=[_ev("date_text", meetings), _ev("format", "on Zoom"), _ev("organizer", "New Haven Camera Club"),
                  _ev("registration_text", "APPLICATION FOR NHCC MEMBERSHIP")],
        warnings=["Manually transcribed case record (not collected by the app)."],
    ))
    return [volleyball, basketball, club]


def case_result() -> SourceResult:
    return SourceResult("case-manual", "snapshot", CHECKED_AT, manual_records(),
                        {"note": "manually verified case records, not app data"})
