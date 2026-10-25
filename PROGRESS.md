# PROGRESS — Beyond Your Circle

> Incrementally updated progress and status record. Requirements baseline: PROJECT_SPEC.md; per-item rubric status: evidence/rubric_checklist.md; evidence for each question: evidence/qNN.md.
> Status words: Verified / Failed / Not verified / Awaiting human input.

Last updated: 2026-10-26 (Question 8 handed over; A: awaiting human input)

## 1. Question progress

| Question | Content | Status | Evidence |
|---|---|---|---|
| Q1 | Check the existing project, fix the rubric and acceptance baseline | Handed over | evidence/q01.md |
| Q2 | Limited public-source collection, real small sample | Handed over | evidence/q02.md |
| Q3 | Browsable basic discovery flow (deterministic, no model) | Handed over | evidence/q03.md |
| Q4 | Purpose-understanding agent and domain tools (including metering gate fix and first real run) | Handed over | evidence/q04.md |
| Q5 | Evidence-based matching, participation gate and exploratory recommendations | Handed over | evidence/q05.md, q05_cases.md, alternatives.md |
| Q6 | End-user flow (Find page, conditions, grouped results, failure recovery, run-details collapse) | Handed over | evidence/q06.md |
| Q7 | Safety and budget boundaries (collection SSRF, malicious announcements, display safety, termination and metering, red team) | Handed over | evidence/q07.md, q07_redteam.json |
| Q8 | Real metering (B), rates and scale cost (C), fresh clone (D); human task (A) prepared | Handed over (A done 2026-10-25: creator n=1, found a recall defect, G-12) | evidence/q08.md, q08_tokenomics.*, q08_clone/ |
| Q9–Q10 | — | Not started | — |

## 2. Current capability snapshot

| Capability | Status | Basis |
|---|---|---|
| Base-layer offline tests | Verified | 434 passed (full suite after Q7) |
| Dev directory startup, reading parent-level `.env` | Verified | q01 §7 |
| No key leakage (workspace, `.git`, runs, evidence, raw collected pages) | Verified | q02 §8 (177 files, 0 hits) |
| Two real automated collections from different sources (CAW photography courses, YCGS events) | Verified | q02 §5–6; `data/snapshots/` |
| Collection failure fallback / last success not erased | Verified (Simulated fault only) | q02 §7; q03 §3 (simulated outage in the UI) |
| Real records browsable on the web (this week/later/long-term, ET dates, source links, refresh and failure states) | Verified | q03 §3–4, 6 screenshots |
| AI recommendations in the target domain (purpose understanding, match explanations) | Verified (5 real runs) | Q4 `r_b79bfbda45ad`; Q5 `r_8aad4fe5a302`, `r_c588d02ea0b5`, `r_835194ffb88a`; Q6 `r_ce638df7cf6e` |
| End-user flow: short input + optional conditions (SOM/participation mode/time) → grouped results → open source; failure/cancel/timeout/budget recoverable | Verified (1 real run + Simulated fault) | q06 §3–4; real Tab-key order, 429 Not verified |
| Participation conditions (server-side match / check first / excluded), fact sources, deletion of details without a source | Verified | q05 §1, §3; no exclusion triggered in real runs |
| Metering gate F-01-F-08 | Verified | q04 §1, 11 tests; real-run ledger fields complete |
| New-domain safety evidence (app's own blocking, red team, collection SSRF, display safety, duration cap) | Verified | q07 §2 (3 real runs + 1 web + 47 tests); vendor filter did not trigger |
| Target-domain tokenomics (real usage, rate check, single run / monthly / 100 / 10,000 users, optimization comparison) | Verified | q08 B/C; n=5, scale is a scenario estimate, optimization is a comparison computed on the same batch of data |
| fresh clone runs within 10 minutes | Verified (this machine) | q08 D: 1st attempt failed because httpx was missing; after the fix, 2nd clone → usable in about 49 s, first AI result in about 2 min; GitHub clone Not verified (no remote) |

## 3. Persistent gaps (later questions must address or explicitly keep)

| ID | Gap | Source | Impact |
|---|---|---|---|
| G-01 | ~~Metering gate F-01-F-08~~ fixed and tested in Q4 | q04 §1 | — |
| G-02 | ~~Domain layer, prompts, result cards~~ replaced in Q4; ~~red-team samples still Harbor~~ Q7 added `scripts/redteam_q7.py` (old `redteam.py` kept as history) | q07 | — |
| G-03 | ~~`ALLOW_DOMAINS`~~ changed in Q4 to yale.edu, creativeartsworkshop.org; card links come from storage, not from model output | q04 §2 | — |
| G-04 | ~~Web data tools not marked untrusted~~ in Q4 both tools are `untrusted_output`; no false positives in real runs | q04 §2 | — |
| G-05 | No source connected yet for sports/spectating interests; community records are 0 (Q5 used only manually checked case records for functional verification, not in the app) | q02 §9, q05 §3 | Coverage of Idea, It works |
| G-06 | ~~No refresh entry or source status display in the app~~ resolved in Q3 (Discover tab) | q03 | — |
| G-10 | Real data has no "date unknown", "community", or "registration closed/full" records yet; these displays are verified only with synthetic tests | q03 §6 | Display coverage of It works |
| G-07 | README/DESIGN still describe the placeholder domain, and "only model calls need network" no longer holds once collection is connected | q01 §3.2 | can run it, repo quality |
| G-08 | ~~Repo has no commits~~ Q8 committed locally (`eaf71fc`, `9a625b9`, not pushed); **still no remote**; `.git` belongs to another account, commit with a single command using `-c safe.directory` | q08 D | Push, GitHub URL (P-02) |
| G-11 | Known issues in Question 5 logic (frozen, unchanged): "Open to Yale students" is judged met when identity is unknown; eligibility text not recognized by the rules does not generate a to-confirm condition (the frontend shows the original text) | q06 §8 | Safety/honesty |
| G-12 | ~~Recall defect found in the user's session: `search_listings` with `when="this_week"`/`"coming"` leaves out ongoing programs, so photography requests with a time window return nothing although two CAW photography programs exist (reproduced offline)~~ Fixed 2026-10-25 in `app/domain/tools.py` (2 regression tests; real check `r_21eea8b51494`) | real_use_log §D.1 | It works, Impact |
| G-13 | User feedback: the page looks plain; wants more Yale visual elements | real_use_log §D.1 | Look + feel |
| G-09 | The historical Harbor Bikes ledger contains 2 cache-replay records; `evidence/tokenomics.*`, `redteam_results.json` cannot be used as evidence for this project | q01 §3.5 | Tokenomics, Safety (history only) |

## 4. Awaiting user input (does not block independent work)

| ID | Content | Status |
|---|---|---|
| ~~P-01~~ | Authorship line for the report/slides | Provided by the user (2026-10-25): **Tongyu David Chen**. Report and slides not started yet |
| P-02 | Real GitHub repo URL, public/private, `zlisto` access status | Awaiting human input (user: do last) |
| ~~P-03~~ | Deadline time zone shown on Canvas | The user said it does not matter (2026-10-25); scheduled for 2026-10-26 18:00 |
| ~~P-04~~ | Creator n=1 real-use record | Done 2026-10-25 (3 searches, feedback and screenshots; timing not measured): `real_use_log.md` §D.1 |
| P-05 | Whether to add this repo to git `safe.directory` (or another way to fix `.git` ownership) | Awaiting human input (user: will update that configuration themselves later; Portkey key already available) |
| ~~P-07~~ | robots.txt of events.yale.edu forbids all automated access | The user confirmed not to collect (2026-10-25) |

## 5. Cumulative model calls (app runtime)

| Question | Real gpt-6-luna calls | Notes |
|---|---|---|
| Q1 | 0 | Read-only check and offline tests |
| Q2 | 0 | Collection is entirely deterministic code extraction |
| Q3 | 0 | Browsing and grouping are entirely deterministic code; 1 real collection refresh from the UI (no model) |
| Q4 | 4 (1 run) | `r_b79bfbda45ad`: guard 1 + matcher 3; 9,325 tokens; $0.000926; ledger 95 → 99 rows |
| Q8 | 4 (1 run in the fresh clone) | `r_af384cbce5e9` $0.001519, recorded in the clone's own ledger (copy in `evidence/q08_clone/`); real calls for this project total 32 rows $0.008269 (normal 19 rows $0.004625 + red team 9 rows $0.002125 + clone 4 rows $0.001519) |
| Q7 | 9 (3 red-team runs, separate ledger) | `r_0c89b3881d73` $0.001075, `r_6dff5fbf9fb4` $0.0000726, `r_7c9a61b04778` $0.000978; total $0.002125; `runs/redteam_q7/usage.jsonl` 9 rows; normal ledger still 114 rows; web blocking demo 0 calls |
| G-12 fix | 4 (1 verification run) | `r_21eea8b51494` $0.001388925; normal ledger 124 → 128 rows |
| Q8-A | 10 (3 runs by the user) | `r_80b535e6cc97`, `r_b8cd2f215d47`, `r_117624a6bd8a`; $0.00172422; normal ledger 114 → 124 rows |
| Q6 | 4 (1 run) | `r_ce638df7cf6e` $0.001309 (guard 1 + matcher 3); ledger 110 → 114 rows; demo server 0 rows |
| Q5 | 11 (3 runs) | `r_8aad4fe5a302` $0.000936, `r_c588d02ea0b5` $0.001075, `r_835194ffb88a` $0.000380; total $0.002390; ledger 99 → 110 rows |
| History (before Question 1) | ledger 95 rows + red team 38 rows | Harbor Bikes placeholder domain, base-layer history only (I-08) |

## 6. Change log

### Q1 (2026-10-25)
- Added: `PROJECT_SPEC.md`, `PROGRESS.md`, `AI_prompts.md`, `evidence/rubric_checklist.md`, `evidence/q01.md`, `evidence/real_use_log.md`.
- No application code modified.

### Q2 (2026-10-25)
- Added: `app/collect/` (`__init__.py`, `htmltree.py`, `fetch.py`, `records.py`, `sources.py`, `store.py`), `scripts/collect.py`, `data/snapshots/caw-photo.json`, `data/snapshots/ycgs-events.json`, `tests/test_collect.py`, `tests/fixtures/collect/*.html` (7 trimmed real pages), `evidence/q02.md`.
- Modified: `tests/conftest.py` (autouse fixture `no_real_network`), `requirements.txt` (`tzdata>=2024.1`), `PROJECT_SPEC.md` (I-10-I-12, P-07), `evidence/rubric_checklist.md`, `AI_prompts.md`.
- `tzdata 2026.5` installed in the local venv.

### Q3 (2026-10-25)
- Added: `app/discover.py`, `web/discover.js`, `tests/test_discover.py`, `evidence/q03.md`, `evidence/screenshots/q03_*.png` (6 files).
- Modified: `app/server.py` (`/api/discover`, `/api/sources`, `/api/refresh`), `app/collect/fetch.py` (simulated-outage transport; real error reported when robots is unreachable), `app/collect/store.py` (`simulated` flag), `app/orchestrator.py` (header title/tagline only), `web/index.html`, `web/styles.css`, `web/app.js` (1 line), `../.claude/launch.json` (added outage demo configuration, not in the repo).

### Q4 (2026-10-25)
- Added: `app/metering.py`, `app/domain/verify.py`, `app/domain/prompts/matcher.md`, `tests/test_metering.py`, `tests/test_domain.py`, `evidence/architecture.md`, `evidence/q04.md`, `evidence/q04_run/` (trace and ledger copy), `evidence/screenshots/q04_real_run_r_b79bfbda45ad.png`.
- Rewritten: `app/domain/__init__.py`, `models.py`, `tools.py`.
- Modified: `app/llm.py`, `app/pricing.py`, `app/ledger.py`, `app/budget.py`, `app/config.py`, `app/agent.py`, `app/safety.py`, `app/orchestrator.py`, `app/discover.py` (not_available carries id), `web/app.js`, `web/discover.js`, `web/index.html`, `web/styles.css`, `.env.example`, `tests/conftest.py`, `tests/test_ledger_budget.py`, `tests/test_server.py`, `tests/test_safety.py`, `tests/test_tools.py`.
- Deleted: `app/domain/prompts/coordinator.md`, `researcher.md`, `verifier.md`; `data/sample/` moved to `tests/fixtures/safety/`.

### Q8 (2026-10-26)
- Added: `scripts/tokenomics_q8.py`, `evidence/q08.md`, `evidence/q08_tokenomics.json/.md`, `evidence/q08_clone/`, `evidence/q08_clone_attempt1_start_log.txt`, `evidence/screenshots/q08_clone_*` (2 files); `evidence/real_use_log.md` §D (human task and record table).
- Modified: `requirements.txt` (added `httpx`, found by the fresh clone).
- git: first local commit `eaf71fc`, fix commit `9a625b9`, not pushed; `my-app/fresh-clone-q8` (Failed) and `fresh-clone-q8-2` (succeeded) are test directories outside the repo and can be deleted.

### Q7 (2026-10-26)
- Added: `scripts/redteam_q7.py`, `tests/test_q7_safety.py`, `evidence/q07.md`, `evidence/q07_redteam.json`, `evidence/q07_redteam/`, `evidence/screenshots/q07_app_input_screen_block_*.jpg`.
- Modified: `app/collect/fetch.py` (malformed URLs no longer crash), `app/config.py` + `app/orchestrator.py` (`RUN_TIMEOUT_S`, `n_failed_attempts`), `app/server.py` (CSP `script-src 'self'`), `web/app.js` (wording), `tests/conftest.py` (environment isolation).

### Q6 (2026-10-25/26)
- Added: `tests/test_flow.py`, `evidence/q06.md`, `evidence/q06_run/`, `evidence/screenshots/q06_*` (6 files).
- Modified: `app/domain/models.py` (RunOptions), `conditions.py` (effective_understood, "you told us"), `verify.py` (grouping/source/also_read/openable excluded items), `app/orchestrator.py`, `app/server.py`, `app/llm.py` (SimulatedFailureLLM), `app/config.py` (daily budget may be 0), `app/safety.py` (simulation label), `web/index.html`, `web/app.js`, `web/discover.js`, `web/styles.css`; `../.claude/launch.json` (8772/8773, 8771 with simulated failure added).
- Withdrawn: the review-suggested change to the Question 5 judgment logic (rules frozen), recorded as G-11.

### Q5 (2026-10-25)
- Added: `app/domain/conditions.py`, `scripts/compare_cases.py`, `tests/test_cases.py`, `tests/fixtures/cases/` (`manual_cases.py`, `specs.py`), `evidence/q05.md`, `evidence/q05_cases.md`, `evidence/q05_cases.json`, `evidence/alternatives.md`, `evidence/q05_runs/`, `evidence/screenshots/q05_*.png` (3 files).
- Modified: `app/domain/models.py`, `verify.py`, `tools.py`, `prompts/matcher.md`, `app/orchestrator.py`, `app/discover.py` (URL + title dedup, registration date range, deadline year), `web/app.js`, `web/styles.css`, `tests/test_domain.py`.

## 7. Non-blocking to-do (ordered by value)

- Third source: Yale Campus Recreation graduate/professional-school intramural leagues (fills the "sports" interest); NHCC photography club Atom feed (fills the photography community).
- Narrative locations in YCGS descriptions (such as "at the Yale Peabody Museum") are currently kept unknown; if extraction is wanted, a later evidence-backed extraction step should handle it and mark it to confirm.
- The this-week window uses "7 days from today" (I-13); if the user prefers a calendar week, it can be changed to Monday through Sunday.
- ~~verifier does not rewrite the model summary~~ Question 6: the UI shows code statistics before the AI summary and marks the summary as not checked by code.
- Prompt-tuning candidate: the model infers "go back regularly" as `when=ongoing`; it read only 1 listing. Decide on adjustment after multiple real runs (to avoid changing things for a single observation).
- ~~`verification` events in the timeline use the generic style~~ Question 6 added a dedicated display.
- `HEAD /` returns 405 (affects only liveness-probe tools); the DESIGN.md description of browser latency is slightly outdated.
- Found in the read-only check in a new conversation (2026-10-25), not yet handled: ① `scripts/tokenomics.py` by default reads the whole `runs/usage.jsonl` (95 rows of Harbor history + 15 rows of the new domain), does not filter by mode/run, and treats null usage/cost as 0 (lines 68, 70); running it directly would mix in history and overwrite `evidence/tokenomics.*`; ② the tokenomics row in §2 of this file, rubric A2/A7 ("1 real run"), B3/B8/B9/B10, C8 and PROJECT_SPEC §6 have status stuck at Q4 or earlier; ③ `evidence/architecture.md` still says `watch_out` and lacks Question 5's server-side match / check first / excluded judgment; ④ the `data/sample` defaults in `app/config.py:120` and `.env.example:31` are no longer valid (no code references them); ⑤ the guard prompt in `app/safety.py:552` still says "help-desk"; ⑥ the static title in `web/index.html` is "Agent Workbench" (replaced at runtime by app.js).
