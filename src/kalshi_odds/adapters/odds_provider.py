"""
Multi-provider odds adapter with automatic fallback.

Tries The Odds API first. If *credits* are exhausted the `get_odds` call
(which costs credits) is routed to OddsPapi.  The `list_events` endpoint on
The Odds API is **free** (never consumes credits), so it is always tried on
the primary first regardless of credit status.  The scan-runner's team-name
matching handles event-ID mismatches across providers.
"""

from __future__ import annotations

import logging
from typing import Optional

from kalshi_odds.adapters.espn import ESPNAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter, OddsAPIQuotaError, OddsAPIError
from kalshi_odds.adapters.oddspapi import OddsPapiAdapter, OddsPapiQuotaError
from kalshi_odds.config import Settings
from kalshi_odds.models.odds import OddsQuote

logger = logging.getLogger(__name__)


class FallbackOddsProvider:
    """Wraps The Odds API + OddsPapi with automatic failover.

    Routing strategy:
    * ``list_events`` — always tries the primary first (free endpoint on
      The Odds API).  Falls back to OddsPapi only on hard failure.
    * ``get_odds`` — routes to OddsPapi when primary credits are exhausted.
    * ``parse_odds_to_quotes`` — delegates to whichever provider last served
      ``get_odds`` (tracked via ``_odds_active_label``).
    """

    def __init__(
        self,
        primary: OddsAPIAdapter,
        fallback: OddsPapiAdapter,
        espn: Optional[ESPNAdapter] = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._espn = espn
        self._primary_credits_exhausted = False
        self._primary_down = False
        self._fallback_exhausted = False
        self._active_label = "The Odds API"
        self._odds_active_label = "The Odds API"

    @property
    def last_requests_remaining(self) -> Optional[str]:
        p = self._primary.last_requests_remaining
        f = self._fallback.last_requests_remaining
        if self._primary_credits_exhausted:
            if f is not None:
                return f"{f} (OddsPapi)"
            return "0 (OddsAPI exhausted, using OddsPapi for odds)"
        if p is not None and f is not None:
            return f"{p} (OddsAPI) + {f} (OddsPapi)"
        if p is not None:
            return p
        if f is not None:
            return f"{f} (OddsPapi)"
        return None

    async def connect(self) -> None:
        await self._primary.connect()
        await self._fallback.connect()
        if self._espn:
            await self._espn.connect()
        await self._probe_primary_quota()

    async def close(self) -> None:
        await self._primary.close()
        await self._fallback.close()
        if self._espn:
            await self._espn.close()

    async def __aenter__(self) -> FallbackOddsProvider:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def _probe_primary_quota(self) -> None:
        """Call the free list_events endpoint and check the x-requests-remaining
        header. If credits are 0, mark *credits* exhausted (only affects get_odds).
        If the endpoint fails entirely, mark the primary as down."""
        if self._primary_credits_exhausted:
            return
        try:
            await self._primary.list_events("basketball_nba")
        except Exception:
            self._primary_down = True
            logger.warning("Odds API appears unreachable — routing everything to OddsPapi")
            return
        remaining = self._primary.last_requests_remaining
        if remaining is not None:
            try:
                if int(remaining) <= 0:
                    self._primary_credits_exhausted = True
                    self._active_label = "The Odds API (events) + OddsPapi (odds)"
                    logger.info(
                        "Odds API has 0 credits — list_events still via OddsAPI, get_odds via OddsPapi"
                    )
            except (ValueError, TypeError):
                pass

    # ------------------------------------------------------------------
    # list_events — free on The Odds API, always try primary first
    # ------------------------------------------------------------------
    async def list_events(self, sport: str) -> list[dict]:
        if not self._primary_down:
            try:
                result = await self._primary.list_events(sport)
                self._active_label = "The Odds API"
                return result
            except OddsAPIQuotaError:
                pass
            except Exception:
                self._primary_down = True
                logger.warning("Odds API list_events failed — falling back to OddsPapi")

        if not self._fallback_exhausted:
            try:
                result = await self._fallback.list_events(sport)
                if result:
                    self._active_label = "OddsPapi"
                    return result
            except OddsPapiQuotaError:
                self._fallback_exhausted = True
            except Exception:
                pass

        # ESPN free fallback for list_events
        if self._espn:
            try:
                result = await self._espn.list_events(sport)
                if result:
                    self._active_label = "ESPN (free)"
                    return result
            except Exception as exc:
                logger.warning("ESPN list_events failed: %s", exc)

        raise OddsAPIQuotaError(
            "All providers exhausted. Get new API keys or wait for monthly reset. "
            "Odds API: https://the-odds-api.com  |  OddsPapi: https://oddspapi.io"
        )

    # ------------------------------------------------------------------
    # get_odds — costs credits on paid providers, ESPN is always free
    # ------------------------------------------------------------------
    async def get_odds(
        self,
        sport: str,
        regions: str = "us",
        markets: str = "h2h",
        odds_format: str = "american",
        bookmakers: Optional[str] = None,
    ) -> list[dict]:
        if not self._primary_credits_exhausted and not self._primary_down:
            try:
                result = await self._primary.get_odds(
                    sport=sport, regions=regions, markets=markets,
                    odds_format=odds_format, bookmakers=bookmakers,
                )
                self._active_label = "The Odds API"
                self._odds_active_label = "The Odds API"
                return result
            except OddsAPIQuotaError:
                self._primary_credits_exhausted = True
                logger.info("Odds API quota exhausted on get_odds — falling back to OddsPapi")

        if not self._fallback_exhausted:
            try:
                result = await self._fallback.get_odds(
                    sport=sport, regions=regions, markets=markets,
                    odds_format=odds_format, bookmakers=bookmakers,
                )
                if result:
                    self._active_label = "OddsPapi"
                    self._odds_active_label = "OddsPapi"
                    return result
            except OddsPapiQuotaError:
                self._fallback_exhausted = True
            except Exception:
                pass

        # ESPN free final fallback — no API key, no credits consumed
        if self._espn:
            try:
                result = await self._espn.get_odds(
                    sport=sport, regions=regions, markets=markets,
                    odds_format=odds_format, bookmakers=bookmakers,
                )
                if result:
                    self._active_label = "ESPN (free)"
                    self._odds_active_label = "ESPN"
                    logger.info("Using ESPN free odds for %s (%d events)", sport, len(result))
                    return result
            except Exception as exc:
                logger.warning("ESPN get_odds failed: %s", exc)

        # Nothing left — return empty to prevent crash; scanner will show 0 opps
        logger.warning("All odds providers unavailable for %s — returning empty", sport)
        return []

    def parse_odds_to_quotes(self, raw_events: list[dict]) -> list[OddsQuote]:
        if self._odds_active_label == "OddsPapi":
            return self._fallback.parse_odds_to_quotes(raw_events)
        if self._odds_active_label == "ESPN":
            if self._espn:
                return self._espn.parse_odds_to_quotes(raw_events)
        return self._primary.parse_odds_to_quotes(raw_events)


def create_odds_provider(settings: Settings) -> OddsAPIAdapter | FallbackOddsProvider:
    """Factory: always returns FallbackOddsProvider with ESPN free tier as final backstop.

    Tier 1: The Odds API (paid, 500 req/month free)
    Tier 2: OddsPapi (paid, 250 req/month free) — if key configured
    Tier 3: ESPN unofficial API (always free, no key needed)
    """
    primary = OddsAPIAdapter(
        api_key=settings.odds_api_key,
        base_url=settings.odds_api_base_url,
        requests_per_second=settings.odds_api_requests_per_second,
    )
    oddspapi_key = getattr(settings, "oddspapi_api_key", "")
    fallback = OddsPapiAdapter(api_key=oddspapi_key) if oddspapi_key else OddsPapiAdapter(api_key="")
    espn = ESPNAdapter()
    return FallbackOddsProvider(primary, fallback, espn=espn)
