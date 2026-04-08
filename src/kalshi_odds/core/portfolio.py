"""Position and P&L models for tracked Kalshi legs."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from kalshi_odds.models.comparison import Direction


class PositionStatus(str, Enum):
    OPEN = "open"
    SETTLED = "settled"
    CANCELLED = "cancelled"


class Position(BaseModel):
    """A recorded Kalshi leg (from scanner execution or manual)."""

    id: Optional[int] = None
    ticker: str
    direction: Direction
    shares: int = Field(ge=0)
    entry_price_cents: int = Field(ge=1, le=99)
    market_key: str = ""
    status: PositionStatus = PositionStatus.OPEN
    entered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    settled_at: Optional[datetime] = None
    realized_pnl: Optional[float] = None
    notes: str = ""


class PnLSummary(BaseModel):
    """Aggregate realized P&L from settled positions."""

    total_realized_pnl: float
    settled_count: int
    open_count: int
    winning_count: int
    losing_count: int
