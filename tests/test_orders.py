"""
Tests for order management.
"""

import pytest

from kalshi_bot.config import TradingMode
from kalshi_bot.core.orders import OrderManager
from kalshi_bot.core.risk import RiskManager
from kalshi_bot.models.order import OrderSide, OrderStatus
from kalshi_bot.models.snapshot import StrategySignal


class TestOrderManager:
    """Test order management functionality."""
    
    @pytest.fixture
    def order_manager(self, mock_client, risk_manager):
        """Create order manager for testing."""
        return OrderManager(
            mock_client,
            risk_manager,
            mode=TradingMode.PAPER,
        )
    
    @pytest.mark.asyncio
    async def test_process_valid_signal(self, order_manager, sample_signal):
        """Test processing a valid signal creates an order."""
        order = await order_manager.process_signal(sample_signal)
        
        assert order is not None
        assert order.ticker == sample_signal.ticker
        assert order.side == sample_signal.side
        assert order.strategy_name == sample_signal.strategy_name
    
    @pytest.mark.asyncio
    async def test_process_invalid_signal_no_side(self, order_manager):
        """Test that signals without a side are ignored."""
        no_trade_signal = StrategySignal(
            strategy_name="test",
            ticker="TEST",
            side=None,  # No trade
            confidence=0.0,
            fair_probability=0.50,
            market_probability=0.50,
            edge=0.0,
            expected_value=0.0,
        )
        
        order = await order_manager.process_signal(no_trade_signal)
        
        assert order is None
    
    @pytest.mark.asyncio
    async def test_idempotency_prevents_duplicates(self, order_manager, sample_signal):
        """Test that duplicate signals don't create duplicate orders."""
        # First signal should create order
        order1 = await order_manager.process_signal(sample_signal)
        assert order1 is not None
        
        # Same signal should be blocked
        order2 = await order_manager.process_signal(sample_signal)
        assert order2 is None
    
    @pytest.mark.asyncio
    async def test_paper_order_execution(self, order_manager, sample_signal):
        """Test paper order execution flow."""
        order = await order_manager.process_signal(sample_signal)
        
        assert order is not None
        # Mock client fills with 100% probability
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity > 0
    
    @pytest.mark.asyncio
    async def test_dry_run_mode(self, mock_client, risk_manager, sample_signal):
        """Test dry-run mode doesn't execute orders."""
        order_manager = OrderManager(
            mock_client,
            risk_manager,
            mode=TradingMode.DRY_RUN,
        )
        
        order = await order_manager.process_signal(sample_signal)
        
        assert order is not None
        assert order.status == OrderStatus.PENDING  # Not executed
    
    @pytest.mark.asyncio
    async def test_get_orders_today(self, order_manager, sample_signal):
        """Test retrieving today's orders."""
        # Create an order
        await order_manager.process_signal(sample_signal)
        
        orders = order_manager.get_orders_today()
        
        assert len(orders) == 1
        assert orders[0].ticker == sample_signal.ticker
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, order_manager, sample_signal):
        """Test order cancellation."""
        # Create order that stays open
        order_manager.client.fill_probability = 0.0  # Don't fill
        
        signal = StrategySignal(
            strategy_name="cancel_test",
            ticker="CANCEL-TEST",
            side=OrderSide.YES,
            confidence=0.75,
            fair_probability=0.55,
            market_probability=0.50,
            edge=0.05,
            expected_value=0.03,
            entry_price=50,
        )
        
        order = await order_manager.process_signal(signal)
        assert order is not None
        
        # Cancel the order
        success = await order_manager.cancel_order(order.id)
        assert success is True
        
        # Verify cancelled
        updated = order_manager.get_order(order.id)
        assert updated.status == OrderStatus.CANCELLED
