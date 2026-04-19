"""Build kalshi.com market page links.

Kalshi web routes individual markets roughly as::

    https://kalshi.com/markets/{series_lower}/{series_slug}/{market_ticker_lower}

The middle segment is a slug derived from the **series** display title from the
public API (GET /series/{series_ticker}), e.g. ``KXPOLITICSMENTION`` →
"General Politics" → ``general-politics``. That resolves markets like
``KXPOLITICSMENTION-26APR19-OIL`` correctly.

Plain ``/markets?search=…`` is *not* dependable (query handling / SPA), so it
is only used as a last resort when we cannot discover a series slug.

Strategy:
1. Known sports series → hardcoded slug (zero API calls).
2. Else → GET /series/{series_ticker} for title → slug (cached).
3. Else → search URL fallback.
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
    "KXNBAGAME": "professional-basketball-game",
    "KXMLBGAME": "professional-baseball-game",
    "KXNFLGAME": "professional-football-game",
    "KXNHLGAME": "professional-hockey-game",
    "KXNCAABGAME": "college-basketball-game",
    "KXNCAAFGAME": "college-football-game",
    "KXSB": "super-bowl",
}

_api_series_slug_cache: dict[str, str] = {}
_market_url_cache: dict[str, str] = {}


def kalshi_search_url(ticker: str) -> str:
    """Last-resort: Kalshi search for this ticker."""
    clean = (ticker or "").strip()
    if not clean:
        return f"{KALSHI_WEB_BASE}/markets"
    return f"{KALSHI_WEB_BASE}/markets?search={quote(clean)}"


def _slug_from_series_title(title: str) -> str:
    s = (title or "market").lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "market"


def _series_prefix(ticker: str) -> str:
    """Series ticker = segment before the first '-', uppercased."""
    return ticker.split("-")[0].upper()


def build_kalshi_url(market_ticker: str, series_slug: str) -> str:
    series = _series_prefix(market_ticker).lower()
    return f"{KALSHI_WEB_BASE}/markets/{series}/{series_slug}/{market_ticker.lower()}"


async def _series_slug_via_api(client: httpx.AsyncClient, series_ticker: str) -> str | None:
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

    if series in _KNOWN_SERIES_SLUGS:
        url = build_kalshi_url(t, _KNOWN_SERIES_SLUGS[series])
        _market_url_cache[t] = url
        return url

    slug = await _series_slug_via_api(client, series)
    if slug:
        url = build_kalshi_url(t, slug)
        _market_url_cache[t] = url
        return url

    url = kalshi_search_url(t)
    _market_url_cache[t] = url
    return url


async def resolve_kalshi_market_web_urls(tickers: set[str], *, concurrency: int = 8) -> dict[str, str]:
    """Batch-resolve unique tickers to kalshi.com market URLs."""
    if not tickers:
        return {}
    out: dict[str, str] = {}
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0)) as client:
        async def one(ticker: str) -> None:
            async with sem:
                out[ticker] = await resolve_kalshi_url(client, ticker)

        await asyncio.gather(*(one(t) for t in tickers))
    return out
