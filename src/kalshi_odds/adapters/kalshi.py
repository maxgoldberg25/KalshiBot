"""
Kalshi API adapter.

Simplified read-only adapter for fetching contracts and orderbooks.
"""

from __future__ import annotations

import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from kalshi_odds.models.kalshi import KalshiContract, KalshiTopOfBook, OutcomeSide, cents_to_decimal


class KalshiAdapter:
    """Read-only Kalshi API adapter with RSA auth."""

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        base_url: str = "https://api.elections.kalshi.com/trade-api/v2",
        requests_per_second: float = 5.0,
    ) -> None:
        self._api_key_id = api_key_id
        self._private_key_path = private_key_path
        self._base_url = base_url.rstrip("/")
        self._min_delay = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None
        self._private_key: Optional[rsa.RSAPrivateKey] = None

    async def connect(self) -> None:
        """Initialize connection."""
        key_path = Path(self._private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(f"Kalshi private key not found: {key_path}")

        key_data = key_path.read_bytes()
        self._private_key = serialization.load_pem_private_key(key_data, password=None)  # type: ignore

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def close(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _sign_request(self, method: str, path: str, timestamp_ms: str) -> str:
        """Create RSA-PSS signature for Kalshi auth."""
        message = f"{timestamp_ms}{method}{path}"
        signature = self._private_key.sign(  # type: ignore
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        import base64
        return base64.b64encode(signature).decode("utf-8")

    def _auth_headers(self, method: str, path: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        sig = self._sign_request(method.upper(), path, ts)
        return {
            "KALSHI-ACCESS-KEY": self._api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
        }

    async def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_delay:
            await asyncio.sleep(self._min_delay - elapsed)
        self._last_request_time = time.monotonic()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        assert self._client is not None
        await self._throttle()
        headers = self._auth_headers("GET", path)
        resp = await self._client.get(path, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _post(self, path: str, json_body: dict) -> dict:
        assert self._client is not None
        await self._throttle()
        headers = self._auth_headers("POST", path)
        resp = await self._client.post(path, json=json_body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def place_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        type: str = "limit",
        yes_price: Optional[int] = None,
        no_price: Optional[int] = None,
    ) -> dict:
        """
        Place a limit order on Kalshi.
        side: "yes" | "no"
        action: "buy" | "sell"
        count: number of contracts
        yes_price: limit price in cents (1-99) for YES side
        no_price: limit price in cents (1-99) for NO side (use when side is "no")
        """
        if count < 1:
            raise ValueError("count must be >= 1")
        if side not in ("yes", "no"):
            raise ValueError('side must be "yes" or "no"')
        if action not in ("buy", "sell"):
            raise ValueError('action must be "buy" or "sell"')
        if yes_price is None and no_price is None:
            raise ValueError("Provide yes_price or no_price (in cents 1-99)")
        payload: dict = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": type,
        }
        if yes_price is not None:
            payload["yes_price"] = max(1, min(99, yes_price))
        if no_price is not None:
            payload["no_price"] = max(1, min(99, no_price))
        return await self._post("/portfolio/orders", payload)

    async def list_markets(self, series_ticker: Optional[str] = None, limit: int = 100, status: str = "open") -> list[dict]:
        """
        Fetch markets from Kalshi, optionally filtered by series_ticker.
        Returns list of raw market dicts.
        """
        params: dict = {"limit": limit, "status": status}
        if series_ticker:
            params["series_ticker"] = series_ticker
        data = await self._get("/markets", params=params)
        return data.get("markets", [])

    async def list_contracts(self, limit: int = 200, series_ticker: Optional[str] = None) -> list[KalshiContract]:
        """
        Fetch active contracts from Kalshi.
        If series_ticker is set, only return contracts in that series.
        Returns list of YES-side contracts only.
        """
        contracts: list[KalshiContract] = []
        cursor: Optional[str] = None
        max_pages = 10

        for page in range(max_pages):
            params: dict = {"limit": limit, "status": "open"}
            if series_ticker:
                params["series_ticker"] = series_ticker
            if cursor:
                params["cursor"] = cursor

            try:
                data = await self._get("/markets", params=params)
            except Exception:
                break

            for m in data.get("markets", []):
                contract = self._parse_contract(m)
                if contract:
                    contracts.append(contract)

            cursor = data.get("cursor")
            if not cursor:
                break

        return contracts

    def _parse_contract(self, raw: dict) -> Optional[KalshiContract]:
        """Parse a Kalshi market into a contract (YES side only)."""
        try:
            ticker = raw.get("ticker", "")
            title = raw.get("title", raw.get("subtitle", ""))
            status = raw.get("status", "")

            # Parse expiration
            exp_str = raw.get("expiration_time") or raw.get("close_time")
            close_time = None
            if exp_str:
                try:
                    close_time = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            if not close_time:
                return None

            # YES price
            yes_price = raw.get("yes_ask")
            if yes_price is None:
                yes_price = raw.get("last_price")
            if yes_price is not None:
                yes_price = cents_to_decimal(yes_price)

            return KalshiContract(
                kalshi_market_id=raw.get("event_ticker", ticker),
                contract_id=ticker,
                title=title,
                outcome_side=OutcomeSide.YES,
                close_time=close_time,
                settlement_rules=raw.get("rules", ""),
                status=status,
                last_price=yes_price,
                fetched_at=datetime.now(timezone.utc),
            )
        except Exception:
            return None

    async def get_top_of_book(self, contract_id: str) -> Optional[KalshiTopOfBook]:
        """Fetch orderbook for a contract."""
        try:
            data = await self._get(f"/markets/{contract_id}/orderbook")
        except Exception:
            return None

        ob = data.get("orderbook", data)
        yes_bids = ob.get("yes", []) if isinstance(ob.get("yes"), list) else []
        no_bids = ob.get("no", []) if isinstance(ob.get("no"), list) else []

        yes_bid = None
        yes_bid_size = 0
        yes_ask = None
        yes_ask_size = 0
        no_bid = None
        no_bid_size = 0

        if yes_bids:
            sorted_yes = sorted(yes_bids, key=lambda x: x[0], reverse=True)
            yes_bid = cents_to_decimal(sorted_yes[0][0])
            yes_bid_size = sorted_yes[0][1]

        if no_bids:
            sorted_no = sorted(no_bids, key=lambda x: x[0], reverse=True)
            # YES ask ≈ 1 - NO bid
            yes_ask = 1.0 - cents_to_decimal(sorted_no[0][0])
            yes_ask_size = sorted_no[0][1]
            no_bid = cents_to_decimal(sorted_no[0][0])
            no_bid_size = sorted_no[0][1]

        return KalshiTopOfBook(
            contract_id=contract_id,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            yes_bid_size=yes_bid_size,
            yes_ask_size=yes_ask_size,
            no_bid=no_bid,
            no_ask=1.0 - yes_bid if yes_bid else None,
            no_bid_size=no_bid_size,
            no_ask_size=yes_bid_size,
            timestamp=datetime.now(timezone.utc),
        )

    async def __aenter__(self) -> KalshiAdapter:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
