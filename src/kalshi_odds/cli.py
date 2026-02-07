"""CLI entrypoint for Kalshi vs Sportsbook odds scanner."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from kalshi_odds.config import get_settings
from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter
from kalshi_odds.core.automapper import auto_map as run_auto_map
from kalshi_odds.core.matcher import MarketMatcher
from kalshi_odds.core.scanner import Scanner, aggregate_opportunities
from kalshi_odds.db import Repository
from kalshi_odds.models.comparison import Alert, Opportunity

app = typer.Typer(
    name="kalshi-odds",
    help="Alert-only Kalshi vs Sportsbook odds comparison scanner.",
    no_args_is_help=True,
)
console = Console()

# File to persist last scan's opportunities for detail/execute (cwd)
LAST_OPPORTUNITIES_FILE = Path(".last_opportunities.json")


def _format_liquidity(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _edge_style(edge_cents: float) -> str:
    if edge_cents >= 2.0:
        return "green"
    if edge_cents >= 1.0:
        return "yellow"
    return "dim"


def _render_opportunities_table(opportunities: list[Opportunity], title: str = "Opportunities") -> None:
    if not opportunities:
        console.print("[dim]No opportunities[/]")
        return
    table = Table(
        title=title,
        show_header=True,
        header_style="bold",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Game", width=22)
    table.add_column("Edge", width=6)
    table.add_column("Action", width=36)
    table.add_column("Hedge", width=38)
    table.add_column("Books", width=6)
    table.add_column("Liq", width=6)
    table.add_column("Conf", width=5)
    for i, opp in enumerate(opportunities, 1):
        edge_style = _edge_style(opp.edge_cents)
        table.add_row(
            str(i),
            opp.game_label[:22],
            f"[{edge_style}]{opp.edge_cents:.1f}c[/]",
            opp.kalshi_action[:36],
            opp.hedge_action[:38],
            f"{opp.book_count}",
            _format_liquidity(opp.kalshi_liquidity),
            opp.confidence.value.upper()[:3],
        )
    console.print(table)
    console.print(
        "[dim]Detail: kalshi-odds detail <#>     |     Execute: kalshi-odds execute <#> --shares 100[/]"
    )


def _save_last_opportunities(opportunities: list[Opportunity]) -> None:
    data = [o.model_dump(mode="json") for o in opportunities]
    with open(LAST_OPPORTUNITIES_FILE, "w") as f:
        json.dump(data, f, indent=0, default=str)


def _load_last_opportunities() -> list[Opportunity]:
    if not LAST_OPPORTUNITIES_FILE.exists():
        return []
    with open(LAST_OPPORTUNITIES_FILE) as f:
        data = json.load(f)
    return [Opportunity.model_validate(d) for d in data]


@app.command("sync-kalshi")
def sync_kalshi() -> None:
    """Fetch and cache Kalshi markets/contracts."""
    settings = get_settings()
    
    if not settings.kalshi_configured:
        console.print("[red]✗ Kalshi not configured. Set KALSHI_ODDS_KALSHI_API_KEY_ID and KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH[/]")
        raise typer.Exit(1)

    async def _run():
        async with KalshiAdapter(
            api_key_id=settings.kalshi_api_key_id,
            private_key_path=settings.kalshi_private_key_path,
            base_url=settings.kalshi_base_url,
            requests_per_second=settings.kalshi_requests_per_second,
        ) as kalshi, Repository(settings.database_url.split("///")[-1]) as repo:
            console.print("[blue]Fetching Kalshi contracts...[/]")
            contracts = await kalshi.list_contracts()
            
            console.print(f"[green]✓[/] Fetched {len(contracts)} contracts")
            
            # Save to database
            for contract in contracts:
                await repo.save_kalshi_contract(contract)
            
            console.print(f"[green]✓[/] Saved to database")
            
            # Display sample
            table = Table(title="Sample Contracts")
            table.add_column("Contract ID")
            table.add_column("Title")
            table.add_column("Close Time")
            table.add_column("Last Price")
            
            for contract in contracts[:10]:
                table.add_row(
                    contract.contract_id,
                    contract.title[:50],
                    contract.close_time.strftime("%Y-%m-%d %H:%M") if contract.close_time else "",
                    f"{contract.last_price:.2f}" if contract.last_price else "",
                )
            
            console.print(table)

    asyncio.run(_run())


@app.command("sync-odds")
def sync_odds(
    sport: str = typer.Option("americanfootball_nfl", "--sport", "-s", help="Sport key"),
) -> None:
    """Fetch and cache odds from sportsbooks."""
    settings = get_settings()
    
    if not settings.odds_api_configured:
        console.print("[red]✗ The Odds API not configured. Set KALSHI_ODDS_ODDS_API_KEY[/]")
        raise typer.Exit(1)

    async def _run():
        async with OddsAPIAdapter(
            api_key=settings.odds_api_key,
            base_url=settings.odds_api_base_url,
            requests_per_second=settings.odds_api_requests_per_second,
        ) as odds_api, Repository(settings.database_url.split("///")[-1]) as repo:
            console.print(f"[blue]Fetching odds for {sport}...[/]")
            
            raw_events = await odds_api.get_odds(sport=sport, markets="h2h")
            quotes = odds_api.parse_odds_to_quotes(raw_events)
            
            console.print(f"[green]✓[/] Fetched {len(quotes)} quotes from {len(raw_events)} events")
            
            # Save to database
            for quote in quotes:
                await repo.save_odds_quote(quote)
            
            console.print(f"[green]✓[/] Saved to database")
            
            # Display sample
            table = Table(title="Sample Odds")
            table.add_column("Event")
            table.add_column("Bookmaker")
            table.add_column("Selection")
            table.add_column("Odds")
            
            for quote in quotes[:15]:
                table.add_row(
                    quote.event_title[:40],
                    quote.bookmaker,
                    quote.selection[:25],
                    f"{quote.odds_value:+.0f}" if quote.odds_format.value == "american" else f"{quote.odds_value:.2f}",
                )
            
            console.print(table)

    asyncio.run(_run())


@app.command("match-candidates")
def match_candidates(
    fuzzy: bool = typer.Option(True, "--fuzzy/--no-fuzzy", help="Enable fuzzy matching"),
) -> None:
    """Show fuzzy match candidates for manual review."""
    settings = get_settings()
    if fuzzy:
        settings.fuzzy_match_enabled = True

    console.print("[yellow]⚠ This command shows candidates only. Review and manually add to mappings.yaml[/]")
    
    async def _run():
        matcher = MarketMatcher(
            mapping_file=settings.mapping_path,
            fuzzy_enabled=settings.fuzzy_match_enabled,
            fuzzy_threshold=settings.fuzzy_match_threshold,
        )
        matcher.load_mappings()
        
        # Load contracts and quotes from DB
        async with Repository(settings.database_url.split("///")[-1]) as repo:
            # Simplified: just show the concept
            console.print("[blue]Fuzzy matching not fully implemented in DB layer.[/]")
            console.print("[blue]Add contracts/quotes to DB via sync commands first.[/]")

    asyncio.run(_run())


async def _run_scan_cycle(
    sport: str,
    matcher: MarketMatcher,
    scanner: Scanner,
    kalshi: KalshiAdapter,
    odds_api: OddsAPIAdapter,
) -> tuple[list[Alert], list[Opportunity]]:
    """Run one scan: fetch odds, compare all mapped markets, return alerts and aggregated opportunities."""
    raw_events = await odds_api.get_odds(sport=sport)
    quotes = odds_api.parse_odds_to_quotes(raw_events)
    all_alerts: list[Alert] = []
    for market_key in matcher.get_all_market_keys():
        mapping = matcher.get_mapping(market_key)
        if not mapping:
            continue
        kalshi_data = mapping.get("kalshi", {})
        contract_id = kalshi_data.get("contract_id")
        if not contract_id:
            continue
        tob = await kalshi.get_top_of_book(contract_id)
        if not tob:
            continue
        odds_data = mapping.get("odds", {})
        event_id = odds_data.get("event_id", "")
        market_type = odds_data.get("market_type", "")
        relevant_quotes = [
            q for q in quotes
            if q.event_id == event_id and q.market_type.value == market_type
        ]
        if not relevant_quotes:
            continue
        alerts = scanner.compare(market_key, tob, relevant_quotes, mapping)
        all_alerts.extend(alerts)
    opportunities = aggregate_opportunities(all_alerts)
    return all_alerts, opportunities


@app.command("scan")
def scan(
    sport: str = typer.Option(None, "--sport", "-s", help="Sport key (default from config)"),
    auto_map: Optional[bool] = typer.Option(None, "--auto-map/--no-auto-map", help="Refresh mappings from Kalshi + Odds API before scanning"),
) -> None:
    """One-shot scan: fetch, compare, display ranked opportunities, and exit."""
    settings = get_settings()
    sport = sport or settings.default_sport
    do_auto_map = auto_map if auto_map is not None else settings.auto_map_enabled
    if not settings.kalshi_configured:
        console.print("[red]✗ Kalshi not configured[/]")
        raise typer.Exit(1)
    if not settings.odds_api_configured:
        console.print("[red]✗ The Odds API not configured[/]")
        raise typer.Exit(1)

    async def _run():
        async with (
            KalshiAdapter(
                api_key_id=settings.kalshi_api_key_id,
                private_key_path=settings.kalshi_private_key_path,
            ) as kalshi,
            OddsAPIAdapter(api_key=settings.odds_api_key) as odds_api,
            Repository(settings.database_url.split("///")[-1]) as repo,
        ):
            if do_auto_map:
                console.print("[blue]Auto-mapping Kalshi ↔ Odds API...[/]")
                try:
                    mappings = await run_auto_map(
                        kalshi, odds_api, sport, settings.mapping_path,
                        merge_with_existing=True, write=True,
                    )
                    console.print(f"[green]✓[/] Mapped {len(mappings)} markets")
                except Exception as e:
                    console.print(f"[yellow]Auto-map failed: {e}[/]")
            matcher = MarketMatcher(mapping_file=settings.mapping_path, fuzzy_enabled=False)
            loaded = matcher.load_mappings()
            if loaded == 0:
                console.print("[yellow]⚠ No mappings found. Create mappings.yaml first.[/]")
                return
            scanner = Scanner(
                kalshi_slippage_buffer=settings.kalshi_slippage_buffer,
                sportsbook_execution_friction=settings.sportsbook_execution_friction,
                min_edge_bps=settings.min_edge_bps,
                min_liquidity=settings.min_liquidity,
                max_staleness_seconds=settings.max_staleness_seconds,
            )
            console.print(f"[blue]Scanning {sport}...[/]")
            all_alerts, opportunities = await _run_scan_cycle(sport, matcher, scanner, kalshi, odds_api)
            now = datetime.now(timezone.utc).strftime("%b %d %Y %I:%M%p EST")
            console.print(f"\n[bold]KALSHI ODDS SCANNER[/]  |  [cyan]{len(opportunities)} opportunities[/]  |  {now}\n")
            _render_opportunities_table(opportunities)
            _save_last_opportunities(opportunities)
            for alert in all_alerts:
                await repo.save_alert(alert)
                with open(settings.output_jsonl, "a") as f:
                    f.write(alert.model_dump_json() + "\n")

    asyncio.run(_run())


@app.command("run")
def run(
    sport: str = typer.Option(None, "--sport", "-s"),
    interval: Optional[float] = typer.Option(None, "--interval", "-i", help="Poll interval in seconds"),
    auto_map: Optional[bool] = typer.Option(None, "--auto-map/--no-auto-map", help="Refresh mappings before first scan"),
) -> None:
    """Start continuous scanner loop (alerts only)."""
    settings = get_settings()
    sport = sport or settings.default_sport
    do_auto_map = auto_map if auto_map is not None else settings.auto_map_enabled
    if interval:
        settings.poll_interval_seconds = interval or 60.0
    else:
        settings.poll_interval_seconds = 60.0
    if not settings.kalshi_configured:
        console.print("[red]✗ Kalshi not configured[/]")
        raise typer.Exit(1)
    if not settings.odds_api_configured:
        console.print("[red]✗ The Odds API not configured[/]")
        raise typer.Exit(1)
    console.print("[green]Starting scanner (alert-only mode)...[/]")

    async def _run():
        async with (
            KalshiAdapter(
                api_key_id=settings.kalshi_api_key_id,
                private_key_path=settings.kalshi_private_key_path,
            ) as kalshi,
            OddsAPIAdapter(api_key=settings.odds_api_key) as odds_api,
            Repository(settings.database_url.split("///")[-1]) as repo,
        ):
            if do_auto_map:
                console.print("[blue]Auto-mapping Kalshi ↔ Odds API...[/]")
                try:
                    mappings = await run_auto_map(
                        kalshi, odds_api, sport, settings.mapping_path,
                        merge_with_existing=True, write=True,
                    )
                    console.print(f"[green]✓[/] Mapped {len(mappings)} markets")
                except Exception as e:
                    console.print(f"[yellow]Auto-map failed: {e}[/]")
            matcher = MarketMatcher(mapping_file=settings.mapping_path, fuzzy_enabled=False)
            loaded = matcher.load_mappings()
            console.print(f"[blue]Loaded {loaded} market mappings[/]")
            if loaded == 0:
                console.print("[yellow]⚠ No mappings found. Create mappings.yaml first.[/]")
                return
            scanner = Scanner(
                kalshi_slippage_buffer=settings.kalshi_slippage_buffer,
                sportsbook_execution_friction=settings.sportsbook_execution_friction,
                min_edge_bps=settings.min_edge_bps,
                min_liquidity=settings.min_liquidity,
                max_staleness_seconds=settings.max_staleness_seconds,
            )
            while True:
                try:
                    console.print(f"[dim]Scanning at [cyan]NOW[/]...[/]")
                    all_alerts, opportunities = await _run_scan_cycle(sport, matcher, scanner, kalshi, odds_api)
                    if opportunities:
                        now = datetime.now(timezone.utc).strftime("%b %d %Y %I:%M%p EST")
                        console.print(f"\n[bold]KALSHI ODDS SCANNER[/]  |  [cyan]{len(opportunities)} opportunities[/]  |  {now}\n")
                        _render_opportunities_table(opportunities)
                        _save_last_opportunities(opportunities)
                        for alert in all_alerts:
                            await repo.save_alert(alert)
                            with open(settings.output_jsonl, "a") as f:
                                f.write(alert.model_dump_json() + "\n")
                    else:
                        console.print("[dim]No opportunities[/]")
                    await asyncio.sleep(settings.poll_interval_seconds)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Stopped by user[/]")
                    break
                except Exception as e:
                    console.print(f"[red]Error: {e}[/]")
                    await asyncio.sleep(10)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped[/]")


@app.command("detail")
def detail(
    index: int = typer.Argument(1, help="Opportunity number from last scan (1-based)"),
) -> None:
    """Show full breakdown for an opportunity from the last scan."""
    opportunities = _load_last_opportunities()
    if not opportunities:
        console.print("[yellow]No opportunities saved. Run [bold]kalshi-odds scan[/] first.[/]")
        raise typer.Exit(1)
    if index < 1 or index > len(opportunities):
        console.print(f"[red]Invalid index {index}. Use 1–{len(opportunities)}.[/]")
        raise typer.Exit(1)
    opp = opportunities[index - 1]
    console.print(f"\n[bold]#{index} {opp.game_label}[/]\n")
    console.print(f"  [bold]Kalshi:[/]  {opp.kalshi_action}")
    console.print(f"  [bold]Hedge:[/]   {opp.hedge_action}")
    console.print(f"  [bold]Edge:[/]   {opp.edge_cents:.2f}c per share  ({opp.edge_bps:.0f} bps)")
    console.print(f"  [bold]Books:[/]  {opp.book_count} agreeing  |  Best: {opp.book_best}  |  Worst: {opp.book_worst}")
    console.print(f"  [bold]Liq:[/]    {_format_liquidity(opp.kalshi_liquidity)} shares  |  Max size: {opp.max_shares}")
    console.print(f"  [bold]P&L:[/]    ${opp.pnl_per_100_shares:.2f} expected per 100 shares")
    console.print(f"\n  [dim]P&L scenarios (100 shares):[/]")
    console.print(f"    Win on Kalshi side:  ~${opp.edge_cents * 100 / 100:.2f} edge captured")
    console.print(f"    Lose:                depends on hedge sizing")
    console.print(f"\n  [bold]Kalshi:[/] [link={opp.kalshi_url}]{opp.kalshi_url}[/]")
    console.print()


@app.command("execute")
def execute(
    index: int = typer.Argument(1, help="Opportunity number from last scan (1-based)"),
    shares: int = typer.Option(100, "--shares", "-n", help="Number of shares to trade"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Preview only, do not place order"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Confirm execution (required for real orders)"),
) -> None:
    """Place the Kalshi leg of an opportunity (buy/sell YES). You must place the sportsbook hedge manually."""
    settings = get_settings()
    if not settings.execution_enabled and not dry_run:
        console.print("[red]Execution is disabled. Set KALSHI_ODDS_EXECUTION_ENABLED=true to enable.[/]")
        raise typer.Exit(1)
    opportunities = _load_last_opportunities()
    if not opportunities:
        console.print("[yellow]No opportunities saved. Run [bold]kalshi-odds scan[/] first.[/]")
        raise typer.Exit(1)
    if index < 1 or index > len(opportunities):
        console.print(f"[red]Invalid index {index}. Use 1–{len(opportunities)}.[/]")
        raise typer.Exit(1)
    opp = opportunities[index - 1]
    if shares > opp.max_shares:
        console.print(f"[yellow]Requested {shares} shares exceeds max {opp.max_shares}. Capping.[/]")
        shares = opp.max_shares
    if dry_run:
        console.print(f"[bold]DRY RUN[/] – no order will be placed.\n")
    console.print(f"  Opportunity: {opp.game_label}")
    console.print(f"  Action:      {opp.kalshi_action}  x {shares} shares")
    console.print(f"  Then hedge:  {opp.hedge_action}")
    if not dry_run and not confirm:
        console.print("\n[red]Add [bold]--confirm[/] to place the order.[/]")
        raise typer.Exit(1)
    if dry_run:
        console.print("\n[dim]Run with --no-dry-run --confirm to place the order.[/]")
        return

    async def _place():
        from kalshi_odds.models.comparison import Direction
        async with KalshiAdapter(
            api_key_id=settings.kalshi_api_key_id,
            private_key_path=settings.kalshi_private_key_path,
        ) as kalshi:
            side = "yes"
            action = "sell" if opp.direction == Direction.KALSHI_RICH else "buy"
            price_cents = max(1, min(99, opp.kalshi_price_cents))
            result = await kalshi.place_order(
                ticker=opp.kalshi_ticker,
                side=side,
                action=action,
                count=shares,
                yes_price=price_cents,
            )
            return result

    try:
        result = asyncio.run(_place())
        console.print("[green]Order placed.[/]")
        console.print(f"  [dim]{result}[/]")
        console.print("\n[yellow]Remember to place the sportsbook hedge manually.[/]")
    except Exception as e:
        console.print(f"[red]Order failed: {e}[/]")
        raise typer.Exit(1)


@app.command("show")
def show(
    last: int = typer.Option(20, "--last", "-n", help="Show last N alerts"),
) -> None:
    """Print recent alerts from database."""
    settings = get_settings()

    async def _run():
        async with Repository(settings.database_url.split("///")[-1]) as repo:
            alerts = await repo.get_recent_alerts(limit=last)
            
            if not alerts:
                console.print("[yellow]No alerts found[/]")
                return
            
            table = Table(title=f"Last {len(alerts)} Alerts")
            table.add_column("Time", style="dim")
            table.add_column("Market")
            table.add_column("Direction")
            table.add_column("Edge")
            table.add_column("Confidence")
            table.add_column("Kalshi Price")
            table.add_column("Book Prob")
            
            for alert in alerts:
                table.add_row(
                    alert.timestamp.strftime("%m-%d %H:%M"),
                    alert.market_key[:25],
                    alert.direction.value,
                    f"{alert.edge_bps:.0f}bps",
                    alert.confidence.value,
                    f"{alert.kalshi_price:.3f}",
                    f"{alert.sportsbook_p_no_vig:.3f}",
                )
            
            console.print(table)

    asyncio.run(_run())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
