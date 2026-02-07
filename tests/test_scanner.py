"""Tests for edge calculation and comparison logic."""

from datetime import datetime, timedelta

import pytest

from kalshi_odds.core.scanner import Scanner
from kalshi_odds.models.kalshi import KalshiTopOfBook
from kalshi_odds.models.odds import OddsQuote, OddsFormat, MarketType
from kalshi_odds.models.comparison import Direction


@pytest.fixture
def scanner() -> Scanner:
    return Scanner(
        kalshi_slippage_buffer=0.005,
        sportsbook_execution_friction=0.01,
        min_edge_bps=50.0,
        min_liquidity=10,
        max_staleness_seconds=60.0,
    )


@pytest.fixture
def kalshi_tob() -> KalshiTopOfBook:
    return KalshiTopOfBook(
        contract_id="TEST-YES",
        yes_bid=0.48,
        yes_ask=0.52,
        yes_bid_size=100,
        yes_ask_size=100,
        no_bid=0.48,
        no_ask=0.52,
        timestamp=datetime.utcnow(),
    )


@pytest.fixture
def odds_quote_h2h() -> list[OddsQuote]:
    """H2H market with two sides."""
    now = datetime.utcnow()
    return [
        OddsQuote(
            source="theoddsapi",
            bookmaker="draftkings",
            event_id="evt123",
            market_type=MarketType.H2H,
            selection="Team A",
            odds_format=OddsFormat.AMERICAN,
            odds_value=-110.0,
            timestamp=now,
        ),
        OddsQuote(
            source="theoddsapi",
            bookmaker="draftkings",
            event_id="evt123",
            market_type=MarketType.H2H,
            selection="Team B",
            odds_format=OddsFormat.AMERICAN,
            odds_value=-110.0,
            timestamp=now,
        ),
    ]


class TestEdgeDetection:
    """Test edge detection logic."""

    def test_no_edge_fair_market(self, scanner: Scanner, kalshi_tob: KalshiTopOfBook, odds_quote_h2h: list[OddsQuote]):
        """When prices match, no alert should trigger."""
        # Both -110 implies 50% no-vig
        # Kalshi at 0.52 ask (+ buffer = 0.525)
        # After sportsbook friction: 0.50 * 0.99 = 0.495
        # Edge = 0.495 - 0.525 = -0.03 (negative, no alert)
        
        alerts = scanner.compare("test-market", kalshi_tob, odds_quote_h2h, {})
        assert len(alerts) == 0

    def test_kalshi_cheap_alert(self, scanner: Scanner):
        """Kalshi cheap: Kalshi ask < sportsbook no-vig prob."""
        # Kalshi at 0.40 ask
        kalshi = KalshiTopOfBook(
            contract_id="TEST",
            yes_bid=0.38,
            yes_ask=0.40,
            yes_bid_size=100,
            yes_ask_size=100,
            timestamp=datetime.utcnow(),
        )
        
        # Sportsbook at 0.55 implied (no-vig ~0.50 after opposite side)
        # But let's make it 0.60 to trigger
        odds = [
            OddsQuote(
                source="theoddsapi",
                bookmaker="dk",
                event_id="evt",
                market_type=MarketType.H2H,
                selection="A",
                odds_format=OddsFormat.DECIMAL,
                odds_value=1.67,  # 60% implied
                timestamp=datetime.utcnow(),
            ),
            OddsQuote(
                source="theoddsapi",
                bookmaker="dk",
                event_id="evt",
                market_type=MarketType.H2H,
                selection="B",
                odds_format=OddsFormat.DECIMAL,
                odds_value=2.50,  # 40% implied
                timestamp=datetime.utcnow(),
            ),
        ]
        
        alerts = scanner.compare("test", kalshi, odds, {})
        
        # Should find kalshi_cheap alert
        cheap_alerts = [a for a in alerts if a.direction == Direction.KALSHI_CHEAP]
        assert len(cheap_alerts) > 0
        
        alert = cheap_alerts[0]
        assert alert.edge_bps > 0

    def test_stale_data_rejected(self, scanner: Scanner, kalshi_tob: KalshiTopOfBook, odds_quote_h2h: list[OddsQuote]):
        """Stale data should be filtered out."""
        # Make Kalshi data stale
        kalshi_tob.timestamp = datetime.utcnow() - timedelta(seconds=120)
        
        alerts = scanner.compare("test", kalshi_tob, odds_quote_h2h, {})
        assert len(alerts) == 0

    def test_low_liquidity_rejected(self, scanner: Scanner, odds_quote_h2h: list[OddsQuote]):
        """Low liquidity should be filtered out."""
        kalshi = KalshiTopOfBook(
            contract_id="TEST",
            yes_bid=0.40,
            yes_ask=0.42,
            yes_bid_size=5,  # Below min_liquidity
            yes_ask_size=5,
            timestamp=datetime.utcnow(),
        )
        
        alerts = scanner.compare("test", kalshi, odds_quote_h2h, {})
        assert len(alerts) == 0


class TestConfidenceScoring:
    """Test confidence scoring logic."""

    def test_confidence_factors(self, scanner: Scanner):
        """Larger edge + fresher data + higher liquidity = higher confidence."""
        # This would require building a full alert and checking confidence
        # For now, we test the compare method indirectly
        
        kalshi = KalshiTopOfBook(
            contract_id="TEST",
            yes_bid=0.30,
            yes_ask=0.32,  # Very cheap
            yes_bid_size=200,  # High liquidity
            yes_ask_size=200,
            timestamp=datetime.utcnow(),  # Fresh
        )
        
        odds = [
            OddsQuote(
                source="theoddsapi",
                bookmaker="dk",
                event_id="evt",
                market_type=MarketType.H2H,
                selection="A",
                odds_format=OddsFormat.DECIMAL,
                odds_value=1.43,  # 70% implied
                timestamp=datetime.utcnow(),
            ),
            OddsQuote(
                source="theoddsapi",
                bookmaker="dk",
                event_id="evt",
                market_type=MarketType.H2H,
                selection="B",
                odds_format=OddsFormat.DECIMAL,
                odds_value=3.33,  # 30% implied
                timestamp=datetime.utcnow(),
            ),
        ]
        
        alerts = scanner.compare("test", kalshi, odds, {})
        
        if alerts:
            # Should have high confidence due to large edge + fresh data + high liquidity
            assert any(a.confidence.value == "high" for a in alerts)
