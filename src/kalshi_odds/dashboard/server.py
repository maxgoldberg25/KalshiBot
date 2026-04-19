"""FastAPI dashboard: opportunities, positions, PnL, scanner status.

Uses persistent API connections across scan cycles and auto-maps on startup.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import sqlite3

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.kalshi_web_url import resolve_kalshi_market_web_urls
from kalshi_odds.adapters.odds_api import OddsAPIAdapter
from kalshi_odds.adapters.odds_provider import create_odds_provider, FallbackOddsProvider
from kalshi_odds.adapters.polymarket import PolymarketAdapter
from kalshi_odds.auth import (
    LOGIN_LIMITER,
    REGISTER_LIMITER,
    WAITLIST_LIMITER,
    auth_deps,
    clear_session_cookie,
    client_ip,
    get_optional_user,
    hash_ip,
    hash_password,
    new_session_token,
    rate_limit_or_raise,
    require_admin,
    require_user,
    session_expiry,
    set_session_cookie,
    validate_email,
    validate_password,
    validate_username,
    verify_password,
)
from kalshi_odds.config import Settings, get_settings
from kalshi_odds.core.automapper import auto_map as run_auto_map
from kalshi_odds.core.matcher import MarketMatcher
from kalshi_odds.core.scan_runner import run_scan_cycle, run_multi_sport_scan, run_poly_scan
from kalshi_odds.core.scanner import Scanner
from kalshi_odds.core.sizing import kelly_shares
from kalshi_odds.db import Repository
from kalshi_odds.execution import place_opportunity_order
from kalshi_odds.models.comparison import Opportunity

_start_time = time.monotonic()

def _friendly_error(exc: Exception) -> str:
    """Convert exception chains into human-readable messages."""
    msg = str(exc)
    if "OUT_OF_USAGE_CREDITS" in msg or "quota exhausted" in msg.lower():
        return "Odds API quota exhausted (0 credits). Get a new key or wait for monthly reset."
    if "RetryError" in msg:
        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        if cause:
            return _friendly_error(cause)
        if "HTTPStatusError" in msg:
            return "API request failed after retries. Check API keys and quota."
        return "API request failed after retries."
    if "401" in msg or "Unauthorized" in msg:
        return "API authentication failed. Check your API keys in .env."
    if "ConnectError" in msg or "ConnectionRefused" in msg:
        return "Cannot reach API server. Check your internet connection."
    return msg[:200]


LAST_OPPORTUNITIES_FILE = Path(".last_opportunities.json")
AUTO_MAP_INTERVAL_SCANS = 360

_templates_dir = Path(__file__).resolve().parent / "templates"
_INDEX_HTML = _templates_dir / "index.html"
# React + shadcn build (optional): repo_root/web/dist
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_REACT_DIST = _REPO_ROOT / "web" / "dist"
_REACT_INDEX = _REACT_DIST / "index.html"
_REACT_ASSETS = _REACT_DIST / "assets"

_scan_lock = asyncio.Lock()
_state: dict[str, Any] = {
    "last_scan_iso": None,
    "scan_count": 0,
    "last_error": None,
    "opportunities": [],
    "odds_requests_remaining": None,
    "is_scanning": False,
    "sports": [],
    "last_automap_scan": 0,
    "mapped_count": 0,
    "poly_opportunities": [],
}


def _load_opportunities_from_disk() -> list[dict]:
    if not LAST_OPPORTUNITIES_FILE.exists():
        return []
    with open(LAST_OPPORTUNITIES_FILE) as f:
        return json.load(f)


def _save_opportunities_disk(opportunities: list[Opportunity]) -> None:
    data = [o.model_dump(mode="json") for o in opportunities]
    with open(LAST_OPPORTUNITIES_FILE, "w") as f:
        json.dump(data, f, indent=0, default=str)
    _state["opportunities"] = data


_MARKET_META_CACHE: dict[str, tuple[float, dict]] = {}
_MARKET_META_TTL_SECONDS = 120.0


def _score_tape_rows(raw_trades: list[dict], min_notional: float) -> list[dict]:
    """Score public tape rows by approximate taker notional (contracts × price)."""
    rows: list[dict] = []
    for t in raw_trades:
        try:
            count = float(str(t.get("count_fp", "0")))
            yp = float(str(t.get("yes_price_dollars", "0")))
            np = float(str(t.get("no_price_dollars", "0")))
            side = t.get("taker_side") or "yes"
            price = yp if side == "yes" else np
            notional = count * price
            if notional < min_notional:
                continue
            if notional >= 10_000:
                tier = "major"
            elif notional >= 2_500:
                tier = "large"
            else:
                tier = "notable"
            rows.append(
                {
                    "trade_id": t.get("trade_id"),
                    "ticker": t.get("ticker"),
                    "taker_side": side,
                    "taker_price": round(price, 4),
                    "count": count,
                    "yes_price": yp,
                    "no_price": np,
                    "notional_usd": round(notional, 2),
                    "tier": tier,
                    "created_time": t.get("created_time"),
                }
            )
        except Exception:
            continue
    rows.sort(key=lambda r: r["notional_usd"], reverse=True)
    return rows


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _flatten_market(raw: dict) -> dict:
    """Pick the fields we actually surface in the UI from the /markets/{ticker} payload."""
    last = _f(raw.get("last_price_dollars"))
    prev = _f(raw.get("previous_price_dollars"))
    change = None
    if last is not None and prev is not None and prev != 0:
        change = round((last - prev), 4)
    return {
        "ticker": raw.get("ticker"),
        "event_ticker": raw.get("event_ticker"),
        "title": raw.get("title") or raw.get("yes_sub_title") or raw.get("ticker"),
        "subtitle": raw.get("subtitle") or "",
        "yes_sub_title": raw.get("yes_sub_title") or "",
        "no_sub_title": raw.get("no_sub_title") or "",
        "status": raw.get("status"),
        "close_time": raw.get("close_time"),
        "expected_expiration_time": raw.get("expected_expiration_time"),
        "yes_bid": _f(raw.get("yes_bid_dollars")),
        "yes_ask": _f(raw.get("yes_ask_dollars")),
        "no_bid": _f(raw.get("no_bid_dollars")),
        "no_ask": _f(raw.get("no_ask_dollars")),
        "last_price": last,
        "previous_price": prev,
        "price_change_24h": change,
        "volume_total": _f(raw.get("volume_fp") or raw.get("volume")),
        "volume_24h": _f(raw.get("volume_24h_fp") or raw.get("volume_24h")),
        "open_interest": _f(raw.get("open_interest_fp") or raw.get("open_interest")),
        "notional_value": _f(raw.get("notional_value_dollars")),
    }


async def _hydrate_market_meta(
    kalshi: KalshiAdapter, tickers: list[str], max_fetch: int
) -> dict[str, dict]:
    """Return {ticker: flat_market_meta} for the given tickers, using an in-process TTL cache."""
    now = time.monotonic()
    out: dict[str, dict] = {}
    to_fetch: list[str] = []
    for tkr in tickers:
        hit = _MARKET_META_CACHE.get(tkr)
        if hit and (now - hit[0]) < _MARKET_META_TTL_SECONDS:
            out[tkr] = hit[1]
        else:
            to_fetch.append(tkr)
    for tkr in to_fetch[:max_fetch]:
        raw = await kalshi.get_market(tkr)
        if not raw:
            continue
        flat = _flatten_market(raw)
        _MARKET_META_CACHE[tkr] = (now, flat)
        out[tkr] = flat
    return out


async def _pull_tape_page(kalshi: KalshiAdapter, limit: int) -> list[dict]:
    data = await kalshi.list_market_trades(limit=limit)
    return list(data.get("trades") or [])


async def _build_tape_payload(
    kalshi: KalshiAdapter,
    raw_trades: list[dict],
    min_notional: float,
    max_rows: int = 150,
    meta_fetch_cap: int = 60,
) -> dict:
    scored = _score_tape_rows(raw_trades, min_notional)
    top = scored[:max_rows]
    unique_tickers = list(dict.fromkeys(r["ticker"] for r in top if r.get("ticker")))
    meta = await _hydrate_market_meta(kalshi, unique_tickers, max_fetch=meta_fetch_cap)
    urls = await resolve_kalshi_market_web_urls(set(unique_tickers))

    total_notional = 0.0
    total_contracts = 0.0
    tier_counts = {"major": 0, "large": 0, "notable": 0}
    unique_markets: dict[str, dict[str, float]] = {}
    for r in top:
        tkr = r.get("ticker")
        m = meta.get(tkr or "") or {}
        oi = m.get("open_interest")
        share = None
        if oi and oi > 0:
            share = round(100.0 * float(r["count"]) / float(oi), 2)
        r["market"] = m
        r["kalshi_url"] = urls.get(tkr or "", "")
        r["share_of_oi_pct"] = share
        total_notional += float(r["notional_usd"] or 0.0)
        total_contracts += float(r["count"] or 0.0)
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
        if tkr:
            agg = unique_markets.setdefault(
                tkr, {"notional": 0.0, "count": 0.0, "trades": 0.0}
            )
            agg["notional"] += float(r["notional_usd"] or 0.0)
            agg["count"] += float(r["count"] or 0.0)
            agg["trades"] += 1.0

    top_markets = [
        {
            "ticker": t,
            "title": (meta.get(t) or {}).get("title") or t,
            "notional": round(v["notional"], 2),
            "contracts": v["count"],
            "trades": int(v["trades"]),
            "kalshi_url": urls.get(t, ""),
        }
        for t, v in unique_markets.items()
    ]
    top_markets.sort(key=lambda x: x["notional"], reverse=True)

    return {
        "trades": top,
        "summary": {
            "trades_shown": len(top),
            "scored_count": len(scored),
            "total_notional_usd": round(total_notional, 2),
            "total_contracts": total_contracts,
            "unique_markets": len(unique_markets),
            "tier_counts": tier_counts,
        },
        "top_markets": top_markets[:8],
    }


def _enrich_opps_with_kelly(opps: list[dict], settings: Settings) -> list[dict]:
    from kalshi_odds.models.comparison import Direction
    for o in opps:
        try:
            direction = Direction(o.get("direction", ""))
            shares = kelly_shares(
                o.get("edge_bps", 0),
                o.get("kalshi_price_cents", 50),
                direction,
                settings.bankroll_dollars,
                settings.kelly_fraction,
                settings.max_notional_per_trade,
                max_shares=o.get("max_shares"),
            )
            o["kelly_shares"] = shares
        except Exception:
            o["kelly_shares"] = 0
    return opps


async def _do_auto_map(
    kalshi: KalshiAdapter,
    odds_api,
    settings: Settings,
    *,
    force_rebuild: bool = False,
) -> int:
    sports = settings.sport_list
    if force_rebuild and settings.mapping_path.exists():
        settings.mapping_path.unlink(missing_ok=True)
    total = 0
    for sport in sports:
        try:
            mappings = await run_auto_map(
                kalshi, odds_api, sport, settings.mapping_path,
                merge_with_existing=True, write=True,
            )
            total += len(mappings)
        except Exception:
            pass
    _state["mapped_count"] = total
    return total


async def run_one_scan(
    settings: Settings,
    kalshi: KalshiAdapter,
    odds_api,
    polymarket: Optional[PolymarketAdapter],
    repo: Repository,
) -> tuple[int, Optional[str]]:
    """Run a scan with pre-existing connections. Returns (alert_count, error_message)."""
    _state["is_scanning"] = True
    try:
        matcher = MarketMatcher(mapping_file=settings.mapping_path, fuzzy_enabled=False)
        loaded = matcher.load_mappings()
        if loaded == 0:
            _state["scan_count"] = int(_state.get("scan_count", 0)) + 1
            _state["last_scan_iso"] = datetime.now(timezone.utc).isoformat()
            _state["last_error"] = "Waiting for mappings — odds provider may be rate limited"
            return 0, "No mappings in mappings.yaml"

        scanner = Scanner(
            kalshi_slippage_buffer=settings.kalshi_slippage_buffer,
            sportsbook_execution_friction=settings.sportsbook_execution_friction,
            min_edge_bps=settings.min_edge_bps,
            min_liquidity=settings.min_liquidity,
            max_staleness_seconds=settings.max_staleness_seconds,
        )
        sports = settings.sport_list

        try:
            expired = await repo.get_expired_contract_ids()
        except Exception:
            expired = set()

        if len(sports) > 1:
            all_alerts, opportunities = await run_multi_sport_scan(
                sports, matcher, scanner, kalshi, odds_api,
                skip_tickers=expired,
            )
        else:
            all_alerts, opportunities = await run_scan_cycle(
                sports[0], matcher, scanner, kalshi, odds_api,
                skip_tickers=expired,
            )

        _state["odds_requests_remaining"] = odds_api.last_requests_remaining
        _state["last_scan_iso"] = datetime.now(timezone.utc).isoformat()
        _state["scan_count"] = int(_state.get("scan_count", 0)) + 1
        _state["last_error"] = None
        _state["sports"] = sports
        active_label = getattr(odds_api, "_active_label", "")
        if active_label:
            _state["active_odds_provider"] = active_label
        _save_opportunities_disk(opportunities)
        if settings.poly_enabled and polymarket is not None:
            try:
                poly_opps = await run_poly_scan(
                    kalshi,
                    polymarket,
                    min_edge_bps=settings.poly_min_edge_bps,
                    min_liquidity_usd=settings.poly_min_liquidity_usd,
                    match_threshold=settings.poly_match_threshold,
                )
                _state["poly_opportunities"] = [o.model_dump(mode="json") for o in poly_opps]
            except Exception:
                _state["poly_opportunities"] = []

        saved = 0
        for alert in all_alerts:
            should = await repo.should_alert(alert.market_key, alert.direction.value, alert.edge_bps)
            if should:
                await repo.save_alert(alert)
                with open(settings.output_jsonl, "a") as f:
                    f.write(alert.model_dump_json() + "\n")
                saved += 1
        return saved, None
    except Exception as e:
        err = _friendly_error(e)
        _state["last_error"] = err
        return 0, err
    finally:
        _state["is_scanning"] = False


async def _run_standalone_scan(settings: Settings) -> tuple[int, Optional[str]]:
    """Open fresh connections for a one-off scan (used by POST /api/scan when no persistent conns)."""
    if not settings.kalshi_configured or not settings.odds_api_configured:
        return 0, "Kalshi or Odds API not configured"
    odds_api = create_odds_provider(settings)
    async with (
        KalshiAdapter(
            api_key_id=settings.kalshi_api_key_id,
            private_key_path=settings.kalshi_private_key_path,
            base_url=settings.kalshi_base_url,
            requests_per_second=settings.kalshi_requests_per_second,
        ) as kalshi,
        PolymarketAdapter() as polymarket,
        Repository(settings.database_url.split("///")[-1]) as repo,
    ):
        await odds_api.connect()
        try:
            return await run_one_scan(settings, kalshi, odds_api, polymarket, repo)
        finally:
            await odds_api.close()


_persistent_kalshi: Optional[KalshiAdapter] = None
_persistent_odds: Optional[OddsAPIAdapter] = None
_persistent_poly: Optional[PolymarketAdapter] = None
_persistent_repo: Optional[Repository] = None


@asynccontextmanager
async def _dashboard_lifespan(app: FastAPI):
    global _persistent_kalshi, _persistent_odds, _persistent_poly, _persistent_repo

    s = get_settings()
    task: Optional[asyncio.Task] = None

    repo = Repository(s.database_url.split("///")[-1])
    await repo.connect()
    _persistent_repo = repo
    auth_deps.bind(repo)
    try:
        await repo.purge_expired_sessions()
    except Exception:
        pass
    for admin_username in s.admin_bootstrap_list:
        try:
            await repo.promote_admin_by_username(admin_username)
        except Exception:
            pass

    if s.kalshi_configured and s.odds_api_configured:
        kalshi = KalshiAdapter(
            api_key_id=s.kalshi_api_key_id,
            private_key_path=s.kalshi_private_key_path,
            base_url=s.kalshi_base_url,
            requests_per_second=s.kalshi_requests_per_second,
        )
        odds_api = create_odds_provider(s)
        polymarket = PolymarketAdapter()
        await kalshi.connect()
        await odds_api.connect()
        await polymarket.connect()
        _persistent_kalshi = kalshi
        _persistent_odds = odds_api
        _persistent_poly = polymarket

        async def loop() -> None:
            scan_num = 0
            while True:
                try:
                    settings = get_settings()
                    if scan_num == 0 or scan_num % AUTO_MAP_INTERVAL_SCANS == 0:
                        await _do_auto_map(
                            kalshi, odds_api, settings,
                            force_rebuild=(scan_num == 0),
                        )
                        _state["last_automap_scan"] = scan_num
                    async with _scan_lock:
                        await run_one_scan(settings, kalshi, odds_api, polymarket, repo)
                    scan_num += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    _state["last_error"] = str(e)
                await asyncio.sleep(get_settings().poll_interval_seconds)

        task = asyncio.create_task(loop())
    if not _state.get("opportunities"):
        _state["opportunities"] = _load_opportunities_from_disk()
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if _persistent_kalshi:
            await _persistent_kalshi.close()
            _persistent_kalshi = None
        if _persistent_odds:
            await _persistent_odds.close()
            _persistent_odds = None
        if _persistent_poly:
            await _persistent_poly.close()
            _persistent_poly = None
        auth_deps.unbind()
        if _persistent_repo:
            await _persistent_repo.close()
            _persistent_repo = None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach conservative security headers to every response."""

    def __init__(self, app, *, secure_cookie: bool) -> None:
        super().__init__(app)
        self._secure = secure_cookie

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if self._secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        # CSP: allow self + inline styles for Tailwind-injected styles; block everything else.
        # Adjust if you add third-party scripts.
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "img-src 'self' data: blob:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; "
                "connect-src 'self' https:; "
                "font-src 'self' data:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
        )
        return response


def create_app(settings_override: Optional[Settings] = None) -> FastAPI:
    _ = settings_override
    s = get_settings()
    app = FastAPI(title="Kalshi Odds Dashboard", lifespan=_dashboard_lifespan)

    # Security headers (first, so they apply to all responses, including CORS preflights).
    app.add_middleware(SecurityHeadersMiddleware, secure_cookie=s.session_cookie_secure)

    # CORS — only enabled when explicit origins are configured.
    origins = s.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
            max_age=600,
        )

    if _REACT_ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=_REACT_ASSETS), name="react_assets")

    @app.get("/", response_model=None)
    async def index() -> FileResponse | HTMLResponse:
        if _REACT_INDEX.is_file():
            return FileResponse(_REACT_INDEX, media_type="text/html")
        html = _INDEX_HTML.read_text(encoding="utf-8")
        return HTMLResponse(html)

    @app.get("/api/state")
    async def api_state(user: dict = Depends(require_user)) -> dict:
        _ = user
        s = get_settings()
        db_path = s.database_url.split("///")[-1]
        async with Repository(db_path) as repo:
            positions = await repo.get_open_positions()
            settled = await repo.get_settled_positions(limit=50)
            pnl = await repo.get_pnl_summary()
        opps = _state.get("opportunities") or _load_opportunities_from_disk()
        opps = _enrich_opps_with_kelly(list(opps), s)
        return {
            "last_scan_iso": _state.get("last_scan_iso"),
            "scan_count": _state.get("scan_count", 0),
            "last_error": _state.get("last_error"),
            "opportunities": opps,
            "odds_requests_remaining": _state.get("odds_requests_remaining"),
            "kalshi_configured": s.kalshi_configured,
            "odds_configured": s.odds_api_configured,
            "execution_enabled": s.execution_enabled,
            "poll_interval_seconds": s.poll_interval_seconds,
            "positions": [p.model_dump(mode="json") for p in positions],
            "settled": [p.model_dump(mode="json") for p in settled],
            "pnl": pnl.model_dump(),
            "bankroll_dollars": s.bankroll_dollars,
            "kelly_fraction": s.kelly_fraction,
            "is_scanning": _state.get("is_scanning", False),
            "sports": _state.get("sports", s.sport_list),
            "mapped_count": _state.get("mapped_count", 0),
            "active_odds_provider": _state.get("active_odds_provider", ""),
            "poly_opportunities": _state.get("poly_opportunities", []),
        }

    @app.post("/api/scan")
    async def api_scan(user: dict = Depends(require_user)) -> dict:
        _ = user
        s = get_settings()
        async with _scan_lock:
            if _persistent_kalshi and _persistent_odds and _persistent_repo:
                n, err = await run_one_scan(s, _persistent_kalshi, _persistent_odds, _persistent_poly, _persistent_repo)
            else:
                n, err = await _run_standalone_scan(s)
        if err:
            return {"ok": False, "alerts": n, "error": err}
        return {"ok": True, "alerts": n}

    @app.post("/api/auto-map")
    async def api_auto_map(user: dict = Depends(require_user)) -> dict:
        _ = user
        s = get_settings()
        if not s.kalshi_configured or not s.odds_api_configured:
            return {"ok": False, "mapped": 0, "error": "APIs not configured"}
        try:
            if _persistent_kalshi and _persistent_odds:
                total = await _do_auto_map(_persistent_kalshi, _persistent_odds, s)
            else:
                odds_api = create_odds_provider(s)
                async with KalshiAdapter(
                    api_key_id=s.kalshi_api_key_id,
                    private_key_path=s.kalshi_private_key_path,
                    base_url=s.kalshi_base_url,
                ) as kalshi:
                    await odds_api.connect()
                    try:
                        total = await _do_auto_map(kalshi, odds_api, s)
                    finally:
                        await odds_api.close()
            return {"ok": True, "mapped": total}
        except Exception as e:
            return {"ok": False, "mapped": 0, "error": str(e)}

    @app.get("/api/health")
    async def api_health() -> dict:
        s = get_settings()
        uptime_s = time.monotonic() - _start_time
        kalshi_ok = _persistent_kalshi is not None
        odds_provider = _persistent_odds
        primary_label = "The Odds API"
        fallback_label = "OddsPapi"
        primary_ok = False
        fallback_ok = False
        active_provider = "none"
        if isinstance(odds_provider, FallbackOddsProvider):
            primary_ok = not odds_provider._primary_down
            fallback_ok = not odds_provider._fallback_exhausted
            active_provider = odds_provider._active_label
        elif odds_provider is not None:
            primary_ok = True
            active_provider = "The Odds API"
        db_ok = _persistent_repo is not None
        return {
            "status": "healthy" if (kalshi_ok and (primary_ok or fallback_ok)) else "degraded",
            "uptime_seconds": round(uptime_s),
            "kalshi": {"connected": kalshi_ok, "configured": s.kalshi_configured},
            "odds_primary": {
                "name": primary_label,
                "connected": primary_ok,
                "configured": bool(s.odds_api_key),
                "credits": _persistent_odds.last_requests_remaining if _persistent_odds else None,
            },
            "odds_fallback": {
                "name": fallback_label,
                "connected": fallback_ok,
                "configured": bool(s.oddspapi_api_key),
            },
            "active_provider": active_provider,
            "database": {"connected": db_ok},
            "scanner": {
                "running": _state.get("is_scanning", False),
                "scan_count": _state.get("scan_count", 0),
                "last_scan": _state.get("last_scan_iso"),
                "last_error": _state.get("last_error"),
                "mapped_count": _state.get("mapped_count", 0),
            },
        }

    @app.get("/api/config")
    async def api_config() -> dict:
        s = get_settings()
        return {
            "sports": s.sport_list,
            "min_edge_bps": s.min_edge_bps,
            "min_liquidity": s.min_liquidity,
            "poll_interval_seconds": s.poll_interval_seconds,
            "bankroll_dollars": s.bankroll_dollars,
            "kelly_fraction": s.kelly_fraction,
            "max_notional_per_trade": s.max_notional_per_trade,
            "execution_enabled": s.execution_enabled,
            "kalshi_slippage_buffer": s.kalshi_slippage_buffer,
            "sportsbook_execution_friction": s.sportsbook_execution_friction,
            "max_staleness_seconds": s.max_staleness_seconds,
            "auto_map_enabled": s.auto_map_enabled,
            "fuzzy_match_enabled": s.fuzzy_match_enabled,
            "poly_enabled": s.poly_enabled,
            "poly_min_edge_bps": s.poly_min_edge_bps,
            "poly_min_liquidity_usd": s.poly_min_liquidity_usd,
            "poly_match_threshold": s.poly_match_threshold,
        }

    @app.get("/api/alerts/recent")
    async def api_alerts_recent(user: dict = Depends(require_user)) -> list[dict]:
        _ = user
        s = get_settings()
        db_path = s.database_url.split("///")[-1]
        async with Repository(db_path) as repo:
            alerts = await repo.get_recent_alerts(limit=20)
        return [a.model_dump(mode="json") for a in alerts]

    class ExecuteBody(BaseModel):
        index: int = 1
        shares: int = 100
        dry_run: bool = True

    @app.post("/api/execute")
    async def api_execute(body: ExecuteBody, user: dict = Depends(require_admin)) -> dict:
        _ = user
        raw = _state.get("opportunities") or _load_opportunities_from_disk()
        if not raw:
            raise HTTPException(400, "No opportunities. Run scan first.")
        if body.index < 1 or body.index > len(raw):
            raise HTTPException(400, f"Invalid index {body.index}")
        opp = Opportunity.model_validate(raw[body.index - 1])
        s = get_settings()
        db_path = s.database_url.split("///")[-1]
        async with Repository(db_path) as repo:
            try:
                return await place_opportunity_order(
                    opp,
                    body.shares,
                    dry_run=body.dry_run,
                    settings=s,
                    repo=repo,
                    save_position=not body.dry_run,
                )
            except Exception as e:
                raise HTTPException(500, str(e)) from e

    @app.get("/api/trades/watch")
    async def api_trades_watch(
        min_notional: float = 250.0,
        fetch_limit: int = 500,
        user: dict = Depends(require_user),
    ) -> dict:
        _ = user
        """
        Recent public Kalshi tape filtered to larger prints (surveillance-style feed).
        Counterparties are not exposed in public data; this ranks by size only.
        """
        s = get_settings()
        now_iso = datetime.now(timezone.utc).isoformat()
        if not s.kalshi_configured:
            return {
                "ok": False,
                "error": "Kalshi API keys not configured",
                "trades": [],
                "kalshi_configured": False,
                "fetched_at": now_iso,
                "min_notional": min_notional,
            }
        fetch_limit = max(50, min(int(fetch_limit), 1000))
        floor = max(0.0, float(min_notional))
        try:
            if _persistent_kalshi is not None:
                raw = await _pull_tape_page(_persistent_kalshi, fetch_limit)
                payload = await _build_tape_payload(_persistent_kalshi, raw, floor)
            else:
                async with KalshiAdapter(
                    api_key_id=s.kalshi_api_key_id,
                    private_key_path=s.kalshi_private_key_path,
                    base_url=s.kalshi_base_url,
                    requests_per_second=s.kalshi_requests_per_second,
                ) as k:
                    raw = await _pull_tape_page(k, fetch_limit)
                    payload = await _build_tape_payload(k, raw, floor)
            return {
                "ok": True,
                "kalshi_configured": True,
                "raw_count": len(raw),
                "fetched_at": now_iso,
                "min_notional": floor,
                "fetch_limit": fetch_limit,
                **payload,
            }
        except Exception as e:
            return {
                "ok": False,
                "error": _friendly_error(e),
                "trades": [],
                "kalshi_configured": True,
                "fetched_at": now_iso,
                "min_notional": floor,
            }

    # ── Auth ────────────────────────────────────────────────────────────
    class AuthCredentials(BaseModel):
        username: str = Field(..., min_length=3, max_length=32)
        password: str = Field(..., min_length=8, max_length=256)
        email: Optional[str] = None
        invite_token: Optional[str] = Field(default=None, max_length=128)

    class LoginCredentials(BaseModel):
        username: str = Field(..., min_length=1, max_length=64)
        password: str = Field(..., min_length=1, max_length=256)

    class WaitlistApplication(BaseModel):
        username: str = Field(..., min_length=3, max_length=32)
        email: Optional[str] = Field(default=None, max_length=254)
        reason: Optional[str] = Field(default=None, max_length=1000)

    class SetBoolBody(BaseModel):
        value: bool

    def _user_public(user: dict) -> dict:
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email"),
            "created_at": user.get("created_at"),
            "last_login_at": user.get("last_login_at"),
            "is_admin": bool(user.get("is_admin")),
            "is_active": bool(user.get("is_active", True)),
        }

    def _write_session_cookie(resp: Response, token: str) -> None:
        cfg = get_settings()
        set_session_cookie(
            resp,
            token,
            secure=cfg.session_cookie_secure,
            samesite=cfg.session_samesite_normalized,
        )

    def _clear_session_cookie(resp: Response) -> None:
        cfg = get_settings()
        clear_session_cookie(
            resp,
            secure=cfg.session_cookie_secure,
            samesite=cfg.session_samesite_normalized,
        )

    async def _maybe_bootstrap_admin(username: str) -> None:
        """Promote the user to admin if their name is in ADMIN_BOOTSTRAP_USERNAMES."""
        if _persistent_repo is None:
            return
        bootstrap = [u.lower() for u in get_settings().admin_bootstrap_list]
        if username.lower() not in bootstrap:
            return
        try:
            await _persistent_repo.promote_admin_by_username(username)
        except Exception:
            pass

    # ── Waitlist (public) ──────────────────────────────────────────────
    @app.post("/api/waitlist")
    async def api_waitlist_apply(
        body: WaitlistApplication, request: Request
    ) -> dict:
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        ip = client_ip(request)
        rate_limit_or_raise(WAITLIST_LIMITER, key=f"waitlist:{ip}")
        username = validate_username(body.username)
        email = validate_email(body.email)
        reason = (body.reason or "").strip()[:1000] or None
        # Prevent duplicate application for an existing active account
        existing_user = await _persistent_repo.get_user_by_username(username)
        if existing_user:
            # Don't leak that a user exists — respond generically.
            return {"ok": True, "status": "received"}
        ip_h = hash_ip(ip)
        # Soft dedupe: cap applications per IP per day.
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        recent = await _persistent_repo.count_recent_waitlist_by_ip(ip_h, since)
        if recent >= 3:
            raise HTTPException(429, "Too many applications from this network today.")
        try:
            entry = await _persistent_repo.create_waitlist_entry(
                username=username, email=email, reason=reason, ip_hash=ip_h
            )
        except sqlite3.IntegrityError:
            return {"ok": True, "status": "received"}
        return {"ok": True, "status": "received", "id": entry["id"]}

    # ── Auth endpoints ─────────────────────────────────────────────────
    @app.post("/api/auth/register")
    async def api_register(
        body: AuthCredentials, response: Response, request: Request
    ) -> dict:
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        cfg = get_settings()
        rate_limit_or_raise(REGISTER_LIMITER, key=f"register:{client_ip(request)}")

        username = validate_username(body.username)
        email = validate_email(body.email)
        password = validate_password(body.password)

        # Invite-gated registration (default). Public registration requires explicit opt-in.
        invite_entry: Optional[dict] = None
        if not cfg.public_registration_enabled:
            token_in = (body.invite_token or "").strip()
            if not token_in:
                raise HTTPException(
                    403,
                    "Registration is invite-only. Join the waitlist to request access.",
                )
            invite_entry = await _persistent_repo.consume_invite_token(token_in)
            if not invite_entry:
                raise HTTPException(400, "Invite link is invalid or has expired.")
            # Bind the account to the exact username/email that was approved.
            if invite_entry["username"].lower() != username.lower():
                raise HTTPException(
                    400,
                    "This invite was issued for a different username.",
                )
            if invite_entry.get("email") and email and email != invite_entry["email"]:
                raise HTTPException(
                    400, "This invite was issued for a different email address."
                )
            if invite_entry.get("email") and not email:
                email = invite_entry["email"]

        salt, pwd_hash = hash_password(password)
        try:
            user = await _persistent_repo.create_user(username, email, salt, pwd_hash)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Username or email already in use") from None
        await _maybe_bootstrap_admin(username)
        full_user = await _persistent_repo.get_user_by_id(user["id"]) or user
        session_token = new_session_token()
        await _persistent_repo.create_session(user["id"], session_token, session_expiry())
        _write_session_cookie(response, session_token)
        return {"ok": True, "user": _user_public(full_user)}

    @app.post("/api/auth/login")
    async def api_login(
        body: LoginCredentials, response: Response, request: Request
    ) -> dict:
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        ip = client_ip(request)
        rate_limit_or_raise(LOGIN_LIMITER, key=f"login:{ip}")
        username = (body.username or "").strip()
        if not username or not body.password:
            raise HTTPException(400, "Username and password required")
        row = await _persistent_repo.get_user_by_username(username)
        invalid = not row or not verify_password(
            body.password, row["password_salt"], row["password_hash"]
        )
        if invalid:
            # Also count login attempts by username to slow targeted brute force.
            rate_limit_or_raise(LOGIN_LIMITER, key=f"login-user:{username.lower()}")
            raise HTTPException(401, "Invalid username or password")
        assert row is not None
        if not row.get("is_active", True):
            raise HTTPException(403, "This account has been disabled.")
        await _maybe_bootstrap_admin(row["username"])
        session_token = new_session_token()
        await _persistent_repo.create_session(row["id"], session_token, session_expiry())
        await _persistent_repo.touch_user_login(row["id"])
        _write_session_cookie(response, session_token)
        # Refresh row so is_admin reflects any just-applied bootstrap promotion.
        refreshed = await _persistent_repo.get_user_by_id(row["id"]) or row
        return {"ok": True, "user": _user_public(refreshed)}

    @app.post("/api/auth/logout")
    async def api_logout(
        response: Response,
        user: Optional[dict] = Depends(get_optional_user),
        session_token: Optional[str] = Cookie(default=None, alias="kb_session"),
    ) -> dict:
        _ = user
        if session_token and _persistent_repo is not None:
            try:
                await _persistent_repo.delete_session(session_token)
            except Exception:
                pass
        _clear_session_cookie(response)
        return {"ok": True}

    @app.get("/api/auth/me")
    async def api_me(user: Optional[dict] = Depends(get_optional_user)) -> dict:
        return {"authenticated": bool(user), "user": _user_public(user) if user else None}

    # ── Admin endpoints ────────────────────────────────────────────────
    @app.get("/api/admin/waitlist")
    async def api_admin_waitlist(
        status_filter: Optional[str] = None,
        admin: dict = Depends(require_admin),
    ) -> list[dict]:
        _ = admin
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        if status_filter and status_filter not in {
            "pending", "approved", "rejected", "consumed"
        }:
            raise HTTPException(400, "Invalid status filter")
        rows = await _persistent_repo.list_waitlist(status_filter)
        # Never leak ip_hash.
        return rows

    @app.post("/api/admin/waitlist/{entry_id}/approve")
    async def api_admin_waitlist_approve(
        entry_id: int, admin: dict = Depends(require_admin)
    ) -> dict:
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        cfg = get_settings()
        token = new_session_token()
        expires = datetime.now(timezone.utc) + timedelta(hours=cfg.invite_ttl_hours)
        result = await _persistent_repo.approve_waitlist_entry(
            entry_id,
            decided_by_user_id=admin["id"],
            invite_token=token,
            invite_expires_at=expires,
        )
        if not result:
            raise HTTPException(404, "Waitlist entry not found or already decided.")
        return {"ok": True, "entry": result}

    @app.post("/api/admin/waitlist/{entry_id}/reject")
    async def api_admin_waitlist_reject(
        entry_id: int, admin: dict = Depends(require_admin)
    ) -> dict:
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        result = await _persistent_repo.reject_waitlist_entry(
            entry_id, decided_by_user_id=admin["id"]
        )
        if not result:
            raise HTTPException(404, "Waitlist entry not found or already decided.")
        return {"ok": True, "entry": result}

    @app.get("/api/admin/users")
    async def api_admin_users(admin: dict = Depends(require_admin)) -> list[dict]:
        _ = admin
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        return await _persistent_repo.list_users()

    @app.post("/api/admin/users/{user_id}/active")
    async def api_admin_set_active(
        user_id: int, body: SetBoolBody, admin: dict = Depends(require_admin)
    ) -> dict:
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        if user_id == admin["id"] and not body.value:
            raise HTTPException(400, "You cannot deactivate your own account.")
        await _persistent_repo.set_user_active(user_id, body.value)
        return {"ok": True}

    @app.post("/api/admin/users/{user_id}/admin")
    async def api_admin_set_admin(
        user_id: int, body: SetBoolBody, admin: dict = Depends(require_admin)
    ) -> dict:
        if _persistent_repo is None:
            raise HTTPException(503, "Database not ready")
        if user_id == admin["id"] and not body.value:
            raise HTTPException(400, "You cannot remove your own admin role.")
        await _persistent_repo.set_user_admin(user_id, body.value)
        return {"ok": True}

    return app


def main() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "kalshi_odds.dashboard.server:create_app",
        factory=True,
        host="127.0.0.1",
        port=s.dashboard_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
