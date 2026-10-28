# Eval System for an Onboarding-Analytics Chatbot: Project Plan

**Owner:** Ayush Shrote
**Goal:** An AI PM portfolio project (GitHub repo + Substack post)
**Effort:** 5 days x 4 hours/day (20 hours total)
**Status:** Planning

---

## 1. What are we building?

An **evaluation system and automated feedback loop** for a chatbot that helps an operations team understand where partners are stuck in a compliance onboarding journey.

The project has three parts:

| Part | What it is | Share of effort |
|---|---|---|
| **The chatbot** (system under test) | A thin natural-language analytics agent over a synthetic onboarding database | ~15% |
| **The eval system** | A golden dataset, code-based checks, an LLM judge calibrated against human labels, and regression runs across bot versions | ~50% |
| **The feedback loop** | Failures from the eval are clustered and turned into proposed fixes to the bot's config; fixes are accepted only if they improve the target metric without regressions | ~25% |
| **Packaging** | A Substack post, a GitHub repo, a short demo, and a one-page summary | ~10% (plus Day 5) |

The majority of the work, and the story, is the eval and the loop, not the bot.

### Deliverables

1. **GitHub repo**: reproducible in about 10 minutes, with a README, architecture diagram, and results table.
2. **Substack post**: the narrative of the problem, the decisions, the results, and the failures (about a 10-minute read, with a TL;DR on top).
3. **Short demo**: a GIF or screen recording of the bot and one eval run.
4. **One-page PDF summary**: attachable to job applications.

---

## 2. Why are we building this? Why now?

### Why

- **To show AI PM skills, not just engineering skills.** AI PM interviews increasingly probe whether a candidate can define "good" for an AI feature, measure it, and make ship/no-ship decisions under uncertainty. Evals are the practical form of that skill.
- **To turn real experience into shareable proof.** I built a compliance onboarding chatbot with an eval framework in a production setting. I can't share anything proprietary, so a clean-room re-creation on synthetic data makes the experience visible and verifiable.
- **To differentiate.** Many portfolios stop at a golden set plus an LLM judge. This project goes further: judge calibration against human labels, a held-out test set, severity-weighted scoring, a compliance/risk angle, and an automated improvement loop with a human approval gate.
- **To support a broad target.** I am targeting AI PM roles generally, so the story is framed around product decisions (problem, metrics, trade-offs, launch thresholds) with technical depth as evidence.

### Why now

- I am actively moving from data science and AI products in compliance/risk into product management, so a public portfolio piece has immediate use in applications.
- Evals have become a core part of shipping AI features, and hiring managers increasingly expect candidates to speak about them from first-hand experience.
- The tooling (Claude Code for building, the Claude API for tool use) makes a 20-hour build feasible for the first time without sacrificing quality.

---

## 3. What is the chatbot, and what is it for?

### The product (fictional, generic)

A **partner-onboarding compliance assistant** for a large gig marketplace (drivers and couriers). Partners must pass several compliance checks before they can earn on the platform. Operations agents need to know quickly who is stuck, where, and why.

### Users

- **Operations agents:** investigate individual partners ("why can't this person go live?").
- **Compliance and ops leads:** monitor cohorts and spot systemic problems ("why are so many Region X partners stuck on document validity?").

### Two core capabilities

| # | Capability | Example question | Expected behavior |
|---|---|---|---|
| 1 | **Entity lookup** | "Where is partner P-10482 stuck?" | States the failed step(s) and fail reason(s) from the data; says "no data" if the ID doesn't exist |
| 2 | **Aggregate analysis** | "What % of Region X partners who started in September are stuck on background check, and why?" | Returns count and %, with the correct denominator and a breakdown of top reasons |

Supporting behaviors: asking clarifying questions on ambiguous requests, handling multi-turn follow-ups, refusing bulk PII dumps and out-of-scope requests, and never inventing a fail reason.

### Source of truth

A single synthetic entity-level table (DuckDB):

`partner_id, region, city, start_date, agent_id, channel, step_k_passed, step_k_fail_reason, ...` plus a data dictionary.

The generator seeds known patterns (e.g., one region with an elevated document-expiry failure rate), so we can verify the bot finds real signal.

### Confidentiality rule

No real company schema names, process names, thresholds, or numbers are used anywhere. Everything is a generic, synthetic re-creation.

### Bots under test

- **Bot A (fixed tools):** a Claude agent with a small set of well-defined tools: `get_user_status(user_id)` and `aggregate_stuck(process, region, date_range, group_by)`.
- **Bot B (free-form SQL):** the same agent with a single `run_sql` tool.

Comparing A and B gives a real product decision: safer and more constrained vs more flexible.

---

## 4. Why is an eval required?

The bot's answers drive operational decisions in a compliance context, and LLM agents fail in ways that look confident and plausible.

### What can go wrong

| Failure | Example | Why it matters |
|---|---|---|
| Wrong number | Stated 18% when the true figure is 12% | Teams prioritize the wrong problem |
| Wrong denominator | % of all partners instead of % of the cohort | Silent, plausible, and wrong |
| Invented reason | Says "document expired" when the data has no reason | Wrong remediation, compliance risk |
| False confidence | Answers instead of saying "no data" or asking for clarification | Erodes trust |
| PII leakage | Dumps a list of partner identities on request | Privacy and compliance violation |
| Prompt injection | A malicious string in a data field changes the bot's behavior | Security risk |
| Brittleness | Fails on typos, region aliases, or follow-up questions | Poor ops usability |

### Why a PM needs this, not just an engineer

- Without an eval, "is it good enough to ship?" is an opinion. With one, it's a threshold on defined metrics.
- Without an eval, every prompt change is a gamble. With one, regressions are caught before users see them.
- Evals let us compare design options (Bot A vs Bot B) with data, and connect quality to business outcomes (ops time saved, wrong-decision risk).

---

## 5. How are we building this?

### Architecture

```
Synthetic data generator -> DuckDB (source of truth)
                              |
                    Bot (A: tools / B: SQL)  <--- versioned config
                              | answer + structured trace
                              v
                      Eval harness
          code-based checks  +  LLM judge (calibrated)
                              |
                              v
               Failure clustering -> proposed config fixes
                              |
                 dev-set re-run + regression gate
                              |
                    human approval -> new config version
```

### Principles

1. **Bot adapter interface.** The harness talks to any bot through `ask(question, history) -> answer, tool_calls, latency, cost`. This lets us swap bots.
2. **Versioned config.** System prompt, tool descriptions, and data dictionary live in files (`bot/config/v1/`, `v2/`, ...). The feedback loop proposes diffs to these files.
3. **Structured traces.** Every response logs tools called, arguments, raw results, latency, and token cost.
4. **Code checks where truth is computable;** LLM judge only for fuzzy dimensions.
5. **Held-out test set** touched once, at the end.

### Eval taxonomy

| Dimension | Examples | Method |
|---|---|---|
| Intent and routing | Lookup vs aggregate vs out-of-scope; clarify when ambiguous | Code + judge |
| Query correctness | Right filters, joins, date ranges, denominator | Code (tool args) |
| Numeric accuracy | Exact match to code-computed truth | Code |
| Reason fidelity | Fail reasons come only from the data | Code |
| Groundedness and honesty | "No data" for missing IDs or empty cohorts | Code + judge |
| Completeness and actionability | Includes the useful breakdown | Judge |
| Safety and compliance | Refuses bulk PII, resists injection, respects scope | Code + judge |
| Robustness | Typos, aliases, multi-turn follow-ups | Code + judge |
| UX | Tone, concision, formatting for ops users | Judge |
| Efficiency | Latency, cost per query, tool calls | Code |

**Severity levels:** each failure carries a severity (S1 = confident wrong number or PII leak, S2 = incomplete or misleading, S3 = cosmetic). We report both pass rate and a severity-weighted score.

### Golden dataset (~100 cases)

| Source | Count | How |
|---|---|---|
| Programmatic from templates | ~60 | Questions generated from the DB, answers computed by code |
| Hand-written tricky cases | ~30 | Ambiguity, missing data, multi-turn, injection |
| Adversarial / red-team | ~10 | PII extraction, out-of-scope, manipulation |

Split into **train / dev / test (50/25/25)**. The feedback loop uses train and dev only.

### LLM judge

- Rubric written by me, with explicit definitions per dimension.
- Run with a different prompt (ideally a different model) from the bot.
- **Calibrated:** I hand-label ~30 bot outputs; we report judge-vs-human agreement and refine the rubric until it is trustworthy.

### Feedback loop

1. Run eval on train; collect failures with judge rationales.
2. Cluster failures by root cause (wrong tool args, missing clarification, invented reason, ...).
3. An "improver" step proposes fixes: prompt edits, tool description changes, few-shot examples, data-dictionary clarifications, guardrail rules.
4. Apply the candidate as a new config version; re-run on dev.
5. **Accept only if** the target metric improves, no other dimension regresses beyond tolerance, and S1 failures do not increase.
6. **Human approval gate:** every accepted change is reviewed by me; diff and metric deltas are logged.
7. Two rounds, then a single run on the test set for final numbers.

### Tools

| Need | Tool |
|---|---|
| Building bot, generator, harness | Claude Code (local repo) |
| Bot runtime | Claude API with tool use |
| Data | DuckDB + Python (Faker, seeded patterns) |
| Demo UI | Streamlit or CLI |
| Eval runner | Custom Python runner (transparent, readable) |
| Results and charts | Python notebook or script |
| Planning and drafts | Claude chat + Google Docs/Notion |
| Publishing | GitHub + Substack |

### Repo structure (target)

```
/data        synthetic generator, data dictionary
/bot         agent, tools, config/v1 v2 v3
/evals       golden set, checks, judge, rubric, runner
/loop        failure clustering, improver, regression gate
/reports     results, charts, failure gallery
README.md    architecture, results table, reproduce-in-10-minutes
```

---

## 6. Timeline (5 days x 4 hours)

### Day 1: Foundations
- Confirm scenario and schema; edit one-page PRD (users, cost of a bad answer, metrics, launch thresholds).
- Claude Code builds repo, data generator with seeded patterns, both tools, agent with trace logging, and the Bot B flag.
- Ask the bot ~10 questions; note what breaks.
- **Done when:** the bot answers lookups and aggregates correctly on the happy path.

### Day 2: Golden set
- Agree on taxonomy and severity levels.
- Generate ~60 programmatic cases; brainstorm and write ~30-40 tricky and adversarial cases together.
- Review everything; split into train/dev/test.
- **Done when:** ~100 reviewed cases with expected answers and severity tags.

### Day 3: Harness and judge
- Build code-based checks and the LLM judge; run the baseline.
- Hand-label ~30 outputs.
- Compare judge to human; fix the rubric.
- **Done when:** baseline score, severity-weighted score, and judge-human agreement.

### Day 4: Feedback loop
- Build the loop (cluster, propose, re-run on dev, gate).
- Review each proposed diff; run two rounds.
- Run the test set once; compare Bot A vs Bot B.
- **Done when:** before/after numbers, A vs B comparison, and a log of accepted and rejected changes.

### Day 5: Packaging
- Charts, results table, 5-6 failure-gallery examples with root causes.
- README, architecture diagram, Substack draft (rewritten in my voice).
- Record GIF; publish; link from resume and LinkedIn.
- **Done when:** the post and repo are live.

### Scope cuts to fit 20 hours

| Original idea | Cut to |
|---|---|
| ~150 test cases | ~100 |
| 50+ hand-labelled outputs | ~30 |
| 3 loop rounds | 2 |
| Dashboard and CI gate | Design notes in the write-up |
| Loom video | GIF or short recording |
| Polished UI | Basic Streamlit or CLI |

---

## 7. Success criteria

**Project success (portfolio):**
- Repo and post published; a reader can reproduce the baseline in ~10 minutes.
- Clear before/after improvement from the feedback loop on the **held-out test set**.
- Judge-vs-human agreement reported honestly.
- Bot A vs Bot B comparison with a stated recommendation.
- A failure gallery with root causes.

**Illustrative launch thresholds for the bot** (to be finalized in the PRD):
- Zero S1 failures on the test set
- >= 95% numeric accuracy on aggregates
- 100% refusal on bulk-PII requests
- Cost and latency per query reported alongside quality

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Overfitting to the eval set | Held-out test set, touched once |
| Improver "games" the judge | Code-based checks for high-severity dimensions; human approval gate |
| Judge is untrustworthy | Calibrate against my hand labels; report agreement |
| Synthetic data feels "toy" | Seeded realistic patterns; messy edge cases; failure gallery |
| Scope creep | Hard caps (~100 cases, 2 loop rounds, bot built in about a day) |
| Day 3 labelling and Day 5 writing overrun | Protect those hours; keep 2-3 spare weekend hours as buffer |
| API cost | Small scale (20-50k rows, ~100 cases); set a spending limit on the key |
| Confidentiality | No proprietary names, schemas, or numbers; all synthetic |

---

## 9. Substack outline (preview)

1. TL;DR and what I built
2. The problem and why a wrong answer is costly
3. What "good" means: taxonomy, severity, thresholds
4. Building the golden set (and what the hand-written cases caught)
5. Calibrating the LLM judge (agreement numbers, what I changed)
6. The feedback loop: what it fixed, what it broke, what I rejected
7. Bot A vs Bot B: the product decision
8. Failure gallery (5-6 vivid failures with root causes)
9. Limitations (judge, synthetic data, overfitting risk)
10. What I'd do in production: monitoring, CI gate, rollout

---

## 10. Open decisions and next step

- [ ] Confirm scenario: gig-marketplace partner onboarding (drivers/couriers)
- [ ] Confirm scale: ~20-50k synthetic partners, 8-10 regions, 6 onboarding steps
- [ ] Approve schema and seeded patterns (shown before any data is generated)

**Next step:** Day 1 starts in Claude Code with the repo skeleton, data dictionary, and generator.
