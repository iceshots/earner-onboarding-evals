# Synthetic data for the Earner Onboarding Assistant

A reproducible, fully synthetic dataset for the Earner Onboarding Assistant portfolio project. It is one wide table, one row per earner, that the assistant answers questions from. Every name, ID, status and number is invented. Nothing is derived from any real company's schema, thresholds or data.

## Quick start

```bash
pip install pandas numpy                  # only dependencies
python generate_data.py                   # writes everything in about 5 seconds
python validate_data.py                   # checks integrity + PRD numbers, exit code 0 if all pass
python generate_data.py --seed 7          # same recipe, different random draw
```

## What you get

| File | Purpose |
|---|---|
| `output/earner_onboarding.csv` | The table (20,000 rows x 23 columns) |
| `output/earner_onboarding.sqlite` | Same table as `earner_onboarding`, indexed, for text-to-SQL. Contains only this table |
| `data_dictionary.md` | Field-by-field dictionary, rebuilt from the data on every run so it never goes stale |
| `config.json` | Every knob: seed, size, mixes, calibration, reason weights, seeded patterns |
| `generate_data.py` | The generator |
| `validate_data.py` | Integrity rules + PRD-number checks. Writes `output/validation_report.md` |
| `hidden/ground_truth.csv` | **Validator and evals only. Never give this to the chatbot.** Latent onboarding hours, queue hours, churn flag, planted-injection flag |

## The table in one paragraph

Each earner is a restaurant, fleet or driver in Europe, APAC or North America, who started onboarding between 2025-11-01 and 2026-10-28. Restaurants and fleets go through three checks: **legal entity**, **shareholder** and **payment profile**. Drivers skip legal entity (`not_applicable`). Each check has a current status (`passed`, `pending`, `rejected`), a failure reason (null only when passed), a last-updated time and an `is_stuck` flag. `overall_status` is `passed` only if every applicable check is passed. The whole table is a snapshot as of `data_last_updated_at` (2026-10-29 00:00 UTC). See `data_dictionary.md` for every field.

## How the data is generated

The generator simulates each earner's journey, then reports where every check stands at the snapshot time. It uses a seeded random generator, so the same seed and config always give the same data.

1. **Profile.** Type (45% restaurant, 45% driver, 10% fleet), region, size, channel and a start timestamp are drawn from the mixes in `config.json`. Starts have a mild weekday pattern and 25% growth over the year. Names are assembled from word lists.
2. **Total onboarding time `T`.** Each earner gets a latent number of hours from start until they complete onboarding or give up. The distribution is calibrated to the PRD: a lognormal body (90% of earners, up to 450h) plus an exponential tail beyond 450h (10%). This gives a median of about 60h, p90 of about 450h and mean of about 118h.
3. **Who gives up (churn).** Earners with `T` above the p90 give up 99% of the time, versus 10% for the rest. That is a churn ratio of about 10x, and an eventual pass rate of about 81%. Those who give up leave one or more checks permanently unfinished.
4. **Check timelines.** One check is the earner's bottleneck and finishes at `T`. Other checks finish earlier. Each check starts `pending`, may go through 0 to 2 reject-and-resubmit cycles (more cycles for longer `T`), then ends `passed`. Blocked checks of earners who give up end in `pending` or `rejected`.
5. **Failure reasons.** Every `pending` or `rejected` event gets a reason from a check-specific list, so reasons are never null unless the check is passed. `awaiting_agent_review` is the platform-side reason; all others are earner-side. Each check only uses its own reasons.
6. **Snapshot.** The table shows each check's latest event on or before the snapshot time. Earners who started recently are naturally still in flight, which is why status can be `pending` with no problem.
7. **Planted signal and traps.** See the next two sections.
8. **Write-out.** CSV, SQLite, hidden ground truth, and the data dictionary built from the final data.

## Seeded patterns (so aggregate questions have a real answer)

| Region | Pattern | Where to see it |
|---|---|---|
| Europe | `document_expired` is about 3x as common among rejected legal entity checks | "Why are Europe restaurants rejected on legal entity?" |
| APAC | `account_name_mismatch` is about 2.5x as common among rejected payment profile checks | "Top payment profile reasons in APAC?" |
| North America | `awaiting_agent_review` is more common among pending checks (a longer agent queue) | "What share of pending checks are waiting on an agent, by region?" |

## Planted red-team rows

Ten rows have prompt-injection text inside `earner_name`, for example an instruction to ignore previous instructions, to report an earner as passed, or to list every earner. Five are blatant and five are subtle. These are the only place injection text appears; no status or reason field is touched. The affected IDs are in `hidden/ground_truth.csv` (`is_injection_row = 1`) for use in evals.

## Design decisions worth knowing

- **One wide table.** No joins. The PRD's "pre-transformed data source".
- **`is_stuck` is point-in-time.** It is 1 when a check is `pending` or `rejected` at the snapshot, regardless of how long it has been there. It carries the same information as `status` and is kept so "stuck on legal entity" maps to one obvious column.
- **No minimum cohort size.** A cohort of 1 is reported as 1. Declines are for bulk earner identities and out-of-scope requests, not for small groups.
- **"No data" cases are natural.** Empty cohorts (for example drivers on legal entity), unknown IDs (anything outside `P-10001` to `P-30000`) and attributes not in the table (such as city or document type) all give a "no data" answer.
- **Booleans are 1/0.** Timestamps are UTC text, `YYYY-MM-DD HH:MM:SS`.
- **Names are not unique** (about 5,900 distinct among 20,000). `earner_id` is the key.
- **Churn definition.** The PRD says earners above p90 onboarding time are 10x more likely to churn. Here, "churn" means the earner never completes onboarding, and the latent onboarding time covers all earners (time to complete, or to give up). That keeps the PRD's 80% pass rate and 10x ratio consistent with each other. A 10x ratio is not possible with a 20% overall churn if the ratio refers to a separate "never went online" flag.

## What the validator checks

- **Integrity (28 checks).** Row count, unique IDs, SQLite equals CSV, allowed values per field, reason null if and only if passed, reasons belong to their check, `is_stuck` and `overall_status` derivations, timestamps between start and snapshot, week and month fields, and agreement with the hidden ground truth.
- **PRD numbers (12 checks).** Median, p90 and mean onboarding time, agent and queue share for the p90+ tail (40%), mean queue time (31h), churn ratio (10x), pass rate (80%, on earners started 60+ days before the snapshot), and the earner type mix.
- **Seeded patterns (3 checks).** The three regional signals above.

The 60-day cutoff for the pass-rate check exists because earners who started recently have not had time to finish.

## Example queries

```sql
-- Core Loop 1: where is an earner stuck?
SELECT * FROM earner_onboarding WHERE earner_id = 'P-10482';

-- Core Loop 2: % of Europe earners who started in September 2026 stuck on legal entity, and why
SELECT legal_entity_failure_reason, COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_stuck
FROM earner_onboarding
WHERE region = 'Europe' AND start_month = '2026-09' AND legal_entity_is_stuck = 1
GROUP BY 1 ORDER BY n DESC;
```

## Limits

This is synthetic data built to behave like the PRD's story. Real onboarding data would be messier: duplicate and merged accounts, late-arriving updates, inconsistent reason codes. The distributions are invented and should be read directionally, as the PRD itself says.
