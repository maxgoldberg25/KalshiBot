"""
The Odds API adapter.

Fetches odds from multiple sportsbooks via The Odds API aggregator.
https://the-odds-api.com/

Requires API key (free tier: 500 requests/month).
"""

from __future__ import annotations

import time
import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from kalshi_odds.models.odds import OddsQuote, OddsFormat, MarketType


class OddsAPIAdapter:
    """
    The Odds API adapter for fetching sportsbook odds.
    
    Read-only, no execution capabilities.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.the-odds-api.com/v4",
        requests_per_second: float = 1.0,  # Conservative for free tier
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._min_delay = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Initialize connection."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def close(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

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
    async def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        assert self._client is not None
        await self._throttle()
        
        params = params or {}
        params["apiKey"] = self._api_key
        
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def list_sports(self) -> list[dict]:
        """
        List available sports.
        
        Returns list of sport objects:
        [
            {"key": "americanfootball_nfl", "group": "American Football", "title": "NFL", ...},
            ...
        ]
        """
        return await self._get("/sports")  # type: ignore

    async def list_events(self, sport: str) -> list[dict]:
        """
        List upcoming events for a sport.
        
        Args:
            sport: Sport key (e.g., "americanfootball_nfl")
            
        Returns list of events:
        [
            {
                "id": "abc123...",
                "sport_key": "americanfootball_nfl",
                "sport_title": "NFL",
                "commence_time": "2025-02-09T00:00:00Z",
                "home_team": "Kansas City Chiefs",
                "away_team": "Philadelphia Eagles"
            },
            ...
        ]
        """
        return await self._get(f"/sports/{sport}/events")  # type: ignore

    async def get_odds(
        self,
        sport: str,
        regions: str = "us",
        markets: str = "h2h",
        odds_format: str = "american",
        bookmakers: Optional[str] = None,
    ) -> list[dict]:
        """
        Get odds for all events in a sport.
        
        Args:
            sport: Sport key
            regions: Comma-separated regions (us, uk, eu, au)
            markets: Comma-separated markets (h2h, spreads, totals, outrights, etc.)
            odds_format: "american" or "decimal"
            bookmakers: Optional comma-separated bookmaker keys
            
        Returns list of events with odds:
        [
            {
                "id": "event_id",
                "sport_key": "...",
                "commence_time": "...",
                "home_team": "...",
                "away_team": "...",
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "title": "DraftKings",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Kansas City Chiefs", "price": -110},
                                    {"name": "Philadelphia Eagles", "price": +150}
                                ]
                            }
                        ]
                    },
                    ...
                ]
            },
            ...
        ]
        """
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        
        return await self._get(f"/sports/{sport}/odds", params=params)  # type: ignore

    def parse_odds_to_quotes(self, raw_events: list[dict]) -> list[OddsQuote]:
        """
        Parse The Odds API response into OddsQuote objects.
        
        Args:
            raw_events: Raw events list from get_odds()
            
        Returns list of OddsQuote objects
        """
        quotes: list[OddsQuote] = []
        
        for event in raw_events:
            event_id = event.get("id", "")
            sport = event.get("sport_key", "")
            commence_time_str = event.get("commence_time")
            
            commence_time = None
            if commence_time_str:
                try:
                    commence_time = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            
            # Build event title
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            event_title = f"{away} @ {home}" if away and home else ""
            
            for bookmaker in event.get("bookmakers", []):
                bookmaker_key = bookmaker.get("key", "")
                
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "")
                    
                    # Map to MarketType
                    try:
                        market_type = MarketType(market_key)
                    except ValueError:
                        continue  # Skip unknown market types
                    
                    for outcome in market.get("outcomes", []):
                        selection = outcome.get("name", "")
                        price = outcome.get("price")
                        point = outcome.get("point")  # For spreads/totals
                        
                        if price is None:
                            continue
                        
                        # Determine odds format
                        if isinstance(price, int) or (isinstance(price, float) and abs(price) > 10):
                            odds_format = OddsFormat.AMERICAN
                        else:
                            odds_format = OddsFormat.DECIMAL
                        
                        quotes.append(OddsQuote(
                            source="theoddsapi",
                            bookmaker=bookmaker_key,
                            event_id=event_id,
                            market_type=market_type,
                            selection=selection,
                            odds_format=odds_format,
                            odds_value=float(price),
                            point=point,
                            timestamp=datetime.now(timezone.utc),
                            event_title=event_title,
                            sport=sport,
                            commence_time=commence_time,
                        ))
        
        return quotes

    async def __aenter__(self) -> OddsAPIAdapter:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
