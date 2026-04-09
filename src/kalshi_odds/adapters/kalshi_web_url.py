"""Build kalshi.com market page links.

Kalshi's web app routes markets as::

    https://kalshi.com/markets/{series_lower}/{series_slug}/{market_ticker_lower}

e.g. KXNBAGAME-26APR08MILDET-MIL →
     https://kalshi.com/markets/kxnbagame/professional-basketball-game/kxnbagame-26apr08mildet-mil

Strategy (fast to slow):
1. Extract the series prefix from the ticker (everything up to the first date-like segment).
2. Look it up in a hardcoded series → slug table — covers all supported sports instantly,
   no API calls, no rate-limit risk.
3. For unknown series, call the public Kalshi API to discover the slug and cache it.
4. If all else fails, return a kalshi.com search URL which always opens the site.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote

import httpx

KALSHI_PUBLIC_API = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WEB_BASE = "https://kalshi.com"

# Known series ticker → web slug (avoids API calls for common sports).
_KNOWN_SERIES_SLUGS: dict[str, str] = {
    "KXNBAGAME":   "professional-basketball-game",
    "KXMLBGAME":   "professional-baseball-game",
    "KXNFLGAME":   "professional-football-game",
    "KXNHLGAME":   "professional-hockey-game",
    "KXNCAABGAME": "college-basketball-game",
    "KXNCAAFGAME": "college-football-game",
    "KXSB":        "super-bowl",
}

# API-discovered slugs (series not in the table above).
_api_series_slug_cache: dict[str, str] = {}

# Final resolved market URLs.
_market_url_cache: dict[str, str] = {}


def kalshi_search_url(ticker: str) -> str:
    """Fallback: open kalshi.com search for this ticker."""
    return f"{KALSHI_WEB_BASE}/markets?search={quote(ticker.strip())}"


def _slug_from_series_title(title: str) -> str:
    s = (title or "market").lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "market"


def _series_prefix(ticker: str) -> str:
    """Extract series ticker prefix from a market ticker.

    Tickers follow the pattern: SERIES-DATEINFO-SIDE
    e.g. KXNBAGAME-26APR08MILDET-MIL  → KXNBAGAME
         KXMLBGAME-26APR091340DETMIN-DET → KXMLBGAME
    """
    return ticker.split("-")[0].upper()


def build_kalshi_url(market_ticker: str, series_slug: str) -> str:
    series = _series_prefix(market_ticker).lower()
    return f"{KALSHI_WEB_BASE}/markets/{series}/{series_slug}/{market_ticker.lower()}"


async def _series_slug_via_api(client: httpx.AsyncClient, series_ticker: str) -> str | None:
    """Fetch series slug via the public Kalshi API. Returns None on failure."""
    if series_ticker in _api_series_slug_cache:
        return _api_series_slug_cache[series_ticker]
    try:
        r = await client.get(f"{KALSHI_PUBLIC_API}/series/{series_ticker}", timeout=10)
        if r.status_code != 200:
            return None
        title = str(r.json().get("series", {}).get("title") or "")
        if not title:
            return None
        slug = _slug_from_series_title(title)
        _api_series_slug_cache[series_ticker] = slug
        return slug
    except Exception:
        return None


async def resolve_kalshi_url(client: httpx.AsyncClient, market_ticker: str) -> str:
    t = market_ticker.strip().upper()
    if not t:
        return f"{KALSHI_WEB_BASE}/markets"
    if t in _market_url_cache:
        return _market_url_cache[t]

    series = _series_prefix(t)

    # Fast path: known series
    if series in _KNOWN_SERIES_SLUGS:
        url = build_kalshi_url(t, _KNOWN_SERIES_SLUGS[series])
        _market_url_cache[t] = url
        return url

    # Slow path: discover via API
    slug = await _series_slug_via_api(client, series)
    if slug:
        url = build_kalshi_url(t, slug)
        _market_url_cache[t] = url
        return url

    # Final fallback
    url = kalshi_search_url(t)
    _market_url_cache[t] = url
    return url


async def resolve_kalshi_market_web_urls(tickers: set[str], *, concurrency: int = 8) -> dict[str, str]:
    """Batch-resolve unique tickers. Known sports series require zero API calls."""
    if not tickers:
        return {}
    out: dict[str, str] = {}

    # For known series we don't need a real HTTP client, but create one anyway
    # for any tickers that fall through to the API path.
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0)) as client:
        async def one(ticker: str) -> None:
            async with sem:
                out[ticker] = await resolve_kalshi_url(client, ticker)

        await asyncio.gather(*(one(t) for t in tickers))
    return out
