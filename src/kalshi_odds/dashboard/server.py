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

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter
from kalshi_odds.adapters.odds_provider import create_odds_provider, FallbackOddsProvider
from kalshi_odds.adapters.polymarket import PolymarketAdapter
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

    if s.kalshi_configured and s.odds_api_configured:
        kalshi = KalshiAdapter(
            api_key_id=s.kalshi_api_key_id,
            private_key_path=s.kalshi_private_key_path,
            base_url=s.kalshi_base_url,
            requests_per_second=s.kalshi_requests_per_second,
        )
        odds_api = create_odds_provider(s)
        polymarket = PolymarketAdapter()
        repo = Repository(s.database_url.split("///")[-1])
        await kalshi.connect()
        await odds_api.connect()
        await polymarket.connect()
        await repo.connect()
        _persistent_kalshi = kalshi
        _persistent_odds = odds_api
        _persistent_poly = polymarket
        _persistent_repo = repo

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
        if _persistent_repo:
            await _persistent_repo.close()
            _persistent_repo = None


def create_app(settings_override: Optional[Settings] = None) -> FastAPI:
    _ = settings_override
    app = FastAPI(title="Kalshi Odds Dashboard", lifespan=_dashboard_lifespan)

    if _REACT_ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=_REACT_ASSETS), name="react_assets")

    @app.get("/", response_model=None)
    async def index() -> FileResponse | HTMLResponse:
        if _REACT_INDEX.is_file():
            return FileResponse(_REACT_INDEX, media_type="text/html")
        html = _INDEX_HTML.read_text(encoding="utf-8")
        return HTMLResponse(html)

    @app.get("/api/state")
    async def api_state() -> dict:
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
    async def api_scan() -> dict:
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
    async def api_auto_map() -> dict:
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
    async def api_alerts_recent() -> list[dict]:
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
    async def api_execute(body: ExecuteBody) -> dict:
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
                result = await place_opportunity_order(
                    opp,
                    body.shares,
                    dry_run=body.dry_run,
                    settings=s,
                    repo=repo,
                    save_position=not body.dry_run,
                )
            except Exception as e:
                raise HTTPException(500, str(e)) from e
        return result

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
