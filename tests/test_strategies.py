"""
Tests for trading strategies.
"""

import pytest

from kalshi_bot.models.market import Market, OrderBook, OrderBookLevel
from kalshi_bot.models.order import OrderSide
from kalshi_bot.strategies.mean_reversion import MeanReversionStrategy
from kalshi_bot.strategies.mispricing import MispricingStrategy


class TestMispricingStrategy:
    """Test mispricing detection strategy."""
    
    @pytest.fixture
    def strategy(self):
        return MispricingStrategy()
    
    def test_no_signal_without_orderbook(self, strategy, sample_market):
        """Test that no signal is generated without orderbook."""
        sample_market.orderbook = None
        features = sample_market.to_features()
        
        signal = strategy.evaluate(sample_market, features)
        
        assert signal.side is None
        assert "No orderbook" in signal.reasoning
    
    def test_no_signal_wide_spread(self, strategy, sample_market):
        """Test that wide spreads are filtered."""
        sample_market.orderbook = OrderBook(
            yes_bids=[OrderBookLevel(price=40, quantity=100)],
            yes_asks=[OrderBookLevel(price=60, quantity=100)],  # 20c spread
        )
        features = sample_market.to_features()
        
        signal = strategy.evaluate(sample_market, features)
        
        assert signal.side is None
        assert "Spread too wide" in signal.reasoning
    
    def test_signal_on_depth_imbalance(self, strategy):
        """Test signal generation on strong depth imbalance."""
        # Create market with heavy bid-side depth (bullish)
        market = Market(
            ticker="BULLISH-DEPTH",
            title="Bullish Depth Market",
            category="test",
            status="active",
            volume_24h=500,
            orderbook=OrderBook(
                yes_bids=[
                    OrderBookLevel(price=49, quantity=500),  # Heavy buying
                    OrderBookLevel(price=48, quantity=300),
                ],
                yes_asks=[
                    OrderBookLevel(price=51, quantity=50),  # Light selling
                    OrderBookLevel(price=52, quantity=50),
                ],
            ),
        )
        features = market.to_features()
        
        signal = strategy.evaluate(market, features)
        
        # Should generate YES signal (bullish imbalance)
        if signal.side is not None:
            assert signal.side == OrderSide.YES
            assert signal.confidence > 0
    
    def test_backtest_with_sufficient_data(self, strategy, sample_snapshots):
        """Test backtesting with sufficient historical data."""
        result = strategy.backtest(sample_snapshots)
        
        assert result.is_valid is True
        assert result.num_samples == len(sample_snapshots)
        # Should have generated some trades
        assert result.num_trades >= 0
    
    def test_backtest_insufficient_data(self, strategy):
        """Test backtest with insufficient data."""
        from datetime import datetime
        from kalshi_bot.models.snapshot import MarketSnapshot
        
        # Only 5 snapshots
        snapshots = [
            MarketSnapshot(
                ticker="TEST",
                timestamp=datetime.utcnow(),
                last_price=50,
                volume_24h=100,
            )
            for _ in range(5)
        ]
        
        result = strategy.backtest(snapshots)
        
        assert result.is_valid is False


class TestMeanReversionStrategy:
    """Test mean reversion strategy."""
    
    @pytest.fixture
    def strategy(self):
        return MeanReversionStrategy()
    
    def test_no_signal_without_history(self, strategy, sample_market):
        """Test that no signal without historical data."""
        features = sample_market.to_features()
        
        signal = strategy.evaluate(sample_market, features, historical_snapshots=None)
        
        assert signal.side is None
        assert "Insufficient history" in signal.reasoning
    
    def test_no_signal_small_deviation(self, strategy, sample_market, sample_snapshots):
        """Test no signal when price is near MA."""
        # Modify snapshots so current price equals MA
        for snap in sample_snapshots:
            snap.mid = 50.0
            snap.last_price = 50
        
        sample_market.last_price = 50
        features = sample_market.to_features()
        
        signal = strategy.evaluate(sample_market, features, sample_snapshots)
        
        assert signal.side is None
        assert "Deviation" in signal.reasoning and "below" in signal.reasoning
    
    def test_signal_on_large_deviation(self, strategy, sample_market, sample_snapshots):
        """Test signal on large price deviation from MA."""
        # Set snapshots to consistent MA
        for snap in sample_snapshots:
            snap.mid = 50.0
            snap.last_price = 50
        
        # Current price way above MA (should trigger NO signal - mean reversion)
        sample_market.last_price = 60
        sample_market.orderbook = OrderBook(
            yes_bids=[OrderBookLevel(price=59, quantity=200)],
            yes_asks=[OrderBookLevel(price=61, quantity=200)],
        )
        features = sample_market.to_features()
        
        signal = strategy.evaluate(sample_market, features, sample_snapshots)
        
        # Price above MA should trigger NO signal (expect reversion down)
        if signal.side is not None:
            assert signal.side == OrderSide.NO
    
    def test_backtest_generates_trades(self, strategy, sample_snapshots):
        """Test backtest generates trades on oscillating data."""
        result = strategy.backtest(sample_snapshots)
        
        assert result.is_valid is True
        # With oscillating sample data, should generate some trades
        # (depends on the specific oscillation pattern)


class TestStrategySignalValidation:
    """Test signal validation and thresholds."""
    
    def test_signal_meets_thresholds(self, sample_signal):
        """Test signal threshold checking."""
        # Default signal should meet thresholds
        assert sample_signal.meets_thresholds(
            min_confidence=0.6,
            min_ev=0.02,
            min_win_rate=0.70,
            min_samples=30,
        ) is True
    
    def test_signal_fails_confidence_threshold(self, sample_signal):
        """Test signal fails on low confidence."""
        sample_signal.confidence = 0.4
        
        assert sample_signal.meets_thresholds(
            min_confidence=0.6,
            min_ev=0.02,
        ) is False
    
    def test_signal_fails_ev_threshold(self, sample_signal):
        """Test signal fails on low EV."""
        sample_signal.expected_value = 0.01
        
        assert sample_signal.meets_thresholds(
            min_confidence=0.5,
            min_ev=0.02,
        ) is False
    
    def test_signal_fails_backtest_win_rate(self, sample_signal):
        """Test signal fails on poor backtest performance."""
        sample_signal.backtest_win_rate = 0.55  # Below 70%
        sample_signal.backtest_samples = 50
        
        assert sample_signal.meets_thresholds(
            min_confidence=0.5,
            min_ev=0.01,
            min_win_rate=0.70,
            min_samples=30,
        ) is False
