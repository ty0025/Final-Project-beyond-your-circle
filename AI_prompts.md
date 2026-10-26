# AI_prompts.md — log of AI prompts used during development

> Format: Initial Prompt / Follow-up Prompt / What Was Lacking.
> Only what actually happened is recorded: if there was no follow-up, it says "None"; no defects or iterations are invented.
> Development tool: Claude Code (desktop app, model Claude Opus 5.5). These are development-tool calls; they are **not** the app's runtime course-model calls (the app only uses gpt-6-luna, see PROJECT_SPEC.md M-01) and are not counted in the app's tokenomics.
> Language: the prompts were written in Chinese. This log gives faithful English translations; quoted prompts are translations, not the original wording.
> Privacy: the local WeChat file path in the prompts is replaced by `<local Word path>`; everything else is translated in full.

---

## Background (before Question 1, 2026-10-25)

### Initial Prompt

The user sent the project background (grading rubric and evidence rules, project goals and original requirements, the real user problem, the product direction already decided, scope and factual boundaries, the existing engineering background, model/key/evidence rules, the final submission format, and the one-question-at-a-time workflow), and asked:

> Reply requirements for now: read only this background; do not inspect directories, go online, run commands or models, create or modify files, or start analysing an implementation plan. Reply only: "Background read; waiting for the first question."

(The key points of the background are captured in PROJECT_SPEC.md sections `U-`, `M-` and `I-`; the original requirements file is `<local Word path>/MGT409_FinalProject_<"requirements summary" in Chinese>(1).docx`, a Chinese summary of the course requirements.)

### Follow-up Prompt

None.

### What Was Lacking

None (this round only asked to confirm reading; Claude Code replied with the requested sentence and took no action).

---

## Question 1: Review the existing project and fix the grading and acceptance baseline (2026-10-25)

### Initial Prompt

```text
Please complete Question 1 of the MGT409 Final Project: review the existing project and fix the grading and acceptance baseline.

Project directory: C:/Users/david/Desktop/Courses/my-app/final project.
The original Final Project requirements take precedence; reuse the existing project wherever possible. The core is discovery of public campus events and communities for SOM students; no private channels and no calendar scheduling.
At the start, check the applicable AGENTS.md, existing changes, and any existing PROJECT_SPEC.md, PROGRESS.md and evidence for this question, and restore the confirmed scope and status. If files are missing, first restore the necessary information from the background and original requirements already received; do not guess the user's preferences.
Gaps from earlier questions must carry over into this question's status, and independent work may continue. When key dependencies such as real data, the safety/usage foundation or real model calls are not in place, the related acceptance items stay failed or unverified; handing them to a later question does not make them pass. Problems within this question's scope should be fixed autonomously and re-verified, not abandoned after the first failure. When something truly needs an external condition or human input, record the blocker clearly and continue with independent work.
At app runtime, course model calls use only gpt-6-luna via Portkey; protect the key, raw data, existing results and real evidence.

Grading: global, especially "can run it" (5 points), "real app" (15 points) and evidence for the later report.
Prerequisite: the previous background message has been read. This question makes no model calls and builds no new pages; you may now inspect the actual project as follows.

Please complete these tasks:
1. First read the original Final Project Word file: <local Word path>/MGT409_FinalProject_<"requirements summary" in Chinese>(1).docx, and check the course's original text against its notes. Then read the existing README, DESIGN, domain models/tools/prompts, orchestration, server and web entry points, and check the Git status and how the app starts. List separately the existing code, what the documents claim, and what has actually been verified.
2. Check and keep the model lock, the two-level .env, key isolation, usage mapping, budget/loop limits and traces. If foundations are missing, fix them first or flag them: no real model requests until they are fixed, but work that does not depend on the model may continue. If the domain is still the Harbor Bikes placeholder, list the places to replace without rewriting the domain yet.
3. Turn the confirmed background and the original requirements checked here into a PROJECT_SPEC.md in the project, and create evidence/rubric_checklist.md listing the 100-point rubric and the final delivery requirements item by item. Distinguish course requirements from our implementation choices.
4. Create PROGRESS.md and a real-interaction log. The rubric checklist uses the columns "rubric item, implementation location, verification method, evidence path/version/run_id, status". Record in advance the information the user must supply, such as the author name, the real repo URL and real-person use; do not stop independent work because these are missing. The user's time figures are only recalled estimates; do not add them up as measurements or claim time savings.
5. If the existing environment works, run the existing offline tests once as a baseline; if dependencies are missing, record the reason and the minimal fix. Do not change a lot of unrelated code just to restore the old placeholder example.

Acceptance: clearly identify the reusable modules, the public-collection capabilities not yet implemented, interface changes and the current baseline; evidence/status files are truthful, with no key leaks.
Deliverables: PROJECT_SPEC.md, PROGRESS.md, evidence/rubric_checklist.md, evidence/q01.md, AI_prompts.md.

At the end of this question, update PROGRESS.md, AI_prompts.md and evidence/q01.md, and report: what was completed, files changed, actual verification and results, unfinished/unverified items, and handover information for the next step. Record only follow-ups that actually happened; do not invent costs or effects.
If resuming after an interruption, first check the existing results and evidence and only complete what is unfinished or invalidated by changes; real runs that still fit the current conditions may be reused instead of paying repeatedly to regenerate records.
After completing and handing over this question, wait for me to send the next question.
```

### Follow-up Prompt

None (as of delivery, the user had not followed up on Question 1).

### What Was Lacking

There was no user feedback at delivery, so no defects are recorded. Environment problems met during the work (no comment objects in the Word file, `.git` owned by another Windows account, `tzdata` missing on Windows) are engineering facts recorded in evidence/q01.md, not prompt defects.

---

## Question 2: Implement bounded collection from public sources and build a small real sample (2026-10-25)

### Initial Prompt

The user first sent a set of general development principles (save tokens, reuse existing results, finish the minimal working flow first, keep the necessary foundations from the start, verify according to the scope of each change, give every call a clear purpose, find the cause of a failure before making a minimal fix, let acceptance results decide whether to keep changing things, keep reports short), followed by Question 2:

```text
Please complete Question 2 of the MGT409 Final Project: implement bounded collection from public sources and build a small real sample.

Project directory: C:/Users/david/Desktop/Courses/my-app/final project.
The original Final Project requirements take precedence; reuse the existing project wherever possible. The core is discovery of public campus events and communities for SOM students; no private channels and no calendar scheduling.
(The general opening is the same as in Question 1 and is omitted here.)

Grading: real app 15, novelty/value 21, later agent and impact evidence.
Prerequisite: Question 1 has checked the foundation; candidate sources are listed below this message. They must be verified before they count as connected.

Please complete these tasks:
1. First verify that two public sources from different official sites or organizers can be read programmatically, supporting a minimal cross-source flow. A third or more sources come only after the core flow and evidence hold; 3–5 is only a suggestion. Do not mark sources that need a login, template shells or error pages as connected; do not retry a single hard source endlessly.
2. Implement bounded collection/refresh for the chosen sources: a limited allowlist, timeouts, size and page-count limits, and safe redirects; no private content and no extra paid search key. Prefer simple reads of public listings and detail pages, and record the actual coverage boundary.
3. Define a unified record for events, communities and ongoing programs that keeps the original URL, organizer, collection time, the original wording that supports each field, date/time zone/location, format, eligibility, cost, registration information and missing values.
4. Persist the last successful records and the source status, and save a small test sample with provenance. On network failure, an existing snapshot clearly marked with its date may be used; a failure does not mean "no events", and it must not erase the last success.
5. Any model extraction during collection also goes through the shared gateway, budget and ledger. Fields that can be extracted deterministically are extracted by code; if a value is uncertain, keep it unknown.
6. Do not turn a season or program into fictitious single events; do not turn a community home page into a fictitious event this week; do not write fictitious samples to pose as real public data.

Acceptance: real collected records from two different sources, field checks and failure/cache fallback support cross-source acceptance; simulated faults are clearly labelled. … (the rest of the acceptance, delivery and closing text is omitted)
Candidate entry points to investigate (verify first; listing them does not mean they are connected):
- https://events.yale.edu/
- https://poorvucenter.yale.edu/
- https://geospatial.yale.edu/events/2026-11-20-build-a-bot-workshop
- https://recreation.yale.edu/gradproims
- https://creativeartsworkshop.org/courses/no-term/open-darkroom-session/
- https://nhccphotoblog.blogspot.com/
- https://yaleconnect.yale.edu/ycyalephotographysociety/home/
```

(The parts marked "omitted" are the general paragraphs and closing text that were identical to Question 1. The user's message was complete; they are left out here only to save space.)

### Follow-up Prompt

None (as of delivery, the user had not followed up on Question 2). When the Question 2 message arrived, the Question 1 background audit was still running; Claude Code first used the finished audit results to complete the Question 1 files and then started Question 2. This was not a user follow-up.

### What Was Lacking

There was no user feedback at delivery, so no defects are recorded. Extraction errors that Claude Code found and fixed itself (missing locations, misread costs, a "flexible" session given a date, a false format-conflict warning) are recorded in evidence/q02.md §6.

---

## Question 3: Complete a browsable basic discovery flow (2026-10-25)

### Initial Prompt

```text
Please complete Question 3 of the MGT409 Final Project: complete a browsable basic discovery flow.

Project directory: C:/Users/david/Desktop/Courses/my-app/final project.
(The general opening is the same as in Questions 1 and 2 and is omitted here.)

Grading: real app 15, ease of use 10, can run it 5.
Prerequisite: the Question 2 data contract is fixed. At least one real source record is needed to accept real-data browsing. With zero real records, only the empty state and isolated mock interfaces/pages are done and the data gap is kept; if the second source is not ready, do not claim cross-source completion. This question does not depend on new model calls.

Please complete these tasks:
1. Connect to the existing FastAPI/static web pages: implement the event and community data API, the source status and a refresh entry point. Use the existing server; add no new build or database service.
2. Provide basic interest / participation mode / time range filters, grouped into this week, later opportunities, and long-term communities/ongoing programs. Show the corresponding America/New_York start and end dates.
3. Handle deterministically: duplicates, past items, missing dates, actual location, registration deadlines, and entries with known unmet conditions. Show unknown eligibility separately from confirmed eligibility.
4. Cards open the correct original detail page; a registration link does not guarantee a spot. Do not register on the user's behalf.
5. Cover no results, unknown date, community only, collection failure and cache/snapshot states. When a refresh fails, keep the last results and show the time.
6. A fixed reference time is used only in clearly labelled tests; the real page uses the actual time. America/New_York uses the real time-zone rules; check dates around week boundaries and daylight-saving changes; do not hard-code a fixed UTC offset. Choose a few checks that can reveal problems.

Acceptance: real source records can be browsed on the web page without calling a model, the three sections are classified correctly, sources can be opened, and refresh/failure states are honest. Deterministic browsing at this stage does not pose as a finished AI recommendation.
Deliverables: data API and basic web page, targeted verification, screenshots of the actual page, evidence/q03.md.
(The closing text is omitted; it is the same as in the previous two questions.)
```

### Follow-up Prompt

None (as of delivery, the user had not followed up on Question 3).

### What Was Lacking

There was no user feedback at delivery, so no defects are recorded. Problems Claude Code found and fixed during browser verification (the refresh result message was cleared, robots.txt was misreported as disallowing access during an outage, online events were repeatedly flagged as missing a location) are recorded in evidence/q03.md §3.

---

## Question 4: Connect a purpose-aware agent and domain tools (2026-10-25)

### Initial Prompt

```text
Please complete Question 4 of the MGT409 Final Project: connect a purpose-aware agent and domain tools.

Project directory: C:/Users/david/Desktop/Courses/my-app/final project.
(The general opening is the same as in Questions 1–3 and is omitted here.)

Grading: agent design 10, real app 15, later tokenomics.
Prerequisite: the Question 3 flow works; keep the shared safety/metering foundation.

Please complete these tasks:
1. Extend the original domain models and tools: turn a natural-language request into explainable conditions such as interest, purpose of interaction, participating vs. watching, experience, identity, and date/location; do not invent anything that was not said.
2. Search and read details and sources by real record ID, and have the model use the tools rather than making up campus events from memory.
3. When reusing coordinator/researcher/verifier, state each one's actual duties, least tool permissions and hand-offs. Choose the organisation for effectiveness and fewer calls; do not force meaningless delegation just to show "multi-agent".
4. Update the old placeholder business prompts, examples, APP_META, output contract and link allowlist. Keep the old generic interfaces compatible or update their callers at the same time; do not just change prompt wording.
5. First verify the tools and the output contract with offline mocks/stubs, without running other local or remote models. Only when real data, a compliant key and the safety and usage foundations are ready, complete one bounded real end-to-end model call; record the actual roles, tool results, usage, stop reason and run_id. Mock interfaces only prove interface behaviour and cannot stand in for real-model evidence; if prerequisites are missing, keep the real call unverified.
6. All calls go only through the existing backend model gateway; if the key or permissions are missing, keep the offline results, state clearly that the real call is unverified, and do not bypass the model restrictions.

Acceptance: one natural-language purpose produces, through real tools, a structured result based on existing records, with traceable sources and all model calls. Screenshots match the trace; roles that were not called are not described as having worked.
Deliverables: domain tool/model/prompt/orchestration updates, a draft architecture, a real run trace and screenshot, evidence/q04.md.
(The closing text is omitted; it is the same as in the previous questions.)
```

### Follow-up Prompt

None (as of delivery, the user had not followed up on Question 4).

### What Was Lacking

There was no user feedback at delivery, so no defects are recorded. Problems Claude Code found and fixed in testing (a duplicate keyword in the verification event, a test helper that bypassed the environment-variable masking, a redaction test that did not actually test redaction) are recorded in evidence/q04.md §1 and §3.

---

## Question 5: Grounded matching, participation conditions and exploratory recommendations (2026-10-25)

### Initial Prompt

```text
Please complete Question 5 of the MGT409 Final Project: implement grounded matching, participation conditions and exploratory recommendations.

Project directory: C:/Users/david/Desktop/Courses/my-app/final project.
(The general opening is the same as in Questions 1–4 and is omitted here.)

Grading: idea 21, motivation/difference 8, real app 15, agent design 10.
Prerequisite: Question 4's tool calls and output contract hold.

Please complete these tasks:
1. Separate topic relevance, the specific purpose of taking part, hard participation conditions and unknowns. Content with a known unmet condition is not a "match you can join"; unknown conditions can only give a conditional recommendation or "to confirm".
2. Key fields such as date, location, organizer, cost and eligibility are restored from the record by the server, which also verifies the referenced IDs; new facts freely generated by the model are not accepted. Store the recommendation reasons separately from the source facts.
3. Each recommendation explains why it fits the purpose, what format offers interaction, and where to look or what to check next; without public evidence, do not promise access to speakers or meeting certain kinds of people.
4. Focus on matches; add a small amount of exploratory content only when there is a grounded connection. Exploration does not relax hard constraints such as identity, time and location; zero is fine when nothing fits.
5. Handle photography discussion/exhibitions and darkroom prerequisites, playing vs. watching sports and closed registration, AI introductions/research talks, unknown eligibility, community-only results and empty results. Use a few manually verified public records as functional cases, labelled with a fixed test time.
6. Make a small, reproducible comparison with keyword/tag-style results that shows what the purpose/condition handling changes. Also create evidence/alternatives.md, checking the actual capabilities, sources and check times of Yale-Localist, YaleConnect and ordinary ChatGPT. Compare fairly according to each tool's actual browsing/search ability and write "not tested" for untested items; the internal keyword comparison cannot prove superiority over external products, nor imply social benefit.

Acceptance: results are traceable item by item, the reasons for exclusion or downgrade to "to confirm" are correct, exploratory links are grounded, and the verifier can reject unsourced fields.
Deliverables: recommendation and verification logic, case comparison, field-support evidence, evidence/q05.md.
(The closing text is omitted; it is the same as in the previous questions.)
```

### Follow-up Prompt

None (as of delivery, the user had not followed up on Question 5).

### What Was Lacking

There was no user feedback at delivery, so no defects are recorded. Problems Claude Code found and fixed itself (several records on one page wrongly deduplicated, parsing of registration date ranges and years, "ai" dropped by a length filter, interaction signals matching the organizer's name, a backspace byte mixed into a patch) are recorded in evidence/q05.md §4.

---

## New-conversation handoff (after Question 5, before Question 6, 2026-10-25)

### Initial Prompt

The previous conversation's context was full. In a new conversation the user pasted a handoff message (full text in section 2 of `my-app/<"new-conversation handoff" in Chinese>_MGT409.md`, the handoff note): read, read-only and in full, the planning and status files, the evidence for each question, the core code and the opening of the remaining files, then reply with a "reading confirmation" (reading list, 6 check questions, problems found, things needed from the user before Question 6); no file changes, no tests, no server starts and no model calls.

### Follow-up Prompt

The user's reply about "things to provide or decide before Question 6" (translated):

> Um, the first one: I'll update that config later, and I already have the Portkey key. Second, we'll finish the GitHub repo URL at the end. The third one isn't important. Uh, writing the report and slides doesn't need to start yet; sign them "Tongyu David Chen". For the live screenshots and recording my exact words, ask me later. Six, uh, the sixth one is fine; no need to collect.

Based on this, P-01, P-03, P-04, P-05 and P-07 in PROGRESS.md §4 and PROJECT_SPEC.md §7 were updated.

### What Was Lacking

None. No files were changed during the read-only phase; inconsistencies found between files were recorded in PROGRESS.md §7 for the relevant questions.

---

## Question 6: Complete the final user flow (2026-10-25/26)

### Initial Prompt

The user first chose how to orchestrate (translated): "For Question 6, use workflow orchestration as usual under ultracode; don't worry about tokens." Then the user pasted Question 6:

```text
Please complete Question 6 of the MGT409 Final Project: complete the final user flow.
(The general opening is the same as in Questions 1–5 and is omitted here.)
Grading: ease of use 10, real app 15, and screenshots for the report.
Prerequisite: Question 5's recommendations are reliable. Keep the visual scope under control; the standard is clear and easy to use.
Please complete these tasks:
1. Users state their needs in short natural language and, when needed, change conditions such as SOM identity and participation mode; input examples come from real interests; avoid long questionnaires or forced sign-up.
2. Integrate the display of this-week / upcoming / community results, labels for main matches vs. exploratory picks, the basis for each match, known conditions and items to confirm, source and update time, and detail/registration links.
3. Keep the source, cache, past/deadline, empty-result, loading, cancel, timeout, model-failure and budget-limit states clear; users can retry the necessary step without losing data that already succeeded.
4. The main page serves activity discovery; tool traces and costs stay in an expandable run-details/evidence view so that technical information does not get in the way.
5. Keep the blue style; verify narrow screens, text readability, keyboard operation and link safety. No complex animation, maps, accounts or social features.
6. Run one complete path on the actual web page from input to opening the source, and take screenshots of the real run. Label separately what automated checks, snapshot data and the real model each cover.
Acceptance: a stranger can understand the recommendations and next steps; frontend and backend are really connected; the main success and failure states work; there is no dead end where only chat text exists and the activity cannot be opened.
Deliverables: complete web page, necessary targeted checks, end-to-end screenshots, evidence/q06.md.
(The closing text is omitted; it is the same as in the previous questions.)
```

### Follow-up Prompt

Messages the user sent while this question was in progress (in order; translations of the original wording or its key points):
1. The full text of Question 7 (safety and budget boundaries) arrived while the Question 6 audit was running; Claude Code replied that it would handle the questions in order and finish Question 6 first.
2. The full text of Question 8 (real metering, usage record, fresh clone) arrived; it was also queued.
3. A message containing only "Q"; Claude Code treated it as possibly sent by mistake and continued Question 6.
4. Stop and rules (translated):

> Pause the current changes and continue under the rules below; do not work on several questions at once:
> 1. Order: finish Question 6 → then Question 7 → then Question 8. After each question, immediately write evidence/q0N.md, update the affected rows of PROGRESS.md, AI_prompts.md and rubric_checklist.md, report in 5 lines, and only then start the next question.
> 2. Freeze accepted logic: do not change code from Questions 1–5 such as app/domain/conditions.py, verify.py and discover.py unless a test fails or this question's acceptance clearly requires it; if you change it, explain why in the report.
> 3. Make only the minimal changes needed for acceptance: no refactoring, no extra features, no polishing of interface details.
> 4. Before real model calls, list a plan (how many, purpose, expected cost), then run them; one run should provide functional, trace and cost evidence at the same time; use ?run=<run_id> replay for extra screenshots instead of paying again.
> 5. Limit each question to about 60–90 minutes. When stuck, record the blocker and what has been verified, then move on to the next question; do not retry repeatedly.
> 6. The deadline is 10/26 18:00, and the README, fresh clone, report.html and slides.html still follow, so Questions 6–8 only need minimal effective acceptance.
> Now first tell me in 3 lines where Questions 6/7/8 each stand and why you were changing conditions.py, then start by wrapping up Question 6.

### What Was Lacking

Reflected by follow-up 4 (only what actually happened): while Question 6 was unfinished, Claude Code had already started a read-only audit for Question 7, which conflicted with "do not work on several questions at once"; it changed Question 5's accepted decision logic following review suggestions (later reverted and recorded as G-11); and it had not listed a separate plan for real calls before that point. Afterwards it followed the rules: it listed a plan for 1 real run before running it, and did not use the Question 7 audit results before handing over Question 6.

---

## Question 7: Verify and harden the project's safety and budget boundaries (2026-10-26)

### Initial Prompt

The full text of Question 7 arrived during Question 6 (the user pasted only the question, with no other text). Following the user's later rules, it was started after Question 6 was handed over:

```text
Please complete Question 7 of the MGT409 Final Project: verify and harden the project's safety and budget boundaries.
(The general opening is the same as in Questions 1–6 and is omitted here.)
Grading: Safety 8, real app 15; supports usability and cost control.
Prerequisite: the first six questions have kept the basic protections; this question does not treat "a prompt was written" as an effective defence.
Please complete these tasks:
1. For the new collection tools, test the source allowlist, redirects, timeouts, size limits, and refusal of file/local/intranet access. Verify with controlled tests or mocks; avoid actually reading private files or accessing the intranet.
2. Use a malicious announcement as an isolated test sample, containing ignore-instructions, output of the canary/key, and lures to non-allowed URLs; compare it with a normal announcement and check tool permissions, outputs and the protection of sensitive information.
3. Check how the browser shows untrusted text and links, avoiding scripts, dangerous protocols and exfiltration parameters. Do not insert unprocessed HTML directly to show the original text.
4. Verify that unsourced fields / wrong eligibility, model failure, repeated delegation/retries, and token/USD/duration caps terminate and are shown honestly, and that all calls that happened are still counted in usage.
5. Keep at least one record/screenshot or test where the app's own defence actually blocked something. If the provider's content filter blocked it, label that separately; it cannot pose as an app-level defence.
6. Also keep a control where normal input passes, so that "rejecting everything" is not written up as a safety success. Keep demo attack data separate from real public events, and test calls separate from normal cost samples, while keeping an overall ledger for both.
Acceptance: concrete input, triggering layer, expected result, actual result, trace/screenshot and limitations; no real key or private content enters the evidence; calls after a refusal do not keep running out of control.
Deliverables: necessary fixes, a few meaningful safety/budget tests, an evidence export, evidence/q07.md.
(The closing text is omitted; it is the same as in the previous questions.)
```

### Follow-up Prompt

No new follow-ups during this question; it followed the rules received during Question 6 (order, freezing accepted logic, minimal changes, planning real calls first, time limits).

### What Was Lacking

No user feedback. The read-only audit that Claude Code ran in advance during Question 6 proposed about 10 code changes and a full red-team framework, beyond "minimal effective acceptance"; this question adopted only the 4 changes directly tied to acceptance and recorded the rest as limitations (q07 §4).

---

## Question 8: Complete real metering, the usage record and fresh-clone verification (2026-10-26)

### Initial Prompt

The full text of Question 8 arrived during Question 6 (the question only). Following the user's rules, it was started after Question 7 was handed over:

```text
Please complete Question 8 of the MGT409 Final Project: complete real metering, the usage record and fresh-clone verification.
(The general opening is the same as in the previous questions and is omitted here.)
Grading: Tokenomics 8, Impact 5, can run it 5, Agent design 10.
Prerequisite: the web flow and safety are verified. Separate work that can be prepared automatically from the parts a real person must do. Save results in four small steps: A real-person task preparation / usage record; B usage and optimisation measurement; C rates and scaled cost; D fresh-clone verification. While A waits for the user, finish B–D first; do not force all four steps into one continuous run.
Please complete these tasks:
1. Define in advance a short task based on real interests and its success criteria … Prepare a concise record sheet.
2. If the user is willing to do it personally, record the real web task's time, results, whether they knew about each item before, whether they want to learn more, and their own words … record the order/familiarity effect.
3. Without the user actually doing it, do not generate real-person feedback, timings or "user has tested" …
4. Read all real-call ledgers, make a few bounded cost measurements of normal tasks and one cost-optimisation comparison … prefer existing real runs; add calls only if the evidence is insufficient.
5. Check rates and usage semantics against verifiable course/gateway sources, noting the source and date …
6. When usage and verifiable rates are complete, give the cost per run, per user per month, and for 100 and 10,000 users …
7. In an isolated directory, fresh-clone the real repository version to be delivered, put .env in the parent folder as the README says, then start and operate it. If a local commit is needed, include only this project, keep the existing history/changes, and do not push to a remote …
8. Report every item that lacks evidence …
Acceptance is recorded as A/B/C/D …
Deliverables: tokenomics data/notes, the usage record or its pending status, the clone check, key screenshots, evidence/q08.md.
(The closing text is omitted.)
```

(Ellipses mark longer items of the original question; the full text is in the user's message and was shortened here to save space.)

### Follow-up Prompt

After Question 8 was handed over (translated):
1. "Do Question 8-A now: please tell me step by step how to do it and what to record; I'll follow the table in real_use_log.md."
2. "Sure. Before that, I want you to change one thing first: my prompt.md is probably mostly in Chinese right now, but the assignment must be entirely in English so the instructor and TAs can read it. Please replace all of it with English that has the same meaning and reads naturally. Use as few tokens as possible, but make sure the task is done well." (Claude Code translated this file, AI_prompts.md, into English.)
3. "Translate the other Chinese documents in the repo that the instructor will see (PROGRESS.md, PROJECT_SPEC.md, evidence/*.md, etc.) into English as well, again using as few tokens as possible." (Claude Code translated 12 documents in parallel and checked each against its committed original.)
4. "Right, the GitHub link isn't submitted yet; I'll create one later and send it to you. Let's go back to the table."
5. "I can't open this site, give me one [that works]." (The preview server ran in Claude Code's own environment; Claude Code started the app with start.bat in the user's terminal on port 8000.)
6. The filled record form for 8-A plus two screenshots, and: "Translate all of it into English for me and expand the wording a little." (Claude Code recorded the session in English, kept the user's feedback as a faithful translation without expanding it because it is evidence, and wrote the descriptive parts in fuller sentences.)
7. "Fix G-12 now: a search with a time window must not miss ongoing programs. Minimal change, add tests, and list a plan before the real verification." (Claude Code changed `search_listings` in `app/domain/tools.py`, added 2 regression tests, listed a 1-run plan, then ran it: `r_21eea8b51494`.)
8. "Then I'd like you to make the page look better: add things like the Yale logo and a cartoon of the Yale mascot, the bulldog. You can search online for images. Change the main colour to SOM blue." (Claude Code checked Yale's brand guidelines: Yale Blue #00356b and High Intensity Blue #286dc0; use of Yale's name and marks needs approval from Yale's Marketing and Trademark Licensing office. So it used the Yale Blue palette and drew an original cartoon bulldog in HTML/SVG instead of downloading the official logo or mascot images, and added a note that the app is an independent student project.)
9. "Make one local commit of the G-12 fix, the English documents and the 8-A record; don't push." (commit `0621a52`)
10. "The new look is fine. Make one local commit; don't push." (commit `8568893`)
11. "Send me the new look and I'll tell you what to improve. A small question: does the look affect the grade?" and "Why doesn't the page run across in one row on a wide screen? It doesn't look good enough." (Claude Code added a wide-screen two-column layout, screenshots `g13_two_column_*`; not committed.)

### What Was Lacking

No user feedback on the deliverables. The first fresh-clone attempt failed (`requirements.txt` was missing `httpx`), a gap left by the earlier questions only starting the app in the development venv; this question fixed it and verified with a new clone. The user asked for this log to be in English for grading; it had been written in Chinese.

---

## Design overhaul (2026-10-26)

### Initial Prompt

Sent right after follow-up 11 of Question 8 (translated):

> Improve the whole thing from a design point of view. Imagine you are a master web designer; don't settle for just the basic functions.

Claude Code backed up the 4 web files to `my-app/handoff_tools/web_before_design/` and ran a workflow of 9 agents: 3 designers each proposed a full direction (Yale classic collegiate, modern product clarity, warm student community), 2 reviewers scored them (a stranger's understanding and the rubric; visual quality, brand consistency and accessibility), a final spec was written, 1 agent implemented it, then a visual check and one fix round. Hard limits: no change to functions, IDs or honesty labels; no external fonts or images (CSP); tests must pass; no official Yale marks.

### Follow-up Prompt

1. "Please try again." (The first run stopped when the session usage limit was reached. Claude Code checked that no half-changed files were left and restarted the workflow.)
2. The context window was nearly full, so the user asked for a short background and a prompt for a new conversation that would review the work against the assignment requirements (full handoff text: `my-app/<"new-conversation handoff" in Chinese>_MGT409.md`). The user pasted that conversation's read-only review back, then wrote: "Let the design workflow finish, and when it's done send me before/after comparison screenshots." (Claude Code sent them and deleted the workflow's intermediate screenshots.)

### What Was Lacking

- The first run ended at the usage limit without changing `web/` (the new conversation found the files identical to the backup).
- The design spec and the `web/styles.css` comments call the overhaul "G-14", a number PROGRESS.md already uses for the Usage-tab fix; it is recorded as G-15.
- The "after" screenshots (`design_after_*`) were taken before the same day's copy and ledger fixes, so they show the old tagline and Usage-tab figures that still included 95 placeholder rows (18 runs, 128 calls, $503.51 for 10,000 users). Codex's review below pointed at that screenshot. (Retaken later on 2026-10-26: first after the fixes but still with the "TEST MODE" banner of a server started with `LLM_SIMULATE=error`, then again without the banner; see the last section.)
- Keep or roll back: no decision recorded yet (PROGRESS.md P-08). The overhaul is not committed.

---

## File cleanup, rubric review and Codex review fixes (2026-10-26)

### Initial Prompt

Translated:

> Now I need you to do two things. First, delete the redundant and process documents that are no longer useful, keeping only the latest version of the content. Second, check what I have done so far strictly against the assignment's grading rubric. Don't look at the report or the presentation slides yet; I'll do those later. Only look at whether what you have already done can get a high score, and if not, which points need to change. Our remaining time and tokens are limited, so problems must be solved in order of priority within that time. I hope you understand and can help me accurately.

Claude Code removed the Harbor Bikes placeholder files (`evidence/tokenomics.*`, `evidence/redteam_results.json`, `scripts/redteam.py`, `scripts/tokenomics.py`), a duplicate screenshot and the failed clone folder `my-app/fresh-clone-q8`, and gave a rubric review with priorities.

### Follow-up Prompt

The user pasted a review written by Codex (another coding agent), with this line (translated): "I also asked Codex, and it gave the following suggestions. Please focus on fixing these first, and then we'll continue discussing optimisation." Summary of the review (not verbatim; Codex said it changed no files and ran no tests or course API calls):
1. README said Python 3.10+, but `app/orchestrator.py` uses `asyncio.timeout` (3.11+); the README opening still described the placeholder domain. Unify version and steps, then fresh-clone the final commit.
2. The Usage screenshot (18 runs, 128 calls, $503.51 for 10,000 users) mixed in 95 Harbor Bikes rows, while the report draft used a 5-run baseline. Separate a typical-run sample, the development and safety-testing total, and historical records; describe the cache saving as a re-pricing of the same real tokens, with no evidence that quality is unchanged.
3. Impact: the user's real session had 3 searches, none chosen, no timing and no retest after the fix. Suggested one post-fix real task recording whether the user knew the item before, wants to learn more, and the next step, reported honestly.
4. The copy and examples promised communities, photography peers and sports, but the data had 2 sources, 11 records, no community records and no sports source. Narrow the promise or add one fitting community source; test-only cases must not be described as product data.
5. Participation conditions (G-11): "open to Yale students" was met with an unknown identity, and unrecognised eligibility wording did not become "to confirm"; a page showed 1 Match + 2 Check first under a summary saying three matches; the verbatim quote check does not prove the reasons or the social purpose. Fix these, or, if the rules stay frozen, the report must keep the defect.
6. Use the real Q5 run `r_8aad4fe5a302` (darkroom prerequisite vs one-on-one coaching) as the concrete example of what is new; keep the honest comparison limits.
7. In the report, follow one real run step by step (request → understanding → tools → evidence → kept or excluded → what the user sees) with an architecture diagram and screenshots.
8. Make the key facts on result cards easy to scan, especially on mobile; examples should match the real coverage.

### What Was Lacking

- Claude Code's own rubric review, written just before, had missed the Python 3.10/3.11 mismatch, the placeholder rows inside the Usage-tab figures, and the summary-vs-cards count contradiction as a defect to fix. Like the earlier review in the new conversation, it had suggested keeping G-11 only as a documented limitation. After Codex's review the user asked for fixes, so G-11 was reopened.
- Fixed with 0 model calls: Python 3.11 minimum (G-16), cost categories and the Usage-tab filter (G-14), participation conditions (G-11), summary vs cards (G-17), narrowed promise and examples (G-05), plus the §D.2 retest form; details in PROGRESS.md §6. Points 6–7 (report) and the mobile reading-order part of point 8 were not part of these fixes. The retest (point 3) is Awaiting human input.
- A check after the fixes found that 1 of 474 tests fails on Python 3.11.17 (float rounding in the cost-evidence test, PROGRESS.md §2). Fixed later the same day (next section).

### App prompt change recorded: matcher (`app/domain/prompts/matcher.md`, 2026-10-26)

This is the app's runtime prompt for gpt-6-luna, not a development prompt. One line of the output section changed (from `git diff`).

Old:

```text
- summary: two or three sentences: what you found, how many close and exploratory picks, and any honest gap (for example "No sports listings are in the current sources").
```

New:

```text
- summary: two or three sentences: what you found and any honest gap (for example "No sports listings are in the current sources"). Do not state how many picks you made and do not call them "matches": the app checks every pick after you answer, labels it Match, Check first or Exploratory, and shows the counts itself.
```

Reason: the model writes its summary before the code checks, so its counts could disagree with the final cards (G-17). All saved Q4–Q8 traces (including the red-team runs, the fresh-clone run, the user's 8-A runs and the G-12 re-check) used the earlier prompt; no real run has used the new prompt yet.

---

## Codex review fixes, later rounds: independent review and fix round 3 (2026-10-26)

### Initial Prompt

No new prompt. These rounds continue the user's request in the previous section ("Please focus on fixing these first…"). Claude Code ran two more workflows after the first fixes (times UTC, from the session log):
- 02:42, "apply" workflow: rewrote README, DESIGN.md, `.env.example` and `evidence/architecture.md`; compacted the results header in `web/`; updated the evidence and progress records; an independent read-only code review of the new code (13 issues confirmed with throwaway probes, none high severity); a read-only consistency check (the Python 3.11 test failure, untracked files that the final commit must include, examples that depend on dated events, out-of-date statements in the docs, the "TEST MODE" banner on the screenshots).
- 03:18, "round 3" workflow: fix the review's issues with tests on both Pythons, retake the screenshots without the banner, sync the docs, then a final read-only check.

### Follow-up Prompt

1. Round 3 stopped at 03:30 UTC when the session usage limit was reached. At 05:41 UTC the user wrote (in English, as sent): "I hit my usage limit while you were working, but it has reset now. Please continue from where you left off." Claude Code checked what the code agent had already changed and restarted round 3.
2. After the fixes were reported, the user wrote (in English, as sent): "Make one local commit of all the Codex review fixes, including the new test files and screenshots. Do not push." Claude Code staged everything, re-ran the suite (572 passed) and the key scan (no hits), and made local commit `6d08bed` on `master`; nothing was pushed (the repo has no remote).
3. The user then wrote (translated from Chinese): "Answer me in Chinese about the process: how far along are we, and what still needs to be done? When you add things to the prompt log, remember to translate them all into English." Claude Code checked the tracked files for untranslated Chinese: the only Chinese left in the docs was two local file names (the Word requirements summary and the handoff note), now written as English descriptions; the Chinese in `app/safety.py` and the tests is deliberate test input and stays. It then gave a status summary in Chinese (not copied here).
4. The user wrote (translated from Chinese): "Codex is writing the report and slides; I'll tell you about them later. Let's do the real-use log retest first." Claude Code restarted the local server on the latest code (the one in the user's terminal was still running the old code) and gave step-by-step instructions in Chinese for the `real_use_log.md` D.2 retest, with a cost plan of 1-3 searches at about $0.001 each.
5. The user wrote (translated from Chinese): "The address you gave me doesn't open; give me one that does." The server's terminal tab had closed, so nothing was listening on port 8000; Claude Code started `start.bat` again (it opens the default browser) and gave http://localhost:8000 and http://127.0.0.1:8000.
6. The user sent the filled retest form (in Chinese) and two screenshots. Claude Code took the date, conditions, data mode, run_id, result and cost from the trace and ledger of `r_e29a8b37a60c`, translated the user's answers and feedback into English, and recorded them in `real_use_log.md` D.2 with the screenshots and trace copies. Reading the trace, it also found that the code had dropped "Save the Date: GIS Day 2026" although that page mentions "GeoAI workshops" (recorded as G-18, not fixed).
7. The user wrote (translated from Chinese): "Fix G-18: make interest-word matching recognise words like GeoAI and GenAI, add tests, and verify offline with the saved run records, without spending on model calls." Claude Code added one shared rule (`term_in`) for Browse, the search tool and the verifier, 22 tests, an offline replay of `r_e29a8b37a60c`, a check of all 53 saved traces and a false-positive check on the stored listings (PROGRESS.md section 6, "G-18 fix").
8. While that ran, the user asked (translated from Chinese): "I've just set up GitHub too. Should I just create a new repository, and what would be a good name?" Claude Code: a new empty public repository (no README, .gitignore or license, because the local history would conflict), suggested name `beyond-your-circle`. The user then sent a screenshot of the form ("Is this OK? I'll send you the link") and the link: "https://github.com/ty0025/Final-Project-beyond-your-circle - I changed the name; this is the link."
9. After the push and the clone check, the user wrote (translated from Chinese): "Run one real AI search in the GitHub clone with Python 3.11 to verify it, record the result, then commit and push the docs update." Claude Code ran example 1 once in the clone (`r_89ca8fd71c77`, $0.001123785), saved a replay screenshot and the run copies, and recorded the result in `evidence/q08.md` D.2, PROGRESS.md and the rubric checklist.
10. The user wrote (translated from Chinese) with the paths of Codex's `report.html` and `slides.html`: "These are the report and slides I had Codex write. Mainly help me update the parts that weren't written before, such as the GitHub link, then stress test them, and then we can wrap up." Claude Code filled in the repository link, the GitHub clone result, the G-18 fix and the updated cost total, then ran a read-only stress-test workflow (rendering, two fact-checks, rubric, first-time reader, triage).
11. The user asked (translated from Chinese) whether the link could be submitted on Canvas first, since only the content still needed work. Claude Code: yes, if Canvas allows resubmission; the final submission must contain all items, pushes must finish before the deadline, and the link in the report must match.
12. The user then pasted the instructor's notice (Canvas takes files only: the report and slides HTML, each with the GitHub repo URL so it can be cloned, "private" stated if private, optional video, nothing else) with their own summary in Chinese, and asked (translated): "This is what I'm submitting; please send me the files I need to submit in this format." Claude Code applied the stress-test fixes, put the full URL and "Public repository" in both files, re-checked them (13 Letter pages; 9 slides) and sent the two files.
13. The user wrote (translated from Chinese): "So are we basically done now? Before submitting, I'd like you to do a final check against the instructor's grading criteria I sent at the very beginning, see whether anything is still not done well, and then we'll submit." Claude Code ran a final read-only check (the official requirements page item by item, a grader-style anonymous clone of the latest commit without a key, and the two submission files). Verdict: no blocker. It then fixed the small items found: the report's stale "example 1" wording, an internal "Q8" label, "internal case C1", a slide footnote, two README notes (install time; 589 passed and 5 skipped on Windows without bash) and stale status lines in the docs.

### What Was Lacking

- The first fix round's own code still had gaps, found by the independent review rather than by its tests: participation rules issues 1–7 (a short quote from another check hid a restriction in the same sentence; "open to all Yale undergraduates" was met for an SOM identity; "open to all <group>" and "not open to the public" read as public; a quote could run into the next eligibility text; the catch-all flagged credits and speaker affiliation; Browse and Find disagreed on "open to all"), summary-check issues 8–12 ("match" as a verb, the size of the searched pool, counts behind commas or several describing words, abbreviations splitting sentences, a whitespace-only summary showing raw JSON), issue 13 (cost and red-team scripts: a half-written ledger line, a fixed "first 95 rows" note) and issue 14 (wording that still promised communities). All were fixed with 0 model calls; none changes an outcome on the 11 stored listings or on the saved real runs (q05 §9, q06 §10). Full suite after round 3: **555 passed** on Python 3.14.7 and on Python 3.11.17 (the 3.11 float-rounding failure was fixed with `math.fsum` in `scripts/tokenomics_q8.py`).
- The `design_after_*` screenshots retaken after the first fixes still showed the "TEST MODE: AI failures are simulated" banner, because the screenshot server was started with `LLM_SIMULATE=error`; round 3 retook them without it.
- A final checker in round 3 still found out-of-date statements in PROGRESS.md, `evidence/q08.md`, `evidence/rubric_checklist.md` and the README examples (dates); they were corrected in the docs sync.

- The round-3 final check (54 eligibility and 35 summary probe sentences) found one regression from round 3 ("open to anyone with a valid Yale ID" read as public) and three older gaps (group-only wording such as "Graduate students only.", age limits in words, a correct Check-first count removed from the summary). Claude Code applied the checker's scratch patch, added 17 regression test cases, and re-checked: 572 passed on Python 3.14.7 and 3.11.17; verdicts for all 11 stored listings byte-identical to the committed code (PROGRESS.md §6 "Final-check fixes").

### App wording change recorded: matcher role and `search_listings` (issue 14, 2026-10-26)

Model-facing text changed in round 3 (from `git diff`); both are read by gpt-6-luna at run time.

`app/domain/prompts/matcher.md`, role line. Old:

```text
... find public events, ongoing programs and communities at Yale and in New Haven that fit what they want ...
```

New:

```text
... find public events, classes and ongoing programs at Yale and in New Haven that fit what they want ...
```

`app/domain/tools.py`, `search_listings` description. Old:

```text
Search the stored public listings (Yale and New Haven events, programs and communities). ... when: 'this_week' (next 7 days), 'coming' (later single-date events), 'ongoing' (programs and communities) or 'all'; 'this_week' and 'coming' also return ongoing programs and communities, whose sessions the app checks against the window.
```

New:

```text
Search the stored public listings (Yale and New Haven events, classes and ongoing programs). ... when: 'this_week' (next 7 days), 'coming' (later single-date events), 'ongoing' (recurring programs and classes) or 'all'; 'this_week' and 'coming' also return ongoing programs and classes, whose sessions the app checks against the window.
```

`app/domain/tools.py`, section label that the tools return for ongoing listings: "ongoing program or community" → "ongoing program or class". The user-facing blocked reply in `app/orchestrator.py` changed the same way ("event or community" → "event or class").

Reason: the data holds events, classes and ongoing programs, no community listings (G-05). All saved traces (Q4–Q8, the red-team runs, the fresh-clone run, the user's 8-A runs and the G-12 re-check) used the earlier text; for example the `get_listing` result in `r_21eea8b51494` says "ongoing program or community". No real run has used the new text yet.
