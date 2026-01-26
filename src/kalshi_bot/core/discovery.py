"""
Market discovery module.

Finds and filters markets that:
1. Expire today (same-day expiration)
2. Meet liquidity requirements
3. Are not blacklisted
4. Are within the trading window
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import pytz
import structlog

from kalshi_bot.client.base import BaseKalshiClient
from kalshi_bot.config import settings
from kalshi_bot.models.market import Market

logger = structlog.get_logger()


class MarketDiscovery:
    """
    Discovers and filters tradeable markets.
    
    Focuses on same-day expiring markets that meet liquidity
    and safety requirements.
    """
    
    def __init__(
        self,
        client: BaseKalshiClient,
        timezone: Optional[str] = None,
    ):
        self.client = client
        self.tz = pytz.timezone(timezone or settings.timezone)
    
    async def find_same_day_markets(
        self,
        reference_time: Optional[datetime] = None,
    ) -> list[Market]:
        """
        Find all markets expiring on the same day as reference_time.
        
        Args:
            reference_time: Reference datetime (default: now in configured timezone)
            
        Returns:
            List of markets expiring today that pass initial filters
        """
        if reference_time is None:
            # Use UTC to determine "today" - this ensures we're looking for markets
            # expiring on the actual calendar day, not affected by timezone differences
            utc_now = datetime.now(pytz.utc)
            # Convert to configured timezone for logging/comparison
            reference_time = utc_now.astimezone(self.tz)
        else:
            # Ensure reference_time is in the correct timezone
            if reference_time.tzinfo is None:
                reference_time = self.tz.localize(reference_time)
            else:
                reference_time = reference_time.astimezone(self.tz)
        
        # Get today's date - use UTC date to avoid timezone edge cases
        utc_today = datetime.now(pytz.utc).date()
        
        logger.info(
            "discovering_markets",
            target_date_utc=utc_today.isoformat(),
            target_date_local=reference_time.date().isoformat(),
            reference_time=reference_time.isoformat(),
            timezone=str(self.tz),
        )
        
        all_markets: list[Market] = []
        cursor: Optional[str] = None
        max_pages = 10  # Limit to 10 pages (1000 markets) to avoid rate limits
        
        # Paginate through markets with rate limit protection
        page_count = 0
        while page_count < max_pages:
            markets, cursor = await self.client.get_markets(limit=100, cursor=cursor)
            all_markets.extend(markets)
            page_count += 1
            
            if cursor is None or len(markets) == 0:
                break
            
            # Add delay between pages to respect rate limits
            await asyncio.sleep(0.5)
        
        logger.info("fetched_markets", total=len(all_markets))
        
        # Debug: Check expiration dates of first few markets
        sample_markets = all_markets[:5]
        sample_expirations = []
        for m in sample_markets:
            if m.expiration_time:
                exp_time = m.expiration_time
                if exp_time.tzinfo is None:
                    exp_time = pytz.utc.localize(exp_time)
                exp_local = exp_time.astimezone(self.tz)
                sample_expirations.append({
                    "ticker": m.ticker,
                    "expiration_date": exp_local.date().isoformat(),
                    "expiration_time": exp_local.isoformat(),
                })
        
        logger.debug(
            "sample_market_expirations",
            target_date_utc=utc_today.isoformat(),
            samples=sample_expirations,
        )
        
        # Filter for same-day expiration
        same_day = []
        for market in all_markets:
            if self._expires_today(market, reference_time):
                # Fetch orderbook for each candidate (with delay to respect rate limits)
                orderbook = await self.client.get_orderbook(market.ticker)
                if orderbook:
                    market.orderbook = orderbook
                same_day.append(market)
                # Small delay between orderbook fetches
                await asyncio.sleep(0.3)
        
        logger.info(
            "same_day_markets",
            count=len(same_day),
            tickers=[m.ticker for m in same_day],
        )
        
        return same_day
    
    def _expires_today(self, market: Market, reference_time: datetime) -> bool:
        """
        Check if market expires on the same day as reference_time.
        
        Uses UTC dates for comparison to avoid timezone edge cases.
        """
        if market.expiration_time is None:
            return False
        
        # Get today's date in UTC (unambiguous)
        utc_today = datetime.now(pytz.utc).date()
        
        # Convert market expiration to UTC date
        exp_time = market.expiration_time
        if exp_time.tzinfo is None:
            # Assume UTC if no timezone info
            exp_time = pytz.utc.localize(exp_time)
        else:
            exp_time = exp_time.astimezone(pytz.utc)
        
        exp_date_utc = exp_time.date()
        
        # Compare UTC dates
        return exp_date_utc == utc_today
    
    def filter_markets(
        self,
        markets: list[Market],
        reference_time: Optional[datetime] = None,
    ) -> list[Market]:
        """
        Apply all filters to candidate markets.
        
        Filters:
        1. Liquidity (volume, spread, depth)
        2. Category whitelist/blacklist
        3. Market blacklist
        4. Trading window (not too close to expiry)
        
        Returns:
            Filtered list of tradeable markets
        """
        if reference_time is None:
            reference_time = datetime.now(self.tz)
        
        filtered = []
        rejection_reasons: dict[str, int] = {}
        
        for market in markets:
            reason = self._check_market(market, reference_time)
            if reason is None:
                filtered.append(market)
            else:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        logger.info(
            "filtered_markets",
            passed=len(filtered),
            rejected=len(markets) - len(filtered),
            rejection_reasons=rejection_reasons,
        )
        
        return filtered
    
    def _check_market(
        self,
        market: Market,
        reference_time: datetime,
    ) -> Optional[str]:
        """
        Check if market passes all filters.
        
        Returns:
            None if market passes, or rejection reason string
        """
        # Category filters
        category = market.category.lower() if market.category else ""
        
        if settings.category_whitelist:
            if not any(c.lower() in category for c in settings.category_whitelist):
                return "not_in_whitelist"
        
        if settings.category_blacklist:
            if any(c.lower() in category for c in settings.category_blacklist):
                return "in_blacklist"
        
        # Market blacklist
        if market.ticker in settings.market_blacklist:
            return "market_blacklisted"
        
        # Liquidity checks
        if market.volume_24h < settings.min_volume_24h:
            return "low_volume"
        
        if market.orderbook is None:
            return "no_orderbook"
        
        if market.orderbook.spread is None:
            return "no_spread"
        
        if market.orderbook.spread > settings.max_spread_cents:
            return "spread_too_wide"
        
        if market.orderbook.total_depth < settings.min_orderbook_depth:
            return "low_depth"
        
        # Trading window check
        try:
            # Ensure both datetimes are timezone-aware for comparison
            close_time = market.close_time
            ref_time = reference_time
            
            if close_time is not None:
                # Make close_time naive if it's aware (for simple comparison)
                if close_time.tzinfo is not None:
                    close_time = close_time.replace(tzinfo=None)
                if ref_time.tzinfo is not None:
                    ref_time = ref_time.replace(tzinfo=None)
                
                delta = close_time - ref_time
                minutes_to_close = int(delta.total_seconds() / 60)
                
                if minutes_to_close < settings.trading_cutoff_minutes:
                    return "too_close_to_expiry"
        except Exception:
            pass  # Skip this check if datetime comparison fails
        
        # Market must be active
        if market.status != "active":
            return "not_active"
        
        if market.result is not None:
            return "already_settled"
        
        return None
    
    async def discover_and_filter(
        self,
        reference_time: Optional[datetime] = None,
    ) -> list[Market]:
        """
        Complete discovery pipeline: find and filter same-day markets.
        
        This is the main entry point for market discovery.
        """
        if reference_time is None:
            reference_time = datetime.now(self.tz)
        
        # Find same-day markets
        candidates = await self.find_same_day_markets(reference_time)
        
        # Apply filters
        tradeable = self.filter_markets(candidates, reference_time)
        
        logger.info(
            "discovery_complete",
            candidates=len(candidates),
            tradeable=len(tradeable),
            tickers=[m.ticker for m in tradeable],
        )
        
        return tradeable
