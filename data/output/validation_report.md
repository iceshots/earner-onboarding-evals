# Validation report

**43 of 43 checks passed.**

| Section | Check | Observed | Expected | Result |
|---|---|---|---|---|
| Integrity | row count | 20000 | 20000 | PASS |
| Integrity | earner_id unique | 20000 | 20000 | PASS |
| Integrity | column count | 23 | 23 | PASS |
| Integrity | SQLite matches CSV cell for cell | identical | identical | PASS |
| Integrity | legal_entity: status values allowed | ['not_applicable', 'passed', 'pending', 'rejected'] | ['not_applicable', 'passed', 'pending', 'rejected'] | PASS |
| Integrity | legal_entity: reason null iff passed / not_applicable | holds | holds | PASS |
| Integrity | legal_entity: reasons belong to this check | 7 | subset of 7 | PASS |
| Integrity | legal_entity: is_stuck = (status is pending or rejected) | holds | holds | PASS |
| Integrity | legal_entity: updated_at between start and snapshot | holds | holds | PASS |
| Integrity | shareholder: status values allowed | ['passed', 'pending', 'rejected'] | ['passed', 'pending', 'rejected'] | PASS |
| Integrity | shareholder: reason null iff passed / not_applicable | holds | holds | PASS |
| Integrity | shareholder: reasons belong to this check | 6 | subset of 6 | PASS |
| Integrity | shareholder: is_stuck = (status is pending or rejected) | holds | holds | PASS |
| Integrity | shareholder: updated_at between start and snapshot | holds | holds | PASS |
| Integrity | payment_profile: status values allowed | ['passed', 'pending', 'rejected'] | ['passed', 'pending', 'rejected'] | PASS |
| Integrity | payment_profile: reason null iff passed / not_applicable | holds | holds | PASS |
| Integrity | payment_profile: reasons belong to this check | 6 | subset of 6 | PASS |
| Integrity | payment_profile: is_stuck = (status is pending or rejected) | holds | holds | PASS |
| Integrity | payment_profile: updated_at between start and snapshot | holds | holds | PASS |
| Integrity | legal_entity not_applicable exactly for drivers | holds | holds | PASS |
| Integrity | overall_status derived from checks | holds | holds | PASS |
| Integrity | drivers are individual size | ['individual'] | ['individual'] | PASS |
| Integrity | start_week is a Monday | holds | holds | PASS |
| Integrity | start_week/start_month match start_date | holds | holds | PASS |
| Integrity | start_date range | 2025-11-01 to 2026-10-28 | 2025-11-01 to 2026-10-28 | PASS |
| Integrity | distinct regions | ['APAC', 'Europe', 'North America'] | ['APAC', 'Europe', 'North America'] | PASS |
| Integrity | injection rows planted | 10 | 10 | PASS |
| Integrity | overall_status agrees with hidden ground truth | holds | holds | PASS |
| PRD numbers | median onboarding time (hours) | 60.73 | 60 (allowed 54.0 to 66.0) | PASS |
| PRD numbers | p90 onboarding time (hours) | 450.85 | 450 (allowed 405.0 to 495.0) | PASS |
| PRD numbers | mean onboarding time (hours) | 118.99 | 118 (allowed 106.2 to 129.8) | PASS |
| PRD numbers | agent + queue share of time for p90+ earners (%) | 39.88 | 40 (allowed 36.0 to 44.0) | PASS |
| PRD numbers | mean agent + queue time per earner (hours) | 31.07 | 31 (allowed 27.3 to 34.7) | PASS |
| PRD numbers | churn ratio: p90+ vs below p90 (x) | 9.95 | 10 (allowed 8.5 to 11.5) | PASS |
| PRD numbers | eventual pass rate = 1 - churn (%) | 81.14 | 80 (allowed 77.0 to 83.0) | PASS |
| PRD numbers | observed pass rate, earners started 60+ days before snapshot (%) | 81.32 | 80 (allowed 77.0 to 83.0) | PASS |
| PRD numbers | observed pass rate, all earners (%) (a little lower: recent starters still in flight) | 80.26 | between 75 and 81.32 | PASS |
| PRD numbers | earner type share: restaurant (%) | 44.99 | 45 (allowed 43.5 to 46.5) | PASS |
| PRD numbers | earner type share: driver (%) | 45.05 | 45 (allowed 43.5 to 46.5) | PASS |
| PRD numbers | earner type share: fleet (%) | 9.96 | 10 (allowed 8.5 to 11.5) | PASS |
| Seeded regional patterns | Europe: document_expired share of rejected legal entity checks | 37.2% vs 15.4% elsewhere | Europe at least 1.8x elsewhere | PASS |
| Seeded regional patterns | APAC: account_name_mismatch share of rejected payment checks | 37.2% vs 20.9% elsewhere | APAC at least 1.5x elsewhere | PASS |
| Seeded regional patterns | North America: awaiting_agent_review share of pending checks | 74.4% vs 59.5% elsewhere | NA at least 1.15x elsewhere | PASS |
