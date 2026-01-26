"""
Main trading runner that orchestrates the complete trading cycle.

This is the entry point for scheduled runs (cron) or manual execution.
"""

import asyncio
from datetime import datetime
from typing import Optional

import pytz
import structlog

from kalshi_bot.client.base import BaseKalshiClient
from kalshi_bot.client.kalshi import KalshiClient
from kalshi_bot.client.mock import MockKalshiClient
from kalshi_bot.config import TradingMode, settings
from kalshi_bot.core.backtest import BacktestHarness
from kalshi_bot.core.discovery import MarketDiscovery
from kalshi_bot.core.orders import OrderManager
from kalshi_bot.core.risk import RiskManager
from kalshi_bot.core.snapshotter import Snapshotter
from kalshi_bot.db.repository import Repository
from kalshi_bot.models.market import Market
from kalshi_bot.models.snapshot import StrategySignal
from kalshi_bot.observability.alerts import send_alert
from kalshi_bot.observability.metrics import generate_daily_report
from kalshi_bot.strategies.base import StrategyRegistry

logger = structlog.get_logger()


class TradingRunner:
    """
    Main orchestrator for the trading bot.
    
    Coordinates all components:
    1. Market discovery
    2. Strategy evaluation
    3. Backtest validation
    4. Risk checks
    5. Order execution
    6. Reporting
    """
    
    def __init__(
        self,
        mode: Optional[TradingMode] = None,
        client: Optional[BaseKalshiClient] = None,
    ):
        self.mode = mode or settings.mode
        self.tz = pytz.timezone(settings.timezone)
        
        # Initialize components
        self.repository = Repository()
        
        # Client selection:
        # - Use provided client if given
        # - Use real client if API key ID AND private key path are set
        # - Fall back to mock client for testing without API credentials
        if client:
            self.client = client
        elif settings.kalshi_api_key_id and settings.kalshi_private_key_path:
            self.client = KalshiClient()
        else:
            self.client = MockKalshiClient()
        
        self.risk_manager = RiskManager()
        self.discovery = MarketDiscovery(self.client)
        self.order_manager = OrderManager(self.client, self.risk_manager, self.mode)
        self.snapshotter = Snapshotter(self.client, self.repository)
        self.backtest_harness = BacktestHarness()
        
        # Load strategies
        self.strategies = StrategyRegistry.create_all()
    
    async def run(self) -> dict:
        """
        Execute complete trading cycle.
        
        Returns:
            Summary dict with results
        """
        # Get current time - use UTC for date determination to avoid timezone issues
        utc_now = datetime.now(pytz.utc)
        run_start = utc_now.astimezone(self.tz)
        
        logger.info(
            "trading_run_started",
            mode=self.mode.value,
            timestamp=run_start.isoformat(),
            date_utc=utc_now.date().isoformat(),
            date_local=run_start.date().isoformat(),
            timezone=str(self.tz),
        )
        
        # Initialize database
        await self.repository.initialize()
        
        # Reset daily state
        self.risk_manager.reset_daily_state()
        
        summary = {
            "start_time": run_start.isoformat(),
            "mode": self.mode.value,
            "markets_discovered": 0,
            "markets_tradeable": 0,
            "signals_generated": 0,
            "signals_valid": 0,
            "orders_placed": 0,
            "orders_filled": 0,
            "errors": [],
        }
        
        try:
            # Step 1: Discover same-day markets
            logger.info("step_1_discovery")
            markets = await self.discovery.discover_and_filter(run_start)
            summary["markets_discovered"] = len(markets)
            
            if not markets:
                logger.warning("no_tradeable_markets_found")
                summary["errors"].append("No tradeable markets found")
                return summary
            
            summary["markets_tradeable"] = len(markets)
            
            # Step 2: Take snapshots for these markets
            logger.info("step_2_snapshots")
            await self.snapshotter.snapshot_markets(markets)
            
            # Step 3: Evaluate strategies for each market
            logger.info("step_3_strategy_evaluation")
            signals = await self._evaluate_all_strategies(markets)
            summary["signals_generated"] = len(signals)
            
            # Step 4: Validate signals against backtest thresholds
            logger.info("step_4_signal_validation")
            valid_signals = await self._validate_signals(signals)
            summary["signals_valid"] = len(valid_signals)
            
            if not valid_signals:
                logger.info("no_valid_signals")
                return summary
            
            # Step 5: Process orders for valid signals
            logger.info("step_5_order_execution")
            orders = await self._process_signals(valid_signals)
            summary["orders_placed"] = len(orders)
            summary["orders_filled"] = sum(1 for o in orders if o.status.value == "filled")
            
            # Step 6: Generate and send report
            logger.info("step_6_reporting")
            if settings.enable_daily_report:
                report = await self._generate_report(summary)
                summary["report"] = report
            
            # Send alert
            await send_alert(
                f"Trading run complete: {summary['orders_filled']}/{summary['orders_placed']} orders filled",
                level="info",
            )
            
        except Exception as e:
            logger.error("trading_run_error", error=str(e))
            summary["errors"].append(str(e))
            
            await send_alert(
                f"Trading run error: {e}",
                level="error",
            )
        
        finally:
            # Cleanup
            await self.client.close()
            
            run_end = datetime.now(self.tz)
            summary["end_time"] = run_end.isoformat()
            summary["duration_seconds"] = (run_end - run_start).total_seconds()
            
            logger.info(
                "trading_run_completed",
                duration=summary["duration_seconds"],
                orders_placed=summary["orders_placed"],
                orders_filled=summary["orders_filled"],
            )
        
        return summary
    
    async def _evaluate_all_strategies(
        self,
        markets: list[Market],
    ) -> list[StrategySignal]:
        """Evaluate all strategies for all markets."""
        signals = []
        
        for market in markets:
            features = market.to_features()
            
            # Get historical data for strategies that need it
            historical = await self.snapshotter.get_historical_snapshots(
                market.ticker,
                days=7,
            )
            
            for strategy in self.strategies:
                try:
                    signal = strategy.evaluate(market, features, historical)
                    
                    if signal.is_tradeable:
                        signals.append(signal)
                        logger.info(
                            "signal_generated",
                            ticker=market.ticker,
                            strategy=strategy.name,
                            side=signal.side.value if signal.side else None,
                            confidence=signal.confidence,
                            ev=signal.expected_value,
                        )
                        
                except Exception as e:
                    logger.error(
                        "strategy_evaluation_error",
                        ticker=market.ticker,
                        strategy=strategy.name,
                        error=str(e),
                    )
        
        return signals
    
    async def _validate_signals(
        self,
        signals: list[StrategySignal],
    ) -> list[StrategySignal]:
        """Validate signals against backtest requirements."""
        valid = []
        
        for signal in signals:
            # Get historical data for backtesting
            snapshots = await self.snapshotter.get_historical_snapshots(
                signal.ticker,
                days=30,  # More history for backtest
            )
            
            # Find the strategy
            strategy_class = StrategyRegistry.get(signal.strategy_name)
            if not strategy_class:
                logger.warning(
                    "strategy_not_found",
                    strategy=signal.strategy_name,
                )
                continue
            
            strategy = strategy_class()
            
            # Validate with backtest
            is_valid, backtest_result, reason = self.backtest_harness.validate_strategy_for_market(
                strategy,
                snapshots,
            )
            
            if is_valid and backtest_result:
                # Attach backtest results to signal
                signal.backtest_win_rate = backtest_result.win_rate
                signal.backtest_samples = backtest_result.num_trades
                signal.backtest_sharpe = backtest_result.sharpe_ratio
                
                # Final threshold check
                if signal.meets_thresholds(
                    min_confidence=settings.confidence_threshold,
                    min_ev=settings.min_expected_value,
                    min_win_rate=settings.min_win_rate,
                    min_samples=settings.min_backtest_samples,
                ):
                    valid.append(signal)
                    logger.info(
                        "signal_validated",
                        ticker=signal.ticker,
                        strategy=signal.strategy_name,
                        backtest_win_rate=signal.backtest_win_rate,
                    )
                else:
                    logger.info(
                        "signal_below_thresholds",
                        ticker=signal.ticker,
                        strategy=signal.strategy_name,
                        win_rate=signal.backtest_win_rate,
                    )
            else:
                logger.info(
                    "signal_backtest_invalid",
                    ticker=signal.ticker,
                    strategy=signal.strategy_name,
                    reason=reason,
                )
        
        return valid
    
    async def _process_signals(
        self,
        signals: list[StrategySignal],
    ) -> list:
        """Process valid signals into orders."""
        orders = []
        
        # Sort by expected value (best first)
        sorted_signals = sorted(
            signals,
            key=lambda s: s.expected_value,
            reverse=True,
        )
        
        for signal in sorted_signals:
            order = await self.order_manager.process_signal(signal)
            
            if order:
                orders.append(order)
                
                # Save to database
                await self.repository.save_order(order)
                
                # Check if we should stop (max trades, loss limit, etc.)
                if len(orders) >= settings.max_trades_per_day:
                    logger.info("max_trades_reached")
                    break
        
        return orders
    
    async def _generate_report(self, summary: dict) -> str:
        """Generate daily performance report."""
        daily_pnl = self.risk_manager.get_daily_summary()
        
        # Save to database
        await self.repository.save_daily_pnl(daily_pnl)
        
        # Generate text report
        report = generate_daily_report(
            summary=summary,
            daily_pnl=daily_pnl,
        )
        
        return report
    
    async def run_snapshot_only(self, tickers: list[str]) -> None:
        """Run snapshot collection without trading (for building history)."""
        await self.repository.initialize()
        
        logger.info("snapshot_only_run", tickers=tickers)
        
        markets = []
        for ticker in tickers:
            market = await self.client.get_market(ticker)
            if market:
                markets.append(market)
        
        await self.snapshotter.snapshot_markets(markets)
        await self.client.close()
