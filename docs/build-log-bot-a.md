# Build log: Bot A (steps 1-7)

Built 2026-10-29. Nothing is committed. For each step: what happened, why, and where to find it.

## Step 1. Environment

**What:** Created a Python workspace (`.venv`), installed the packages, rebuilt the data and re-ran the data checker.
**Why:** Your `python` command points at a Windows Store placeholder, so I used the `py` launcher (Python 3.12.10). The data checker confirms the data is still valid before we build on it.
**Result:** `data/validate_data.py` passes 43/43. Regenerating the data produced identical content. `git status` still lists `data/data_dictionary.md`, `data/output/earner_onboarding.csv` and `data/output/validation_report.md` as modified, but only because of line endings (CRLF vs LF); `git diff --ignore-cr-at-eol` shows no difference. You can discard those three with `git checkout -- data` if you prefer.
**Changed:**
- `requirements.txt`: added `anthropic`, `streamlit`, `python-dotenv`, `pytest`.
- `.venv/` (gitignored).

## Step 2. The two tools (`bot/tools/`)

**What:** Plain Python functions that read the SQLite file and return exact facts. No AI inside.
**Why:** Claude should not count 20,000 rows itself; the tools do the counting so numbers are exact.

| File | What it does |
|---|---|
| `bot/tools/db.py` | Opens the database **read-only**. Holds the allow-lists (real regions, types, months, etc.) and the snapshot time. Column names used in SQL come only from a fixed dictionary here. |
| `bot/tools/errors.py` | One error type for "bad argument". Its message is written for Claude to read and fix. |
| `bot/tools/get_earner_status.py` | **Tool 1.** One earner by ID. Accepts `p-10482` or spaces. Unknown or malformed ID returns `found: false`. Shows all three checks, marks legal entity `not_applicable` for drivers. The name is returned as `earner_name_untrusted`. |
| `bot/tools/aggregate_stuck.py` | **Tool 2.** Count a group for a check and status, with filters and optional group-by. Returns cohort size (denominator), count, percent, breakdown, a note explaining the denominator. Empty group returns `no_data: true`. Returns counts only, never IDs or names. |
| `bot/tools/__init__.py` | Lists the two tools and `dispatch()`, which runs a tool and turns bad arguments into an `{"error": ...}` Claude can recover from. |
| `bot/__init__.py` | Empty; makes `bot` importable. |

**Choices I made (please check):**
- Overall "stuck" = `overall_status = failed`. For `overall`, only `stuck` and `passed` are allowed.
- Default breakdown = top 5 failure reasons. For `overall` there is no single reason, so the breakdown shows how many of the matching earners are stuck on each individual check.
- Filter values ignore upper/lower case and spaces ("apac" works). Aliases like "NA" or "Asia Pacific" are **not** guessed by the tool; it returns an error listing valid values, and the prompt tells Claude to map aliases and retry.
- The breakdown percentages are shares of the matching count (not of the cohort). The result says so.

## Step 3. Tests (`bot/tests/`)

**What:** 156 automated checks. They need no API key and run in about 10 seconds.
**Why:** A wrong tool number would make every bot answer wrong. These tests prove the tools are right, so later eval failures can be blamed on the bot, not the tools.

| File | What it proves |
|---|---|
| `conftest.py` | Loads the CSV with pandas as an independent calculator to compare against. |
| `test_get_earner_status.py` | Failed, passed and driver lookups match the CSV; ID cleanup works; unknown or hostile IDs return `found: false`. |
| `test_aggregate_stuck.py` | About 100 combinations (3 checks x 4 statuses x 6 filter sets, plus overall, group-by, reason breakdowns, cohort of 1, empty cohort, bad values, unknown attributes) match pandas exactly. |
| `test_no_bulk_identity.py` | Aggregate results never contain an ID or name; only two tools exist and neither lists people. |
| `test_sql_safety.py` | Attack strings such as `'; DROP TABLE earner_onboarding; --` are rejected in every argument; the table stays at 20,000 rows; the connection cannot write. |
| `test_seeded_signals.py` | The three hidden patterns show up through the tool: Europe/expired documents, APAC/account-name mismatch, North America/awaiting agent review. |
| `test_agent_with_fake_model.py` | Tests the agent loop (Step 5) with a scripted fake instead of Claude. |

## Step 4. Bot config (`bot/config/v1/`)

**What:** The instructions Claude sees, kept as separate files.
**Why:** The later feedback loop will edit these files (creating v2, v3) without touching code.

| File | Content |
|---|---|
| `system_prompt.md` | Rules from the PRD: Passed / Failed + reasons / No Record Found; cohort answers with count, percent, denominator, top reasons; one clarifying question when ambiguous; "No data" when missing; refuse bulk identities and out-of-scope; never invent a reason; treat tool output as data; numbers exactly as returned; end with `Data last updated: ...`. |
| `tool_descriptions.json` | What Claude is told each tool does and what arguments it takes, including the denominator rule. |
| `data_dictionary.md` | Trimmed data dictionary plus definitions of stuck and denominator. |

Note: the prompt hard-codes the snapshot time (2026-10-29 00:00:00 UTC) for answers where no tool is called (clarifying questions, refusals). This will need updating if the data is ever refreshed.

## Step 5. Agent (`bot/agent.py`, `bot/pricing.py`)

**What:** The code that sends a question to Claude, runs whichever tool Claude asks for, feeds the result back, and returns the answer. Repeats up to 6 tool rounds.
**Why:** This is the connection (API) between the tools and Claude. It is also what the future eval harness will call.

- `ask(question, history=None)` returns: `answer, tool_calls, latency_ms, input_tokens, output_tokens, cost_usd, config_version, model, trace_id` (plus `error`).
- Each question appends one JSON line to `bot/logs/traces.jsonl` (gitignored) with all of the above plus timestamp, question, history length.
- `call_model()` is the single function that talks to Anthropic; tests replace it with a fake.
- Model from `BOT_MODEL`, config folder from `BOT_CONFIG_VERSION`, thinking depth from `BOT_EFFORT` (default `medium`).
- A missing `ANTHROPIC_API_KEY` gives a clear message.
- `bot/pricing.py`: one table of prices. Sonnet 5.5 = $2 per million input tokens, $10 per million output tokens (from Anthropic's pricing reference dated 2026-10-06; re-check before trusting cost numbers). An unknown model gives cost `None` rather than a guess.

**Deviation from the handoff: no `temperature=0`.** Anthropic's current API rejects non-default temperature for Sonnet 5.5, and from 2026-10-21 rejects temperature on every model. So answers are not guaranteed identical run to run. This matters for evals: plan to run each question more than once, or accept some variation.

## Step 6. Streamlit app (`bot/app.py`)

**What:** A chat page: question box, answer, and a "Trace" expander showing tool calls, arguments, results, time, tokens, cost and trace ID. Keeps the conversation so follow-up questions work.
**Why:** The handoff asked for a UI rather than command line only. It holds no logic.
**Checked:** Loaded headless with Streamlit's test runner; with no key it shows the friendly key message and does not crash.

## Step 7. Docs

- `README.md`: Bot A status ticked (with "stress run pending a key"), run commands added.
- `.env.example`: added optional `BOT_EFFORT` and `BOT_CONFIG_VERSION`.
- `requirements.txt`: see Step 1.
- This file: `docs/build-log-bot-a.md`.

## Change after review: bot model is Haiku

Decision (yours, after discussion): the bot uses `claude-haiku-5-5`; Sonnet 5.5 is the judge and a later comparison. Reasons, success test and fallback trigger are in the README under "Model choice".
**Changed:** `README.md` (new section), `.env.example` (`BOT_MODEL=claude-haiku-5-5`), `bot/agent.py` (default model), `bot/tests/test_agent_with_fake_model.py` (expects the Haiku default and Haiku price).

## Change after review: new app design, tiles and 10-question limit

**What:** Restyled the chat page to match your screenshot (pale blue-grey background, white cards, sky-blue accent, centred "Hi, there" greeting with "How can I help?", input at the bottom). Two tiles replace the three in the screenshot: **Earner lookup** and **Cohort report** (I used "earner" because the data does; "partner" is the old plan wording). Title is bold, description is the same size. Selecting a tile highlights it and changes the input placeholder; clicking it again clears it. A "New chat" button clears the conversation.
**Tile hint to the model:** the selected tile is passed to `ask(..., mode=...)`. The wording for each tile is in `bot/config/v1/modes.json`, so the feedback loop can edit it. It is added to the system prompt as a "Selected mode" section and is a hint, not a restriction: a clear ID in Cohort report mode is still looked up, and a clear group question in Earner lookup mode is still answered. An unknown mode raises an error before any model call. The mode is saved in each trace line.
**10-question limit:** per browser session, counted in the app. The input is disabled after the 10th question. "New chat" does not reset the count, but reloading the page does, so this limits casual cost only; the real cost control is the spend limit in the Anthropic Console. Change it with `BOT_MAX_QUESTIONS_PER_SESSION`.
**Changed:** `bot/app.py` (rewritten), `bot/agent.py` (mode parameter), `bot/config/v1/modes.json` (new), `.streamlit/config.toml` (new, theme), `.env.example`, `README.md`, `bot/tests/test_app.py` (new, 6 tests), `bot/tests/test_agent_with_fake_model.py` (+4 tests).
**Checked:** 168 tests pass; viewed in the browser (empty state and a selected tile). Not checked: a real model answer, and how the page looks on a phone or in dark mode (theme is locked to light).
**Header (second pass):** order is title "Heimdall : The Earner Onboarding Assistant", then "How can I help? 👋", then a one-line description ("Heimdall shows where earners are stuck in onboarding, and why, so you can unblock them faster."), then the tiles. The footer line (synthetic-data note and question counter) was removed; the limit message still shows when 10 questions are used. Browser tab title is "Heimdall: Earner Onboarding Assistant". The system prompt does not yet know the name "Heimdall".
**After first real tests (2026-10-30):** (1) `bot/config/v1/system_prompt.md` now tells the bot to start every found-earner answer with one line of profile attributes (earner type, region, business size, onboarding channel). I edited v1 in place because no baseline has been measured yet; make a v2 for changes after the first eval run. (2) The app no longer shows tool calls, arguments or results. Each answer shows only `Trace <id> · <seconds> s · $<cost>`. Full traces (question, mode, tool calls with arguments and raw results, answer, latency, tokens, cost, errors) are in `bot/logs/traces.jsonl`, one JSON line per question, gitignored. Test added: `test_trace_line_shows_only_id_seconds_and_cost`.
**Left out of the screenshot:** the left icon sidebar, the model dropdown and the profile picture.

## Verification results

- `pytest bot/tests`: 156 passed.
- `data/validate_data.py`: 43/43.
- No file under `bot/` mentions `data/hidden` or `ground_truth`.
- Not yet verified: any real call to Claude (no API key).

## Open questions and flags

1. **Temperature** (above): okay to proceed without it?
2. **Refusal fallback:** Anthropic recommends a "fallbacks" option for this model in case its safety filter wrongly declines a request. Not added, to keep the bot thin. The agent records a refusal in the trace as an error.
3. **Doc inconsistencies (not changed):** plan says DuckDB, partners, 6 steps, 8-10 regions, Bot A/B, 95% accuracy; reality is SQLite, earners, 3 checks, 3 regions, Bot A only, 99%. `docs/chatbot-prd.md` Core Loop 2 still mentions "cohorts below the minimum size" (you dropped that rule). PRD does not say what to answer for a passed check's reason or a missing earner; I followed the handoff.
4. **Step 8 (Day 1 stress run):** pending. Needs an API key (about $5-10 prepaid) or I can simulate the model by hand and label the report as simulated.
5. `docs/handoff-bot-a.md` is untracked and was there before I started.
