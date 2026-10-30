"""Shared fixtures. The oracle is pandas over the pinned CSV, independent of the SQLite tools."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CHECKS = ("legal_entity", "shareholder", "payment_profile")


@pytest.fixture(scope="session")
def df() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "output" / "earner_onboarding.csv", dtype=str, keep_default_na=False, na_values=[""])


def oracle(df, check, status, filters=None):
    """Independent pandas computation: returns (cohort_df, matching_df)."""
    d = df
    for k, v in (filters or {}).items():
        if k == "start_date_from":
            d = d[d["start_date"] >= v]
        elif k == "start_date_to":
            d = d[d["start_date"] <= v]
        else:
            d = d[d[k] == v]
    if check == "overall":
        col, stuck_vals = "overall_status", {"failed"}
    else:
        d = d[d[f"{check}_status"] != "not_applicable"]
        col, stuck_vals = f"{check}_status", {"pending", "rejected"}
    cohort = d
    match = d[d[col].isin(stuck_vals)] if status == "stuck" else d[d[col] == status]
    return cohort, match
