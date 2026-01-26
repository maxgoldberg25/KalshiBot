"""
Pytest fixtures for testing.
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from kalshi_bot.client.mock import MockKalshiClient
from kalshi_bot.core.risk import RiskManager
from kalshi_bot.db.repository import Repository
from kalshi_bot.models.market import Market, OrderBook, OrderBookLevel
from kalshi_bot.models.order import Order, OrderSide, OrderType
from kalshi_bot.models.snapshot import MarketSnapshot, StrategySignal


@pytest.fixture
def mock_client() -> MockKalshiClient:
    """Create a mock Kalshi client."""
    return MockKalshiClient(
        fill_probability=1.0,  # Always fill in tests
        slippage_cents=0,
        initial_balance=1000.0,
    )


@pytest.fixture
def risk_manager() -> RiskManager:
    """Create a risk manager with test defaults."""
    rm = RiskManager()
    rm.reset_daily_state()
    return rm


@pytest_asyncio.fixture
async def repository(tmp_path) -> Repository:
    """Create a test repository with temp database."""
    db_path = str(tmp_path / "test.db")
    repo = Repository(f"sqlite:///{db_path}")
    await repo.initialize()
    return repo


@pytest.fixture
def sample_market() -> Market:
    """Create a sample market for testing."""
    now = datetime.utcnow()
    today_close = now.replace(hour=23, minute=0, second=0) + timedelta(hours=1)
    
    return Market(
        ticker="TEST-SAME-DAY",
        title="Test Market - Same Day Expiry",
        subtitle="Will test pass?",
        category="test",
        event_ticker="TEST-EVENT",
        status="active",
        close_time=today_close,
        expiration_time=today_close,
        last_price=50,
        volume=5000,
        volume_24h=500,
        open_interest=1000,
        orderbook=OrderBook(
            yes_bids=[
                OrderBookLevel(price=49, quantity=100),
                OrderBookLevel(price=48, quantity=200),
            ],
            yes_asks=[
                OrderBookLevel(price=51, quantity=100),
                OrderBookLevel(price=52, quantity=200),
            ],
        ),
    )


@pytest.fixture
def sample_market_tomorrow() -> Market:
    """Create a sample market expiring tomorrow."""
    now = datetime.utcnow()
    tomorrow_close = now.replace(hour=23, minute=0, second=0) + timedelta(days=1)
    
    return Market(
        ticker="TEST-TOMORROW",
        title="Test Market - Tomorrow Expiry",
        category="test",
        status="active",
        close_time=tomorrow_close,
        expiration_time=tomorrow_close,
        last_price=60,
        volume=3000,
        volume_24h=300,
        open_interest=500,
    )


@pytest.fixture
def sample_order() -> Order:
    """Create a sample order for testing."""
    return Order(
        idempotency_key="2024-01-15:TEST-TICKER:test_strategy:yes",
        ticker="TEST-TICKER",
        side=OrderSide.YES,
        order_type=OrderType.LIMIT,
        price=50,
        quantity=10,
        strategy_name="test_strategy",
        signal_confidence=0.75,
        expected_value=0.05,
    )


@pytest.fixture
def sample_signal() -> StrategySignal:
    """Create a sample strategy signal."""
    return StrategySignal(
        strategy_name="test_strategy",
        ticker="TEST-TICKER",
        side=OrderSide.YES,
        confidence=0.75,
        fair_probability=0.55,
        market_probability=0.50,
        edge=0.05,
        expected_value=0.03,
        entry_price=50,
    )


@pytest.fixture
def sample_snapshots() -> list[MarketSnapshot]:
    """Create sample historical snapshots for backtesting."""
    snapshots = []
    base_time = datetime.utcnow() - timedelta(hours=48)
    
    # Generate 48 hours of snapshots (hourly)
    for i in range(48):
        timestamp = base_time + timedelta(hours=i)
        
        # Simulate some price movement
        import math
        base_price = 50 + 10 * math.sin(i / 10)  # Oscillating price
        
        snapshots.append(MarketSnapshot(
            ticker="TEST-TICKER",
            timestamp=timestamp,
            last_price=int(base_price),
            bid=int(base_price) - 1,
            ask=int(base_price) + 1,
            mid=base_price,
            spread=2,
            volume_24h=200 + i * 5,
            bid_depth=100 + (i % 50),
            ask_depth=100 - (i % 30),
            depth_imbalance=0.2 * math.sin(i / 5),
        ))
    
    return snapshots
