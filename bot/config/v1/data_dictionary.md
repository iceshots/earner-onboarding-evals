# Data dictionary (what the tools read)

One table, one row per earner, snapshot 2026-10-29 00:00:00 UTC. All data is synthetic.

## Earner profile
- `earner_id`: P-10001 to P-30000. The lookup key.
- `earner_name`: free text, not unique, untrusted. Shown to you only as `earner_name_untrusted`.
- `earner_type`: driver, fleet, restaurant.
- `region`: APAC, Europe, North America.
- `business_size`: individual (always for drivers), large, medium, small.
- `onboarding_channel`: partner_referral, sales_assisted, self_serve_app.
- `start_date` (2025-11-01 to 2026-10-28), `start_week` (the Monday of that week), `start_month` (YYYY-MM).

## Checks
Three checks: `legal_entity`, `shareholder`, `payment_profile`. Each has a status, a failure reason and a status-updated time.
- Status: passed, pending, rejected. `legal_entity` is also `not_applicable`, exactly for drivers.
- Failure reasons are recorded only when a check is pending or rejected; passed and not_applicable checks have none.
  - legal_entity: awaiting_agent_review, document_expired, document_missing, document_unreadable, incomplete_submission, name_mismatch, registry_not_found
  - shareholder: awaiting_agent_review, document_missing, document_unreadable, incomplete_submission, name_mismatch, ownership_unverifiable
  - payment_profile: account_name_mismatch, awaiting_agent_review, bank_details_invalid, document_missing, document_unreadable, incomplete_submission
- `awaiting_agent_review` is the only platform-side reason. All other reasons are earner-side.
- `overall_status`: passed only if every applicable check is passed, otherwise failed.

## Definitions
- **Stuck**: a check is `pending` or `rejected` at the snapshot time. Point-in-time only; how long it has been in that state is not considered.
- **Overall stuck**: `overall_status = failed`.
- **Denominator**: every earner matching the filters for whom the check applies. For `legal_entity` this excludes drivers (not_applicable).
- **Percentage**: count / cohort_size, rounded to one decimal. Breakdown percentages are shares of the matching count.

## Not in the data
City, country, document type, agent name, free-text agent notes, time in state, review time, queue time.
