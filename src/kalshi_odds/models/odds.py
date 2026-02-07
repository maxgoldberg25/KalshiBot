"""Sportsbook odds quote models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OddsFormat(str, Enum):
    """Odds format types."""
    AMERICAN = "american"  # e.g., -110, +150
    DECIMAL = "decimal"    # e.g., 1.91, 2.50
    FRACTIONAL = "fractional"  # e.g., 10/11, 3/2


class MarketType(str, Enum):
    """Sportsbook market types."""
    H2H = "h2h"  # Head-to-head (moneyline)
    SPREADS = "spreads"
    TOTALS = "totals"
    OUTRIGHTS = "outrights"  # Futures
    PLAYER_PROPS = "player_props"


class OddsQuote(BaseModel):
    """
    A single odds quote from a sportsbook via an aggregator.
    
    Raw odds value as returned by the API.
    """
    source: str = Field(description="Odds aggregator (e.g., 'theoddsapi')")
    bookmaker: str = Field(description="Bookmaker name (e.g., 'draftkings')")
    
    event_id: str = Field(description="Aggregator's event ID")
    market_type: MarketType
    selection: str = Field(description="Selection name (team, player, outcome)")
    
    odds_format: OddsFormat
    odds_value: float = Field(description="Raw odds value")
    
    # Optional point/line for spreads/totals
    point: Optional[float] = None
    
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    # Metadata
    event_title: str = ""
    sport: str = ""
    commence_time: Optional[datetime] = None
