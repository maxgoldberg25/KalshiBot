"""FastAPI dashboard: opportunities, positions, PnL, scanner status."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter
from kalshi_odds.config import Settings, get_settings
from kalshi_odds.core.matcher import MarketMatcher
from kalshi_odds.core.scan_runner import run_scan_cycle
from kalshi_odds.core.scanner import Scanner
from kalshi_odds.db import Repository
from kalshi_odds.execution import place_opportunity_order
from kalshi_odds.models.comparison import Opportunity

LAST_OPPORTUNITIES_FILE = Path(".last_opportunities.json")

_templates_dir = Path(__file__).resolve().parent / "templates"
_INDEX_HTML = _templates_dir / "index.html"

_scan_lock = asyncio.Lock()
_state: dict[str, Any] = {
    "last_scan_iso": None,
    "scan_count": 0,
    "last_error": None,
    "opportunities": [],
    "odds_requests_remaining": None,
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


async def run_one_scan(settings: Settings) -> tuple[int, Optional[str]]:
    """Returns (alert_count, error_message)."""
    if not settings.kalshi_configured or not settings.odds_api_configured:
        return 0, "Kalshi or Odds API not configured"

    matcher = MarketMatcher(mapping_file=settings.mapping_path, fuzzy_enabled=False)
    loaded = matcher.load_mappings()
    if loaded == 0:
        return 0, "No mappings in mappings.yaml"

    scanner = Scanner(
        kalshi_slippage_buffer=settings.kalshi_slippage_buffer,
        sportsbook_execution_friction=settings.sportsbook_execution_friction,
        min_edge_bps=settings.min_edge_bps,
        min_liquidity=settings.min_liquidity,
        max_staleness_seconds=settings.max_staleness_seconds,
    )
    sport = settings.default_sport

    try:
        async with (
            KalshiAdapter(
                api_key_id=settings.kalshi_api_key_id,
                private_key_path=settings.kalshi_private_key_path,
                base_url=settings.kalshi_base_url,
                requests_per_second=settings.kalshi_requests_per_second,
            ) as kalshi,
            OddsAPIAdapter(
                api_key=settings.odds_api_key,
                base_url=settings.odds_api_base_url,
                requests_per_second=settings.odds_api_requests_per_second,
            ) as odds_api,
            Repository(settings.database_url.split("///")[-1]) as repo,
        ):
            all_alerts, opportunities = await run_scan_cycle(sport, matcher, scanner, kalshi, odds_api)
            _state["odds_requests_remaining"] = odds_api.last_requests_remaining
            _state["last_scan_iso"] = datetime.now(timezone.utc).isoformat()
            _state["scan_count"] = int(_state.get("scan_count", 0)) + 1
            _state["last_error"] = None
            _save_opportunities_disk(opportunities)
            for alert in all_alerts:
                await repo.save_alert(alert)
                with open(settings.output_jsonl, "a") as f:
                    f.write(alert.model_dump_json() + "\n")
            return len(all_alerts), None
    except Exception as e:
        err = str(e)
        _state["last_error"] = err
        return 0, err


@asynccontextmanager
async def _dashboard_lifespan(app: FastAPI):
    async def loop() -> None:
        while True:
            try:
                async with _scan_lock:
                    await run_one_scan(get_settings())
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _state["last_error"] = str(e)
            await asyncio.sleep(get_settings().poll_interval_seconds)

    s = get_settings()
    task: Optional[asyncio.Task] = None
    if s.kalshi_configured and s.odds_api_configured:
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


def create_app(settings_override: Optional[Settings] = None) -> FastAPI:
    _ = settings_override  # reserved for tests
    app = FastAPI(title="Kalshi Odds Dashboard", lifespan=_dashboard_lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
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
        }

    @app.post("/api/scan")
    async def api_scan() -> dict:
        async with _scan_lock:
            n, err = await run_one_scan(get_settings())
        if err:
            return {"ok": False, "alerts": n, "error": err}
        return {"ok": True, "alerts": n}

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
