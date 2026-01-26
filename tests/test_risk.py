"""
Tests for risk management.
"""

import pytest

from kalshi_bot.core.risk import RiskManager
from kalshi_bot.models.order import Order, OrderSide, OrderStatus, OrderType
from kalshi_bot.models.snapshot import StrategySignal


class TestRiskManager:
    """Test risk management functionality."""
    
    def test_check_order_passes(self, risk_manager, sample_signal):
        """Test that valid orders pass risk checks."""
        result = risk_manager.check_order(sample_signal, 5.0)
        
        assert result.passed is True
        assert result.allowed_size is not None
        assert result.allowed_size > 0
    
    def test_check_order_fails_low_ev(self, risk_manager):
        """Test that low EV signals are rejected."""
        low_ev_signal = StrategySignal(
            strategy_name="test",
            ticker="TEST",
            side=OrderSide.YES,
            confidence=0.7,
            fair_probability=0.51,
            market_probability=0.50,
            edge=0.01,
            expected_value=0.005,  # Below 2% threshold
            entry_price=50,
        )
        
        result = risk_manager.check_order(low_ev_signal, 5.0)
        
        assert result.passed is False
        assert "EV too low" in result.reason
    
    def test_check_order_fails_low_confidence(self, risk_manager):
        """Test that low confidence signals are rejected."""
        low_conf_signal = StrategySignal(
            strategy_name="test",
            ticker="TEST",
            side=OrderSide.YES,
            confidence=0.4,  # Below threshold
            fair_probability=0.55,
            market_probability=0.50,
            edge=0.05,
            expected_value=0.03,
            entry_price=50,
        )
        
        result = risk_manager.check_order(low_conf_signal, 5.0)
        
        assert result.passed is False
        assert "Confidence too low" in result.reason
    
    def test_max_trades_limit(self, risk_manager, sample_signal):
        """Test that max trades per day is enforced."""
        # Simulate hitting max trades
        from kalshi_bot.config import settings
        
        for i in range(settings.max_trades_per_day):
            order = Order(
                idempotency_key=f"key-{i}",
                ticker="TEST",
                side=OrderSide.YES,
                price=50,
                quantity=1,
            )
            risk_manager.record_order_submitted(order)
        
        # Next order should be rejected
        result = risk_manager.check_order(sample_signal, 5.0)
        
        assert result.passed is False
        assert "Max trades reached" in result.reason
    
    def test_daily_loss_limit(self, risk_manager, sample_signal):
        """Test that daily loss limit stops trading."""
        from kalshi_bot.config import settings
        
        # Simulate large loss
        risk_manager.record_pnl("LOSER", -settings.max_daily_loss_dollars - 1)
        
        # Next order should be rejected
        result = risk_manager.check_order(sample_signal, 5.0)
        
        assert result.passed is False
        assert "Daily loss limit" in result.reason
    
    def test_idempotency_check(self, risk_manager):
        """Test that duplicate orders are blocked."""
        key = "2024-01-15:TEST:strategy:yes"
        
        # First check should pass
        assert risk_manager.check_idempotency(key) is True
        
        # Record order with that key
        order = Order(
            idempotency_key=key,
            ticker="TEST",
            side=OrderSide.YES,
            price=50,
            quantity=1,
        )
        risk_manager.record_order_submitted(order)
        
        # Second check should fail
        assert risk_manager.check_idempotency(key) is False
    
    def test_position_sizing_kelly(self, risk_manager, sample_signal):
        """Test Kelly criterion position sizing."""
        # High confidence, high EV signal should get larger size
        high_ev_signal = StrategySignal(
            strategy_name="test",
            ticker="TEST",
            side=OrderSide.YES,
            confidence=0.85,
            fair_probability=0.70,
            market_probability=0.50,
            edge=0.20,
            expected_value=0.15,
            entry_price=50,
        )
        
        result = risk_manager.check_order(high_ev_signal, 20.0)
        
        assert result.passed is True
        assert result.allowed_size > 0
    
    def test_exposure_limits(self, risk_manager, sample_signal):
        """Test that exposure limits are enforced."""
        from kalshi_bot.config import settings
        
        # Fill up to near max exposure
        order = Order(
            idempotency_key="big-order",
            ticker="BIG",
            side=OrderSide.YES,
            price=50,
            quantity=int(settings.max_total_exposure_dollars * 100 / 50),
        )
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_fill_price = 50
        
        risk_manager.record_order_submitted(order)
        risk_manager.record_fill(order)
        
        # New order should be constrained
        result = risk_manager.check_order(sample_signal, settings.max_total_exposure_dollars)
        
        # Should either fail or have reduced size
        if result.passed:
            assert result.allowed_size < int(settings.max_total_exposure_dollars * 100 / 50)
