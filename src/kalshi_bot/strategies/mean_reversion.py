"""
Strategy 2: Mean Reversion / Spread Capture

Uses limit orders to capture bid-ask spread in liquid markets
when price deviates from short-term mean.

Logic:
- Track short-term price mean from recent snapshots
- When price deviates significantly, place limit order anticipating reversion
- Use tight limits and conservative sizing
- Avoid illiquid markets where spread capture is difficult

This strategy is designed for:
- High-frequency same-day markets
- Liquid markets with tight spreads
- Small edge, many trades approach
"""

from datetime import datetime
from typing import Optional

import numpy as np

from kalshi_bot.models.market import Market
from kalshi_bot.models.order import OrderSide
from kalshi_bot.models.snapshot import BacktestResult, MarketSnapshot, StrategySignal
from kalshi_bot.strategies.base import BaseStrategy, StrategyRegistry


@StrategyRegistry.register
class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy for liquid same-day markets.
    
    Places limit orders when price deviates from moving average,
    expecting short-term reversion.
    """
    
    def __init__(
        self,
        lookback_periods: int = 6,          # Number of snapshots for MA
        deviation_threshold: float = 0.03,   # 3% deviation from MA
        max_spread_cents: int = 4,           # Require very tight spreads
        min_volume: int = 200,               # Higher volume requirement
        min_depth: int = 100,                # Minimum orderbook depth
    ):
        self.lookback_periods = lookback_periods
        self.deviation_threshold = deviation_threshold
        self.max_spread_cents = max_spread_cents
        self.min_volume = min_volume
        self.min_depth = min_depth
    
    @property
    def name(self) -> str:
        return "mean_reversion_v1"
    
    @property
    def description(self) -> str:
        return (
            "Mean reversion strategy that trades when price deviates from "
            f"short-term moving average by >{self.deviation_threshold:.0%}. "
            "Uses limit orders to capture spread while betting on reversion."
        )
    
    def evaluate(
        self,
        market: Market,
        features: dict,
        historical_snapshots: Optional[list[MarketSnapshot]] = None,
    ) -> StrategySignal:
        """Evaluate market for mean reversion opportunity."""
        
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
        volume_24h = features.get("volume_24h", 0)
        mid_price = features.get("mid_price")
        total_depth = features.get("bid_depth", 0) + features.get("ask_depth", 0)
        
        # Strict liquidity requirements
        if spread is None or spread > self.max_spread_cents:
            no_trade.reasoning = f"Spread too wide: {spread}c"
            return no_trade
        
        if volume_24h < self.min_volume:
            no_trade.reasoning = f"Volume too low: {volume_24h}"
            return no_trade
        
        if total_depth < self.min_depth:
            no_trade.reasoning = f"Depth too low: {total_depth}"
            return no_trade
        
        if mid_price is None:
            no_trade.reasoning = "Cannot calculate mid price"
            return no_trade
        
        # Need historical data for MA calculation
        if historical_snapshots is None or len(historical_snapshots) < self.lookback_periods:
            no_trade.reasoning = (
                f"Insufficient history: need {self.lookback_periods} snapshots, "
                f"have {len(historical_snapshots) if historical_snapshots else 0}"
            )
            return no_trade
        
        # Calculate moving average from recent snapshots
        recent = historical_snapshots[-self.lookback_periods:]
        prices = [s.mid if s.mid else s.last_price for s in recent]
        ma = np.mean(prices)
        
        # Calculate deviation from MA
        deviation = (mid_price - ma) / ma
        
        if abs(deviation) < self.deviation_threshold:
            no_trade.reasoning = f"Deviation {deviation:.2%} below threshold {self.deviation_threshold:.0%}"
            return no_trade
        
        # Determine direction: fade the deviation (mean reversion)
        if deviation > 0:
            # Price above MA, expect reversion down -> buy NO
            side = OrderSide.NO
            fair_prob = (ma / 100)  # Fair prob is at MA level
            entry_price = 100 - int(mid_price) + 1  # Buy NO at slightly above mid
        else:
            # Price below MA, expect reversion up -> buy YES
            side = OrderSide.YES
            fair_prob = (ma / 100)
            entry_price = int(mid_price) - 1  # Buy YES at slightly below mid
        
        market_prob = mid_price / 100
        edge = abs(fair_prob - market_prob)
        
        # Confidence based on deviation magnitude and liquidity
        deviation_factor = min(abs(deviation) / self.deviation_threshold, 2.0) / 2
        liquidity_factor = min(volume_24h / 500, 1.0)
        confidence = deviation_factor * liquidity_factor * 0.7  # Max 0.7 confidence
        
        # Expected value calculation
        # For mean reversion, expect price to move toward MA
        expected_move = abs(mid_price - ma)
        prob_reversion = 0.6  # Conservative estimate of reversion probability
        expected_value = (prob_reversion * expected_move - (1 - prob_reversion) * expected_move) / 100
        
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
                "mid_price": mid_price,
                "ma": ma,
                "deviation": deviation,
                "spread": spread,
                "volume_24h": volume_24h,
            },
            reasoning=(
                f"Price {mid_price:.0f}c deviates {deviation:.1%} from MA {ma:.0f}c. "
                f"Expect mean reversion toward {ma:.0f}c."
            ),
        )
    
    def backtest(
        self,
        snapshots: list[MarketSnapshot],
        settlement_price: Optional[int] = None,
    ) -> BacktestResult:
        """Backtest mean reversion on historical snapshots."""
        
        min_required = self.lookback_periods + 5
        if len(snapshots) < min_required:
            return BacktestResult.insufficient_data(
                self.name,
                snapshots[0].ticker if snapshots else "unknown",
                len(snapshots),
            )
        
        ticker = snapshots[0].ticker
        trades = []
        
        # Simulate trades
        for i in range(self.lookback_periods, len(snapshots) - 1):
            snap = snapshots[i]
            
            # Calculate MA from lookback
            lookback = snapshots[i - self.lookback_periods:i]
            prices = [s.mid if s.mid else s.last_price for s in lookback]
            ma = np.mean(prices)
            
            current = snap.mid if snap.mid else snap.last_price
            deviation = (current - ma) / ma if ma > 0 else 0
            
            # Check filters
            if snap.spread is not None and snap.spread > self.max_spread_cents:
                continue
            if snap.volume_24h < self.min_volume:
                continue
            
            # Check for signal
            if abs(deviation) >= self.deviation_threshold:
                side = OrderSide.NO if deviation > 0 else OrderSide.YES
                entry = current
                
                # Check exit at next snapshot
                next_snap = snapshots[i + 1]
                exit_price = next_snap.mid if next_snap.mid else next_snap.last_price
                
                # P&L depends on side
                if side == OrderSide.YES:
                    pnl = (exit_price - entry) / 100
                else:
                    pnl = (entry - exit_price) / 100
                
                trades.append({
                    "entry": entry,
                    "exit": exit_price,
                    "side": side,
                    "deviation": deviation,
                    "ma": ma,
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
        
        # Sharpe
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
