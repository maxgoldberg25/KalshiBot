"""Abstract base class for Kalshi API clients."""

from abc import ABC, abstractmethod
from typing import Optional

from kalshi_bot.models.market import Market, OrderBook
from kalshi_bot.models.order import Fill, Order


class BaseKalshiClient(ABC):
    """
    Abstract interface for Kalshi API operations.
    
    Implementations:
    - KalshiClient: Real API client for production
    - MockKalshiClient: Mock client for testing
    """
    
    # ─────────────────────────────────────────────────────────────────────────
    # MARKET DATA
    # ─────────────────────────────────────────────────────────────────────────
    
    @abstractmethod
    async def get_markets(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
        event_ticker: Optional[str] = None,
    ) -> tuple[list[Market], Optional[str]]:
        """
        Fetch markets from the API.
        
        Returns:
            Tuple of (markets, next_cursor)
        """
        pass
    
    @abstractmethod
    async def get_market(self, ticker: str) -> Optional[Market]:
        """Get a single market by ticker."""
        pass
    
    @abstractmethod
    async def get_orderbook(self, ticker: str) -> Optional[OrderBook]:
        """Get orderbook for a market."""
        pass
    
    @abstractmethod
    async def get_events(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """
        Fetch events (market categories).
        
        Returns:
            Tuple of (events, next_cursor)
        """
        pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRADING
    # ─────────────────────────────────────────────────────────────────────────
    
    @abstractmethod
    async def place_order(self, order: Order) -> Order:
        """
        Place an order on Kalshi.
        
        Returns:
            Updated order with exchange order ID and status
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order status by ID."""
        pass
    
    @abstractmethod
    async def get_fills(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
    ) -> list[Fill]:
        """Get recent fills, optionally filtered by ticker."""
        pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT
    # ─────────────────────────────────────────────────────────────────────────
    
    @abstractmethod
    async def get_balance(self) -> float:
        """Get account balance in dollars."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[dict]:
        """Get current positions."""
        pass
    
    # ─────────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────────
    
    @abstractmethod
    async def close(self) -> None:
        """Close the client and cleanup resources."""
        pass
