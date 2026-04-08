"""
ESPN free unofficial API adapter for sportsbook odds.

No API key required. Returns DraftKings moneyline odds from ESPN's
public scoreboard endpoint. Used as a final free fallback when both
The Odds API and OddsPapi are unavailable.

Endpoint: https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from kalshi_odds.models.odds import OddsQuote, OddsFormat, MarketType

logger = logging.getLogger(__name__)

# Maps Odds API sport key -> ESPN sport path
SPORT_TO_ESPN_PATH: dict[str, str] = {
    "basketball_nba": "basketball/nba",
    "baseball_mlb": "baseball/mlb",
    "americanfootball_nfl": "football/nfl",
    "icehockey_nhl": "hockey/nhl",
    "basketball_ncaab": "basketball/mens-college-basketball",
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"


class ESPNAdapter:
    """Free ESPN scoreboard adapter — DraftKings moneyline odds, no auth needed."""

    def __init__(self, requests_per_second: float = 2.0) -> None:
        self._min_delay = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def last_requests_remaining(self) -> Optional[str]:
        return "∞ (ESPN free)"

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> ESPNAdapter:
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

    async def _scoreboard(self, sport: str) -> list[dict]:
        """Fetch ESPN scoreboard for a sport. Returns list of raw ESPN event dicts."""
        path = SPORT_TO_ESPN_PATH.get(sport)
        if not path:
            return []
        await self._throttle()
        assert self._client is not None
        try:
            resp = await self._client.get(f"{ESPN_BASE}/{path}/scoreboard")
            resp.raise_for_status()
            data = resp.json()
            return data.get("events", [])
        except Exception as exc:
            logger.warning("ESPN scoreboard failed for %s: %s", sport, exc)
            return []

    async def list_events(self, sport: str) -> list[dict]:
        """Return events in The Odds API format: [{id, home_team, away_team, ...}]."""
        raw = await self._scoreboard(sport)
        events = []
        for ev in raw:
            comps = ev.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            home_team, away_team, event_id = "", "", ev.get("id", "")
            for c in comp.get("competitors", []):
                name = c.get("team", {}).get("displayName", "")
                if c.get("homeAway") == "home":
                    home_team = name
                elif c.get("homeAway") == "away":
                    away_team = name
            if home_team and away_team:
                commence_time = comp.get("date", ev.get("date", ""))
                events.append({
                    "id": f"espn_{event_id}",
                    "sport_key": sport,
                    "home_team": home_team,
                    "away_team": away_team,
                    "commence_time": commence_time,
                })
        return events

    async def get_odds(
        self,
        sport: str,
        regions: str = "us",
        markets: str = "h2h",
        odds_format: str = "american",
        bookmakers: Optional[str] = None,
    ) -> list[dict]:
        """Return events in The Odds API format including bookmaker odds."""
        raw = await self._scoreboard(sport)
        results = []
        for ev in raw:
            comps = ev.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            home_team, away_team, event_id = "", "", ev.get("id", "")
            for c in comp.get("competitors", []):
                name = c.get("team", {}).get("displayName", "")
                if c.get("homeAway") == "home":
                    home_team = name
                elif c.get("homeAway") == "away":
                    away_team = name
            if not home_team or not away_team:
                continue

            commence_time = comp.get("date", ev.get("date", ""))
            espn_odds_list = comp.get("odds", [])
            bookmakers_out = []

            for espn_odds in espn_odds_list:
                provider = espn_odds.get("provider", {})
                book_name = provider.get("name", "Unknown").lower().replace(" ", "_")
                moneyline = espn_odds.get("moneyline", {})
                if not moneyline:
                    continue

                home_ml_raw = moneyline.get("home", {}).get("close", {}).get("odds")
                away_ml_raw = moneyline.get("away", {}).get("close", {}).get("odds")
                if home_ml_raw is None or away_ml_raw is None:
                    continue

                try:
                    home_ml = int(home_ml_raw)
                    away_ml = int(away_ml_raw)
                except (ValueError, TypeError):
                    continue

                bookmakers_out.append({
                    "key": book_name,
                    "title": provider.get("name", book_name),
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": home_team, "price": home_ml},
                            {"name": away_team, "price": away_ml},
                        ],
                    }],
                })

            if bookmakers_out:
                results.append({
                    "id": f"espn_{event_id}",
                    "sport_key": sport,
                    "home_team": home_team,
                    "away_team": away_team,
                    "commence_time": commence_time,
                    "bookmakers": bookmakers_out,
                })

        logger.info("ESPN: %d events with odds for %s", len(results), sport)
        return results

    def parse_odds_to_quotes(self, raw_events: list[dict]) -> list[OddsQuote]:
        """Parse ESPN get_odds output into OddsQuote objects (same format as OddsAPIAdapter)."""
        quotes: list[OddsQuote] = []
        now = datetime.now(timezone.utc)

        for event in raw_events:
            event_id = event.get("id", "")
            sport = event.get("sport_key", "")
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            event_title = f"{away} @ {home}" if away and home else ""

            commence_time = None
            ct_str = event.get("commence_time")
            if ct_str:
                try:
                    commence_time = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            for bookmaker in event.get("bookmakers", []):
                bk = bookmaker.get("key", "")
                for market in bookmaker.get("markets", []):
                    mk = market.get("key", "")
                    try:
                        market_type = MarketType(mk)
                    except ValueError:
                        continue
                    for outcome in market.get("outcomes", []):
                        selection = outcome.get("name", "")
                        price = outcome.get("price")
                        if price is None:
                            continue
                        quotes.append(OddsQuote(
                            source="espn",
                            bookmaker=bk,
                            event_id=event_id,
                            market_type=market_type,
                            selection=selection,
                            odds_format=OddsFormat.AMERICAN,
                            odds_value=float(price),
                            timestamp=now,
                            event_title=event_title,
                            sport=sport,
                            commence_time=commence_time,
                        ))

        return quotes
