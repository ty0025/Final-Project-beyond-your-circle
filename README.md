# MGT 409 Final Project: Multi-Agent Assistant

> **TODO: the project topic has not been chosen yet.**
> This repo currently runs a *placeholder* domain: a support assistant for "Harbor Bikes", a
> fictional bike shop in New Haven. It exists so that every part of the foundation (agents, tools,
> cost tracking, safety) can be shown working end to end. Once the topic is chosen, rewrite this
> section and follow [Swapping in the real topic](#swapping-in-the-real-topic).

## What it is

A small web app where a team of AI agents answers questions over a document collection, running on
`gpt-6-luna` through Portkey.

- **Multi-agent flow:** a `coordinator` plans and delegates to a `researcher` (search, read and
  calculate tools) and a `verifier` (checks every claim against the source documents).
- **Live timeline:** every model call, tool call, hand-off and safety event streams to the browser.
- **Tokenomics:** each model call is logged with input, cached-input, cache-write, output and
  reasoning tokens plus its USD cost. The app shows cost per run and cache hit rate, and projects
  costs for 100 and 10,000 users. Every call bypasses Portkey's response cache
  (`x-portkey-cache-force-refresh`), so logged usage is always from a real model call; the
  provider's prompt cache still makes the repeated system-prompt prefix cheap.
- **Safety:** layered prompt-injection defenses, tool allowlists, output screening, and spend and
  loop caps. Offline tests and a live red-team script show the defenses working.
- **Simple to run:** one Python process, no database, no Node build step. Only the model calls need
  the internet.

## Quick start

You need **Python 3.10 or newer** and a **Portkey API key**.

1. Put your key in a file named `.env` (see [API key](#api-key)).
2. Start the app:
   - **Mac / Linux:** `./start.sh` (if you get "permission denied", run `chmod +x start.sh` once)
   - **Windows:** double-click `start.bat`, or run it in a terminal opened in the repo folder:
     `start.bat` in cmd, `.\start.bat` in PowerShell
3. Your browser opens <http://127.0.0.1:8000>. Click an example question and press **Run**.

On the first run the start scripts create a `.venv` folder and install `requirements.txt` (about
1–2 minutes). Later runs start in seconds.

Both start scripts pass their options on to `run.py`, for example
`./start.sh --port 8001 --no-browser` or `.\start.bat --port 8001 --no-browser`.

### Manual steps

Mac / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Windows (cmd or PowerShell):

```bat
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

`run.py` options: `--port 8001`, `--host 0.0.0.0`, `--no-browser`. It also reads the `PORT`
environment variable (used by Render).

## API key

Create a file named `.env` that contains this line. The key name must be exactly `PORTKEY_API_KEY`.

```
PORTKEY_API_KEY=your_portkey_api_key_here
```

Put it in **either** place:

- the repo folder (next to `run.py`), **or**
- the folder above the repo (handy if several course projects share one key).

If both files exist, the repo `.env` wins. A real environment variable (for example on Render)
wins over both. `.env.example` is a template you can copy; it also lists the optional tuning
variables.

On startup `run.py` prints which `.env` files it found and whether the key is set (yes or no,
never the value). The key is never logged, returned by the API, or written to traces. `.env` is
gitignored, so never commit it.

The model is locked to `gpt-6-luna` via `https://api.portkey.ai/v1` in `app/config.py`, and no
environment variable can change it.

## Using the app

- **Ask** (left): type a question or click an example, then press **Run** (or **Stop**). The counter
  shows how many characters you have left.
- **Result:** the answer with citations, a confidence badge and the reason the run stopped.
- **How it worked** (right): a live timeline grouped by agent. Expand a tool call to see its
  arguments and result. Safety events are shown in amber or red.
- **Cost card:** tokens by type, number of model calls, cost in USD, cache hit rate and elapsed time.
- **Usage tab:** average tokens and cost per run, p50 and p90 costs, cost projections and recent
  runs. Click a run to replay its trace.

## Switching datasets

The agents read every `.md`, `.txt`, `.csv` and `.json` file under `DATA_DIR`, including
subfolders. The default is `data/sample/`, a small test set that ships with the repo.

```
DATA_DIR=data/my_bigger_set      # in .env; relative to the repo, or an absolute path
```

Restart the app after changing it.

## Tests

With the venv active (see [Manual steps](#manual-steps)):

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The suite runs fully offline. A `FakeLLM` stands in for the model, so it never needs or reads your
real key. It covers config and `.env` lookup, pricing, the ledger and budgets, tools (including
path-traversal and safe-math checks), the agent loop (delegation, caps, least privilege), every
safety layer, and the HTTP API.

## Scripts

Run these from the repo folder with the venv active.

| Command | What it does | Cost |
|---|---|---|
| `python scripts/smoke_test.py` | One live model call. Prints the reply, token usage and cost. | < $0.001 |
| `python scripts/redteam.py` | Sends 12 attacks and 1 benign control question through the real pipeline. Records which defense layer caught each one in `evidence/redteam_results.json`. `--dry-run` lists the attacks without calling the model. `--only id1,id2` runs a subset. `--no-llm-guard` shows the heuristics alone. | a few cents |
| `python scripts/tokenomics.py` | Reads `runs/usage.jsonl` and writes `evidence/tokenomics.json` and `evidence/tokenomics.md`: per-run averages, cache hit rate and savings, a per-agent breakdown, and projections for 1, 100 and 10,000 users. `--runs-per-user N` changes the usage assumption. | free |
| `python scripts/inline_images.py report.html [out.html]` | Embeds local images as base64 so `report.html` and `slides.html` are self-contained. | free |

Red-team model calls go to `runs/redteam_usage.jsonl`, not the main ledger, so tokenomics reflect
normal use only.

## Cost and safety caps

All caps are optional settings. Put them in `.env` or set them as environment variables. If a
value is invalid, the default is used.

| Variable | Default | Meaning |
|---|---|---|
| `RUN_BUDGET_USD` | `0.05` | Max spend for one run |
| `RUN_TOKEN_CAP` | `250000` | Max input + output tokens for one run |
| `DAILY_BUDGET_USD` | `2.00` | Max spend across all runs per UTC day (read from the ledger) |
| `MAX_STEPS_PER_AGENT` | `8` | Max model calls per agent invocation |
| `MAX_TOOL_CALLS_PER_RUN` | `30` | Max tool calls in one run |
| `MAX_AGENT_DEPTH` | `2` | Max delegation depth (the entry agent is depth 0) |
| `MAX_OUTPUT_TOKENS` | `4000` | Max output tokens per model call |
| `MAX_INPUT_CHARS` | `8000` | Max length of a user question |
| `RATE_LIMIT_RUNS` / `RATE_LIMIT_WINDOW_S` | `15` / `600` | Max runs per client IP per window |
| `SAFETY_LLM_GUARD` | `1` | Extra `gpt-6-luna` check on user input. Set to `0` to turn it off. |
| `RUNS_PER_USER_PER_MONTH` | `30` | Usage assumption for cost projections |
| `LLM_TIMEOUT_S` | `90` | Timeout per model call |
| `RUNS_DIR` | `runs` | Where the ledger and traces are written |

The safety layers (details in `DESIGN.md` §4.8):

1. **Input screening:** a length cap, injection heuristics and an optional LLM guard. High-risk
   input is blocked before any agent sees it. If the model provider's own content filter rejects a
   request (Azure OpenAI does this for many jailbreak prompts), the run is reported as blocked,
   not as an error.
2. **Spotlighting:** untrusted content is wrapped in nonce-tagged blocks. Every agent is told to
   treat it as data, never as instructions.
3. **Tool-output scanning:** document text is checked for injected instructions. The sample
   `supplier_note.md` is booby-trapped on purpose to show this.
4. **Least privilege:** each agent has a tool allowlist, and any other tool call is refused.
5. **Output screening:** a leaked canary marker blocks the output, secrets are redacted, and
   exfiltration URLs have their query strings stripped.
6. **Caps:** step, tool-call, depth, token, USD, daily and rate limits. Each one emits a safety event
   when it trips.

## Evidence for the report

| Report section | Where the evidence comes from |
|---|---|
| Agent design | `runs/traces/<run_id>.json`, plus a screenshot of the UI timeline |
| Tokenomics | `python scripts/tokenomics.py` → `evidence/tokenomics.{json,md}`, plus a screenshot of the Usage tab |
| Safety | `python -m pytest tests/test_safety.py -v` output, `python scripts/redteam.py` → `evidence/redteam_results.json`, plus a UI screenshot of a safety event |

`runs/` is gitignored and `evidence/` is committed.

## Project layout

```
run.py, start.sh, start.bat   entry points
app/                          config, pricing, llm, ledger, budget, events, tools, safety, agent,
                              orchestrator, server
app/domain/                   PLACEHOLDER domain: tools, output models, prompts/*.md
data/sample/                  small test dataset
web/                          index.html, styles.css, app.js (no build step)
scripts/                      smoke_test, redteam, tokenomics, inline_images
tests/                        offline pytest suite
runs/                         runtime output (gitignored)
evidence/                     curated exports for the report
```

`DESIGN.md` has the full module contracts.

## Swapping in the real topic

Replace `app/domain/` (tools, output models and prompts), the files in `data/sample/`, and the
`APP_META` title, tagline and examples in `app/orchestrator.py`. The agent wiring stays declarative
in `build_team()`. Everything else (ledger, budgets, safety, UI, scripts) stays as it is.

## Deployment (optional): Render

Create a single Render **Web Service**:

- Build command: `pip install -r requirements.txt`
- Start command: `python run.py --host 0.0.0.0 --no-browser` (it reads `PORT`)
- Environment variable: `PORTKEY_API_KEY`

The free tier sleeps when idle, so **the first page load can take about a minute.** Please wait.
A fresh local clone is still the main way to run the app.

## Troubleshooting

| Problem | Fix |
|---|---|
| `address already in use` / port 8000 busy | `./start.sh --port 8001` (Mac / Linux) or `.\start.bat --port 8001` (Windows), then open <http://127.0.0.1:8001> |
| `start.bat` "is not recognized" in PowerShell | PowerShell does not run scripts from the current folder by name. Type `.\start.bat`. |
| "PORTKEY_API_KEY is not set" / UI says key missing | The file must be named exactly `.env`, not `.env.txt` (Windows hides extensions). It must sit in the repo folder or the folder above, and the line must start with `PORTKEY_API_KEY=`. Restart the app after editing. |
| 401 / "rejected the API key" | The key value is wrong or expired. Paste it again with no quotes or spaces. |
| Python version error | Check `python3 --version` (Mac) or `py -3 --version` (Windows). You need 3.10+. Install it from <https://www.python.org/downloads/>. |
| `py` not found on Windows | Install Python from python.org and tick "Add python.exe to PATH". `start.bat` falls back to `python`. |
| PowerShell blocks `.venv\Scripts\activate` | Use `start.bat` or cmd, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. |
| "Too many runs" (HTTP 429) | The per-IP rate limit was hit. Wait, or raise `RATE_LIMIT_RUNS`. |
| Run stops with "budget" | A run or daily cap was reached. See [Cost and safety caps](#cost-and-safety-caps). |
| Need a clean slate | Delete `.venv/` (reinstall) or `runs/` (clears history and the cost ledger). |
