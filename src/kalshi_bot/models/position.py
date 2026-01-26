"""Position and PnL tracking models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from kalshi_bot.models.order import OrderSide


class Position(BaseModel):
    """Current position in a market."""
    
    ticker: str
    side: OrderSide
    quantity: int = Field(default=0, description="Number of contracts")
    average_entry_price: float = Field(description="Average entry price in cents")
    
    # Market state
    current_price: Optional[int] = Field(default=None)
    
    # Tracking
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    @computed_field
    @property
    def cost_basis(self) -> float:
        """Total cost in dollars."""
        return (self.average_entry_price * self.quantity) / 100
    
    @computed_field
    @property
    def current_value(self) -> Optional[float]:
        """Current value in dollars based on current price."""
        if self.current_price is None:
            return None
        return (self.current_price * self.quantity) / 100
    
    @computed_field
    @property
    def unrealized_pnl(self) -> Optional[float]:
        """Unrealized profit/loss in dollars."""
        if self.current_value is None:
            return None
        return self.current_value - self.cost_basis
    
    @computed_field
    @property
    def unrealized_pnl_percent(self) -> Optional[float]:
        """Unrealized P&L as percentage."""
        if self.unrealized_pnl is None or self.cost_basis == 0:
            return None
        return self.unrealized_pnl / self.cost_basis
    
    def update_price(self, price: int) -> None:
        """Update current market price."""
        self.current_price = price
        self.last_updated = datetime.utcnow()
    
    def add_quantity(self, quantity: int, price: float) -> None:
        """Add to position (new fill)."""
        total_cost = (self.average_entry_price * self.quantity) + (price * quantity)
        self.quantity += quantity
        if self.quantity > 0:
            self.average_entry_price = total_cost / self.quantity
        self.last_updated = datetime.utcnow()
    
    def reduce_quantity(self, quantity: int) -> None:
        """Reduce position (partial close or settlement)."""
        self.quantity = max(0, self.quantity - quantity)
        self.last_updated = datetime.utcnow()


class DailyPnL(BaseModel):
    """Daily profit and loss record."""
    
    date: datetime
    
    # P&L components
    realized_pnl: float = Field(default=0.0, description="P&L from closed positions")
    unrealized_pnl: float = Field(default=0.0, description="P&L from open positions")
    fees: float = Field(default=0.0, description="Total fees paid")
    
    # Trade stats
    trades_placed: int = Field(default=0)
    trades_filled: int = Field(default=0)
    trades_won: int = Field(default=0)
    trades_lost: int = Field(default=0)
    
    # Exposure
    peak_exposure: float = Field(default=0.0, description="Maximum capital at risk")
    ending_exposure: float = Field(default=0.0, description="EOD capital at risk")
    
    # Markets traded
    markets_traded: list[str] = Field(default_factory=list)
    
    @computed_field
    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized - fees)."""
        return self.realized_pnl + self.unrealized_pnl - self.fees
    
    @computed_field
    @property
    def win_rate(self) -> Optional[float]:
        """Win rate for completed trades."""
        total = self.trades_won + self.trades_lost
        if total == 0:
            return None
        return self.trades_won / total
    
    @computed_field
    @property
    def fill_rate(self) -> Optional[float]:
        """Fill rate for placed orders."""
        if self.trades_placed == 0:
            return None
        return self.trades_filled / self.trades_placed
    
    def record_trade(self, won: bool, pnl: float) -> None:
        """Record a completed trade."""
        if won:
            self.trades_won += 1
        else:
            self.trades_lost += 1
        self.realized_pnl += pnl
    
    def update_exposure(self, exposure: float) -> None:
        """Update exposure tracking."""
        self.ending_exposure = exposure
        if exposure > self.peak_exposure:
            self.peak_exposure = exposure
