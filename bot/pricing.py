"""Model prices in one place. USD per 1M tokens.

Source: Anthropic model pricing table in the claude-api reference (cached 2026-10-06); re-check
https://platform.claude.com/docs/en/about-claude/pricing before relying on cost numbers.
Cache reads/writes are not used by Bot A, so they are not priced here.
"""

PRICES_PER_MTOK = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Cost of one call, or None if the model is not in the table (never guess a price)."""
    p = PRICES_PER_MTOK.get(model)
    if p is None:
        return None
    return round((input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000, 6)
