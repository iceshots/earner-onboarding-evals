import pytest

from bot.tools import dispatch, get_earner_status


def _pick(df, mask):
    return df[mask].iloc[0]


def test_failed_earner_matches_csv(df):
    row = _pick(df, df["overall_status"] == "failed")
    out = get_earner_status(row["earner_id"])
    assert out["found"] and out["overall_status"] == "failed"
    for c in out["checks"]:
        assert c["status"] == row[f"{c['check']}_status"]
        expected = row[f"{c['check']}_failure_reason"]
        assert c["failure_reason"] == (None if expected != expected else expected)  # NaN-safe
        if c["status"] in ("pending", "rejected"):
            assert c["failure_reason"]


def test_passed_earner_has_no_reasons(df):
    row = _pick(df, (df["overall_status"] == "passed") & (df["earner_type"] != "driver"))
    out = get_earner_status(row["earner_id"])
    assert out["overall_status"] == "passed"
    assert all(c["status"] == "passed" and c["failure_reason"] is None for c in out["checks"])


def test_driver_legal_entity_is_marked_not_applicable(df):
    row = _pick(df, df["earner_type"] == "driver")
    out = get_earner_status(row["earner_id"])
    legal = next(c for c in out["checks"] if c["check"] == "legal_entity")
    assert legal["status"] == "not_applicable" and legal["failure_reason"] is None and "note" in legal


@pytest.mark.parametrize("fmt", [lambda i: i.lower(), lambda i: f"  {i} \n", lambda i: i.lower().center(14)])
def test_id_normalisation(df, fmt):
    eid = df.iloc[7]["earner_id"]
    assert get_earner_status(fmt(eid))["earner_id"] == eid


@pytest.mark.parametrize("bad", ["P-99999", "P-00001", "", "P-1", "10482", "P-10482 OR 1=1", "'; DROP TABLE earner_onboarding; --", None, 123])
def test_unknown_or_hostile_id_is_not_found(bad):
    out = get_earner_status(bad)
    assert out["found"] is False and out["data_last_updated_at"] == "2026-10-29 00:00:00"
    assert "checks" not in out


def test_name_is_labelled_untrusted(df):
    out = get_earner_status(df.iloc[0]["earner_id"])
    assert "earner_name" not in out and "earner_name_untrusted" in out


def test_dispatch_wrong_arguments_returns_error():
    assert "error" in dispatch("get_earner_status", {"wrong": 1})
    assert "error" in dispatch("nope", {})
