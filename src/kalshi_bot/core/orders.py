"""
Order management module.

Handles order lifecycle:
- Order generation from signals
- Idempotency enforcement
- Order submission (paper or live)
- Order status tracking
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

import structlog

from kalshi_bot.client.base import BaseKalshiClient
from kalshi_bot.config import TradingMode, settings
from kalshi_bot.core.risk import RiskManager
from kalshi_bot.models.order import Order, OrderSide, OrderStatus, OrderType
from kalshi_bot.models.snapshot import StrategySignal

logger = structlog.get_logger()


class OrderManager:
    """
    Manages order creation and execution.
    
    Features:
    - Generates orders from strategy signals
    - Enforces idempotency
    - Routes to paper or live execution
    - Tracks order status
    """
    
    def __init__(
        self,
        client: BaseKalshiClient,
        risk_manager: RiskManager,
        mode: Optional[TradingMode] = None,
    ):
        self.client = client
        self.risk_manager = risk_manager
        self.mode = mode or settings.mode
        
        self._orders: dict[str, Order] = {}
    
    async def process_signal(
        self,
        signal: StrategySignal,
        position_size_dollars: Optional[float] = None,
    ) -> Optional[Order]:
        """
        Process a strategy signal and potentially create an order.
        
        Args:
            signal: Strategy signal to process
            position_size_dollars: Override position size (optional)
            
        Returns:
            Created order if approved, None if rejected
        """
        if not signal.is_tradeable:
            logger.debug("signal_not_tradeable", ticker=signal.ticker)
            return None
        
        # Default position size
        if position_size_dollars is None:
            position_size_dollars = settings.default_position_size_dollars
        
        # Risk check
        risk_check = self.risk_manager.check_order(signal, position_size_dollars)
        if not risk_check.passed:
            logger.info(
                "signal_rejected_by_risk",
                ticker=signal.ticker,
                strategy=signal.strategy_name,
                reason=risk_check.reason,
            )
            return None
        
        # Generate order
        order = self._create_order(signal, risk_check.allowed_size or 1)
        
        # Idempotency check
        if not self.risk_manager.check_idempotency(order.idempotency_key):
            logger.info(
                "duplicate_order_skipped",
                ticker=signal.ticker,
                idempotency_key=order.idempotency_key,
            )
            return None
        
        # Execute based on mode
        if self.mode == TradingMode.DRY_RUN:
            return await self._dry_run_order(order)
        elif self.mode == TradingMode.PAPER:
            return await self._paper_order(order)
        else:
            return await self._live_order(order)
    
    def _create_order(
        self,
        signal: StrategySignal,
        quantity: int,
    ) -> Order:
        """Create an order from a signal."""
        # Determine order type
        order_type = OrderType.LIMIT if settings.use_limit_orders_only else OrderType.MARKET
        
        # Use signal's entry price or calculate from market
        price = signal.entry_price or 50
        
        # Generate idempotency key
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        idempotency_key = f"{date_str}:{signal.ticker}:{signal.strategy_name}:{signal.side.value}"
        
        order = Order(
            id=str(uuid4()),
            idempotency_key=idempotency_key,
            ticker=signal.ticker,
            side=signal.side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            strategy_name=signal.strategy_name,
            signal_confidence=signal.confidence,
            expected_value=signal.expected_value,
        )
        
        logger.info(
            "order_created",
            ticker=order.ticker,
            side=order.side.value,
            price=order.price,
            quantity=order.quantity,
            strategy=order.strategy_name,
            idempotency_key=order.idempotency_key,
        )
        
        return order
    
    async def _dry_run_order(self, order: Order) -> Order:
        """Log order without executing (dry run mode)."""
        logger.info(
            "dry_run_order",
            ticker=order.ticker,
            side=order.side.value,
            price=order.price,
            quantity=order.quantity,
            notional=order.notional_value,
            strategy=order.strategy_name,
        )
        
        order.status = OrderStatus.PENDING
        self._orders[order.id] = order
        
        return order
    
    async def _paper_order(self, order: Order) -> Order:
        """Execute paper trade."""
        # Record with risk manager
        self.risk_manager.record_order_submitted(order)
        
        # Submit to mock client (handles paper fills)
        order = await self.client.place_order(order)
        self._orders[order.id] = order
        
        # If filled, record with risk manager
        if order.status == OrderStatus.FILLED:
            self.risk_manager.record_fill(order)
        
        logger.info(
            "paper_order_result",
            ticker=order.ticker,
            status=order.status.value,
            filled_quantity=order.filled_quantity,
        )
        
        return order
    
    async def _live_order(self, order: Order) -> Order:
        """Execute live trade."""
        # Safety check
        if not settings.kalshi_api_key:
            logger.error("live_order_blocked", reason="No API key configured")
            order.status = OrderStatus.REJECTED
            order.error_message = "No API key configured for live trading"
            return order
        
        # Record with risk manager
        self.risk_manager.record_order_submitted(order)
        
        # Submit to real client
        try:
            order = await self.client.place_order(order)
            self._orders[order.id] = order
            
            logger.info(
                "live_order_submitted",
                ticker=order.ticker,
                kalshi_order_id=order.kalshi_order_id,
                status=order.status.value,
            )
            
        except Exception as e:
            logger.error(
                "live_order_failed",
                ticker=order.ticker,
                error=str(e),
            )
            order.status = OrderStatus.REJECTED
            order.error_message = str(e)
        
        return order
    
    async def sync_order_status(self, order_id: str) -> Optional[Order]:
        """Sync order status from exchange."""
        order = self._orders.get(order_id)
        if order is None:
            return None
        
        if order.kalshi_order_id is None:
            return order
        
        try:
            updated = await self.client.get_order(order.kalshi_order_id)
            if updated:
                order.status = updated.status
                order.filled_quantity = updated.filled_quantity
                
                if order.status == OrderStatus.FILLED and order.filled_at is None:
                    order.filled_at = datetime.utcnow()
                    self.risk_manager.record_fill(order)
                
        except Exception as e:
            logger.error(
                "order_sync_failed",
                order_id=order_id,
                error=str(e),
            )
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        order = self._orders.get(order_id)
        if order is None:
            return False
        
        if order.kalshi_order_id is None:
            order.status = OrderStatus.CANCELLED
            return True
        
        success = await self.client.cancel_order(order.kalshi_order_id)
        if success:
            order.status = OrderStatus.CANCELLED
        
        return success
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)
    
    def get_orders_today(self) -> list[Order]:
        """Get all orders from today."""
        today = datetime.utcnow().date()
        return [
            order for order in self._orders.values()
            if order.created_at.date() == today
        ]
    
    def get_pending_orders(self) -> list[Order]:
        """Get all pending/open orders."""
        return [
            order for order in self._orders.values()
            if order.status in {OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.OPEN}
        ]
