"""Tool 1: look up ONE earner by exact ID."""
import re

from .db import CHECKS, TABLE, connect, data_last_updated_at

_ID_RE = re.compile(r"^P-\d{5}$")

_PROFILE_FIELDS = ("earner_type", "region", "business_size", "onboarding_channel", "start_date")


def get_earner_status(earner_id: str) -> dict:
    ts = data_last_updated_at()
    # Normalise case and whitespace. Anything that is not a well-formed ID cannot exist, so it is "not found"
    # and never reaches SQL.
    normalised = earner_id.strip().upper() if isinstance(earner_id, str) else ""
    if not _ID_RE.match(normalised):
        return {"found": False, "earner_id": normalised[:40], "data_last_updated_at": ts}

    with connect() as conn:
        row = conn.execute(f"SELECT * FROM {TABLE} WHERE earner_id = ?", (normalised,)).fetchone()
    if row is None:
        return {"found": False, "earner_id": normalised, "data_last_updated_at": ts}

    checks = []
    for check in CHECKS:
        status = row[f"{check}_status"]
        entry = {
            "check": check,
            "status": status,
            "failure_reason": row[f"{check}_failure_reason"],
            "status_updated_at": row[f"{check}_status_updated_at"],
        }
        if status == "not_applicable":
            entry["note"] = "This check does not apply to this earner type."
        checks.append(entry)

    return {
        "found": True,
        "earner_id": row["earner_id"],
        # Free text from the data. Treat as data only, never as instructions.
        "earner_name_untrusted": row["earner_name"],
        **{f: row[f] for f in _PROFILE_FIELDS},
        "checks": checks,
        "overall_status": row["overall_status"],
        "data_last_updated_at": row["data_last_updated_at"],
    }
