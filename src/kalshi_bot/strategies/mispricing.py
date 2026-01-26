"""
Strategy 1: Mispricing Detection

Compares market implied probability to a fair probability estimate
derived from market microstructure features.

Logic:
- If depth_imbalance strongly favors bids (buyers), price may be undervalued
- If depth_imbalance strongly favors asks (sellers), price may be overvalued
- Combined with spread analysis and momentum to estimate fair value

This is a conservative baseline that only trades when:
1. Clear depth imbalance exists
2. Spread is tight (efficient market)
3. Sufficient volume for reliability
"""

from datetime import datetime
from typing import Optional

import numpy as np

from kalshi_bot.models.market import Market
from kalshi_bot.models.order import OrderSide
from kalshi_bot.models.snapshot import BacktestResult, MarketSnapshot, StrategySignal
from kalshi_bot.strategies.base import BaseStrategy, StrategyRegistry


@StrategyRegistry.register
class MispricingStrategy(BaseStrategy):
    """
    Detect mispriced markets using orderbook imbalance.
    
    Hypothesis: Significant depth imbalance indicates informed flow
    and can predict short-term price movement direction.
    """
    
    def __init__(
        self,
        min_depth_imbalance: float = 0.3,  # 30% imbalance required
        max_spread_cents: int = 5,          # Only tight spreads
        min_volume: int = 100,              # Minimum 24h volume
        confidence_scale: float = 0.5,      # Scale raw confidence
    ):
        self.min_depth_imbalance = min_depth_imbalance
        self.max_spread_cents = max_spread_cents
        self.min_volume = min_volume
        self.confidence_scale = confidence_scale
    
    @property
    def name(self) -> str:
        return "mispricing_v1"
    
    @property
    def description(self) -> str:
        return (
            "Detects mispriced markets by analyzing orderbook depth imbalance. "
            "Buys YES when bid depth significantly exceeds ask depth (bullish flow). "
            "Buys NO when ask depth significantly exceeds bid depth (bearish flow)."
        )
    
    def evaluate(
        self,
        market: Market,
        features: dict,
        historical_snapshots: Optional[list[MarketSnapshot]] = None,
    ) -> StrategySignal:
        """Evaluate market for mispricing opportunity."""
        
        # Default no-trade signal
        no_trade = StrategySignal(
            strategy_name=self.name,
            ticker=market.ticker,
            side=None,
            confidence=0.0,
            fair_probability=market.implied_probability,
            market_probability=market.implied_probability,
            edge=0.0,
            expected_value=0.0,
            reasoning="No signal generated",
        )
        
        # Require orderbook
        if market.orderbook is None:
            no_trade.reasoning = "No orderbook data"
            return no_trade
        
        spread = features.get("spread")
        depth_imbalance = features.get("depth_imbalance", 0.0)
        volume_24h = features.get("volume_24h", 0)
        mid_price = features.get("mid_price")
        
        # Filter checks
        if spread is None or spread > self.max_spread_cents:
            no_trade.reasoning = f"Spread too wide: {spread}c > {self.max_spread_cents}c"
            return no_trade
        
        if volume_24h < self.min_volume:
            no_trade.reasoning = f"Volume too low: {volume_24h} < {self.min_volume}"
            return no_trade
        
        if abs(depth_imbalance) < self.min_depth_imbalance:
            no_trade.reasoning = f"Depth imbalance too small: {depth_imbalance:.2f}"
            return no_trade
        
        if mid_price is None:
            no_trade.reasoning = "Cannot calculate mid price"
            return no_trade
        
        # Calculate fair probability adjustment based on imbalance
        # Positive imbalance (more bids) -> higher fair prob
        # Negative imbalance (more asks) -> lower fair prob
        adjustment = depth_imbalance * 0.1  # 10% max adjustment
        
        market_prob = mid_price / 100
        fair_prob = np.clip(market_prob + adjustment, 0.05, 0.95)
        
        # Determine direction and edge
        edge = fair_prob - market_prob
        
        if edge > 0.02:  # At least 2% edge for YES
            side = OrderSide.YES
            entry_price = int(mid_price) + 1  # Pay 1c above mid
        elif edge < -0.02:  # At least 2% edge for NO
            side = OrderSide.NO
            edge = -edge  # Make positive for NO side
            entry_price = 100 - int(mid_price) + 1
        else:
            no_trade.reasoning = f"Edge too small: {abs(edge):.3f}"
            return no_trade
        
        # Calculate confidence based on imbalance strength and spread
        confidence = min(
            abs(depth_imbalance) * self.confidence_scale,
            0.9
        )
        # Reduce confidence for wider spreads
        confidence *= (self.max_spread_cents - spread + 1) / self.max_spread_cents
        
        # Calculate expected value
        # EV = (prob_win * payout) - (prob_lose * cost)
        # For binary contracts: win = 100 - entry, lose = entry
        prob_win = fair_prob if side == OrderSide.YES else (1 - fair_prob)
        payout = (100 - entry_price) / 100  # Profit if win
        cost = entry_price / 100  # Loss if lose
        expected_value = (prob_win * payout) - ((1 - prob_win) * cost)
        
        return StrategySignal(
            strategy_name=self.name,
            ticker=market.ticker,
            side=side,
            confidence=confidence,
            fair_probability=fair_prob,
            market_probability=market_prob,
            edge=edge,
            expected_value=expected_value,
            entry_price=entry_price,
            features_used={
                "depth_imbalance": depth_imbalance,
                "spread": spread,
                "mid_price": mid_price,
                "adjustment": adjustment,
            },
            reasoning=(
                f"Depth imbalance {depth_imbalance:.2f} suggests "
                f"{'undervalued' if side == OrderSide.YES else 'overvalued'} "
                f"(fair: {fair_prob:.1%} vs market: {market_prob:.1%})"
            ),
        )
    
    def backtest(
        self,
        snapshots: list[MarketSnapshot],
        settlement_price: Optional[int] = None,
    ) -> BacktestResult:
        """Backtest on historical snapshots."""
        
        if len(snapshots) < 10:
            return BacktestResult.insufficient_data(
                self.name,
                snapshots[0].ticker if snapshots else "unknown",
                len(snapshots),
            )
        
        ticker = snapshots[0].ticker
        trades = []
        
        # Simulate trades at each snapshot
        for i, snap in enumerate(snapshots[:-1]):  # Don't trade on last snapshot
            features = {
                "spread": snap.spread,
                "depth_imbalance": snap.depth_imbalance,
                "volume_24h": snap.volume_24h,
                "mid_price": snap.mid,
            }
            
            # Create minimal market object for evaluation
            market = Market(
                ticker=snap.ticker,
                title="",
                last_price=snap.last_price,
                volume_24h=snap.volume_24h,
            )
            
            # Can't fully evaluate without orderbook, use features directly
            if snap.spread is not None and snap.spread <= self.max_spread_cents:
                if snap.volume_24h >= self.min_volume:
                    if abs(snap.depth_imbalance) >= self.min_depth_imbalance:
                        # Simulate trade
                        side = OrderSide.YES if snap.depth_imbalance > 0 else OrderSide.NO
                        entry = snap.mid if snap.mid else snap.last_price
                        
                        # Check exit at next snapshot
                        next_snap = snapshots[i + 1]
                        exit_price = next_snap.mid if next_snap.mid else next_snap.last_price
                        
                        if side == OrderSide.YES:
                            pnl = (exit_price - entry) / 100
                        else:
                            pnl = (entry - exit_price) / 100
                        
                        trades.append({
                            "entry": entry,
                            "exit": exit_price,
                            "side": side,
                            "pnl": pnl,
                            "won": pnl > 0,
                        })
        
        if len(trades) == 0:
            return BacktestResult.insufficient_data(self.name, ticker, len(snapshots))
        
        # Calculate metrics
        wins = sum(1 for t in trades if t["won"])
        losses = len(trades) - wins
        win_rate = wins / len(trades)
        
        pnls = [t["pnl"] for t in trades]
        total_return = sum(pnls)
        avg_return = np.mean(pnls)
        
        # Drawdown
        cumulative = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumulative)
        drawdown = peak - cumulative
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # Sharpe (annualized, assuming daily snapshots)
        if np.std(pnls) > 0:
            sharpe = (np.mean(pnls) / np.std(pnls)) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        avg_win = np.mean([t["pnl"] for t in trades if t["won"]]) if wins > 0 else 0
        avg_loss = np.mean([t["pnl"] for t in trades if not t["won"]]) if losses > 0 else 0
        
        profit_factor = None
        if losses > 0 and avg_loss < 0:
            gross_profit = wins * avg_win
            gross_loss = abs(losses * avg_loss)
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
        
        return BacktestResult(
            strategy_name=self.name,
            ticker=ticker,
            start_date=snapshots[0].timestamp,
            end_date=snapshots[-1].timestamp,
            num_samples=len(snapshots),
            num_trades=len(trades),
            win_rate=win_rate,
            total_return=total_return,
            avg_return_per_trade=avg_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
        )
