# Beyond Your Circle

Describe in one plain-English sentence what you want to do outside Yale SOM, and the app finds public
Yale and New Haven events and classes that fit, each checked against its source page.

**Repository:** <https://github.com/ty0025/Final-Project-beyond-your-circle>

## What it is

You type one request, for example "I'm curious about drones. Is there a casual meetup where I can meet
hobbyists outside SOM?". A `gpt-6-luna` agent turns it into explicit conditions and searches the
stored public listings with two read-only tools. Code (no model call) then checks every pick against
the stored page: the listing must exist, still be available and have been read by the agent, and its
quotes are checked word for word. Each card is labelled **Match**, **Check first** (a condition such
as "open to Yale students" cannot be confirmed from what you said), **Exploratory** (a related idea,
shown only with a verified quote) or **Not a fit** (the page rules it out for what you said, for
example online only when you want in person), with the reasons, the source link, the dates and who
can join, as the page states them.

Coverage is small and honest. The app holds **2 public sources and 11 listings**: Creative Arts
Workshop photography classes (Photography Individual Coaching, Open Darkroom Session) and 9 events of
the Yale Center for Geospatial Solutions (AI, mapping and drone events). It has **no sports, clubs or
standing communities yet**. The Yale Recreation graduate and professional intramurals page was checked
but is not connected; `python scripts/collect.py sources` lists every source that was checked and why it
is or is not connected.

## Quick start

You need **Python 3.11 or newer**, an internet connection for the first install, and a Portkey API
key. Check with `python3 --version` (Mac / Linux) or `py -3 --version` (Windows). The `python3` that
comes with macOS is 3.9, which is too old: install a current Python from
<https://www.python.org/downloads/> first. The start scripts check the version and stop with a clear
message if no suitable Python is found.

1. **Key.** Create a file named `.env` that contains one line (the name must be exactly `PORTKEY_API_KEY`):

   ```
   PORTKEY_API_KEY=your_portkey_api_key_here
   ```

   Put it in the repo folder (next to `run.py`) **or** in the folder one level above the repo. The
   app looks in the repo folder first, then one level up; if both have a key, the repo file wins (a
   `PORTKEY_API_KEY` already set in the environment wins over both).
   Nothing else is required: every other setting has a default (see
   [Limits and settings](#limits-and-settings)). `.env.example` is a template you can copy.
2. **Start.**
   - **Mac / Linux:** `./start.sh` (if you get "permission denied", run `chmod +x start.sh` once, or use `bash start.sh`)
   - **Windows:** double-click `start.bat`, or run it in a terminal opened in the repo folder:
     `start.bat` in cmd, `.\start.bat` in PowerShell
3. **Open** <http://127.0.0.1:8000>. The browser opens by itself once the server is ready.

The first start creates a `.venv` folder and installs `requirements.txt`; later starts skip the
creation step. Installing prints little for about a minute. In the final check, an anonymous clone from GitHub
was usable in about 1 minute (Python 3.11.17 and 3.14, pip cache present; `evidence/q08.md` D.2). The terminal should show `Model: gpt-6-luna via Portkey`, which `.env`
files were found, and `PORTKEY_API_KEY configured: yes` (never the key itself). Press Ctrl+C to stop.

Both start scripts pass options on to `run.py`: `--port 8001`, `--host 0.0.0.0`, `--no-browser`
(for example `./start.sh --port 8001` or `.\start.bat --port 8001`).

### Manual steps

Mac / Linux:

```bash
python3 --version              # must be 3.11 or newer; otherwise use e.g. python3.13 on the next line
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Windows (cmd or PowerShell):

```bat
py -3 --version
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## What to try first

- **Find** tab: click one of the 4 example requests, then press **Find** (or Ctrl+Enter):
  1. "I shoot film and want hands-on help getting better, in person. I've never worked in a darkroom."
  2. "I'm not technical but want to see how people at Yale actually use AI tools. Online is fine."
  3. "I'm curious about drones. Is there a casual meetup where I can meet hobbyists outside SOM?"
  4. "Any in-person maps or GIS event where I could meet people from other fields?"

  The examples match the committed snapshot of 25 October 2026: for instance the drone example relies
  on the YCGS Drone Hobbyist Gathering II (9 November 2026) and the maps example on GIS Day 2026
  (16 November 2026). Past events drop off automatically, so if you run the app after those dates,
  first press **Refresh sources** on the **Browse all** tab (needs internet, no model call); the
  examples may then find different listings. A live refresh on 26 October 2026 already returned 8
  YCGS events instead of 9: the site no longer lists GIS Day 2026, so after a refresh the maps
  example uses the remaining map events.

  Optional form fields (SOM graduate student, in person / online, next 7 days / next 4 weeks) are
  applied by code. Open **Run details** under the results to see every model call, tool call and
  safety event, and the cost of the run.
- **Browse all** tab: every stored listing, grouped and filterable, with **no AI and no model call**.
  It works even without a key.
- **Usage** tab: average tokens and cost per run, cache hit rate, projections and recent runs from this
  machine's ledger (`runs/usage.jsonl`, empty on a fresh clone). Select a run to replay its saved trace
  (no new model call). The project's committed cost figures are in `evidence/q08_tokenomics.md`.

## Data freshness

Listings come from a **committed snapshot** in `data/snapshots/` (`caw-photo.json`,
`ycgs-events.json`), collected on **25 October 2026 at 01:32–01:33 UTC** (the evening of 24 October
in New Haven). The app always shows it as a snapshot with that date, never as live data. The 9 YCGS
events in it are dated 27 October to 15 December 2026. Dated events drop off automatically once they
have passed, so later the app has fewer listings.

To fetch current listings, press **Refresh sources** on the Browse all tab (or run
`python scripts/collect.py refresh`). This needs internet, makes **no model call** and fetches a
bounded number of pages with polite delays; the button can be pressed again after 300 seconds. A successful
refresh is stored in `runs/collect/` (gitignored) and used from then on; a failed or empty refresh never
replaces the last good data.

This committed snapshot is the project's small test data set; there is no large dataset.

## How it works

```
request -> screen (code) -> guard (gpt-6-luna, 1 call) -> matcher agent (gpt-6-luna) -> verifier (code) -> cards
                                                            | search_listings / get_listing (read-only)
                                                            v
                                              stored listings (runs/collect/ or data/snapshots/)
```

1. **screen** (code): length limit and prompt-injection rules on your request.
2. **guard** (1 model call): `gpt-6-luna` classifies the request as an attack or not.
3. **matcher** (model agent, at most 4 model calls): reads your request, calls `search_listings` and
   `get_listing` over the stored records, and returns structured picks with exact quotes. It cannot
   fetch the web, write files or register for anything.
4. **verifier** (code, `app/domain/verify.py` + `app/domain/conditions.py`): drops picks the agent did
   not read, that do not exist or have passed; checks quotes word for word; removes prices, times,
   dates or links in the AI's wording that the page does not contain; restores every fact from the
   stored record; judges
   participation conditions only against what you said (for example "open to Yale students" is met
   only if you said you are one, otherwise Check first); and removes AI summary sentences whose counts
   disagree with the final cards.

The model is locked to `gpt-6-luna` through Portkey (`https://api.portkey.ai/v1`) in `app/config.py`;
no setting can change it. Every call bypasses Portkey's response cache, so each logged call is a real
one; the provider's prompt cache still makes the repeated instructions cheaper. Every model attempt is
written to `runs/usage.jsonl` with its tokens and USD cost. In the 9 recorded typical runs a search
made 3 to 4 model calls and cost $0.000860 on average (`evidence/q08_tokenomics.md`).

Safety: untrusted page text is wrapped as data and scanned for injected instructions; each agent has a
tool allowlist; outputs are screened for a canary marker, secrets and suspicious links; the key is
never printed, logged, returned by the API or written to traces.

### Limits and settings

All optional. Put them in `.env` or set them as environment variables; an invalid value keeps the default.

| Variable | Default | Meaning |
|---|---|---|
| `RUN_BUDGET_USD` | `0.05` | Max spend for one run |
| `RUN_TOKEN_CAP` | `250000` | Max input + output tokens for one run |
| `DAILY_BUDGET_USD` | `2.00` | Max spend per UTC day, all runs (read from the ledger); `0` switches AI off, Browse still works |
| `MAX_MODEL_CALLS_PER_RUN` | `12` | Every model attempt counts: guard, agent turns, retries |
| `LLM_MAX_RETRIES` | `1` | Retries of a failed model call (each attempt is ledgered) |
| `RUN_TIMEOUT_S` | `180` | Wall-clock limit for one whole run |
| `LLM_TIMEOUT_S` | `90` | Timeout per model call |
| `MAX_TOOL_CALLS_PER_RUN` | `30` | Max tool calls in one run |
| `MAX_OUTPUT_TOKENS` | `4000` | Max output tokens per model call |
| `MAX_INPUT_CHARS` | `8000` | Max length of a request |
| `RATE_LIMIT_RUNS` / `RATE_LIMIT_WINDOW_S` | `15` / `600` | Max runs per client IP per window |
| `SAFETY_LLM_GUARD` | `1` | Set to `0` to skip the guard call |
| `RUNS_PER_USER_PER_MONTH` | `30` | Assumption for the Usage tab's projections |
| `RUNS_DIR` | `runs` | Where the ledger, traces and refreshed listings go |
| `REFRESH_COOLDOWN_S` | `300` | Wait between two Refresh sources |
| `PORT` | `8000` | Port when `--port` is not given |
| `LLM_SIMULATE` | unset | Demo: `timeout` or `error` makes every model call fail, with no network call and no cost (`LLM_SIMULATE_DELAY_S`, default `8`) |
| `COLLECT_SIMULATE_OUTAGE` | unset | Demo: `1` makes Refresh sources fail as if the sites were down |

## Scripts

Run from the repo folder with the venv active (`source .venv/bin/activate` or `.venv\Scripts\activate`).

| Command | What it does | Model calls |
|---|---|---|
| `python scripts/collect.py sources\|status\|show\|refresh\|snapshot\|reparse [--source ID]` | Collector CLI: list sources, show stored records, live refresh (needs internet), copy the last success to `data/snapshots/`, re-parse saved pages | none |
| `python scripts/compare_cases.py` | Keyword list vs this app's condition-aware handling on fixed cases; writes `evidence/q05_cases.{md,json}` | none |
| `python scripts/tokenomics_q8.py` | Cost summary from the committed ledger copies in `evidence/`; writes `evidence/q08_tokenomics.{md,json}`. No options. On a fresh clone (no local `runs/`) it rewrites row (iii) and the local ledger check as "not present"; figures (i) and (ii) stay the same. Run `git checkout -- evidence` afterwards to restore the committed files | none |
| `python scripts/redteam_q7.py --dry-run` | Lists the 3 red-team cases; no key needed | none |
| `python scripts/redteam_q7.py` | Runs the 3 cases for real (the script estimates about $0.004); separate ledger `runs/redteam_q7/usage.jsonl`; writes `evidence/q07_redteam.json` | live |
| `python scripts/smoke_test.py` | One short live call to check the key and gateway; not written to the usage ledger | live |
| `python scripts/inline_images.py report.html [out.html]` | Embeds local images so `report.html` / `slides.html` are self-contained (those two are the Canvas deliverables; they are not in this repo) | none |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The suite runs fully offline: a fake model stands in for `gpt-6-luna`, so it never needs or reads
your real key. Last run (26 October 2026): **594 passed** on Python 3.14 and on Python 3.11. On Windows without
`bash`, the 5 `start.sh` tests are skipped (589 passed, 5 skipped).

## Evidence map

| What | Where |
|---|---|
| Work log per course question | `evidence/q01.md` to `evidence/q08.md` |
| Architecture and design choices | `evidence/architecture.md`, `DESIGN.md` |
| Real model runs (trace + ledger rows) | `evidence/q04_run/`, `q05_runs/`, `q06_run/`, `q07_redteam/`, `q08a/`, `q08_clone/` |
| Keyword vs condition-aware comparison | `evidence/q05_cases.md`, `evidence/alternatives.md` |
| Red team (3 live cases) | `evidence/q07.md`, `evidence/q07_redteam.json` |
| Cost | `evidence/q08_tokenomics.md`: (i) typical-run sample, (ii) all project live spend, (iii) old placeholder rows, excluded |
| Fresh-clone check | `evidence/q08.md` |
| Real use by a person | `evidence/real_use_log.md` |
| Rubric status | `evidence/rubric_checklist.md` |
| Screenshots | `evidence/screenshots/` |

`runs/` is gitignored; `evidence/` is committed.

## Project layout

```
run.py, start.sh, start.bat   entry points
app/                          config, pricing, llm, ledger, budget, events, tools, safety, agent,
                              orchestrator, server, discover (Browse), collect/ (collector)
app/domain/                   listing tools, output models, verifier, conditions, prompts/matcher.md
data/snapshots/               committed snapshot of the 2 sources (the small test set)
web/                          index.html, styles.css, app.js, discover.js (no build step)
scripts/                      see Scripts
tests/                        offline pytest suite
runs/                         runtime output (gitignored)
evidence/                     evidence for the report
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `address already in use` / port 8000 busy | `./start.sh --port 8001` (Mac / Linux) or `.\start.bat --port 8001` (Windows), then open <http://127.0.0.1:8001> |
| `start.bat` "is not recognized" in PowerShell | PowerShell does not run scripts from the current folder by name. Type `.\start.bat`. |
| "PORTKEY_API_KEY is not set" / "still has the placeholder value" / the page says the key is missing | The file must be named exactly `.env`, not `.env.txt` (Windows hides extensions). It must sit in the repo folder or the folder one level up, and the line must start with `PORTKEY_API_KEY=`. A template value such as `your_portkey_api_key_here` is treated as not set: replace it with the real key. Restart the app after editing. Browse all works meanwhile. |
| 401 / "rejected the API key" | The key value is wrong or expired. Paste it again with no quotes or spaces. |
| Python version error | Check `python3 --version` (Mac) or `py -3 --version` (Windows). You need 3.11+. Install it from <https://www.python.org/downloads/>, open a new terminal, and start again. |
| `pip install` says `No matching distribution found for openai<4,>=3.26` | The `.venv` was made with Python 3.9. Delete the `.venv` folder and start again with Python 3.11+ (`start.sh` / `start.bat` do this for you). |
| `py` not found on Windows | Install Python from python.org and tick "Add python.exe to PATH". `start.bat` falls back to `python`. |
| PowerShell blocks `.venv\Scripts\activate` | Use `start.bat` or cmd, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |
| Fewer listings than expected, or none this week | Past events are hidden. Press **Refresh sources** on Browse all (needs internet). |
| Refresh sources fails or says to wait | No internet or a site is down: the app keeps showing the last stored data with its date. After a refresh, the next one is allowed after 300 s. |
| "Too many runs" (HTTP 429) on Find | The per-IP rate limit was hit. Wait, or raise `RATE_LIMIT_RUNS`. |
| Run stops with a budget or time-limit message | A run, daily or time cap was reached. See [Limits and settings](#limits-and-settings). |
| Need a clean slate | Delete `.venv/` (reinstall) or `runs/` (clears history, the local cost ledger and refreshed listings; the snapshot is used again). |
