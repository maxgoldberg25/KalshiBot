"""Kalshi contract and orderbook models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OutcomeSide(str, Enum):
    """Outcome side for binary contracts."""
    YES = "YES"
    NO = "NO"


class KalshiContract(BaseModel):
    """
    A Kalshi prediction market contract.
    
    Prices are normalized to decimals in [0, 1].
    """
    kalshi_market_id: str
    contract_id: str = Field(description="Kalshi ticker")
    title: str
    outcome_side: OutcomeSide
    close_time: datetime
    settlement_rules: str = ""
    status: str = "active"
    
    # Latest price (optional)
    last_price: Optional[float] = Field(default=None, ge=0, le=1)
    fetched_at: Optional[datetime] = None


class KalshiTopOfBook(BaseModel):
    """
    Top-of-book orderbook snapshot for a Kalshi contract.
    
    All prices in [0, 1].
    """
    contract_id: str
    
    # YES side
    yes_bid: Optional[float] = Field(default=None, ge=0, le=1)
    yes_ask: Optional[float] = Field(default=None, ge=0, le=1)
    yes_bid_size: int = 0
    yes_ask_size: int = 0
    
    # NO side
    no_bid: Optional[float] = Field(default=None, ge=0, le=1)
    no_ask: Optional[float] = Field(default=None, ge=0, le=1)
    no_bid_size: int = 0
    no_ask_size: int = 0
    
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    @property
    def is_valid(self) -> bool:
        """Check if we have usable YES side data."""
        return (
            self.yes_bid is not None
            and self.yes_ask is not None
            and self.yes_bid < self.yes_ask
            and self.yes_bid_size > 0
            and self.yes_ask_size > 0
        )
    
    @property
    def yes_mid(self) -> Optional[float]:
        """YES side mid price."""
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2.0
        return None


def cents_to_decimal(cents: int | float) -> float:
    """Convert Kalshi cents (0-100) to decimal (0-1)."""
    return cents / 100.0


def decimal_to_cents(dec: float) -> float:
    """Convert decimal (0-1) to cents (0-100)."""
    return dec * 100.0
