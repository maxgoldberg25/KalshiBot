"""
Backtesting harness for strategy evaluation.

Implements walk-forward / train-test split methodology
to evaluate strategy performance on historical data.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import structlog

from kalshi_bot.config import settings
from kalshi_bot.models.snapshot import BacktestResult, MarketSnapshot
from kalshi_bot.strategies.base import BaseStrategy

logger = structlog.get_logger()


@dataclass
class WalkForwardResult:
    """Results from walk-forward backtesting."""
    
    strategy_name: str
    ticker: str
    
    # Aggregate metrics across all folds
    total_trades: int
    overall_win_rate: float
    overall_return: float
    avg_fold_sharpe: float
    max_drawdown: float
    
    # Per-fold results
    fold_results: list[BacktestResult]
    
    # Validity
    is_valid: bool
    meets_thresholds: bool
    failure_reason: Optional[str] = None


class BacktestHarness:
    """
    Backtesting framework for evaluating strategies.
    
    Uses walk-forward methodology:
    1. Split data into training and test periods
    2. Train/calibrate on training data
    3. Evaluate on test data
    4. Roll forward and repeat
    """
    
    def __init__(
        self,
        train_ratio: float = 0.7,
        min_train_samples: int = 20,
        min_test_samples: int = 10,
    ):
        self.train_ratio = train_ratio
        self.min_train_samples = min_train_samples
        self.min_test_samples = min_test_samples
    
    def backtest_strategy(
        self,
        strategy: BaseStrategy,
        snapshots: list[MarketSnapshot],
        settlement_price: Optional[int] = None,
    ) -> BacktestResult:
        """
        Run simple backtest on a strategy.
        
        Args:
            strategy: Strategy to evaluate
            snapshots: Historical market snapshots
            settlement_price: Final settlement (100 for YES, 0 for NO)
            
        Returns:
            BacktestResult with performance metrics
        """
        if len(snapshots) < settings.min_backtest_samples:
            return BacktestResult.insufficient_data(
                strategy.name,
                snapshots[0].ticker if snapshots else "unknown",
                len(snapshots),
            )
        
        return strategy.backtest(snapshots, settlement_price)
    
    def walk_forward_backtest(
        self,
        strategy: BaseStrategy,
        snapshots: list[MarketSnapshot],
        n_folds: int = 5,
    ) -> WalkForwardResult:
        """
        Run walk-forward backtest with multiple folds.
        
        Splits data into n_folds sequential segments,
        backtests on each, and aggregates results.
        
        Args:
            strategy: Strategy to evaluate
            snapshots: Historical market snapshots (chronological)
            n_folds: Number of folds for cross-validation
            
        Returns:
            WalkForwardResult with aggregate and per-fold metrics
        """
        ticker = snapshots[0].ticker if snapshots else "unknown"
        
        if len(snapshots) < self.min_train_samples + self.min_test_samples:
            return WalkForwardResult(
                strategy_name=strategy.name,
                ticker=ticker,
                total_trades=0,
                overall_win_rate=0.0,
                overall_return=0.0,
                avg_fold_sharpe=0.0,
                max_drawdown=0.0,
                fold_results=[],
                is_valid=False,
                meets_thresholds=False,
                failure_reason="Insufficient data for walk-forward",
            )
        
        # Calculate fold sizes
        fold_size = len(snapshots) // n_folds
        if fold_size < self.min_test_samples:
            n_folds = len(snapshots) // self.min_test_samples
            fold_size = len(snapshots) // max(n_folds, 1)
        
        fold_results: list[BacktestResult] = []
        all_wins = 0
        all_trades = 0
        all_returns: list[float] = []
        all_drawdowns: list[float] = []
        all_sharpes: list[float] = []
        
        logger.info(
            "walk_forward_start",
            strategy=strategy.name,
            ticker=ticker,
            n_folds=n_folds,
            fold_size=fold_size,
            total_samples=len(snapshots),
        )
        
        for i in range(n_folds):
            start_idx = i * fold_size
            end_idx = start_idx + fold_size
            if i == n_folds - 1:
                end_idx = len(snapshots)  # Last fold gets remainder
            
            fold_data = snapshots[start_idx:end_idx]
            
            if len(fold_data) < self.min_test_samples:
                continue
            
            result = strategy.backtest(fold_data, settlement_price=None)
            fold_results.append(result)
            
            if result.is_valid and result.num_trades > 0:
                wins = int(result.win_rate * result.num_trades)
                all_wins += wins
                all_trades += result.num_trades
                all_returns.append(result.total_return)
                all_drawdowns.append(result.max_drawdown)
                if result.sharpe_ratio is not None:
                    all_sharpes.append(result.sharpe_ratio)
        
        # Aggregate metrics
        if all_trades == 0:
            return WalkForwardResult(
                strategy_name=strategy.name,
                ticker=ticker,
                total_trades=0,
                overall_win_rate=0.0,
                overall_return=0.0,
                avg_fold_sharpe=0.0,
                max_drawdown=0.0,
                fold_results=fold_results,
                is_valid=False,
                meets_thresholds=False,
                failure_reason="No trades generated across folds",
            )
        
        overall_win_rate = all_wins / all_trades
        overall_return = sum(all_returns)
        avg_sharpe = np.mean(all_sharpes) if all_sharpes else 0.0
        max_dd = max(all_drawdowns) if all_drawdowns else 0.0
        
        # Check thresholds
        meets_thresholds = (
            overall_win_rate >= settings.min_win_rate and
            all_trades >= settings.min_backtest_samples and
            max_dd <= settings.max_drawdown_percent
        )
        
        failure_reason = None
        if not meets_thresholds:
            if overall_win_rate < settings.min_win_rate:
                failure_reason = f"Win rate {overall_win_rate:.1%} < {settings.min_win_rate:.0%}"
            elif all_trades < settings.min_backtest_samples:
                failure_reason = f"Trades {all_trades} < {settings.min_backtest_samples}"
            elif max_dd > settings.max_drawdown_percent:
                failure_reason = f"Max DD {max_dd:.1%} > {settings.max_drawdown_percent:.0%}"
        
        result = WalkForwardResult(
            strategy_name=strategy.name,
            ticker=ticker,
            total_trades=all_trades,
            overall_win_rate=overall_win_rate,
            overall_return=overall_return,
            avg_fold_sharpe=avg_sharpe,
            max_drawdown=max_dd,
            fold_results=fold_results,
            is_valid=True,
            meets_thresholds=meets_thresholds,
            failure_reason=failure_reason,
        )
        
        logger.info(
            "walk_forward_complete",
            strategy=strategy.name,
            ticker=ticker,
            total_trades=all_trades,
            win_rate=f"{overall_win_rate:.1%}",
            meets_thresholds=meets_thresholds,
        )
        
        return result
    
    def validate_strategy_for_market(
        self,
        strategy: BaseStrategy,
        snapshots: list[MarketSnapshot],
    ) -> tuple[bool, Optional[BacktestResult], Optional[str]]:
        """
        Validate if a strategy meets requirements for a specific market.
        
        Args:
            strategy: Strategy to validate
            snapshots: Historical data for the market
            
        Returns:
            Tuple of (is_valid, backtest_result, failure_reason)
        """
        if len(snapshots) < settings.min_backtest_samples:
            return (
                False,
                None,
                f"Insufficient samples: {len(snapshots)} < {settings.min_backtest_samples}",
            )
        
        result = self.backtest_strategy(strategy, snapshots)
        
        if not result.is_valid:
            return (False, result, result.reason_invalid)
        
        if result.num_trades < 5:
            return (False, result, f"Too few trades: {result.num_trades}")
        
        if result.win_rate < settings.min_win_rate:
            return (
                False,
                result,
                f"Win rate {result.win_rate:.1%} < {settings.min_win_rate:.0%}",
            )
        
        if result.max_drawdown > settings.max_drawdown_percent:
            return (
                False,
                result,
                f"Max drawdown {result.max_drawdown:.1%} > {settings.max_drawdown_percent:.0%}",
            )
        
        return (True, result, None)
