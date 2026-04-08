"""
Kelly Criterion position sizing for Kalshi YES contracts.

Uses fractional Kelly (default quarter-Kelly) on the probability edge vs. execution price.
"""

from __future__ import annotations

from kalshi_odds.models.comparison import Direction


def kelly_full_fraction(edge_bps: float, price_cents: int, direction: Direction) -> float:
    """
    Full Kelly fraction of bankroll for a binary Kalshi YES contract.

    - KALSHI_CHEAP (buy YES): f* = edge / (1 - p) where p is YES price in (0,1).
    - KALSHI_RICH (sell YES): f* = edge / p where edge is (bid - fair) in probability units.

    edge_bps is the scanner's edge in basis points (edge * 10_000).
    """
    if price_cents <= 0 or price_cents >= 100:
        return 0.0
    p = price_cents / 100.0
    edge = edge_bps / 10_000.0
    if edge <= 0:
        return 0.0

    if direction == Direction.KALSHI_CHEAP:
        denom = 1.0 - p
        if denom <= 0:
            return 0.0
        return edge / denom
    # KALSHI_RICH: sell YES
    if p <= 0:
        return 0.0
    return edge / p


def kelly_shares(
    edge_bps: float,
    price_cents: int,
    direction: Direction,
    bankroll_dollars: float,
    kelly_fraction: float = 0.25,
    max_notional: float = 100.0,
    max_shares: int | None = None,
) -> int:
    """
    Integer share count from fractional Kelly, capped by max_notional and optional liquidity.

    Cost per share ≈ price_cents/100 dollars for buy YES; for sizing we use the same
    notional cap for sell YES (exposure per share at the limit price).
    """
    if bankroll_dollars <= 0:
        return 0

    f_full = kelly_full_fraction(edge_bps, price_cents, direction)
    if f_full <= 0:
        return 0

    stake_fraction = min(kelly_fraction * f_full, 1.0)
    notional = bankroll_dollars * stake_fraction
    notional = min(notional, max_notional)

    p_dollars = price_cents / 100.0
    if p_dollars <= 0:
        return 0

    shares = int(notional / p_dollars)
    if shares < 1 and notional >= p_dollars * 0.99:
        shares = 1

    if max_shares is not None:
        shares = min(shares, max_shares)

    return max(0, shares)
