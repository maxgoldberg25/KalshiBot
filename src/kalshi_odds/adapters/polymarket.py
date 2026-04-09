"""Polymarket public market-data adapter (read-only).

Uses:
- Gamma API for market discovery and top-of-book summary fields
- No authentication required for read endpoints
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx


@dataclass
class PolyMarket:
    market_id: str
    question: str
    slug: str
    best_bid: float
    best_ask: float
    liquidity_usd: float
    end_date: Optional[datetime]
    tags: list[str]
    outcomes: list[str]
    clob_token_ids: list[str]


class PolymarketAdapter:
    """Read-only Polymarket adapter."""

    def __init__(
        self,
        gamma_base_url: str = "https://gamma-api.polymarket.com",
        requests_per_second: float = 2.0,
    ) -> None:
        self._gamma_base_url = gamma_base_url.rstrip("/")
        self._min_delay = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._gamma_base_url,
            timeout=httpx.Timeout(20.0, connect=10.0),
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> PolymarketAdapter:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_delay:
            await asyncio.sleep(self._min_delay - elapsed)
        self._last_request_time = time.monotonic()

    async def _get(self, path: str, params: Optional[dict] = None) -> list[dict]:
        assert self._client is not None
        await self._throttle()
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    @staticmethod
    def _parse_dt(raw: str | None) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _safe_float(v: object) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0

    @staticmethod
    def _safe_list_str(raw: object) -> list[str]:
        if isinstance(raw, list):
            return [str(x) for x in raw]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                return []
        return []

    def _to_market(self, raw: dict) -> Optional[PolyMarket]:
        if not raw.get("active", False) or raw.get("closed", False):
            return None
        question = str(raw.get("question", "")).strip()
        if not question:
            return None
        best_bid = self._safe_float(raw.get("bestBid"))
        best_ask = self._safe_float(raw.get("bestAsk"))
        if best_ask <= 0:
            return None
        tags = [str(t.get("label", "")).lower() for t in raw.get("tags", []) if isinstance(t, dict)]
        return PolyMarket(
            market_id=str(raw.get("id", "")),
            question=question,
            slug=str(raw.get("slug", "")),
            best_bid=max(0.0, min(1.0, best_bid)),
            best_ask=max(0.0, min(1.0, best_ask)),
            liquidity_usd=self._safe_float(raw.get("liquidityNum", raw.get("liquidity"))),
            end_date=self._parse_dt(raw.get("endDate")),
            tags=tags,
            outcomes=self._safe_list_str(raw.get("outcomes")),
            clob_token_ids=self._safe_list_str(raw.get("clobTokenIds")),
        )

    async def list_all_markets(
        self,
        *,
        limit_per_page: int = 500,
        max_pages: int = 6,
        min_liquidity_usd: float = 100.0,
    ) -> list[PolyMarket]:
        """Fetch active Polymarket markets across all categories."""
        all_markets: list[PolyMarket] = []
        for page in range(max_pages):
            offset = page * limit_per_page
            raws = await self._get(
                "/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "enableOrderBook": "true",
                    "limit": limit_per_page,
                    "offset": offset,
                },
            )
            if not raws:
                break
            for raw in raws:
                m = self._to_market(raw)
                if not m:
                    continue
                if m.liquidity_usd < min_liquidity_usd:
                    continue
                all_markets.append(m)
            if len(raws) < limit_per_page:
                break
        return all_markets
