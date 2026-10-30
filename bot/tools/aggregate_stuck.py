"""Tool 2: count a cohort of earners (aggregates only, never identities)."""
import re
from datetime import datetime

from .db import CHECKS, FILTER_COLUMNS, TABLE, connect, data_last_updated_at, valid_values
from .errors import ToolValidationError

STATUSES = ("stuck", "pending", "rejected", "passed")
DATE_FILTERS = {"start_date_from": ">=", "start_date_to": "<="}
TOP_N_REASONS = 5


def _check_choice(value, allowed, name):
    if not isinstance(value, str) or value.strip().lower() not in allowed:
        raise ToolValidationError(f"Invalid {name}. Valid values: {', '.join(allowed)}.")
    return value.strip().lower()


def _validate_filters(filters) -> tuple[list[str], list, dict]:
    """Return (sql_conditions, params, canonical_filters). Column names come only from FILTER_COLUMNS."""
    if filters is None:
        return [], [], {}
    if not isinstance(filters, dict):
        raise ToolValidationError("filters must be an object of attribute: value pairs.")
    allowed_attrs = sorted(list(FILTER_COLUMNS) + list(DATE_FILTERS))
    conds, params, applied = [], [], {}
    for attr, value in filters.items():
        if attr in DATE_FILTERS:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
                raise ToolValidationError(f"{attr} must be a date in YYYY-MM-DD format.")
            try:
                datetime.strptime(value.strip(), "%Y-%m-%d")
            except ValueError:
                raise ToolValidationError(f"{attr} is not a real calendar date: {value!r}.") from None
            conds.append(f"start_date {DATE_FILTERS[attr]} ?")
            params.append(value.strip())
            applied[attr] = value.strip()
        elif attr in FILTER_COLUMNS:
            options = valid_values()[attr]
            lookup = {o.lower(): o for o in options}
            canonical = lookup.get(value.strip().lower()) if isinstance(value, str) else None
            if canonical is None:
                raise ToolValidationError(
                    f"Unknown value {str(value)[:60]!r} for {attr}. Valid values: {', '.join(options)}."
                )
            conds.append(f"{FILTER_COLUMNS[attr]} = ?")
            params.append(canonical)
            applied[attr] = canonical
        else:
            raise ToolValidationError(
                f"Attribute {str(attr)[:60]!r} is not in the data. Available filters: {', '.join(allowed_attrs)}."
            )
    return conds, params, applied


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def aggregate_stuck(check: str, status: str, filters: dict | None = None, group_by: str | None = None) -> dict:
    check = _check_choice(check, CHECKS + ("overall",), "check")
    status = _check_choice(status, STATUSES, "status")
    if check == "overall" and status in ("pending", "rejected"):
        raise ToolValidationError("For check=overall only status 'stuck' (overall failed) or 'passed' is valid.")
    if group_by is not None:
        group_options = sorted(list(FILTER_COLUMNS) + ["failure_reason"])
        group_by = _check_choice(group_by, group_options, "group_by")
        if check == "overall" and group_by == "failure_reason":
            raise ToolValidationError("group_by=failure_reason is not available for check=overall.")

    conds, params, applied = _validate_filters(filters)

    # Cohort = everyone matching the filters for whom the check applies.
    if check == "overall":
        status_col = "overall_status"
        match_cond = "overall_status = ?"
        match_params = ["passed" if status == "passed" else "failed"]
        cohort_conds = list(conds)
        note = "Cohort = all earners matching the filters. 'stuck' for overall means overall_status = failed."
    else:
        status_col = f"{check}_status"
        cohort_conds = conds + [f"{status_col} != 'not_applicable'"]
        if status == "stuck":
            match_cond, match_params = f"{status_col} IN ('pending', 'rejected')", []
        else:
            match_cond, match_params = f"{status_col} = ?", [status]
        note = (
            "Cohort = all earners matching the filters for whom this check applies "
            "(not_applicable rows are excluded). 'stuck' = pending or rejected."
        )

    where_cohort = " AND ".join(cohort_conds) or "1=1"
    where_match = f"{where_cohort} AND {match_cond}"

    result = {
        "check": check,
        "status": status,
        "filters_applied": applied,
        "denominator_note": note,
        "data_last_updated_at": data_last_updated_at(),
    }

    with connect() as conn:
        cohort_size = conn.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE {where_cohort}", params).fetchone()[0]
        if cohort_size == 0:
            return {**result, "cohort_size": 0, "count": 0, "pct": None, "no_data": True, "breakdown": []}
        count = conn.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE {where_match}", params + match_params).fetchone()[0]

        if group_by in FILTER_COLUMNS:
            col = FILTER_COLUMNS[group_by]
            rows = conn.execute(
                f"SELECT {col} AS k, COUNT(*) AS n FROM {TABLE} WHERE {where_match} GROUP BY {col} ORDER BY n DESC, k ASC",
                params + match_params,
            ).fetchall()
            breakdown_type, breakdown = f"by_{group_by}", [{group_by: r["k"], "count": r["n"], "pct": _pct(r["n"], count)} for r in rows]
        elif check == "overall":
            # No single reason for overall: show which individual checks are stuck among the matching earners.
            breakdown_type, breakdown = "by_check_stuck", []
            if status == "stuck":
                for c in CHECKS:
                    n = conn.execute(
                        f"SELECT COUNT(*) FROM {TABLE} WHERE {where_match} AND {c}_is_stuck = 1", params + match_params
                    ).fetchone()[0]
                    breakdown.append({"check": c, "count": n, "pct": _pct(n, count)})
                breakdown.sort(key=lambda b: (-b["count"], b["check"]))
        else:
            reason_col = f"{check}_failure_reason"
            limit = "" if group_by == "failure_reason" else f" LIMIT {TOP_N_REASONS}"
            rows = conn.execute(
                f"SELECT {reason_col} AS k, COUNT(*) AS n FROM {TABLE} WHERE {where_match} AND {reason_col} IS NOT NULL "
                f"GROUP BY {reason_col} ORDER BY n DESC, k ASC{limit}",
                params + match_params,
            ).fetchall()
            breakdown_type = "by_failure_reason" if group_by else "top_failure_reasons"
            breakdown = [{"failure_reason": r["k"], "count": r["n"], "pct": _pct(r["n"], count)} for r in rows]

    return {
        **result,
        "cohort_size": cohort_size,
        "count": count,
        "pct": _pct(count, cohort_size),
        "breakdown_type": breakdown_type,
        "breakdown_pct_note": "Breakdown pct is the share of 'count', not of cohort_size.",
        "breakdown": breakdown,
    }
