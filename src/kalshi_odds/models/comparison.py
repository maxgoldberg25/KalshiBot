"""Comparison and alert models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
    """Direction of price discrepancy."""
    KALSHI_CHEAP = "kalshi_cheap"  # Kalshi YES < sportsbook no-vig prob
    KALSHI_RICH = "kalshi_rich"    # Kalshi YES > sportsbook no-vig prob


class Confidence(str, Enum):
    """Alert confidence level."""
    LOW = "low"
    MED = "med"
    HIGH = "high"


class Comparison(BaseModel):
    """
    A price comparison between Kalshi and sportsbook.
    """
    market_key: str
    
    # Kalshi side
    kalshi_contract_id: str
    kalshi_side: str  # "YES" or "NO"
    kalshi_price: float = Field(ge=0, le=1, description="Kalshi price used (bid or ask)")
    kalshi_price_adj: float = Field(ge=0, le=1, description="After slippage buffer")
    
    # Sportsbook side
    sportsbook_bookmaker: str
    sportsbook_selection: str
    sportsbook_p_no_vig: float = Field(ge=0, le=1)
    
    # Edge
    edge_bps: float = Field(description="Edge in basis points")
    edge_pct: float = Field(description="Edge as percentage")
    
    # Assumptions
    assumptions: list[str] = Field(default_factory=list)
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Alert(BaseModel):
    """
    A triggered alert for a price discrepancy.
    """
    alert_id: str = Field(description="Unique alert ID")
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    market_key: str
    direction: Direction
    
    # Edge metrics
    edge_pct: float
    edge_bps: float
    
    # Confidence
    confidence: Confidence
    confidence_score: float = Field(ge=0, le=1)
    
    # Details
    kalshi_contract_id: str
    kalshi_side: str
    kalshi_price: float
    kalshi_liquidity: int = Field(description="Size available")
    
    sportsbook_bookmaker: str
    sportsbook_selection: str
    sportsbook_p_no_vig: float
    
    # Metadata
    notes: str = ""
    raw_snapshot_refs: dict = Field(default_factory=dict)
    
    # Freshness
    kalshi_data_age_seconds: float
    sportsbook_data_age_seconds: float


class Opportunity(BaseModel):
    """
    Aggregated actionable opportunity (one per game-side).
    Consolidates multiple raw alerts into a single trade instruction.
    """
    market_key: str
    game_label: str = Field(description='e.g. "Thunder vs Rockets"')

    direction: Direction

    # Kalshi action
    kalshi_action: str = Field(description='e.g. "BUY Thunder YES @ 68c" or "SELL Thunder YES @ 66c"')
    kalshi_ticker: str
    kalshi_price_cents: int = Field(ge=0, le=100)
    kalshi_spread_cents: int = Field(ge=0, le=100)
    kalshi_liquidity: int = Field(ge=0)

    # Sportsbook consensus
    book_fair_prob: float = Field(ge=0, le=1)
    book_count: int = Field(ge=0)
    book_best: str = Field(description='e.g. "DraftKings +170"')
    book_worst: str = Field(description='e.g. "MyBookie +220"')

    # Edge
    edge_cents: float = Field(description="Cents per share edge")
    edge_bps: float = Field(description="Basis points edge")

    # Hedge instruction
    hedge_action: str = Field(description='e.g. "Bet Thunder ML on DraftKings at -220"')
    hedge_odds: str = Field(description='e.g. "-220"')

    # P&L projection
    pnl_per_100_shares: float = Field(description="Expected edge in dollars per 100 shares")
    max_shares: int = Field(ge=0, description="Limited by Kalshi liquidity")

    # Scoring
    confidence: Confidence
    rank_score: float = Field(description="Composite score for sorting")

    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_alert_count: int = Field(ge=0)
    kalshi_url: str = Field(default="", description="Link to Kalshi market page")
