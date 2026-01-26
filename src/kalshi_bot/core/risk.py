"""
Risk management module.

Enforces all risk limits:
- Position sizing (Kelly or fixed)
- Maximum daily loss
- Maximum per-market exposure
- Maximum total exposure
- Maximum open positions
- Maximum trades per day
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import structlog

from kalshi_bot.config import settings
from kalshi_bot.models.order import Order, OrderSide
from kalshi_bot.models.position import DailyPnL, Position
from kalshi_bot.models.snapshot import StrategySignal

logger = structlog.get_logger()


@dataclass
class RiskState:
    """Current risk state tracking."""
    
    date: datetime = field(default_factory=datetime.utcnow)
    
    # Daily tracking
    trades_today: int = 0
    daily_realized_pnl: float = 0.0
    daily_unrealized_pnl: float = 0.0
    
    # Position tracking
    open_positions: dict[str, Position] = field(default_factory=dict)
    total_exposure: float = 0.0
    
    # Pending orders
    pending_order_exposure: float = 0.0
    
    @property
    def daily_total_pnl(self) -> float:
        return self.daily_realized_pnl + self.daily_unrealized_pnl
    
    @property
    def num_open_positions(self) -> int:
        return len(self.open_positions)


@dataclass
class RiskCheck:
    """Result of a risk check."""
    
    passed: bool
    reason: Optional[str] = None
    allowed_size: Optional[int] = None  # Maximum allowed position size


class RiskManager:
    """
    Central risk management for the trading system.
    
    Enforces all configurable risk limits and calculates
    appropriate position sizes.
    """
    
    def __init__(self):
        self.state = RiskState()
        self._idempotency_keys: set[str] = set()
    
    def reset_daily_state(self) -> None:
        """Reset daily tracking (call at start of each trading day)."""
        self.state = RiskState(date=datetime.utcnow())
        self._idempotency_keys.clear()
        logger.info("risk_state_reset")
    
    def check_order(
        self,
        signal: StrategySignal,
        proposed_size_dollars: float,
    ) -> RiskCheck:
        """
        Check if a proposed order passes all risk checks.
        
        Args:
            signal: Strategy signal with expected value and confidence
            proposed_size_dollars: Proposed position size in dollars
            
        Returns:
            RiskCheck with pass/fail and allowed size
        """
        checks = [
            self._check_daily_loss(),
            self._check_max_trades(),
            self._check_max_positions(),
            self._check_total_exposure(proposed_size_dollars),
            self._check_market_exposure(signal.ticker, proposed_size_dollars),
            self._check_signal_quality(signal),
        ]
        
        for check in checks:
            if not check.passed:
                logger.warning(
                    "risk_check_failed",
                    ticker=signal.ticker,
                    reason=check.reason,
                )
                return check
        
        # All checks passed, calculate allowed size
        allowed_size = self._calculate_allowed_size(signal, proposed_size_dollars)
        
        return RiskCheck(
            passed=True,
            allowed_size=allowed_size,
        )
    
    def _check_daily_loss(self) -> RiskCheck:
        """Check if daily loss limit has been breached."""
        if self.state.daily_total_pnl < -settings.max_daily_loss_dollars:
            return RiskCheck(
                passed=False,
                reason=f"Daily loss limit breached: ${self.state.daily_total_pnl:.2f}",
            )
        return RiskCheck(passed=True)
    
    def _check_max_trades(self) -> RiskCheck:
        """Check if maximum trades per day reached."""
        if self.state.trades_today >= settings.max_trades_per_day:
            return RiskCheck(
                passed=False,
                reason=f"Max trades reached: {self.state.trades_today}",
            )
        return RiskCheck(passed=True)
    
    def _check_max_positions(self) -> RiskCheck:
        """Check if maximum open positions reached."""
        if self.state.num_open_positions >= settings.max_open_positions:
            return RiskCheck(
                passed=False,
                reason=f"Max positions reached: {self.state.num_open_positions}",
            )
        return RiskCheck(passed=True)
    
    def _check_total_exposure(self, proposed_size: float) -> RiskCheck:
        """Check if total exposure limit would be exceeded."""
        new_total = (
            self.state.total_exposure + 
            self.state.pending_order_exposure + 
            proposed_size
        )
        if new_total > settings.max_total_exposure_dollars:
            return RiskCheck(
                passed=False,
                reason=f"Total exposure limit: ${new_total:.2f} > ${settings.max_total_exposure_dollars}",
            )
        return RiskCheck(passed=True)
    
    def _check_market_exposure(self, ticker: str, proposed_size: float) -> RiskCheck:
        """Check if per-market exposure limit would be exceeded."""
        existing = 0.0
        if ticker in self.state.open_positions:
            existing = self.state.open_positions[ticker].cost_basis
        
        new_exposure = existing + proposed_size
        if new_exposure > settings.max_per_market_exposure_dollars:
            return RiskCheck(
                passed=False,
                reason=f"Market exposure limit: ${new_exposure:.2f} > ${settings.max_per_market_exposure_dollars}",
            )
        return RiskCheck(passed=True)
    
    def _check_signal_quality(self, signal: StrategySignal) -> RiskCheck:
        """Check if signal meets quality thresholds."""
        if signal.expected_value < settings.min_expected_value:
            return RiskCheck(
                passed=False,
                reason=f"EV too low: {signal.expected_value:.3f} < {settings.min_expected_value}",
            )
        
        if signal.confidence < settings.confidence_threshold:
            return RiskCheck(
                passed=False,
                reason=f"Confidence too low: {signal.confidence:.2f} < {settings.confidence_threshold}",
            )
        
        # Backtest requirements
        if signal.backtest_win_rate is not None:
            if signal.backtest_win_rate < settings.min_win_rate:
                return RiskCheck(
                    passed=False,
                    reason=f"Backtest win rate too low: {signal.backtest_win_rate:.1%}",
                )
        
        if signal.backtest_samples is not None:
            if signal.backtest_samples < settings.min_backtest_samples:
                return RiskCheck(
                    passed=False,
                    reason=f"Insufficient backtest samples: {signal.backtest_samples}",
                )
        
        return RiskCheck(passed=True)
    
    def _calculate_allowed_size(
        self,
        signal: StrategySignal,
        proposed_size: float,
    ) -> int:
        """
        Calculate the maximum allowed position size.
        
        Uses Kelly criterion if enabled, capped by risk limits.
        """
        if settings.use_kelly_sizing and signal.expected_value > 0:
            # Kelly fraction: f = (p*b - q) / b
            # where p = win probability, q = 1-p, b = odds (payout ratio)
            
            # For binary contracts, odds depend on entry price
            entry_price = signal.entry_price or 50
            win_payout = (100 - entry_price) / entry_price  # e.g., 50c -> 1:1
            
            # Estimate win probability from fair probability
            if signal.side == OrderSide.YES:
                p = signal.fair_probability
            else:
                p = 1 - signal.fair_probability
            
            q = 1 - p
            
            if win_payout > 0:
                kelly = (p * win_payout - q) / win_payout
                kelly = max(0, kelly)  # No negative sizing
                kelly *= settings.kelly_fraction  # Fractional Kelly
                
                # Convert to dollar amount
                bankroll = settings.max_total_exposure_dollars
                kelly_size = kelly * bankroll
            else:
                kelly_size = 0
            
            # Cap at various limits
            max_size = min(
                proposed_size,
                kelly_size,
                settings.max_per_market_exposure_dollars,
                settings.max_total_exposure_dollars - self.state.total_exposure,
            )
        else:
            max_size = min(
                proposed_size,
                settings.default_position_size_dollars,
                settings.max_per_market_exposure_dollars,
            )
        
        # Convert to contracts (assuming entry price in signal)
        entry_price = signal.entry_price or 50
        contracts = int(max_size * 100 / entry_price)
        
        return max(1, contracts)  # At least 1 contract if approved
    
    def check_idempotency(self, key: str) -> bool:
        """
        Check if an idempotency key has been used.
        
        Returns:
            True if key is new (order can proceed)
            False if key exists (duplicate order)
        """
        if key in self._idempotency_keys:
            logger.warning("duplicate_order_blocked", idempotency_key=key)
            return False
        return True
    
    def record_order_submitted(self, order: Order) -> None:
        """Record that an order was submitted."""
        self._idempotency_keys.add(order.idempotency_key)
        self.state.trades_today += 1
        self.state.pending_order_exposure += order.notional_value
        
        logger.info(
            "order_recorded",
            ticker=order.ticker,
            trades_today=self.state.trades_today,
            pending_exposure=self.state.pending_order_exposure,
        )
    
    def record_fill(self, order: Order) -> None:
        """Record a filled order, update positions."""
        # Remove from pending
        self.state.pending_order_exposure -= order.notional_value
        self.state.pending_order_exposure = max(0, self.state.pending_order_exposure)
        
        # Update position
        ticker = order.ticker
        if ticker not in self.state.open_positions:
            self.state.open_positions[ticker] = Position(
                ticker=ticker,
                side=order.side,
                quantity=order.filled_quantity,
                average_entry_price=order.average_fill_price or order.price,
            )
        else:
            pos = self.state.open_positions[ticker]
            pos.add_quantity(
                order.filled_quantity,
                order.average_fill_price or order.price,
            )
        
        # Update total exposure
        self._recalculate_exposure()
        
        logger.info(
            "fill_recorded",
            ticker=ticker,
            quantity=order.filled_quantity,
            total_exposure=self.state.total_exposure,
        )
    
    def record_pnl(self, ticker: str, realized_pnl: float) -> None:
        """Record realized P&L from a closed position."""
        self.state.daily_realized_pnl += realized_pnl
        
        if ticker in self.state.open_positions:
            del self.state.open_positions[ticker]
        
        self._recalculate_exposure()
        
        logger.info(
            "pnl_recorded",
            ticker=ticker,
            pnl=realized_pnl,
            daily_total=self.state.daily_total_pnl,
        )
    
    def update_unrealized_pnl(self) -> None:
        """Recalculate unrealized P&L from open positions."""
        unrealized = sum(
            pos.unrealized_pnl or 0
            for pos in self.state.open_positions.values()
        )
        self.state.daily_unrealized_pnl = unrealized
    
    def _recalculate_exposure(self) -> None:
        """Recalculate total exposure from open positions."""
        self.state.total_exposure = sum(
            pos.cost_basis
            for pos in self.state.open_positions.values()
        )
    
    def get_daily_summary(self) -> DailyPnL:
        """Get daily P&L summary."""
        return DailyPnL(
            date=self.state.date,
            realized_pnl=self.state.daily_realized_pnl,
            unrealized_pnl=self.state.daily_unrealized_pnl,
            trades_placed=self.state.trades_today,
            peak_exposure=self.state.total_exposure,  # Simplified
            ending_exposure=self.state.total_exposure,
            markets_traded=list(self.state.open_positions.keys()),
        )
