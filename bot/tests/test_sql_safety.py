import pytest

from bot.tools import dispatch, get_earner_status
from bot.tools.db import TABLE, connect, data_last_updated_at

HOSTILE = [
    "'; DROP TABLE earner_onboarding; --",
    "x' OR '1'='1",
    "region; DELETE FROM earner_onboarding",
    "\" OR 1=1 --",
    "APAC' UNION SELECT earner_name FROM earner_onboarding --",
]


def _count():
    with connect() as c:
        return c.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]


@pytest.mark.parametrize("bad", HOSTILE)
def test_hostile_strings_in_every_argument(bad):
    cases = [
        {"check": bad, "status": "stuck"},
        {"check": "shareholder", "status": bad},
        {"check": "shareholder", "status": "stuck", "group_by": bad},
        {"check": "shareholder", "status": "stuck", "filters": {bad: "APAC"}},
        {"check": "shareholder", "status": "stuck", "filters": {"region": bad}},
        {"check": "shareholder", "status": "stuck", "filters": {"start_date_from": bad}},
        {"check": "shareholder", "status": "stuck", "filters": {"start_month": bad}},
    ]
    for args in cases:
        assert "error" in dispatch("aggregate_stuck", args), args
    assert get_earner_status(bad)["found"] is False
    assert _count() == 20000


def test_connection_is_read_only():
    with connect() as c:
        with pytest.raises(Exception, match="readonly"):
            c.execute(f"DELETE FROM {TABLE}")
    assert _count() == 20000


def test_snapshot_timestamp():
    assert data_last_updated_at() == "2026-10-29 00:00:00"
