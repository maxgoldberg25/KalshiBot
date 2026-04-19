"""Shared Kalshi order placement for opportunities (CLI + dashboard)."""

from __future__ import annotations

from kalshi_odds.adapters.kalshi import kalshi_adapter_from_settings
from kalshi_odds.config import Settings
from kalshi_odds.core.portfolio import Position, PositionStatus
from kalshi_odds.db import AnyRepository
from kalshi_odds.models.comparison import Direction, Opportunity


async def place_opportunity_order(
    opp: Opportunity,
    shares: int,
    *,
    dry_run: bool,
    settings: Settings,
    repo: AnyRepository | None = None,
    save_position: bool = True,
) -> dict:
    """
    Place the Kalshi leg for an opportunity. If save_position and repo given, record OPEN row.
    """
    if dry_run:
        return {"dry_run": True, "ticker": opp.kalshi_ticker, "shares": shares, "action": opp.kalshi_action}

    if not settings.execution_enabled:
        raise RuntimeError("Execution disabled. Set KALSHI_ODDS_EXECUTION_ENABLED=true")

    side = "yes"
    action = "sell" if opp.direction == Direction.KALSHI_RICH else "buy"
    price_cents = max(1, min(99, opp.kalshi_price_cents))

    async with kalshi_adapter_from_settings(settings) as kalshi:
        result = await kalshi.place_order(
            ticker=opp.kalshi_ticker,
            side=side,
            action=action,
            count=shares,
            yes_price=price_cents,
        )

    if save_position and repo is not None:
        pos = Position(
            ticker=opp.kalshi_ticker,
            direction=opp.direction,
            shares=shares,
            entry_price_cents=price_cents,
            market_key=opp.market_key,
            status=PositionStatus.OPEN,
            notes="kalshi_odds",
        )
        await repo.save_position(pos)

    return {"order": result, "ticker": opp.kalshi_ticker, "shares": shares}
