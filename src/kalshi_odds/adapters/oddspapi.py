"""
OddsPapi adapter — fallback odds provider when The Odds API quota is exhausted.

https://oddspapi.io/en/docs
Free tier: 250 requests/month, 350+ bookmakers including sharp books (Pinnacle).
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from kalshi_odds.models.odds import OddsQuote, OddsFormat, MarketType


class OddsPapiError(Exception):
    """Non-retryable OddsPapi error."""


class OddsPapiQuotaError(OddsPapiError):
    """Raised when free-tier request quota is exhausted."""


class _OddsPapiRateLimited(Exception):
    """Transient 429 — retried automatically."""


ODDS_API_SPORT_TO_SLUG: dict[str, tuple[str, str]] = {
    "basketball_nba": ("basketball", "nba"),
    "baseball_mlb": ("baseball", "mlb"),
    "americanfootball_nfl": ("american-football", "nfl"),
    "basketball_ncaab": ("basketball", "ncaa"),
    "icehockey_nhl": ("ice-hockey", "nhl"),
}

MONEYLINE_MARKET_IDS = {"101", "111"}
HOME_OUTCOME_IDS = {"101", "111"}
DRAW_OUTCOME_IDS = {"102", "112"}
AWAY_OUTCOME_IDS = {"103", "113"}

PREFERRED_BOOKMAKERS = ["pinnacle", "draftkings"]


class OddsPapiAdapter:
    """OddsPapi adapter that produces data compatible with our OddsQuote model."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.oddspapi.io",
        requests_per_second: float = 0.4,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._min_delay = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

        self._sport_id_map: dict[str, int] = {}
        self._tournament_map: dict[str, list[int]] = {}
        self._last_requests_remaining: Optional[str] = None
        self._initialized = False
        self._discover_failed_at: float = 0.0
        self._fixture_cache: dict[int, list[dict]] = {}
        self._fixture_cache_ts: float = 0.0

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> OddsPapiAdapter:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    @property
    def last_requests_remaining(self) -> Optional[str]:
        return self._last_requests_remaining

    async def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_delay:
            await asyncio.sleep(self._min_delay - elapsed)
        self._last_request_time = time.monotonic()

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, _OddsPapiRateLimited)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=3, min=10, max=60),
    )
    async def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        assert self._client is not None
        await self._throttle()
        params = params or {}
        params["apiKey"] = self._api_key
        resp = await self._client.get(path, params=params)

        remaining = resp.headers.get("x-requests-remaining") or resp.headers.get("x-ratelimit-remaining")
        if remaining is not None:
            self._last_requests_remaining = remaining

        if resp.status_code == 401:
            body = resp.json() if "json" in resp.headers.get("content-type", "") else {}
            msg = body.get("message", "Unauthorized")
            if "quota" in msg.lower() or "usage" in msg.lower() or "limit" in msg.lower():
                raise OddsPapiQuotaError(f"OddsPapi quota exhausted. See https://oddspapi.io/en/account")
            raise OddsPapiError(f"OddsPapi auth failed: {msg}")
        if resp.status_code == 429:
            raise _OddsPapiRateLimited("OddsPapi rate limit hit — retrying")
        if resp.status_code == 403:
            raise OddsPapiError("OddsPapi access denied — check your API key.")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    async def _ensure_discovered(self) -> None:
        if self._initialized:
            return
        now = time.monotonic()
        if self._discover_failed_at and (now - self._discover_failed_at) < 300:
            return
        await self._discover()

    async def _discover(self) -> None:
        """Discover sport IDs and tournament IDs for configured sports."""
        try:
            sports_data = await self._get("/v4/sports")
        except Exception:
            self._discover_failed_at = time.monotonic()
            return

        for sport in sports_data if isinstance(sports_data, list) else []:
            s_slug = (sport.get("sportSlug") or sport.get("slug") or "").lower()
            s_id = sport.get("sportId") or sport.get("id")
            if not s_id:
                continue

            for odds_key, (sport_slug, _tourn_kw) in ODDS_API_SPORT_TO_SLUG.items():
                if s_slug == sport_slug:
                    self._sport_id_map[odds_key] = int(s_id)

        tourns_cache: dict[int, list] = {}
        for odds_key, sport_id in self._sport_id_map.items():
            _, tourn_kw = ODDS_API_SPORT_TO_SLUG[odds_key]
            if sport_id not in tourns_cache:
                try:
                    tourns_cache[sport_id] = await self._get("/v4/tournaments", {"sportId": sport_id})
                except Exception:
                    tourns_cache[sport_id] = []
            tourns = tourns_cache[sport_id]
            exact: list[int] = []
            partial: list[int] = []
            for t in tourns if isinstance(tourns, list) else []:
                t_name = (t.get("tournamentName") or t.get("name") or "").lower()
                t_slug = (t.get("tournamentSlug") or t.get("slug") or "").lower()
                t_id = t.get("tournamentId") or t.get("id")
                if not t_id:
                    continue
                if t_slug == tourn_kw or t_name == tourn_kw:
                    exact.append(int(t_id))
                elif tourn_kw in t_slug or tourn_kw in t_name:
                    partial.append(int(t_id))
            matched = exact if exact else partial[:3]
            if matched:
                self._tournament_map.setdefault(odds_key, []).extend(matched)

        self._initialized = True

    def _tournament_ids_for(self, sport: str) -> list[int]:
        return self._tournament_map.get(sport, [])

    async def _get_fixtures(self, tid: int) -> list[dict]:
        """Fetch fixtures for a tournament, with 60s caching to reduce API calls."""
        now = time.monotonic()
        if now - self._fixture_cache_ts > 60:
            self._fixture_cache.clear()
            self._fixture_cache_ts = now
        if tid in self._fixture_cache:
            return self._fixture_cache[tid]
        data = await self._get("/v4/fixtures", {"tournamentId": str(tid)})
        result = data if isinstance(data, list) else []
        self._fixture_cache[tid] = result
        return result

    async def list_events(self, sport: str) -> list[dict]:
        """Return events in The Odds API compatible format for the automapper."""
        await self._ensure_discovered()
        t_ids = self._tournament_ids_for(sport)
        if not t_ids:
            return []

        all_fixtures: list[dict] = []
        for tid in t_ids[:3]:
            try:
                all_fixtures.extend(await self._get_fixtures(tid))
            except Exception:
                continue

        events: list[dict] = []
        for f in all_fixtures:
            fid = f.get("fixtureId") or f.get("id") or ""
            p1 = f.get("participant1Name") or ""
            p2 = f.get("participant2Name") or ""
            start = f.get("startTime") or ""
            if not p1 and not p2:
                continue
            events.append({
                "id": str(fid),
                "sport_key": sport,
                "home_team": p1,
                "away_team": p2,
                "commence_time": start,
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
        """Fetch odds and return in The Odds API compatible format."""
        await self._ensure_discovered()
        t_ids = self._tournament_ids_for(sport)
        if not t_ids:
            return []

        fixture_names: dict[str, tuple[str, str]] = {}
        for tid in t_ids[:3]:
            try:
                for fx in await self._get_fixtures(tid):
                    fxid = str(fx.get("fixtureId") or fx.get("id") or "")
                    p1 = fx.get("participant1Name") or ""
                    p2 = fx.get("participant2Name") or ""
                    if fxid and (p1 or p2):
                        fixture_names[fxid] = (p1, p2)
            except Exception:
                continue

        all_fixtures: list[dict] = []
        target_books = bookmakers.split(",") if bookmakers else PREFERRED_BOOKMAKERS
        for bk in target_books:
            for tid in t_ids[:3]:
                try:
                    data = await self._get("/v4/odds-by-tournaments", {
                        "tournamentIds": str(tid),
                        "bookmaker": bk.strip(),
                    })
                    if isinstance(data, list):
                        all_fixtures.extend(data)
                except Exception:
                    continue

        events_by_id: dict[str, dict] = {}
        for f in all_fixtures:
            fid = str(f.get("fixtureId") or f.get("id") or "")
            if not fid:
                continue
            names = fixture_names.get(fid, (f.get("participant1Name") or "Home", f.get("participant2Name") or "Away"))
            p1_name, p2_name = names
            start = f.get("startTime") or ""

            if fid not in events_by_id:
                events_by_id[fid] = {
                    "id": fid,
                    "sport_key": sport,
                    "home_team": p1_name,
                    "away_team": p2_name,
                    "commence_time": start,
                    "bookmakers": [],
                }

            bk_odds = f.get("bookmakerOdds", {})
            for bk_name, bk_data in bk_odds.items():
                bk_markets = bk_data.get("markets", {})

                ml_market = None
                for mid in MONEYLINE_MARKET_IDS:
                    if mid in bk_markets:
                        ml_market = bk_markets[mid]
                        break
                if not ml_market:
                    continue

                outcomes_raw = ml_market.get("outcomes", {})
                outcomes: list[dict] = []

                home_out = None
                away_out = None
                for oid, odata in outcomes_raw.items():
                    players = odata.get("players", {})
                    player = players.get("0", {})
                    bid = (player.get("bookmakerOutcomeId") or "").lower()
                    if bid == "home" or oid in HOME_OUTCOME_IDS:
                        home_out = player
                    elif bid == "away" or oid in AWAY_OUTCOME_IDS:
                        away_out = player

                for player, team_name in [(home_out, p1_name), (away_out, p2_name)]:
                    if not player:
                        continue
                    price_am = player.get("priceAmerican")
                    price_dec = player.get("price")
                    if price_am is not None:
                        try:
                            outcomes.append({"name": team_name, "price": float(price_am)})
                        except (ValueError, TypeError):
                            pass
                    elif price_dec is not None:
                        outcomes.append({"name": team_name, "price": float(price_dec)})

                if outcomes:
                    events_by_id[fid]["bookmakers"].append({
                        "key": bk_name,
                        "title": bk_name.title(),
                        "markets": [{"key": "h2h", "outcomes": outcomes}],
                    })

        return list(events_by_id.values())

    def parse_odds_to_quotes(self, raw_events: list[dict]) -> list[OddsQuote]:
        """Parse OddsPapi data (already in Odds API format) into OddsQuote objects."""
        quotes: list[OddsQuote] = []

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
                    commence_time = datetime.fromisoformat(str(ct_str).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            for bookmaker in event.get("bookmakers", []):
                bk_key = bookmaker.get("key", "")
                for market in bookmaker.get("markets", []):
                    mk = market.get("key", "")
                    try:
                        market_type = MarketType(mk)
                    except ValueError:
                        continue
                    for outcome in market.get("outcomes", []):
                        selection = outcome.get("name", "")
                        price = outcome.get("price")
                        point = outcome.get("point")
                        if price is None:
                            continue

                        if isinstance(price, int) or (isinstance(price, float) and abs(price) > 10):
                            fmt = OddsFormat.AMERICAN
                        else:
                            fmt = OddsFormat.DECIMAL

                        quotes.append(OddsQuote(
                            source="oddspapi",
                            bookmaker=bk_key,
                            event_id=event_id,
                            market_type=market_type,
                            selection=selection,
                            odds_format=fmt,
                            odds_value=float(price),
                            point=point,
                            timestamp=datetime.now(timezone.utc),
                            event_title=event_title,
                            sport=sport,
                            commence_time=commence_time,
                        ))

        return quotes
