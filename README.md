# Earner Onboarding Assistant: evals and feedback loop

An AI PM portfolio project. A chatbot helps onboarding agents find out why an earner (restaurant, fleet or driver) is stuck in onboarding. This repo builds the assistant, measures its accuracy with an eval system, and closes the loop to push accuracy toward 99%.

All data is synthetic. This is an independent exercise, not a description of any real company's system.

## Repo layout

| Folder | What lives there |
|---|---|
| `docs/` | The PRD (`chatbot-prd.md`) |
| `data/` | Synthetic data generator, validator, config, data dictionary and the pinned CSV snapshot. See `data/README.md` |
| `bot/` | The assistant (Bot A: fixed tools). `config/v1/` holds the versioned system prompt and tool descriptions |
| `evals/` | Golden question set (`golden/`), graders and the eval runner |
| `loop/` | The feedback loop: failure analysis, fixes and re-runs |
| `reports/` | Eval results and write-ups |

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then add your ANTHROPIC_API_KEY (needed once Bot A is built)
```

## Rebuild the data

```powershell
python data/generate_data.py      # writes CSV, SQLite, data dictionary, hidden ground truth
python data/validate_data.py      # 43 checks; exit code 0 means all pass
```

The same seed always gives the same data. `data/output/earner_onboarding.csv` is committed as the pinned snapshot that the golden set is computed from. The SQLite file and `data/hidden/` are gitignored and rebuilt by the generator.

## Model choice

The bot runs on **Claude Haiku 5.5** (`BOT_MODEL=claude-haiku-5-5`) for now. Sonnet 5.5 is reserved for the judge and for one later comparison run.

Why Haiku (hypotheses, to be tested, not facts):
1. The task is narrow: two fixed tools, allow-lists and error messages that list valid values, so the tools carry the hard parts.
2. The system prompt is clear enough for a smaller model to follow. Day 1 stress run checks this.
3. A weaker bot surfaces more failures, which gives the eval and feedback loop more to analyse and fix.
4. About 20x cheaper and faster per question, which matters when the golden set is re-run every loop.

How the choice will be judged:
- Success test: the Day 1 stress run, then the 99% accuracy gate after the feedback loop.
- Fallback trigger: if prompt and tool-description fixes plateau below the gate, run the same set on Sonnet 5.5 and compare. The gap shows what the model upgrade is worth versus the prompt fixes.

Note: no `temperature` is sent (the API no longer accepts it), so repeat each eval question more than once to handle run-to-run variation.

## Run Bot A

```powershell
pytest bot/tests -q               # tool, safety and agent-loop tests; no API key needed
streamlit run bot/app.py          # chat UI; needs ANTHROPIC_API_KEY in .env
```

The app has two tiles, **Earner lookup** and **Cohort report**. Selecting one passes a hint (from `bot/config/v1/modes.json`) to the model about how to read the free-text question; clicking it again clears it. Each browser session is limited to 10 questions (reloading the page starts a new session, so this is a cost guard, not security). Theme colours live in `.streamlit/config.toml`.

Every question is traced to `bot/logs/traces.jsonl` (gitignored). The build log in `docs/build-log-bot-a.md` lists what each file does and why. Versioned prompts and tool descriptions live in `bot/config/<version>/` (default `v1`; set `BOT_CONFIG_VERSION` to switch).

## Status

- [x] PRD
- [x] Synthetic data and validator
- [x] Bot A (fixed tools) with trace logging and a Streamlit app (Day 1 stress run pending an API key)
- [ ] Golden set and graders
- [ ] Failure analysis and feedback loop
- [ ] Write-up
