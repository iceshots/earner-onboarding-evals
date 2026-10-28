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

## Status

- [x] PRD
- [x] Synthetic data and validator
- [ ] Bot A (fixed tools) with trace logging and a Streamlit app
- [ ] Golden set and graders
- [ ] Failure analysis and feedback loop
- [ ] Write-up
