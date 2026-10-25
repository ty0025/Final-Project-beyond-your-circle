"""Problem-5 functional cases and the keyword-vs-purpose comparison (deterministic, no model call).

Each case has: the request in plain words; a HAND-WRITTEN structured profile (what a correct reading
of the request contains; the model's own reading is tested separately in real runs); and the keyword
tags a tag-style search would use. Data = committed real snapshot + manually verified case records,
evaluated at the fixed TEST time CASE_NOW.

- keyword/tag baseline: every non-past listing whose title, topics or summary contains a tag.
- purpose-aware: the same candidates after the server's checks (availability from the page, hard
  conditions against what the user said, topic relevance, interaction evidence).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.collect.sources import SOURCES
from app.collect.store import load_source
from app.discover import build_discovery
from app.domain.conditions import evaluate, interaction_text, topic_matches, verdict
from app.domain.tools import ListingSession
from tests.fixtures.cases.manual_cases import CASE_NOW, case_result

REPO_DIR = Path(__file__).resolve().parents[3]
SNAPSHOTS = REPO_DIR / "data" / "snapshots"
_INTERACTION = re.compile(r"\b(club|meetings?|meetup|gathering|competitions?|field trips?|workshops?|hands-on|"
                          r"league|teams?|social|networking|community|series)\b", re.I)


def profile(**kw) -> dict:
    base = {"interests": [], "purpose": None, "purpose_type": "not_stated", "participation": "not_stated",
            "play_or_watch": "not_stated", "experience_level": None, "identity": None, "time_window": "not_stated",
            "time_preference": None, "location_preference": None, "not_stated": []}
    return base | kw


PHOTO = ["photography", "photo", "photographer", "camera", "darkroom", "film"]
SPORTS = ["sport", "sports", "volleyball", "basketball", "intramural", "intramurals", "league"]
AI = ["ai", "genai", "generative ai", "chatbot", "bot", "prompt"]

CASES = [
    {"id": "C1", "title": "Photography: meet people in person, no darkroom experience",
     "request": "I'm an SOM MBA student. I love photography but have never done darkroom work. I want to meet people who shoot, in person.",
     "tags": PHOTO,
     "profile": profile(interests=["photography"], purpose="meet people who shoot", purpose_type="meet_people_or_join_community",
                        participation="in_person", experience_level="never done darkroom work", identity="SOM MBA student")},
    {"id": "C2", "title": "Photography: a club to share photos, online is fine",
     "request": "I'd like a photography club where people share and discuss their photos. Online is fine.",
     "tags": PHOTO,
     "profile": profile(interests=["photography"], purpose="share and discuss photos", purpose_type="meet_people_or_join_community",
                        participation="either")},
    {"id": "C3", "title": "Sports: play casually as a beginner",
     "request": "I'm an SOM student and a beginner. I'd like to play volleyball or basketball casually with other grad students.",
     "tags": SPORTS,
     "profile": profile(interests=["volleyball", "basketball"], purpose="play casually with grad students", purpose_type="do_the_activity",
                        play_or_watch="play", experience_level="beginner", identity="SOM student")},
    {"id": "C4", "title": "Sports: watch games with others",
     "request": "I don't want to play; I'd like to watch basketball games with other people.",
     "tags": SPORTS,
     "profile": profile(interests=["basketball"], purpose="watch games with others", purpose_type="watch_or_spectate",
                        play_or_watch="watch")},
    {"id": "C5", "title": "AI introduction for a non-technical student, online fine",
     "request": "I'm not technical. I want a beginner-friendly introduction to using AI tools. Online is fine.",
     "tags": AI,
     "profile": profile(interests=["ai"], purpose="learn to use AI tools", purpose_type="learn_or_discuss_topic",
                        participation="either", experience_level="not technical")},
    {"id": "C6", "title": "AI or maps talk this week, in person",
     "request": "Any hands-on AI or mapping session this week, in person?",
     "tags": AI + ["maps", "mapping"],
     "profile": profile(interests=["ai", "maps"], purpose="hands-on session", purpose_type="learn_or_discuss_topic",
                        participation="in_person", time_window="this_week")},
    {"id": "C7", "title": "Unknown eligibility: drone hobby meetup",
     "request": "Is there a casual drone hobby meetup?",
     "tags": ["drone", "drones"],
     "profile": profile(interests=["drones"], purpose="casual meetup", purpose_type="meet_people_or_join_community")},
    {"id": "C8", "title": "Empty result: pottery wheel class",
     "request": "Is there a pottery wheel class?",
     "tags": ["pottery", "ceramics", "wheel"],
     "profile": profile(interests=["pottery"], purpose="learn pottery", purpose_type="do_the_activity")},
]


def case_session() -> ListingSession:
    results = [load_source(s, runs_dir=Path("/nonexistent-test-dir"), snapshot_dir=SNAPSHOTS) for s in SOURCES] + [case_result()]
    return ListingSession.from_results(results, now=CASE_NOW)


def _tag_hit(tags: list[str], record) -> bool:
    text = " ".join([record.title, " ".join(record.topics), record.summary or ""])
    return any(re.search(rf"\b{re.escape(t)}\b", text, re.I) for t in tags)


def run_case(case: dict, s: ListingSession | None = None) -> dict:
    s = s or case_session()
    windows = s.view["windows"]  # type: ignore[attr-defined]
    view_all = build_discovery(s.results, now=s.now)
    past_ids = {rid for rid in s.records if rid not in s.cards and rid not in s.unavailable}
    baseline = [rid for rid, r in s.records.items() if rid not in past_ids and _tag_hit(case["tags"], r)]
    rows = []
    for rid in baseline:
        r = s.records[rid]
        if rid in s.unavailable:
            rows.append({"id": rid, "title": r.title, "kind": r.kind, "status": "excluded",
                         "reasons": [s.unavailable[rid]], "to_confirm": [], "met": [], "interaction": None})
            continue
        conds = evaluate(r, s.cards[rid], case["profile"], windows)
        status = verdict(conds)
        inter = _INTERACTION.search(interaction_text(r))
        rows.append({
            "id": rid, "title": r.title, "kind": r.kind,
            "status": {"excluded": "excluded", "conditional": "conditional", "clear": "match"}[status],
            "reasons": [c.text for c in conds if c.status == "not_met"],
            "to_confirm": [c.text for c in conds if c.status == "to_confirm"],
            "met": [c.text for c in conds if c.status == "met"],
            "relevance": [m["term"] for m in topic_matches(case["tags"], r)],
            "interaction": inter.group(0) if inter else None,
        })
    order = {"match": 0, "conditional": 1, "excluded": 2}
    rows.sort(key=lambda x: (order[x["status"]], x["title"]))
    return {"case": case["id"], "title": case["title"], "request": case["request"], "baseline": baseline,
            "rows": rows, "counts": {k: sum(1 for x in rows if x["status"] == k) for k in order},
            "test_time": CASE_NOW.isoformat(), "sources": [x["data_mode"] for x in view_all["sources"]]}
