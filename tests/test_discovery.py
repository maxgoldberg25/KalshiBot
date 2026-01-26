"""
Tests for market discovery and filtering.
"""

from datetime import datetime, timedelta

import pytest

from kalshi_bot.core.discovery import MarketDiscovery
from kalshi_bot.models.market import Market, OrderBook, OrderBookLevel


class TestMarketDiscovery:
    """Test market discovery functionality."""
    
    @pytest.mark.asyncio
    async def test_find_same_day_markets(self, mock_client):
        """Test finding markets that expire today."""
        discovery = MarketDiscovery(mock_client)
        
        # Mock client has test markets
        markets = await discovery.find_same_day_markets()
        
        # Should find the same-day markets
        same_day_tickers = [m.ticker for m in markets]
        assert "TEST-TODAY-A" in same_day_tickers
        assert "TEST-TODAY-B" in same_day_tickers
        # Should NOT include tomorrow's market
        assert "TEST-TOMORROW-C" not in same_day_tickers
    
    def test_filter_by_liquidity(self, mock_client, sample_market):
        """Test liquidity filtering."""
        discovery = MarketDiscovery(mock_client)
        
        # Liquid market should pass
        filtered = discovery.filter_markets([sample_market])
        assert len(filtered) == 1
        
        # Illiquid market should fail
        illiquid_market = Market(
            ticker="ILLIQUID",
            title="Illiquid Market",
            category="test",
            status="active",
            expiration_time=sample_market.expiration_time,
            close_time=sample_market.close_time,
            volume_24h=10,  # Below threshold
            orderbook=OrderBook(
                yes_bids=[OrderBookLevel(price=40, quantity=10)],
                yes_asks=[OrderBookLevel(price=60, quantity=10)],  # Wide spread
            ),
        )
        
        filtered = discovery.filter_markets([illiquid_market])
        assert len(filtered) == 0
    
    def test_filter_by_category_blacklist(self, mock_client, sample_market):
        """Test category blacklist filtering."""
        discovery = MarketDiscovery(mock_client)
        
        # Sports category is blacklisted by default
        sports_market = Market(
            ticker="SPORTS-MARKET",
            title="Sports Market",
            category="sports",
            status="active",
            expiration_time=sample_market.expiration_time,
            close_time=sample_market.close_time,
            volume_24h=500,
            orderbook=sample_market.orderbook,
        )
        
        filtered = discovery.filter_markets([sports_market])
        assert len(filtered) == 0
    
    def test_filter_too_close_to_expiry(self, mock_client):
        """Test filtering markets too close to expiry."""
        discovery = MarketDiscovery(mock_client)
        
        now = datetime.utcnow()
        close_soon = now + timedelta(minutes=10)  # Closes in 10 minutes
        
        closing_soon_market = Market(
            ticker="CLOSING-SOON",
            title="Closing Soon Market",
            category="test",
            status="active",
            expiration_time=close_soon,
            close_time=close_soon,
            volume_24h=500,
            orderbook=OrderBook(
                yes_bids=[OrderBookLevel(price=49, quantity=100)],
                yes_asks=[OrderBookLevel(price=51, quantity=100)],
            ),
        )
        
        filtered = discovery.filter_markets([closing_soon_market], reference_time=now)
        # Should be filtered out (default cutoff is 30 minutes)
        assert len(filtered) == 0


class TestMarketExpiry:
    """Test market expiry checking."""
    
    def test_expires_today_true(self, sample_market):
        """Test market that expires today."""
        now = datetime.utcnow()
        assert sample_market.expires_today(now) is True
    
    def test_expires_today_false(self, sample_market_tomorrow):
        """Test market that expires tomorrow."""
        now = datetime.utcnow()
        assert sample_market_tomorrow.expires_today(now) is False
    
    def test_minutes_until_close(self, sample_market):
        """Test minutes until close calculation."""
        now = datetime.utcnow()
        minutes = sample_market.minutes_until_close(now)
        
        assert minutes is not None
        assert minutes > 0
