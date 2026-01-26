"""
Orderbook snapshotter for building historical datasets.

Records market state at regular intervals for:
1. Backtesting strategies
2. Feature engineering
3. Market analysis
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import structlog

from kalshi_bot.client.base import BaseKalshiClient
from kalshi_bot.config import settings
from kalshi_bot.db.repository import Repository
from kalshi_bot.models.market import Market
from kalshi_bot.models.snapshot import MarketSnapshot

logger = structlog.get_logger()


class Snapshotter:
    """
    Records orderbook snapshots at regular intervals.
    
    Used to build historical datasets for backtesting when
    Kalshi doesn't provide historical orderbook data.
    """
    
    def __init__(
        self,
        client: BaseKalshiClient,
        repository: Repository,
        interval_minutes: Optional[int] = None,
    ):
        self.client = client
        self.repository = repository
        self.interval_minutes = interval_minutes or settings.snapshot_interval_minutes
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def snapshot_market(self, market: Market) -> Optional[MarketSnapshot]:
        """
        Take a snapshot of a single market.
        
        Args:
            market: Market to snapshot (must have orderbook)
            
        Returns:
            MarketSnapshot if successful, None otherwise
        """
        if market.orderbook is None:
            orderbook = await self.client.get_orderbook(market.ticker)
            if orderbook is None:
                logger.warning("snapshot_no_orderbook", ticker=market.ticker)
                return None
            market.orderbook = orderbook
        
        snapshot = MarketSnapshot.from_market(
            ticker=market.ticker,
            orderbook=market.orderbook,
            last_price=market.last_price,
            volume_24h=market.volume_24h,
        )
        
        # Store in database
        await self.repository.save_snapshot(snapshot)
        
        logger.debug(
            "snapshot_taken",
            ticker=market.ticker,
            mid=snapshot.mid,
            spread=snapshot.spread,
        )
        
        return snapshot
    
    async def snapshot_markets(self, markets: list[Market]) -> list[MarketSnapshot]:
        """
        Take snapshots of multiple markets.
        
        Args:
            markets: List of markets to snapshot
            
        Returns:
            List of successful snapshots
        """
        snapshots = []
        
        for market in markets:
            try:
                snapshot = await self.snapshot_market(market)
                if snapshot:
                    snapshots.append(snapshot)
            except Exception as e:
                logger.error(
                    "snapshot_failed",
                    ticker=market.ticker,
                    error=str(e),
                )
        
        logger.info(
            "batch_snapshot_complete",
            total=len(markets),
            successful=len(snapshots),
        )
        
        return snapshots
    
    async def get_historical_snapshots(
        self,
        ticker: str,
        days: int = 7,
    ) -> list[MarketSnapshot]:
        """
        Retrieve historical snapshots for a market.
        
        Args:
            ticker: Market ticker
            days: Number of days of history to retrieve
            
        Returns:
            List of snapshots in chronological order
        """
        since = datetime.utcnow() - timedelta(days=days)
        return await self.repository.get_snapshots(ticker, since=since)
    
    async def start_continuous_snapshotting(
        self,
        tickers: list[str],
    ) -> None:
        """
        Start continuous snapshotting in the background.
        
        Args:
            tickers: List of market tickers to monitor
        """
        if self._running:
            logger.warning("snapshotter_already_running")
            return
        
        self._running = True
        self._task = asyncio.create_task(
            self._snapshot_loop(tickers)
        )
        
        logger.info(
            "continuous_snapshotting_started",
            tickers=tickers,
            interval_minutes=self.interval_minutes,
        )
    
    async def stop(self) -> None:
        """Stop continuous snapshotting."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("snapshotter_stopped")
    
    async def _snapshot_loop(self, tickers: list[str]) -> None:
        """Main snapshotting loop."""
        while self._running:
            try:
                # Fetch current market data
                markets = []
                for ticker in tickers:
                    market = await self.client.get_market(ticker)
                    if market:
                        markets.append(market)
                
                # Take snapshots
                await self.snapshot_markets(markets)
                
                # Wait for next interval
                await asyncio.sleep(self.interval_minutes * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("snapshot_loop_error", error=str(e))
                await asyncio.sleep(60)  # Back off on error
    
    async def cleanup_old_snapshots(self, retention_days: Optional[int] = None) -> int:
        """
        Delete snapshots older than retention period.
        
        Returns:
            Number of snapshots deleted
        """
        days = retention_days or settings.data_retention_days
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        deleted = await self.repository.delete_old_snapshots(cutoff)
        
        logger.info(
            "snapshots_cleaned_up",
            cutoff=cutoff.isoformat(),
            deleted=deleted,
        )
        
        return deleted
