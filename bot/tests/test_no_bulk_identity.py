import itertools

from bot.tests.conftest import CHECKS
from bot.tools import TOOL_FUNCTIONS, aggregate_stuck, get_earner_status

IDENTITY_KEYS = {"earner_id", "earner_name", "earner_name_untrusted"}


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def test_aggregate_never_returns_identity_keys():
    for check, status, group_by in itertools.product(CHECKS + ("overall",), ("stuck", "passed"), (None, "region", "start_week")):
        out = aggregate_stuck(check, status, {"region": "Europe"}, group_by)
        assert not IDENTITY_KEYS & set(_keys(out))


def test_only_two_tools_and_no_listing_tool():
    assert set(TOOL_FUNCTIONS) == {"get_earner_status", "aggregate_stuck"}


def test_lookup_returns_exactly_one_earner(df):
    for bad in ["P-1%", "P-1*", "P-10001,P-10002", ["P-10001", "P-10002"]]:
        assert get_earner_status(bad)["found"] is False
    out = get_earner_status("P-10001")
    assert out["earner_id"] == "P-10001"
    assert [k for k in _keys(out) if k in IDENTITY_KEYS] == ["earner_id", "earner_name_untrusted"]
