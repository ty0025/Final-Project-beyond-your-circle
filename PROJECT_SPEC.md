# PROJECT_SPEC — Beyond Your Circle (MGT 409 Final Project)

> This file is the baseline for project requirements and boundaries, created in Question 1 (2026-10-25). Later questions change it only with justification and record the reason for the change in PROGRESS.md.
> Numbering: `C-` course requirements (from the course's original text/Word), `U-` product decisions already made by the user (from the background brief), `M-` model/key/evidence rules, `I-` our implementation choices (not course rules), `P-` information awaiting the user.
> Only four status terms are used: **Verified** (check run and satisfied), **Failed** (check run and not satisfied), **Not verified** (not yet implemented or not yet checked), **Awaiting human input** (requires the user (Tongyu David Chen) to provide or perform).

## 0. Sources and priority

| Source | Location | Version/time | Use |
|---|---|---|---|
| The course's original text (highest priority) | https://zlisto.github.io/mgt_409_fa26/project_requirements.html | Downloaded 2026-10-25 01:10Z, HTML sha256 `a861edcd…a6`, page has no "last updated" info | Basis for course requirements `C-` |
| Chinese-summary Word file | The user's local `MGT409_FinalProject_要求整理(1).docx` (Chinese summary of the requirements) (WeChat folder) | sha256 `dad97a8c…94`, document has no comment objects; body says "when writing the report and slides, the course website's original text prevails" | Cross-check; consistent with the original, differences in evidence/q01.md §2 |
| Lecture 11 slides | https://zlisto.github.io/mgt_409_fa26/lectures/slides/lec11-slides.html | Read 2026-10-25 | gpt-6-luna unit prices |
| The user's background brief | First message of this conversation (before Question 1) | 2026-10-25 | Product decisions `U-`, rules `M-` |
| Project AGENTS.md | `../AGENTS.md` (one level above the repo) | 2026-10-25 | Only gpt-6-luna, no key leakage, blue visual style, creatures in HTML |

Conflict resolution: the course's original text > Word summary > our implementation choices. Product decisions in the user's brief apply only when they do not violate the course's original text (currently no conflict).

## 1. Course requirements (C-, all from the course's original text; where the Word file agrees, this is not repeated)

| ID | Requirement | Notes |
|---|---|---|
| C-01 | Individual project, Canvas deadline **Monday, October 26, 2026, 6:00 PM** | Original text gives no time zone; go by what Canvas shows (P-03) |
| C-02 | Canvas submission has 3 items: GitHub repo link, `report.html`, `slides.html`; optional 2–3 minute demo video (uploaded to Canvas) | Repo is public, or private with GitHub user `zlisto` added as collaborator |
| C-03 | Both HTML files are self-contained: double-click to open on any computer, all screenshots display (images embedded in the file) | |
| C-04 | Report is 10–15 pages (letter, normal font, with screenshots); written for a smart manager who has not seen the app; AI assistance allowed, but every word and number must match the actual app; padding to reach the page count is penalized | |
| C-05 | Report has eight sections in order: 1 Title + links (project name, name, repo link = the one submitted to Canvas, online link if any, one-sentence description); 2 Motivation; 3 What is new here; 4 The agents (each agent's role, tools, organization/handoffs, architecture diagram, model and rationale, one real run step by step with screenshots); 5 Tokenomics (measured input/cached input/output for a typical run; cost per run, per user per month, for 100 and 10,000 users; cost-saving measures and whether they degrade quality, with evidence); 6 Safety (attacks, agent failure, overspend; at least one screenshot or test where a defense really took effect); 7 Impact (quantified, with the source of the numbers explained; strongest evidence is real user trials); 8 Limits + next steps | |
| C-06 | Slides: a single HTML file, **at most 10 slides**, using reveal.js (arrow keys to navigate, F for full screen); suggested order: title/problem/what is new/architecture diagram/demo screenshot/cost/safety/impact numbers/next steps; when done, double-click to open and check each slide with arrow keys | The original text's example prompt says "using reveal.js, loaded from a CDN" |
| C-07 | Repo: all code needed to run; README states what the app is and step-by-step run instructions (or an online link); `.env.example` lists required key names without real values; never commit the real `.env` or `PORTKEY_API_KEY` | |
| C-08 | If a large dataset is used, include a small test set in the repo and explain in the README how to switch | |
| C-09 | Course key: `PORTKEY_API_KEY` **may only use gpt-6-luna**; other models require a personal key at own expense (OpenAI's is named `OPENAI_API_KEY`) | |
| C-10 | The instructor runs the app in one of two ways: online (link at top of README and report, kept available until final grades are posted; free hosting sleeps, so confirm on the submission day), or local fresh clone following the README; the simpler the local setup, the better | |
| C-11 | 10-minute rule: if it still does not run after 10 minutes following the README, "The teaching staff can run it" gets 0 points | |
| C-12 | `.env` is looked up first in the repo's own directory, then one level up; the instructor's `.env` has only `PORTKEY_API_KEY` and `OPENAI_API_KEY`, names must match exactly; **an app that needs other keys must be deployed online and the professor consulted** | Word file does not mention the last point |
| C-13 | Dry run before submission: clone into a fresh folder, put `.env` one level up, run and use the app from scratch following the README | |
| C-14 | A video can save "It works" and "Look + feel", but **cannot** save the 5 points for "can run it" | |
| C-15 | Grading is 100 points (Idea 21; App 30 = It works 15 + can run 5 + Look & feel 10; Report 41 = Motivation & new 8 + Agent design 10 + Tokenomics 8 + Safety 8 + Impact 5 + Design 2; Slides 8 = Content 6 + Design 2) | Item by item in evidence/rubric_checklist.md |
| C-16 | Evidence rule: a Report row missing its specified evidence gets at most half of that row (Motivation: named existing products compared; Agent design: one real run traced step by step + a screenshot of each agent; Tokenomics: real-run token counts, from logs or shown in the app, pure estimates halved; Safety: screenshot/test of a defense actually stopping an attack or fault, description only halved; Impact: real user trial (quotes, screenshots, or before/after times), pure guesses halved) | |
| C-17 | Tier 1/2/3 definitions; common topics (resume/cover letter, Chat with PDF/documents, trip planning, email/meeting summary, recipes, generic study buddy/flashcards, class/homework reuse without substantive additions) cap Idea at Tier 1 unless there is a real twist | |
| C-18 | (Advice, not mandatory) people first, then technology; talk to real users; take screenshots as you go; build something that runs first, then make it smarter | "Ship something that works first" appears only in the original text |

## 2. Product definition (U-, decided by the user)

| ID | Decision |
|---|---|
| U-01 | Project name **Beyond Your Circle**: a campus event and community discovery assistant |
| U-02 | First-version primary users: Yale SOM graduate students; discovery scope: **public** events, communities, and ongoing programs in other Yale schools and in New Haven |
| U-03 | Primary goal: find people or communities with the same interests, to make sustained participation easy; secondary goal: professional/topic networking opportunities |
| U-04 | Test interests (test cases only, must not be hard-coded as just three tags): (1) photography technique discussion, sharing work, and shooting together; (2) sports, casual competitions, and watching games open to ordinary enthusiasts; (3) AI literacy for non-technical people |
| U-05 | User input: interest + specific networking purpose + way of participating; app output: the public information collected, why it matches, the participation conditions, and where to learn more or sign up next |
| U-06 | Results in three groups: this week / coming weeks / long-term communities or ongoing programs; times in America/New_York, with the window stated explicitly |
| U-07 | Recommendations stay mainly close to the interest, with a few exploratory picks that must explain the connection; may be zero when there is no suitable exploratory pick |
| U-08 | Differentiation focus: cross-source discovery, understanding the specific purpose, explaining the match, presenting participation barriers; these must be implemented as **checkable functional differences**, not just wording |
| U-09 | Honest comparison: Yale-Localist and YaleConnect already offer event lookup and some personalization; must not claim the campus never had event aggregation |
| U-10 | First version uses limited, verified public sources; the user's manual refresh triggers automatic collection; no push notifications after the web page is closed |
| U-11 | Not doing: private Slack, WhatsApp, email, Canvas (no need for their accounts or authorization); automatic sign-up, payment, messaging, calendar scheduling, matching individuals or forming teams; complex account systems |
| U-12 | Fact boundaries: a public page does not mean open to all students; a sign-up link does not mean spots are left; a season in progress does not mean sign-up is still open; a community existing does not mean it is recruiting. Anything known to fail a hard condition cannot be a "can join" match; unknown conditions are marked "to confirm"; records without a date cannot pose as this week's events; empty results are shown honestly |
| U-13 | Data provenance: keep the original URL, organizer, collection time, basis for key fields, and missing values; distinguish online refresh, cache, fixed snapshot, real model, and simulated tests; do not present historical or fabricated data as live results |
| U-14 | The user's pain-point figures are only personal recollection estimates (asking friends 10–20 minutes, Google 10–20 minutes, CampusGroups/Slack/WhatsApp a dozen-odd minutes each; frequency, whether it is the same task, and whether it is repeated were not measured). **Must not be summed into a per-session/weekly total, and must not be written as time the app has saved**; actual effect is measured separately |
| U-15 | The user (Tongyu David Chen) is a real target user and can make a creator n=1 real-use record; this is not an independent pilot; recruiting others is not planned for now; without human operation, mark "Awaiting human input"; do not fabricate interviews, feedback, timings, or social outcomes |
| U-16 | Pages are clear and easy to use, with features and evidence first; all pages use a blue visual style (AGENTS.md) |

## 3. Models, keys, and evidence rules (M-)

| ID | Rule |
|---|---|
| M-01 | All course-model calls at app runtime use only **gpt-6-luna**, via Portkey, with `PORTKEY_API_KEY`. Claude Code is only a development tool and is not part of the app's model calls |
| M-02 | Keys stay in the backend only; `.env` is looked up in the repo first, then the parent directory; must not be printed, committed, passed to the frontend, or written into evidence/logs |
| M-03 | From the first real call, record **all** model calls (extraction, guard, verification, and retries all count): actual usage such as input, cached input, output, plus run_id, role, tool, duration, stop reason; missing fields are not passed off as measured zero; no double billing |
| M-04 | Keep caps on calls/retries/duration/tokens/cost; announcement/web content is untrusted data and cannot change system instructions or tool permissions |
| M-05 | When the safety and usage foundations are not ready, do only offline mock/stub checks and send no real model requests; mock means a scripted fake model, not another local or remote model |
| M-06 | Unit prices (Lecture 11 slides, per 1M tokens, gpt-6-luna): input $0.10, cached input $0.01, cache write $0.125, output $0.50. Cost is computed per call from measured tokens |

## 4. Implementation choices (I-, our decisions, not course rules)

| ID | Choice | Reason / basis |
|---|---|---|
| I-01 | Reuse the existing FastAPI single-process + static HTML/CSS/JS base (no Node build, no database), replace the domain layer, do not rebuild the HW4/HW5 tech stack | Background requirement; base modules already have offline tests (see §6) |
| I-02 | Fresh clone is the main delivery path; online deployment is not mandatory | Background decision; C-10 either/or |
| I-03 | First get **two** verified public sources working on one real recommendation path, keeping run, cost, and safety evidence; a third and further sources, extra cases, and visual extensions come after the core evidence is complete | Background time trade-off |
| I-04 | Public sources must be readable **without any extra API key** (public pages/public feeds) | C-12: other keys would force going online and consulting the professor, breaking the fresh clone path |
| I-05 | Slides use the reveal.js CDN (allowed by the course example); the report and slides must state this network dependency and not claim to be fully offline; screenshots embedded as base64 (`scripts/inline_images.py`) | C-03, C-06 |
| I-06 | When implementing the America/New_York date window, add `tzdata` to `requirements.txt` | Measured in Question 1: on this machine's Windows Python 3.14 without `tzdata`, `ZoneInfo("America/New_York")` raises `ZoneInfoNotFoundError`; the instructor's Windows environment is the same |
| I-07 | Verification favors offline and targeted checks; regression at integration nodes as needed; do not repeatedly run unrelated tests or paid calls | Background |
| I-08 | Existing Harbor Bikes run records (`runs/`, `evidence/tokenomics.*`, `evidence/redteam_results.json`) are kept as "foundation verification history of the placeholder domain" and **must not** be used as tokenomics/safety evidence for the new domain | U-13, C-16 |
| I-09 | Each question's handoff uses "rubric item → implementation location → verification method → evidence path/version/run_id → status"; maintain this file, PROGRESS.md, AI_prompts.md, and evidence/qNN.md | Background collaboration method |
| I-10 | Automatic collection obeys robots.txt and Crawl-delay; sites that robots.txt forbids (such as events.yale.edu) are not collected automatically, only usable as a comparison with existing products | Measured in Question 2; responsible collection posture |
| I-11 | Fields are extracted deterministically by code first; if the page does not say, record as unknown (`missing`), do not infer free/unlimited spots/open to everyone; if collection needs a model, it must go through the same gateway, budget, and ledger, and F-01 to F-08 must be fixed first | Question 2 task 5; U-12 |
| I-13 | "This week" = 7 calendar days starting from today 00:00 (America/New_York); "later opportunities" = single-date events after that; programs and communities are listed separately as "long-term", showing the next open session; undated events are listed separately as "date unknown" | Question 3; avoids "this week" being nearly empty on weekends, the window dates are stated on the page |
| I-14 | UI refresh: only one at a time, 300 s cooldown after completion (`REFRESH_COOLDOWN_S`); `COLLECT_SIMULATE_OUTAGE=1` is used only for clearly labeled offline demos | Question 3; polite to source sites, failure demos are not disguised as real outages |
| I-15 | Agent organization: rule screening (code) → guard (1 gpt-6-luna call) → a single matcher agent (tools `search_listings`/`get_listing`, at most 4 rounds) → verifier (code, no model call); the researcher and LLM verifier are retired | Question 4; retrieval and verification done by deterministic code use fewer calls and are reproducible; see evidence/architecture.md |
| I-16 | Every model attempt (success, failure, retry) is entered in the ledger one by one: `mode` live/mock, `served_model`, missing usage recorded as null; at most 12 calls per run and at most 1 application-level retry | Question 4 metering gates F-01 to F-08 |
| I-17 | Recommendation status is decided by the server: hard conditions (format, time window, audience, prerequisites, age, membership, participating/watching, sign-up) are checked against the user's own words, `not_met` is excluded, `to_confirm` is "check first"; facts are restored by the server with the page's original text attached; prices/times/dates/links etc. in model text that the page does not contain are deleted; networking format and exploratory connection must have verbatim quotes | Question 5; U-12's "known-unmet is not a can-join match, unknown is to confirm" |
| I-18 | Functional cases may use manually checked public records (copied verbatim, with read time noted), used only as test fixtures and not entering app data; comparisons only show the difference between two treatments within the same app | Question 5 tasks 5–6 |
| I-12 | First sources connected (Question 2): `caw-photo` (Creative Arts Workshop photography courses, community nonprofit) and `ycgs-events` (Yale Center for Geospatial Solutions events, official Yale); candidates checked but not connected and the reasons are in `NOT_CONNECTED` in `app/collect/sources.py` and evidence/q02.md §1 | Measured in Question 2 |

## 5. Deliverables checklist (course requirement → our check method)

| Deliverable | Course requirement | Our check method (implementation choice) |
|---|---|---|
| GitHub repo | All code, README, `.env.example` (no real values), small test data; public or private + zlisto | Fresh clone into a new directory, `.env` one level up, run timed following the README; secret scan; record visibility/collaborator status |
| report.html | 10–15 letter print pages, eight sections in order, images embedded, opens by double-click | Count pages in browser print preview; check no external image links; compare numbers against evidence files item by item |
| slides.html | ≤10 slides, reveal.js, images embedded | Open by double-click, check each slide with arrow keys; state the CDN dependency |
| Demo video (optional) | 2–3 minute real demo | Recorded only after the user records it; does not replace run acceptance |

## 6. Existing engineering baseline (Question 1 check results)

Detailed evidence: evidence/q01.md. Summary:

- **Reusable**: `app/config.py` (model lock, two-level `.env`), `app/llm.py` (single call point, Portkey, forced bypass of response cache), `app/pricing.py`/`ledger.py`/`budget.py` (pricing, ledger, pre-call budget check), `app/agent.py`/`tools.py`/`events.py` (agent loop, delegation, allowlist, caps, trace), `app/safety.py` (spotlight, injection scan, redaction), `app/server.py` shell and `web/` timeline/cost card, `run.py`/startup scripts, `scripts/tokenomics.py`/`inline_images.py`. Offline tests 296 passed.
- **Placeholder (to be replaced)**: `app/domain/*`, `data/sample/*`, team/metadata/`ALLOW_DOMAINS`/refusal text in `app/orchestrator.py`, result cards in `web/app.js`, `scripts/redteam.py`, tests depending on sample files, README/DESIGN.
- **Not implemented (as of Question 1)**: public source collection, source registry, unified record schema, America/New_York date window, hard-condition filtering, match explanation output, refresh/source status endpoints, data mode labels, collector network isolation test. Question 2 has implemented the collection, source registry, unified record, snapshot/cache labels, and network isolation test (`app/collect/`); date-window grouping, hard-condition filtering, match explanation, and in-app refresh are still not implemented.
- **Gates before real model calls**: F-01 to F-08 (missing usage recorded as 0, failures/retries not in the ledger, no call count cap, model field is a constant, no real/mock marker, `OPENAI_*` environment variables, key with spaces).

## 7. Awaiting user input (P-)

| ID | Information needed | Use | Blocks current work? |
|---|---|---|---|
| P-01 | Name for the report/slides byline (name spelling) | Report §1, slides title | Provided: **Tongyu David Chen** (2026-10-25) |
| P-02 | Real GitHub repo URL, public/private, whether `zlisto` has been added | Report §1, Canvas submission, "can run it" | No (needed before submission) |
| P-03 | The deadline time zone Canvas actually shows | Scheduling | No; the user said it is not important (2026-10-25) |
| P-04 | Creator n=1 real-use record (human operation, timing, screenshots, own words) | Impact evidence | No (needed once the app is usable) |
| P-05 | The `.git` directory is owned by another Windows account (CodexSandboxOffline), and ordinary git commands report "dubious ownership". The user must decide: allow running `git config --global --add safe.directory "C:/Users/david/Desktop/Courses/my-app/final project"`, or fix the ownership another way | First commit, push | No (needed before commit; read-only checks can use `git -c safe.directory=...`); the user said they will update this setting themselves later (2026-10-25) |
| P-06 | Whether the final choice of the first two public sources needs the user's confirmation | Public collection | No (Question 2 already chose by measuring candidates, see I-12) |
| P-07 | events.yale.edu's robots.txt is `Disallow: /`: keep not collecting automatically (default), or the user obtains permission separately | Source coverage | Decided: do not collect (confirmed by the user 2026-10-25) |

## 8. Collaboration method

- The user sends questions 1 to 10 one by one; only the current question is completed, later questions are not implemented ahead of time.
- At the end of each question, update PROGRESS.md, AI_prompts.md (Initial Prompt / Follow-up Prompt / What Was Lacking, recording only what really happened), and evidence/qNN.md.
- Gaps from earlier questions carry forward; acceptance that depends on real data, metering/safety, or a real model cannot skip past a prerequisite gap; generating a document does not close an item.
- After an interruption, first read this file, PROGRESS.md, and this question's evidence, check existing changes, and complete only what is unfinished or invalidated by new changes; reuse real runs where possible and do not pay to rerun just to get screenshots.
