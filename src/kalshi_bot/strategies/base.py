"""
Base strategy interface.

All strategies must implement this interface to be used by the trading system.
"""

from abc import ABC, abstractmethod
from typing import Optional

from kalshi_bot.models.market import Market
from kalshi_bot.models.snapshot import BacktestResult, MarketSnapshot, StrategySignal


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    Strategies are plug-ins that:
    1. Evaluate a market and generate a signal
    2. Can be backtested against historical data
    3. Have configurable parameters
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this strategy."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the strategy logic."""
        pass
    
    @abstractmethod
    def evaluate(
        self,
        market: Market,
        features: dict,
        historical_snapshots: Optional[list[MarketSnapshot]] = None,
    ) -> StrategySignal:
        """
        Evaluate a market and generate a trading signal.
        
        Args:
            market: Current market state with orderbook
            features: Extracted features (spread, depth, momentum, etc.)
            historical_snapshots: Optional historical data for momentum/trend
            
        Returns:
            StrategySignal with direction, confidence, and expected value
        """
        pass
    
    @abstractmethod
    def backtest(
        self,
        snapshots: list[MarketSnapshot],
        settlement_price: Optional[int] = None,
    ) -> BacktestResult:
        """
        Backtest strategy on historical data.
        
        Args:
            snapshots: Historical market snapshots in chronological order
            settlement_price: Final settlement price (100 for YES, 0 for NO)
            
        Returns:
            BacktestResult with performance metrics
        """
        pass
    
    def validate_signal(self, signal: StrategySignal) -> bool:
        """
        Validate that a signal is reasonable.
        
        Override in subclasses for strategy-specific validation.
        """
        # Basic sanity checks
        if signal.fair_probability < 0 or signal.fair_probability > 1:
            return False
        if signal.confidence < 0 or signal.confidence > 1:
            return False
        if signal.entry_price is not None and not (1 <= signal.entry_price <= 99):
            return False
        return True


class StrategyRegistry:
    """Registry of available strategies."""
    
    _strategies: dict[str, type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, strategy_class: type[BaseStrategy]) -> type[BaseStrategy]:
        """Register a strategy class."""
        # Instantiate to get name
        instance = strategy_class()
        cls._strategies[instance.name] = strategy_class
        return strategy_class
    
    @classmethod
    def get(cls, name: str) -> Optional[type[BaseStrategy]]:
        """Get a strategy class by name."""
        return cls._strategies.get(name)
    
    @classmethod
    def list_all(cls) -> list[str]:
        """List all registered strategy names."""
        return list(cls._strategies.keys())
    
    @classmethod
    def create_all(cls) -> list[BaseStrategy]:
        """Create instances of all registered strategies."""
        return [strategy_class() for strategy_class in cls._strategies.values()]
