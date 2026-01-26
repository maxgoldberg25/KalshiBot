"""
Production Kalshi API client with RSA authentication, retries, and rate limiting.

Kalshi API uses RSA-PSS signing with SHA256 for authentication.
You need an API Key ID and a Private Key from https://kalshi.com/settings/api
"""

import asyncio
import base64
import hashlib
import time as time_module
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from kalshi_bot.client.base import BaseKalshiClient
from kalshi_bot.config import settings
from kalshi_bot.models.market import Market, OrderBook, OrderBookLevel
from kalshi_bot.models.order import Fill, Order, OrderSide, OrderStatus

import structlog

logger = structlog.get_logger()


class RateLimitError(Exception):
    """Raised when rate limit is hit."""
    pass


class KalshiAuthError(Exception):
    """Raised for authentication errors."""
    pass


class KalshiAPIError(Exception):
    """Raised for API errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Kalshi API Error {status_code}: {message}")


class KalshiClient(BaseKalshiClient):
    """
    Production Kalshi API client with RSA-PSS signing.
    
    Features:
    - RSA-PSS signature authentication (Kalshi's required method)
    - Automatic retries with exponential backoff
    - Rate limit handling
    - Request logging
    
    Requires:
    - API Key ID (UUID from Kalshi)
    - Private Key file path (.pem or .key)
    """
    
    def __init__(
        self,
        api_key_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key_id = api_key_id or settings.kalshi_api_key_id
        self.private_key_path = private_key_path or settings.kalshi_private_key_path
        self.base_url = base_url or settings.kalshi_api_base_url
        
        self._client: Optional[httpx.AsyncClient] = None
        self._private_key: Optional[rsa.RSAPrivateKey] = None
        self._rate_limit_remaining: int = 100
        self._rate_limit_reset: Optional[datetime] = None
        self._min_request_delay: float = 0.5  # Minimum delay between requests (seconds)
        self._last_request_time: float = 0.0
        
        # Load private key if path provided
        if self.private_key_path:
            self._load_private_key()
    
    def _load_private_key(self) -> None:
        """Load RSA private key from file."""
        key_path = Path(self.private_key_path)
        if not key_path.exists():
            raise KalshiAuthError(f"Private key file not found: {self.private_key_path}")
        
        try:
            with open(key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                )
            logger.info("private_key_loaded", path=str(key_path))
        except Exception as e:
            raise KalshiAuthError(f"Failed to load private key: {e}")
    
    def _sign_request(self, method: str, path: str, timestamp: int) -> str:
        """
        Create RSA-PSS signature for Kalshi API authentication.
        
        Signature format: timestamp + method + path
        """
        if not self._private_key:
            raise KalshiAuthError("Private key not loaded")
        
        # Create message to sign: timestamp + method + path
        message = f"{timestamp}{method}{path}".encode("utf-8")
        
        # Sign with RSA-PSS
        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        
        return base64.b64encode(signature).decode("utf-8")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._client
    
    def _get_auth_headers(self, method: str, path: str) -> dict[str, str]:
        """Get request headers with RSA signature authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self.api_key_id and self._private_key:
            # Timestamp in milliseconds
            timestamp = int(time_module.time() * 1000)
            
            # Create signature
            signature = self._sign_request(method, path, timestamp)
            
            headers["KALSHI-ACCESS-KEY"] = self.api_key_id
            headers["KALSHI-ACCESS-SIGNATURE"] = signature
            headers["KALSHI-ACCESS-TIMESTAMP"] = str(timestamp)
        
        return headers
    
    async def _check_rate_limit_before_request(self) -> None:
        """Check rate limit and wait if needed before making request."""
        # If we're low on remaining requests, wait longer
        if self._rate_limit_remaining < 5:
            wait_time = 2.0  # Wait 2 seconds if very low
            logger.debug("rate_limit_low", remaining=self._rate_limit_remaining, wait=wait_time)
            await asyncio.sleep(wait_time)
        elif self._rate_limit_remaining < 20:
            wait_time = 1.0  # Wait 1 second if getting low
            logger.debug("rate_limit_moderate", remaining=self._rate_limit_remaining, wait=wait_time)
            await asyncio.sleep(wait_time)
        
        # Enforce minimum delay between requests
        now = time_module.time()
        time_since_last = now - self._last_request_time
        if time_since_last < self._min_request_delay:
            await asyncio.sleep(self._min_request_delay - time_since_last)
        self._last_request_time = time_module.time()
    
    async def _handle_rate_limit(self, response: httpx.Response) -> None:
        """Update rate limit tracking from response headers."""
        if "X-RateLimit-Remaining" in response.headers:
            self._rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        
        if "X-RateLimit-Reset" in response.headers:
            try:
                reset_timestamp = int(response.headers["X-RateLimit-Reset"])
                self._rate_limit_reset = datetime.fromtimestamp(reset_timestamp)
            except (ValueError, TypeError):
                pass
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            logger.warning("rate_limit_hit", retry_after=retry_after, remaining=self._rate_limit_remaining)
            await asyncio.sleep(retry_after)
            # Reset remaining after waiting
            self._rate_limit_remaining = 50  # Conservative estimate
            raise RateLimitError(f"Rate limited, retry after {retry_after}s")
    
    @retry(
        retry=retry_if_exception_type((httpx.RequestError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make an API request with RSA signature authentication."""
        # Check rate limits and add delay before request
        await self._check_rate_limit_before_request()
        
        client = await self._get_client()
        
        # Get auth headers with signature for this specific request
        headers = self._get_auth_headers(method.upper(), path)
        
        logger.debug(
            "api_request",
            method=method,
            path=path,
            params=params,
            authenticated=bool(self.api_key_id and self._private_key),
            rate_limit_remaining=self._rate_limit_remaining,
        )
        
        response = await client.request(
            method=method,
            url=path,
            params=params,
            json=json,
            headers=headers,
        )
        
        await self._handle_rate_limit(response)
        
        if response.status_code == 401:
            logger.error(
                "authentication_failed",
                path=path,
                hint="Check your KALSHI_BOT_KALSHI_API_KEY_ID and KALSHI_BOT_KALSHI_PRIVATE_KEY_PATH",
            )
            raise KalshiAuthError("Authentication failed - check your API credentials")
        
        if response.status_code >= 400:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                pass
            
            logger.error(
                "api_error",
                status_code=response.status_code,
                error=error_msg,
                path=path,
            )
            raise KalshiAPIError(response.status_code, error_msg)
        
        return response.json()
    
    # ─────────────────────────────────────────────────────────────────────────
    # MARKET DATA
    # ─────────────────────────────────────────────────────────────────────────
    
    async def get_markets(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
        event_ticker: Optional[str] = None,
    ) -> tuple[list[Market], Optional[str]]:
        """Fetch markets from the API."""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        
        data = await self._request("GET", "/markets", params=params)
        
        markets = [self._parse_market(m) for m in data.get("markets", [])]
        next_cursor = data.get("cursor")
        
        return markets, next_cursor
    
    async def get_market(self, ticker: str) -> Optional[Market]:
        """Get a single market by ticker."""
        try:
            data = await self._request("GET", f"/markets/{ticker}")
            return self._parse_market(data.get("market", {}))
        except KalshiAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_orderbook(self, ticker: str) -> Optional[OrderBook]:
        """Get orderbook for a market."""
        try:
            data = await self._request("GET", f"/markets/{ticker}/orderbook")
            return self._parse_orderbook(data.get("orderbook", {}))
        except KalshiAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_events(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """Fetch events (market categories)."""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        data = await self._request("GET", "/events", params=params)
        
        events = data.get("events", [])
        next_cursor = data.get("cursor")
        
        return events, next_cursor
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRADING
    # ─────────────────────────────────────────────────────────────────────────
    
    async def place_order(self, order: Order) -> Order:
        """Place an order on Kalshi."""
        order_data = {
            "ticker": order.ticker,
            "action": "buy",
            "side": order.side.value,
            "type": order.order_type.value,
            "count": order.quantity,
        }
        
        if order.order_type.value == "limit":
            order_data["yes_price" if order.side == OrderSide.YES else "no_price"] = order.price
        
        # Use idempotency key if provided
        headers = {}
        if order.idempotency_key:
            headers["Idempotency-Key"] = order.idempotency_key
        
        try:
            data = await self._request("POST", "/portfolio/orders", json=order_data)
            
            order.kalshi_order_id = data.get("order", {}).get("order_id")
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.utcnow()
            
            logger.info(
                "order_placed",
                ticker=order.ticker,
                side=order.side.value,
                quantity=order.quantity,
                price=order.price,
                kalshi_order_id=order.kalshi_order_id,
            )
            
        except KalshiAPIError as e:
            order.status = OrderStatus.REJECTED
            order.error_message = e.message
            logger.error(
                "order_rejected",
                ticker=order.ticker,
                error=e.message,
            )
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            await self._request("DELETE", f"/portfolio/orders/{order_id}")
            logger.info("order_cancelled", order_id=order_id)
            return True
        except KalshiAPIError as e:
            logger.error("cancel_failed", order_id=order_id, error=e.message)
            return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order status by ID."""
        try:
            data = await self._request("GET", f"/portfolio/orders/{order_id}")
            return self._parse_order(data.get("order", {}))
        except KalshiAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_fills(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
    ) -> list[Fill]:
        """Get recent fills."""
        params: dict[str, Any] = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        
        data = await self._request("GET", "/portfolio/fills", params=params)
        
        fills = []
        for f in data.get("fills", []):
            fills.append(Fill(
                kalshi_trade_id=f.get("trade_id"),
                order_id=f.get("order_id", ""),
                ticker=f.get("ticker", ""),
                side=OrderSide.YES if f.get("side") == "yes" else OrderSide.NO,
                price=f.get("price", 0),
                quantity=f.get("count", 0),
                notional=(f.get("price", 0) * f.get("count", 0)) / 100,
                timestamp=datetime.fromisoformat(f["created_time"].replace("Z", "+00:00"))
                if f.get("created_time") else datetime.utcnow(),
            ))
        
        return fills
    
    # ─────────────────────────────────────────────────────────────────────────
    # ACCOUNT
    # ─────────────────────────────────────────────────────────────────────────
    
    async def get_balance(self) -> float:
        """Get account balance in dollars."""
        data = await self._request("GET", "/portfolio/balance")
        # Balance is returned in cents
        return data.get("balance", 0) / 100
    
    async def get_positions(self) -> list[dict]:
        """Get current positions."""
        data = await self._request("GET", "/portfolio/positions")
        return data.get("market_positions", [])
    
    # ─────────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────────
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # ─────────────────────────────────────────────────────────────────────────
    # PARSING HELPERS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _parse_market(self, data: dict) -> Market:
        """Parse market data from API response."""
        close_time = None
        if data.get("close_time"):
            try:
                close_time = datetime.fromisoformat(data["close_time"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        expiration_time = None
        if data.get("expiration_time"):
            try:
                expiration_time = datetime.fromisoformat(
                    data["expiration_time"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass
        
        return Market(
            ticker=data.get("ticker", ""),
            title=data.get("title", ""),
            subtitle=data.get("subtitle", ""),
            category=data.get("category", ""),
            event_ticker=data.get("event_ticker", ""),
            status=data.get("status", "active"),
            result=data.get("result"),
            close_time=close_time,
            expiration_time=expiration_time,
            last_price=data.get("last_price", 50),
            volume=data.get("volume", 0),
            volume_24h=data.get("volume_24h", 0),
            open_interest=data.get("open_interest", 0),
        )
    
    def _parse_orderbook(self, data: dict) -> OrderBook:
        """Parse orderbook data from API response."""
        yes_bids = [
            OrderBookLevel(price=level[0], quantity=level[1])
            for level in data.get("yes", [])
            if len(level) >= 2
        ]
        yes_asks = [
            OrderBookLevel(price=level[0], quantity=level[1])
            for level in data.get("no", [])  # NO orders = YES asks
            if len(level) >= 2
        ]
        
        return OrderBook(
            yes_bids=yes_bids,
            yes_asks=yes_asks,
            timestamp=datetime.utcnow(),
        )
    
    def _parse_order(self, data: dict) -> Order:
        """Parse order data from API response."""
        status_map = {
            "pending": OrderStatus.PENDING,
            "open": OrderStatus.OPEN,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELLED,
            "cancelled": OrderStatus.CANCELLED,
        }
        
        return Order(
            kalshi_order_id=data.get("order_id"),
            idempotency_key=data.get("order_id", ""),
            ticker=data.get("ticker", ""),
            side=OrderSide.YES if data.get("side") == "yes" else OrderSide.NO,
            price=data.get("yes_price") or data.get("no_price") or 50,
            quantity=data.get("count", 0),
            status=status_map.get(data.get("status", ""), OrderStatus.PENDING),
            filled_quantity=data.get("filled_count", 0),
        )
