"""Market and orderbook data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class OrderBookLevel(BaseModel):
    """Single level in the orderbook."""
    
    price: int = Field(description="Price in cents (1-99)")
    quantity: int = Field(description="Number of contracts")


class OrderBook(BaseModel):
    """Orderbook with bids and asks for YES contracts."""
    
    yes_bids: list[OrderBookLevel] = Field(default_factory=list)
    yes_asks: list[OrderBookLevel] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @computed_field
    @property
    def best_bid(self) -> Optional[int]:
        """Best (highest) bid price for YES."""
        if not self.yes_bids:
            return None
        return max(level.price for level in self.yes_bids)
    
    @computed_field
    @property
    def best_ask(self) -> Optional[int]:
        """Best (lowest) ask price for YES."""
        if not self.yes_asks:
            return None
        return min(level.price for level in self.yes_asks)
    
    @computed_field
    @property
    def spread(self) -> Optional[int]:
        """Bid-ask spread in cents."""
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid
    
    @computed_field
    @property
    def mid_price(self) -> Optional[float]:
        """Mid-point price."""
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2
    
    @property
    def implied_probability(self) -> Optional[float]:
        """Implied probability of YES from mid-price."""
        if self.mid_price is None:
            return None
        return self.mid_price / 100
    
    @property
    def bid_depth(self) -> int:
        """Total quantity at all bid levels."""
        return sum(level.quantity for level in self.yes_bids)
    
    @property
    def ask_depth(self) -> int:
        """Total quantity at all ask levels."""
        return sum(level.quantity for level in self.yes_asks)
    
    @property
    def total_depth(self) -> int:
        """Total orderbook depth."""
        return self.bid_depth + self.ask_depth


class Market(BaseModel):
    """Kalshi market with metadata and orderbook."""
    
    ticker: str = Field(description="Market ticker symbol")
    title: str = Field(description="Human-readable title")
    subtitle: str = Field(default="")
    category: str = Field(default="")
    event_ticker: str = Field(default="")
    
    # Status
    status: str = Field(default="active")
    result: Optional[str] = Field(default=None, description="Settlement result if settled")
    
    # Timing
    close_time: Optional[datetime] = Field(default=None)
    expiration_time: Optional[datetime] = Field(default=None)
    
    # Market data
    last_price: int = Field(default=50, description="Last traded price in cents")
    volume: int = Field(default=0, description="Total volume")
    volume_24h: int = Field(default=0, description="24h volume")
    open_interest: int = Field(default=0)
    
    # Orderbook (optional, populated separately)
    orderbook: Optional[OrderBook] = Field(default=None)
    
    @computed_field
    @property
    def implied_probability(self) -> float:
        """Implied probability from last price."""
        return self.last_price / 100
    
    def expires_today(self, reference_date: datetime) -> bool:
        """Check if market expires on the reference date."""
        if self.expiration_time is None:
            return False
        return self.expiration_time.date() == reference_date.date()
    
    def minutes_until_close(self, now: datetime) -> Optional[int]:
        """Minutes until market closes."""
        if self.close_time is None:
            return None
        delta = self.close_time - now
        return int(delta.total_seconds() / 60)
    
    def is_liquid(
        self,
        min_volume: int = 100,
        max_spread: int = 10,
        min_depth: int = 50
    ) -> bool:
        """Check if market meets liquidity thresholds."""
        if self.volume_24h < min_volume:
            return False
        
        if self.orderbook is None:
            return False
        
        if self.orderbook.spread is None or self.orderbook.spread > max_spread:
            return False
        
        if self.orderbook.total_depth < min_depth:
            return False
        
        return True
    
    def to_features(self) -> dict:
        """Extract features for strategy evaluation."""
        features = {
            "ticker": self.ticker,
            "last_price": self.last_price,
            "implied_prob": self.implied_probability,
            "volume_24h": self.volume_24h,
            "open_interest": self.open_interest,
        }
        
        if self.orderbook:
            features.update({
                "spread": self.orderbook.spread,
                "mid_price": self.orderbook.mid_price,
                "bid_depth": self.orderbook.bid_depth,
                "ask_depth": self.orderbook.ask_depth,
                "depth_imbalance": (
                    (self.orderbook.bid_depth - self.orderbook.ask_depth) /
                    max(self.orderbook.total_depth, 1)
                ),
            })
        
        return features
