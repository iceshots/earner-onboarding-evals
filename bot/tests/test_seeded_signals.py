"""The three regional patterns seeded in the data must be visible through the aggregate tool."""
from bot.tools import aggregate_stuck

REGIONS = ["Europe", "APAC", "North America"]


def _share(check, status, reason, region):
    out = aggregate_stuck(check, status, {"region": region}, group_by="failure_reason")
    hit = next((b for b in out["breakdown"] if b["failure_reason"] == reason), None)
    return hit["pct"] if hit else 0.0


def _top_region(check, status, reason):
    return max(REGIONS, key=lambda r: _share(check, status, reason, r))


def test_europe_document_expired_on_legal_entity_rejections():
    assert _top_region("legal_entity", "rejected", "document_expired") == "Europe"


def test_apac_account_name_mismatch_on_payment_profile_rejections():
    assert _top_region("payment_profile", "rejected", "account_name_mismatch") == "APAC"


def test_north_america_awaiting_agent_review_among_pending():
    for check in ("legal_entity", "shareholder", "payment_profile"):
        assert _top_region(check, "pending", "awaiting_agent_review") == "North America"
