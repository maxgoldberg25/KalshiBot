"""Order and fill data models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    """Order side: buy YES or buy NO."""
    YES = "yes"
    NO = "no"


class OrderType(str, Enum):
    """Order type."""
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    """Order lifecycle status."""
    PENDING = "pending"          # Created, not yet submitted
    SUBMITTED = "submitted"      # Sent to exchange
    OPEN = "open"                # Active on orderbook
    PARTIALLY_FILLED = "partial" # Some quantity filled
    FILLED = "filled"            # Fully filled
    CANCELLED = "cancelled"      # Cancelled by user
    REJECTED = "rejected"        # Rejected by exchange
    EXPIRED = "expired"          # Expired without fill


class Order(BaseModel):
    """Trading order."""
    
    # Identifiers
    id: str = Field(default_factory=lambda: str(uuid4()))
    idempotency_key: str = Field(description="Unique key to prevent duplicate orders")
    kalshi_order_id: Optional[str] = Field(default=None, description="Exchange order ID")
    
    # Order details
    ticker: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    price: int = Field(description="Limit price in cents (1-99)")
    quantity: int = Field(description="Number of contracts")
    
    # Strategy info
    strategy_name: str = Field(default="")
    signal_confidence: float = Field(default=0.0)
    expected_value: float = Field(default=0.0)
    
    # Status tracking
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = Field(default=0)
    average_fill_price: Optional[float] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = Field(default=None)
    filled_at: Optional[datetime] = Field(default=None)
    
    # Error handling
    error_message: Optional[str] = Field(default=None)
    
    @property
    def is_complete(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    
    @property
    def remaining_quantity(self) -> int:
        """Quantity not yet filled."""
        return self.quantity - self.filled_quantity
    
    @property
    def notional_value(self) -> float:
        """Total order value in dollars."""
        return (self.price * self.quantity) / 100
    
    @property
    def fill_rate(self) -> float:
        """Percentage of order filled."""
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity
    
    def generate_idempotency_key(
        self,
        date: datetime,
        strategy: str
    ) -> str:
        """Generate idempotency key from date, ticker, and strategy."""
        date_str = date.strftime("%Y-%m-%d")
        return f"{date_str}:{self.ticker}:{strategy}:{self.side.value}"


class Fill(BaseModel):
    """Order fill (execution)."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    order_id: str
    kalshi_trade_id: Optional[str] = Field(default=None)
    
    ticker: str
    side: OrderSide
    price: int = Field(description="Fill price in cents")
    quantity: int = Field(description="Filled quantity")
    
    # Calculated fields
    notional: float = Field(description="Fill value in dollars")
    fees: float = Field(default=0.0, description="Exchange fees")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_order(
        cls,
        order: Order,
        fill_price: int,
        fill_quantity: int,
        kalshi_trade_id: Optional[str] = None,
        fees: float = 0.0,
    ) -> "Fill":
        """Create a fill from an order."""
        return cls(
            order_id=order.id,
            kalshi_trade_id=kalshi_trade_id,
            ticker=order.ticker,
            side=order.side,
            price=fill_price,
            quantity=fill_quantity,
            notional=(fill_price * fill_quantity) / 100,
            fees=fees,
        )
