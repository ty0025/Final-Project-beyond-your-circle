# Real-use log (creator n=1 and other human operations)

> Purpose: human-use evidence for Impact, Look + feel and Agent design. Only **actual** human operations are recorded; if there are none, keep "No record".
> This log does not record Claude Code development operations (see AI_prompts.md) or offline tests (see each question's evidence/qNN.md).
> Rules (PROJECT_SPEC.md U-14, U-15): creator n=1 is not an independent pilot; do not invent interviews, feedback, timings or social outcomes; recall estimates must not be added together or written as time the app has saved.

## A. Recall estimates before using the app (not measured)

Source: the user's own account in the background statement (2026-10-25). The following are **personal recall estimates**; frequency, whether they belong to the same task, and whether they overlap with each other were **not measured**.

| Channel | Recalled time per attempt | Status |
|---|---|---|
| Asking friends | Ten-plus to twenty minutes | Recall estimate, not measured |
| Google search | Ten-plus to twenty minutes | Recall estimate, not measured |
| CampusGroups, Slack, WhatsApp | Ten-plus minutes each | Recall estimate, not measured |

The user also described: not wanting to check every day; often finding no useful content after checking; over time exploring less actively, so that what they learn about is mainly what the people around them care about. (Qualitative description, not quantified.)

**Prohibited use**: do not add the table above into a "total time per attempt/week", and do not subtract app time from it and write the result as "time saved". For a before/after comparison, measure the same task separately.

## B. Human operation records

| Date and time (America/New_York) | Operator | Task (interest + purpose + participation mode) | Data mode (live refresh/cache/fixed snapshot) | run_id | Measured time | Result and quotes | Screenshot path |
|---|---|---|---|---|---|---|---|
| Sun Oct 25, 2026, 5:13 PM EDT | Tongyu David Chen (creator n=1) | Animation; find someone with the same interest; SOM checked, Online, Next 7 days | Saved from last refresh (collected Sat Oct 24, 9:50 PM EDT) | `r_80b535e6cc97` | Not measured | No verified match (there is no animation listing in the two connected sources) | — |
| Sun Oct 25, 2026, 5:14 PM EDT | Tongyu David Chen (creator n=1) | Photography (typed "photograph"); same purpose and conditions | Same | `r_b8cd2f215d47` | Not measured | No verified match: the photography programs were filtered out by the search time filter (see §D.1) | — |
| Sun Oct 25, 2026, 5:15 PM EDT | Tongyu David Chen (creator n=1) | Photography; find someone with the same interest; SOM checked, Either is fine, Next 4 weeks | Same | `r_117624a6bd8a` | Not measured (the AI run itself took 12.0 s) | No verified match; one listing read by the AI but not recommended (YCGS Drone Hobbyist Gathering II). Feedback in §D.1 | `screenshots/q08a_user_results_r_117624a6bd8a.webp`, `screenshots/q08a_user_run_details_r_117624a6bd8a.webp` |

Status: **Verified** for "a real person used the app" (creator n=1, 3 searches, 2026-10-25). Task time was not measured. This is the app's creator, not an independent trial.

## C. Comparison measurement (if done)

Not yet designed or performed. If done later, state the definition of the same task, the timing method and the start and end points, and record the raw data here.

## D. Question 8-A: predefined human task and record form (prepared 2026-10-26; not yet executed)

**Operator**: Tongyu David Chen (the user) (creator n=1, not an independent trial). No one else is recruited; no synthetic users are used.

**Task (about 10 minutes)**: Open the app (Find page) and describe in one's own words a real interest and what one wants to get (for example photography exchange, non-technical AI introduction, sports or watching games), setting the SOM identity / participation mode / time if needed. Within the window of "this week (next 7 days) or next 4 weeks", find **at most 3** activities or communities you would like to learn more about; for each one write down the conditions to confirm first and the next step (open the original page or sign-up page).

**Success criteria**: 1-3 items are selected within the window (or an explicit judgment that "none is suitable"); each item can open its original page; each item has at least 1 condition to confirm or next step written. Timing runs from opening the page to finishing the list (phone or computer stopwatch).

**Optional comparison (manual search)**: Afterwards, search manually with the same public scope (the two connected sources: the Creative Arts Workshop photography course page and the Yale Center for Geospatial Solutions events page) and the same time window, also timed. The order must be recorded (app first then manual creates a familiarity effect), and recalled times (§A) must not be treated as measured.

| Field | Record (filled in by the user; leave blank until performed) |
|---|---|
| Date and time (America/New_York) | |
| Device / browser | |
| Verbatim request | |
| Conditions set (SOM / participation mode / time) | |
| Data mode (cache / snapshot, collection time shown on the page) | |
| run_id (in Run details) | |
| Measured time (mm:ss) | |
| Selected items (title + link, ≤3) | |
| Whether each was already known before (yes / no) | |
| Whether each is worth learning more about (yes / no) | |
| Conditions to confirm first / next step for each | |
| Verbatim feedback (exact words, record both good and bad) | |
| Screenshot path | |
| Manual comparison: order, time, items found | |

Status: carried out on 2026-10-25; the filled record is in §D.1.

### D.1 Completed record (2026-10-25, creator n=1)

| Field | Record |
|---|---|
| Date and time (America/New_York) | Sunday, Oct 25, 2026, about 5:13–5:15 PM EDT (from the run timestamps; the user wrote "the evening of 10/25") |
| Device / browser | Chrome on a Windows PC |
| Request (as typed, in English) | Search 1: "I need to find someone who is also interested in Animation". Search 2: "I need to find someone who is also interested in photograph". Search 3, the one reported in the form: "I need to find someone who is also interested in photography" |
| Conditions set | Search 3: "I'm a Yale SOM graduate student" checked, How you want to take part = Either is fine, When = Next 4 weeks (from the trace; the user's form lists only "either is fine"). Searches 1–2: SOM checked, Online, Next 7 days |
| Data mode | Both sources "Saved from last refresh", collected Sat Oct 24, 9:50 PM EDT, as shown at the top of the results |
| run_id (number of searches) | 3 searches: `r_80b535e6cc97`, `r_b8cd2f215d47`, `r_117624a6bd8a` (taken from the ledger; the user left this field blank) |
| Measured time (mm:ss) | Not measured (left blank). The app's own run time for search 3 was 12.0 s; that is the AI run, not the task time |
| Selected items (up to 3) | None. All three searches returned "No verified match". The user chose no item, so "known before" and "willing to learn more" do not apply |
| Feedback (the user's words, translated from Chinese, not expanded) | "I think the features are simple and clear, but the page doesn't look great right now. I think it needs more Yale elements to make it look nicer." |
| Screenshots | `screenshots/q08a_user_results_r_117624a6bd8a.webp` (results) and `screenshots/q08a_user_run_details_r_117624a6bd8a.webp` (run details), taken by the user |
| Manual comparison | Not performed. The user's estimate (translated): "If I had to find these things myself, it might take half an hour to an hour." This is an estimate, not a measurement, and must not be reported as time saved |

**Outcome against the success criteria: Failed.** The task asked for 1–3 items within the window, or a clear judgement that nothing fits. For photography the app returned no match, although the stored data contains two Creative Arts Workshop photography programs (Open Darkroom Session, with sessions inside the window, and Photography Individual Coaching). "Nothing fits" was therefore not a correct result.

**Cause (Claude Code's reading of the traces):** in all three searches the matcher passed a time filter to `search_listings` (`when="this_week"` in searches 1–2, `when="coming"` in search 3). In that tool these values return only single-date events and leave out ongoing programs and communities, so the photography programs never reached the model, and the AI summary then said that the sources contain no photography listings. For animation there is simply no listing in the two sources. The defect sits where the form's time condition (Question 6) meets the search tool's time filter (Question 4); the automated tests and the developer's own runs had not caught it.

**Fixed on 2026-10-25 (G-12): `search_listings` now keeps ongoing programs and communities when a time window is set; the window is still checked against their sessions by the existing code. Two regression tests fail without the fix and pass with it (437 offline tests passed). Real check `r_21eea8b51494`: the same request and conditions as search 3 now return Open Darkroom Session as "Check first" (time condition met; prerequisite to confirm); 4 calls, $0.001388925 (normal ledger 124 → 128 rows; copy in `evidence/q08a/`).**

**What this session shows:** a real person used the delivered flow (creator n=1, not an independent trial); the function was judged simple and clear; the visual design was judged plain, with a request for more Yale branding; and a recall failure appeared in the main photography scenario.

Cost: 3 runs, 10 model calls, $0.00172422, in the normal ledger (`runs/usage.jsonl` 114 → 124 rows). Copies of the traces and ledger rows: `evidence/q08a/`.

### D.2 Post-fix retest (prepared 2026-10-26; to be filled by the user after the final fixes)

**Why:** §D.1 shows a real person used the app and that a defect was found and fixed. It does not yet show the core value: finding an opportunity the person did not know about and wants to follow up. This retest checks exactly that, on the final version. A bad result is recorded as it is.

**Operator and task:** the same as §D (creator n=1, not an independent trial). One real request of your own, on the version that will be submitted. Start a stopwatch when the Find page is open; stop it when you have written down your list (or decided nothing fits).

| Field | Record (leave blank until performed) |
|---|---|
| Date and time (America/New_York) | |
| Device / browser | |
| Request (as typed) | |
| Conditions set (SOM / participation mode / time) | |
| Data mode and collection time shown on the page | |
| run_id (in Run details) | |
| Measured time (mm:ss) | |
| Item(s) you picked (title + link), or "none fits" | |
| 1. Did you know about it before? (yes / no) | |
| 2. Do you now want to learn more? (yes / no / maybe, and why) | |
| 3. Your next step (e.g. open the page, email the organizer, register, nothing) | |
| Anything the app got wrong or left unclear (your words) | |
| Screenshot path | |

Status: **Not verified** (not yet performed).
