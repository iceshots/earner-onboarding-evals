"""Read-only access to the SQLite snapshot, plus the allow-lists the tools validate against."""
import os
import sqlite3
from functools import lru_cache
from pathlib import Path

DB_PATH = Path(os.environ.get("EARNER_DB_PATH") or Path(__file__).resolve().parents[2] / "data" / "output" / "earner_onboarding.sqlite")
TABLE = "earner_onboarding"

CHECKS = ("legal_entity", "shareholder", "payment_profile")

# Attributes the model may filter or group by -> real column names. Column names in SQL come only from here.
FILTER_COLUMNS = {
    "region": "region",
    "earner_type": "earner_type",
    "business_size": "business_size",
    "onboarding_channel": "onboarding_channel",
    "start_month": "start_month",
    "start_week": "start_week",
}


def connect() -> sqlite3.Connection:
    """Open a read-only connection. Writes fail at the SQLite level."""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=1)
def valid_values() -> dict[str, list[str]]:
    """Distinct real values per filter attribute (the allow-list for filter values)."""
    with connect() as conn:
        return {
            attr: [r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM {TABLE} ORDER BY 1")]
            for attr, col in FILTER_COLUMNS.items()
        }


@lru_cache(maxsize=1)
def data_last_updated_at() -> str:
    with connect() as conn:
        return conn.execute(f"SELECT MAX(data_last_updated_at) FROM {TABLE}").fetchone()[0]
