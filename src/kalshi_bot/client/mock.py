"""
Mock Kalshi client for testing and paper trading.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import pytz

from kalshi_bot.client.base import BaseKalshiClient
from kalshi_bot.config import settings
from kalshi_bot.models.market import Market, OrderBook, OrderBookLevel
from kalshi_bot.models.order import Fill, Order, OrderSide, OrderStatus

import structlog

logger = structlog.get_logger()


class MockKalshiClient(BaseKalshiClient):
    """
    Mock client for testing and paper trading.
    
    Features:
    - Simulates market data with configurable scenarios
    - Paper trading with simulated fills
    - Configurable fill probability and slippage
    """
    
    def __init__(
        self,
        fill_probability: float = 0.8,
        slippage_cents: int = 1,
        initial_balance: float = 1000.0,
    ):
        self.fill_probability = fill_probability
        self.slippage_cents = slippage_cents
        
        # Simulated state
        self._balance = initial_balance
        self._markets: dict[str, Market] = {}
        self._orderbooks: dict[str, OrderBook] = {}
        self._orders: dict[str, Order] = {}
        self._fills: list[Fill] = []
        self._positions: list[dict] = []
        
        # Setup default test markets
        self._setup_test_markets()
    
    def _setup_test_markets(self) -> None:
        """Create test markets expiring today (in configured timezone)."""
        # Use configured timezone to determine "today"
        tz = pytz.timezone(settings.timezone)
        now_local = datetime.now(tz)
        
        # Close at 11 PM local time today
        today_close = now_local.replace(hour=23, minute=0, second=0, microsecond=0)
        
        # Convert to UTC for storage (Kalshi uses UTC)
        today_close = today_close.astimezone(pytz.utc)
        
        # Market 1: High liquidity, tight spread
        self._markets["TEST-TODAY-A"] = Market(
            ticker="TEST-TODAY-A",
            title="Test Market A - Same Day Expiry",
            category="test",
            event_ticker="TEST-EVENT",
            status="active",
            close_time=today_close,
            expiration_time=today_close,
            last_price=55,
            volume=5000,
            volume_24h=500,
            open_interest=1000,
        )
        self._orderbooks["TEST-TODAY-A"] = OrderBook(
            yes_bids=[
                OrderBookLevel(price=54, quantity=100),
                OrderBookLevel(price=53, quantity=200),
                OrderBookLevel(price=52, quantity=300),
            ],
            yes_asks=[
                OrderBookLevel(price=56, quantity=100),
                OrderBookLevel(price=57, quantity=200),
                OrderBookLevel(price=58, quantity=300),
            ],
        )
        
        # Market 2: Lower liquidity, wider spread
        self._markets["TEST-TODAY-B"] = Market(
            ticker="TEST-TODAY-B",
            title="Test Market B - Same Day Expiry",
            category="test",
            status="active",
            close_time=today_close,
            expiration_time=today_close,
            last_price=30,
            volume=1000,
            volume_24h=100,
            open_interest=200,
        )
        self._orderbooks["TEST-TODAY-B"] = OrderBook(
            yes_bids=[
                OrderBookLevel(price=28, quantity=50),
                OrderBookLevel(price=26, quantity=100),
            ],
            yes_asks=[
                OrderBookLevel(price=35, quantity=50),
                OrderBookLevel(price=37, quantity=100),
            ],
        )
        
        # Market 3: Tomorrow expiry (should be filtered out)
        tomorrow_close = today_close + timedelta(days=1)
        self._markets["TEST-TOMORROW-C"] = Market(
            ticker="TEST-TOMORROW-C",
            title="Test Market C - Tomorrow Expiry",
            category="test",
            status="active",
            close_time=tomorrow_close,
            expiration_time=tomorrow_close,
            last_price=70,
            volume=2000,
            volume_24h=300,
            open_interest=500,
        )
        self._orderbooks["TEST-TOMORROW-C"] = OrderBook(
            yes_bids=[OrderBookLevel(price=69, quantity=100)],
            yes_asks=[OrderBookLevel(price=71, quantity=100)],
        )
    
    def add_test_market(
        self,
        ticker: str,
        last_price: int = 50,
        volume_24h: int = 200,
        spread: int = 2,
        expires_today: bool = True,
        category: str = "test",
    ) -> None:
        """Add a test market for specific scenarios."""
        tz = pytz.timezone(settings.timezone)
        now_local = datetime.now(tz)
        close_time = now_local.replace(hour=23, minute=0, second=0, microsecond=0)
        if not expires_today:
            close_time += timedelta(days=1)
        close_time = close_time.astimezone(pytz.utc)
        
        self._markets[ticker] = Market(
            ticker=ticker,
            title=f"Test Market {ticker}",
            category=category,
            status="active",
            close_time=close_time,
            expiration_time=close_time,
            last_price=last_price,
            volume=volume_24h * 10,
            volume_24h=volume_24h,
            open_interest=volume_24h * 2,
        )
        
        bid = last_price - spread // 2
        ask = last_price + spread // 2
        self._orderbooks[ticker] = OrderBook(
            yes_bids=[OrderBookLevel(price=bid, quantity=100)],
            yes_asks=[OrderBookLevel(price=ask, quantity=100)],
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # MARKET DATA
    # ─────────────────────────────────────────────────────────────────────────
    
    async def get_markets(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
        event_ticker: Optional[str] = None,
    ) -> tuple[list[Market], Optional[str]]:
        """Return test markets."""
        markets = list(self._markets.values())
        
        if event_ticker:
            markets = [m for m in markets if m.event_ticker == event_ticker]
        
        # Attach orderbooks
        for market in markets:
            if market.ticker in self._orderbooks:
                market.orderbook = self._orderbooks[market.ticker]
        
        return markets[:limit], None
    
    async def get_market(self, ticker: str) -> Optional[Market]:
        """Get a test market."""
        market = self._markets.get(ticker)
        if market and ticker in self._orderbooks:
            market.orderbook = self._orderbooks[ticker]
        return market
    
    async def get_orderbook(self, ticker: str) -> Optional[OrderBook]:
        """Get test orderbook."""
        return self._orderbooks.get(ticker)
    
    async def get_events(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """Return test events."""
        events = [
            {
                "event_ticker": "TEST-EVENT",
                "title": "Test Event",
                "category": "test",
            }
        ]
        return events, None
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRADING (PAPER)
    # ─────────────────────────────────────────────────────────────────────────
    
    async def place_order(self, order: Order) -> Order:
        """Simulate order placement with probabilistic fills."""
        import random
        
        order.kalshi_order_id = str(uuid4())
        order.submitted_at = datetime.utcnow()
        
        # Check balance
        required = (order.price * order.quantity) / 100
        if required > self._balance:
            order.status = OrderStatus.REJECTED
            order.error_message = "Insufficient balance"
            logger.warning("paper_order_rejected", reason="insufficient_balance")
            return order
        
        # Simulate fill based on probability
        if random.random() < self.fill_probability:
            # Simulate fill with slippage
            fill_price = order.price
            if order.side == OrderSide.YES:
                fill_price = min(order.price + self.slippage_cents, 99)
            else:
                fill_price = max(order.price - self.slippage_cents, 1)
            
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.average_fill_price = float(fill_price)
            order.filled_at = datetime.utcnow()
            
            # Create fill
            fill = Fill.from_order(order, fill_price, order.quantity)
            self._fills.append(fill)
            
            # Update balance
            self._balance -= (fill_price * order.quantity) / 100
            
            logger.info(
                "paper_order_filled",
                ticker=order.ticker,
                side=order.side.value,
                quantity=order.quantity,
                fill_price=fill_price,
            )
        else:
            order.status = OrderStatus.OPEN
            logger.info(
                "paper_order_open",
                ticker=order.ticker,
                side=order.side.value,
                quantity=order.quantity,
                price=order.price,
            )
        
        self._orders[order.id] = order
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a paper order."""
        if order_id in self._orders:
            self._orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get paper order by ID."""
        return self._orders.get(order_id)
    
    async def get_fills(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
    ) -> list[Fill]:
        """Get paper fills."""
        fills = self._fills
        if ticker:
            fills = [f for f in fills if f.ticker == ticker]
        return fills[-limit:]
    
    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT
    # ─────────────────────────────────────────────────────────────────────────
    
    async def get_balance(self) -> float:
        """Get simulated balance."""
        return self._balance
    
    async def get_positions(self) -> list[dict]:
        """Get simulated positions."""
        return self._positions
    
    def set_balance(self, balance: float) -> None:
        """Set simulated balance for testing."""
        self._balance = balance
    
    # ─────────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────────
    
    async def close(self) -> None:
        """No cleanup needed for mock client."""
        pass
