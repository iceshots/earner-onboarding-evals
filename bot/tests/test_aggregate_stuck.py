import itertools

import pytest

from bot.tests.conftest import CHECKS, oracle
from bot.tools import aggregate_stuck, dispatch

STATUSES = ["stuck", "pending", "rejected", "passed"]
FILTER_SETS = [
    {},
    {"region": "APAC"},
    {"region": "APAC", "earner_type": "restaurant", "start_month": "2026-09"},
    {"earner_type": "driver"},
    {"onboarding_channel": "sales_assisted", "business_size": "small"},
    {"start_date_from": "2026-03-01", "start_date_to": "2026-05-31"},
]


def pct(a, b):
    return round(100 * a / b, 1)


@pytest.mark.parametrize("check,status,filters", list(itertools.product(CHECKS, STATUSES, FILTER_SETS)))
def test_check_counts_match_oracle(df, check, status, filters):
    cohort, match = oracle(df, check, status, filters)
    out = aggregate_stuck(check, status, filters)
    assert out["cohort_size"] == len(cohort)
    if len(cohort) == 0:
        assert out["no_data"] is True
        return
    assert out["count"] == len(match)
    assert out["pct"] == pct(len(match), len(cohort))
    assert out["filters_applied"] == filters
    assert "denominator_note" in out and out["data_last_updated_at"] == "2026-10-29 00:00:00"


@pytest.mark.parametrize("status", ["stuck", "passed"])
@pytest.mark.parametrize("filters", FILTER_SETS)
def test_overall_matches_oracle(df, status, filters):
    cohort, match = oracle(df, "overall", status, filters)
    out = aggregate_stuck("overall", status, filters)
    assert (out["cohort_size"], out["count"]) == (len(cohort), len(match))


def test_driver_legal_entity_cohort_excludes_not_applicable(df):
    out = aggregate_stuck("legal_entity", "stuck", {"earner_type": "driver"})
    assert out["cohort_size"] == 0 and out["no_data"] is True
    all_out = aggregate_stuck("legal_entity", "stuck")
    assert all_out["cohort_size"] == (df["earner_type"] != "driver").sum()


@pytest.mark.parametrize("check", CHECKS)
def test_top_reasons_match_oracle(df, check):
    _, match = oracle(df, check, "stuck", {"region": "Europe"})
    expected = match[f"{check}_failure_reason"].value_counts()
    out = aggregate_stuck(check, "stuck", {"region": "Europe"})
    assert out["breakdown_type"] == "top_failure_reasons" and len(out["breakdown"]) <= 5
    for item in out["breakdown"]:
        assert item["count"] == expected[item["failure_reason"]]
        assert item["pct"] == pct(item["count"], len(match))
    counts = [b["count"] for b in out["breakdown"]]
    assert counts == sorted(counts, reverse=True) and counts[0] == expected.max()


@pytest.mark.parametrize("check", CHECKS)
def test_group_by_failure_reason_is_complete(df, check):
    _, match = oracle(df, check, "rejected")
    out = aggregate_stuck(check, "rejected", group_by="failure_reason")
    assert {b["failure_reason"]: b["count"] for b in out["breakdown"]} == match[f"{check}_failure_reason"].value_counts().to_dict()
    assert sum(b["count"] for b in out["breakdown"]) == out["count"]


@pytest.mark.parametrize("group_by", ["region", "earner_type", "business_size", "onboarding_channel", "start_month", "start_week"])
def test_group_by_attribute_matches_oracle(df, group_by):
    _, match = oracle(df, "payment_profile", "stuck")
    out = aggregate_stuck("payment_profile", "stuck", group_by=group_by)
    assert {b[group_by]: b["count"] for b in out["breakdown"]} == match[group_by].value_counts().to_dict()
    assert all(b["pct"] == pct(b["count"], out["count"]) for b in out["breakdown"])


def test_overall_breakdown_by_check(df):
    _, match = oracle(df, "overall", "stuck")
    out = aggregate_stuck("overall", "stuck")
    assert out["breakdown_type"] == "by_check_stuck"
    for b in out["breakdown"]:
        assert b["count"] == (match[f"{b['check']}_is_stuck"] == "1").sum()


def test_passed_status_has_no_reason_breakdown():
    assert aggregate_stuck("shareholder", "passed")["breakdown"] == []


def test_cohort_of_one_constructed(df):
    # Use a date range that isolates one specific start_date + week + type combination and check exactness against oracle.
    sizes = df.groupby(["start_date", "earner_type", "region", "business_size", "onboarding_channel"]).size()
    key = sizes[sizes == 1].index[0]
    filters = dict(zip(["start_date_from", "earner_type", "region", "business_size", "onboarding_channel"], key))
    filters["start_date_to"] = key[0]
    cohort, match = oracle(df, "overall", "stuck", filters)
    assert len(cohort) == 1
    out = aggregate_stuck("overall", "stuck", filters)
    assert out["cohort_size"] == 1 and out["count"] == len(match) and out["pct"] in (0.0, 100.0)


def test_empty_cohort():
    out = aggregate_stuck("shareholder", "stuck", {"start_date_from": "2030-01-01"})
    assert out["no_data"] is True and out["cohort_size"] == 0


def test_filter_value_is_case_insensitive_canonicalised(df):
    assert aggregate_stuck("shareholder", "stuck", {"region": " apac "})["filters_applied"] == {"region": "APAC"}


@pytest.mark.parametrize("filters", [{"region": "Asia Pacific"}, {"region": "NA"}, {"region": "Nort America"}, {"earner_type": "bike"}])
def test_bad_filter_value_lists_valid_values(filters):
    out = dispatch("aggregate_stuck", {"check": "shareholder", "status": "stuck", "filters": filters})
    assert "Valid values" in out["error"]


@pytest.mark.parametrize("attr", ["city", "agent", "document_type", "country"])
def test_unknown_attribute(attr):
    out = dispatch("aggregate_stuck", {"check": "shareholder", "status": "stuck", "filters": {attr: "x"}})
    assert "not in the data" in out["error"]


@pytest.mark.parametrize("args", [
    {"check": "address", "status": "stuck"},
    {"check": "shareholder", "status": "failed"},
    {"check": "overall", "status": "pending"},
    {"check": "overall", "status": "stuck", "group_by": "failure_reason"},
    {"check": "shareholder", "status": "stuck", "group_by": "city"},
    {"check": "shareholder", "status": "stuck", "filters": {"start_date_from": "yesterday"}},
    {"check": "shareholder", "status": "stuck", "filters": {"start_date_from": "2026-02-31"}},
    {"check": "shareholder", "status": "stuck", "filters": "region=APAC"},
])
def test_invalid_arguments_return_error(args):
    assert "error" in dispatch("aggregate_stuck", args)
