"""
Command-line interface using Typer.

Usage:
    kalshi-bot run --mode paper
    kalshi-bot run --mode live
    kalshi-bot run --mode dry_run
    kalshi-bot snapshot --tickers TICKER1,TICKER2
    kalshi-bot report --date 2024-01-15
"""

import asyncio
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kalshi_bot.config import TradingMode, settings
from kalshi_bot.observability.logging import setup_logging
from kalshi_bot.scheduler.runner import TradingRunner

app = typer.Typer(
    name="kalshi-bot",
    help="Production trading bot for Kalshi prediction markets",
    add_completion=False,
)
console = Console()


def print_banner() -> None:
    """Print startup banner with safety warnings."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                    KALSHI TRADING BOT                         ║
╠═══════════════════════════════════════════════════════════════╣
║  ⚠️  WARNING: This bot can trade real money!                   ║
║                                                               ║
║  • Start with PAPER mode to validate your setup               ║
║  • Review all risk parameters before going LIVE               ║
║  • Monitor positions and set stop-losses                      ║
║  • No guarantees of profitability                             ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold yellow")


def print_config_summary() -> None:
    """Print current configuration summary."""
    table = Table(title="Configuration Summary", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Mode", settings.mode.value)
    table.add_row("Timezone", settings.timezone)
    table.add_row("Max Daily Loss", f"${settings.max_daily_loss_dollars:.2f}")
    table.add_row("Max Per-Market", f"${settings.max_per_market_exposure_dollars:.2f}")
    table.add_row("Max Trades/Day", str(settings.max_trades_per_day))
    table.add_row("Min Win Rate", f"{settings.min_win_rate:.0%}")
    table.add_row("Min EV", f"{settings.min_expected_value:.1%}")
    
    # Check for proper API credentials (both key ID and private key)
    api_configured = bool(settings.kalshi_api_key_id and settings.kalshi_private_key_path)
    table.add_row("API Credentials", "✓" if api_configured else "✗ (mock mode)")
    
    console.print(table)


@app.command()
def run(
    mode: str = typer.Option(
        "paper",
        "--mode", "-m",
        help="Trading mode: paper, live, or dry_run",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """
    Run the trading bot.
    
    Discovers same-day markets, evaluates strategies, and places trades
    based on configured risk parameters.
    """
    print_banner()
    
    # Parse mode
    try:
        trading_mode = TradingMode(mode.lower())
    except ValueError:
        console.print(f"[red]Invalid mode: {mode}[/red]")
        console.print("Valid modes: paper, live, dry_run")
        raise typer.Exit(1)
    
    # Setup logging
    log_level = "DEBUG" if verbose else settings.log_level
    setup_logging(level=log_level)
    
    # Safety confirmation for live mode
    if trading_mode == TradingMode.LIVE:
        console.print("\n[bold red]⚠️  LIVE TRADING MODE[/bold red]")
        console.print("This will execute real trades with real money.\n")
        
        if not settings.kalshi_api_key:
            console.print("[red]ERROR: KALSHI_API_KEY not set for live trading[/red]")
            raise typer.Exit(1)
        
        confirm = typer.confirm("Are you sure you want to proceed?")
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit(0)
    
    print_config_summary()
    
    console.print(f"\n[bold]Starting trading run in {trading_mode.value} mode...[/bold]\n")
    
    # Run the bot
    runner = TradingRunner(mode=trading_mode)
    summary = asyncio.run(runner.run())
    
    # Print summary
    console.print("\n")
    console.print(Panel(
        f"Orders Placed: {summary['orders_placed']}\n"
        f"Orders Filled: {summary['orders_filled']}\n"
        f"Duration: {summary.get('duration_seconds', 0):.1f}s",
        title="Run Complete",
        border_style="green" if not summary.get("errors") else "red",
    ))
    
    if summary.get("errors"):
        for error in summary["errors"]:
            console.print(f"[red]Error: {error}[/red]")


@app.command()
def snapshot(
    tickers: str = typer.Option(
        ...,
        "--tickers", "-t",
        help="Comma-separated list of market tickers to snapshot",
    ),
) -> None:
    """
    Take snapshots of specified markets.
    
    Use this to build historical data for backtesting before
    running the full trading system.
    """
    setup_logging()
    
    ticker_list = [t.strip() for t in tickers.split(",")]
    
    console.print(f"Taking snapshots for: {ticker_list}")
    
    runner = TradingRunner(mode=TradingMode.PAPER)
    asyncio.run(runner.run_snapshot_only(ticker_list))
    
    console.print("[green]Snapshots saved.[/green]")


@app.command()
def report(
    date: Optional[str] = typer.Option(
        None,
        "--date", "-d",
        help="Date for report (YYYY-MM-DD), defaults to today",
    ),
) -> None:
    """
    Generate performance report for a specific date.
    """
    from kalshi_bot.db.repository import Repository
    from kalshi_bot.observability.metrics import generate_daily_report
    
    setup_logging()
    
    # Parse date
    if date:
        report_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        report_date = datetime.now()
    
    async def fetch_and_print():
        repo = Repository()
        await repo.initialize()
        
        daily_pnl = await repo.get_daily_pnl(report_date)
        
        if daily_pnl is None:
            console.print(f"[yellow]No data for {report_date.date()}[/yellow]")
            return
        
        orders = await repo.get_orders_by_date(report_date)
        
        summary = {
            "mode": "historical",
            "orders_placed": len(orders),
            "orders_filled": sum(1 for o in orders if o.status.value == "filled"),
        }
        
        report_text = generate_daily_report(summary, daily_pnl)
        console.print(report_text)
    
    asyncio.run(fetch_and_print())


@app.command()
def config() -> None:
    """
    Display current configuration.
    """
    print_config_summary()
    
    console.print("\n[dim]Configuration is loaded from environment variables.[/dim]")
    console.print("[dim]Create a .env file or export variables to customize.[/dim]")


@app.command()
def validate() -> None:
    """
    Validate configuration and API connectivity.
    """
    setup_logging()
    
    console.print("[bold]Validating configuration...[/bold]\n")
    
    errors = []
    warnings = []
    
    # Check required settings
    if settings.mode == TradingMode.LIVE and not settings.kalshi_api_key:
        errors.append("KALSHI_API_KEY required for live trading")
    
    if settings.max_daily_loss_dollars <= 0:
        errors.append("max_daily_loss_dollars must be positive")
    
    if settings.min_win_rate < 0.5:
        warnings.append(f"min_win_rate ({settings.min_win_rate}) is below 50%")
    
    # Test API connectivity
    console.print("Testing API connectivity...")
    
    async def test_api():
        from kalshi_bot.client.kalshi import KalshiClient
        
        if not settings.kalshi_api_key:
            warnings.append("Cannot test API without KALSHI_API_KEY")
            return
        
        try:
            client = KalshiClient()
            markets, _ = await client.get_markets(limit=1)
            await client.close()
            console.print("[green]✓ API connection successful[/green]")
        except Exception as e:
            errors.append(f"API connection failed: {e}")
    
    asyncio.run(test_api())
    
    # Print results
    if warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in warnings:
            console.print(f"  ⚠️  {w}")
    
    if errors:
        console.print("\n[red]Errors:[/red]")
        for e in errors:
            console.print(f"  ❌ {e}")
        raise typer.Exit(1)
    
    console.print("\n[green]✓ Configuration valid[/green]")


if __name__ == "__main__":
    app()
