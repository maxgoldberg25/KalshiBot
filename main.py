#!/usr/bin/env python3
"""
KalshiBot - An intelligent bot for analyzing Kalshi prediction markets

Usage:
    python main.py analyze <ticker>     - Analyze a specific market
    python main.py search <query>       - Search for markets
    python main.py list [category]      - List active markets
"""
import sys
import argparse
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

from config import config
from kalshi_client import KalshiClient, Market
from news_fetcher import NewsFetcher
from analyzer import MarketAnalyzer, Signal


console = Console()


def extract_keywords(market: Market) -> list[str]:
    """Extract search keywords from market title and subtitle"""
    # Common stop words to remove
    stop_words = {
        "will", "the", "a", "an", "be", "to", "of", "in", "for", "on",
        "by", "at", "or", "and", "is", "it", "this", "that", "with",
        "as", "are", "was", "were", "been", "being", "have", "has",
        "had", "do", "does", "did", "but", "if", "than", "more", "most",
        "other", "some", "such", "no", "not", "only", "same", "so",
        "can", "just", "should", "now", "yes", "before", "after",
    }
    
    # Combine title and subtitle
    text = f"{market.title} {market.subtitle}".lower()
    
    # Remove punctuation and split
    import re
    words = re.findall(r'\b[a-z]+\b', text)
    
    # Filter and get unique keywords
    keywords = []
    seen = set()
    
    for word in words:
        if word not in stop_words and len(word) > 2 and word not in seen:
            seen.add(word)
            keywords.append(word)
    
    # Also add some bigrams (two-word phrases) that might be relevant
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if words[i] not in stop_words or words[i+1] not in stop_words:
            if bigram not in seen:
                seen.add(bigram)
                keywords.append(bigram)
    
    return keywords[:15]  # Limit to top 15 keywords


def categorize_market(market: Market) -> str:
    """Determine the category of a market for news fetching"""
    text = f"{market.title} {market.subtitle} {market.category}".lower()
    
    if any(word in text for word in ["president", "election", "senate", "congress", "vote", "biden", "trump", "democrat", "republican"]):
        return "politics"
    elif any(word in text for word in ["fed", "inflation", "gdp", "economy", "unemployment", "rate", "stock", "market"]):
        return "economics"
    elif any(word in text for word in ["tech", "ai", "software", "apple", "google", "microsoft", "startup"]):
        return "technology"
    elif any(word in text for word in ["game", "nfl", "nba", "mlb", "team", "championship", "sport"]):
        return "sports"
    elif any(word in text for word in ["weather", "temperature", "storm", "hurricane", "snow", "rain"]):
        return "weather"
    
    return "general"


def display_market_info(market: Market):
    """Display market information in a formatted panel"""
    info = f"""
**{market.title}**
{market.subtitle}

📊 **Current Prices:**
• YES: {market.yes_price:.0f}¢ (implied probability: {market.implied_probability:.1%})
• NO: {market.no_price:.0f}¢

📈 **Market Stats:**
• 24h Volume: {market.volume_24h:,} contracts
• Total Volume: {market.volume:,} contracts
• Open Interest: {market.open_interest:,} contracts
• Bid-Ask Spread: {market.spread:.1f}¢

⏰ **Closes:** {market.close_time.strftime('%Y-%m-%d %H:%M UTC') if market.close_time else 'Unknown'}
"""
    
    console.print(Panel(
        Markdown(info),
        title=f"[bold blue]{market.ticker}[/bold blue]",
        border_style="blue",
        box=box.ROUNDED,
    ))


def display_analysis_result(result):
    """Display the analysis result in a formatted way"""
    # Signal colors
    signal_colors = {
        Signal.STRONG_YES: "bold green",
        Signal.LEAN_YES: "green",
        Signal.NEUTRAL: "yellow",
        Signal.LEAN_NO: "red",
        Signal.STRONG_NO: "bold red",
    }
    
    # Create analysis summary
    signal_color = signal_colors.get(result.signal, "white")
    
    console.print("\n")
    console.print(Panel(
        f"[{signal_color}]{result.signal.value}[/{signal_color}]",
        title="📊 Signal",
        border_style=signal_color.replace("bold ", ""),
    ))
    
    console.print(Panel(
        f"[bold]{result.confidence.value}[/bold]",
        title="🎯 Confidence",
        border_style="cyan",
    ))
    
    # Reasoning table
    reasoning_table = Table(
        title="📝 Analysis Reasoning",
        box=box.SIMPLE,
        show_header=False,
    )
    reasoning_table.add_column("Point", style="cyan")
    
    for point in result.reasoning:
        reasoning_table.add_row(f"• {point}")
    
    console.print(reasoning_table)
    
    # Risk factors
    if result.risk_factors:
        risk_table = Table(
            title="⚠️ Risk Factors",
            box=box.SIMPLE,
            show_header=False,
        )
        risk_table.add_column("Risk", style="red")
        
        for risk in result.risk_factors:
            risk_table.add_row(f"• {risk}")
        
        console.print(risk_table)
    
    # Recommendation
    console.print(Panel(
        result.recommendation,
        title="💡 Recommendation",
        border_style="green",
        box=box.DOUBLE,
    ))


def analyze_market(ticker: str):
    """Analyze a specific market"""
    console.print(f"\n[bold]Analyzing market: {ticker}[/bold]\n")
    
    # Initialize clients
    kalshi = KalshiClient()
    news = NewsFetcher()
    analyzer = MarketAnalyzer()
    
    try:
        # Step 1: Fetch market data
        with console.status("[bold green]Fetching market data..."):
            market = kalshi.get_market(ticker)
            
        if not market:
            console.print(f"[red]Error: Market '{ticker}' not found[/red]")
            return
        
        display_market_info(market)
        
        # Step 2: Get price history
        with console.status("[bold green]Fetching price history..."):
            history = kalshi.get_market_history(ticker, days=7)
        
        if history:
            console.print(f"[dim]Retrieved {len(history)} historical data points[/dim]")
        else:
            console.print("[dim]No historical data available[/dim]")
        
        # Step 3: Extract keywords and fetch news
        keywords = extract_keywords(market)
        category = categorize_market(market)
        
        console.print(f"[dim]Search keywords: {', '.join(keywords[:7])}...[/dim]")
        console.print(f"[dim]Category: {category}[/dim]")
        
        with console.status("[bold green]Fetching relevant news..."):
            articles = news.fetch_news(
                keywords=keywords[:10],
                category=category,
                days=config.NEWS_LOOKBACK_DAYS,
                limit=20
            )
        
        if articles:
            console.print(f"[dim]Found {len(articles)} relevant articles[/dim]")
            
            # Show top headlines
            news_table = Table(
                title="📰 Top Headlines",
                box=box.SIMPLE,
            )
            news_table.add_column("Source", style="cyan", width=15)
            news_table.add_column("Headline", style="white")
            news_table.add_column("Date", style="dim", width=12)
            
            for article in articles[:5]:
                date_str = article.published_at.strftime("%m/%d") if article.published_at else "N/A"
                news_table.add_row(
                    article.source[:15],
                    article.title[:80] + ("..." if len(article.title) > 80 else ""),
                    date_str
                )
            
            console.print(news_table)
        else:
            console.print("[yellow]No relevant news articles found[/yellow]")
        
        # Step 4: Run analysis
        with console.status("[bold green]Running analysis..."):
            result = analyzer.analyze(market, articles, history)
        
        # Step 5: Display results
        display_analysis_result(result)
        
    except Exception as e:
        console.print(f"[red]Error during analysis: {e}[/red]")
        raise
    finally:
        kalshi.close()
        news.close()


def search_markets(query: str):
    """Search for markets by keyword"""
    console.print(f"\n[bold]Searching for markets matching: {query}[/bold]\n")
    
    kalshi = KalshiClient()
    
    try:
        with console.status("[bold green]Searching..."):
            markets = kalshi.search_markets(query, limit=15)
        
        if not markets:
            # Try listing all active markets and filtering
            all_markets = kalshi.list_active_markets(limit=100)
            markets = [
                m for m in all_markets 
                if query.lower() in m.title.lower() or query.lower() in m.subtitle.lower()
            ][:15]
        
        if not markets:
            console.print("[yellow]No markets found matching your query[/yellow]")
            return
        
        table = Table(
            title=f"Found {len(markets)} Markets",
            box=box.ROUNDED,
        )
        table.add_column("Ticker", style="cyan", width=20)
        table.add_column("Title", style="white", width=50)
        table.add_column("YES", style="green", justify="right")
        table.add_column("Volume", style="dim", justify="right")
        
        for market in markets:
            table.add_row(
                market.ticker,
                market.title[:50] + ("..." if len(market.title) > 50 else ""),
                f"{market.yes_price:.0f}¢",
                f"{market.volume_24h:,}",
            )
        
        console.print(table)
        console.print("\n[dim]Use 'python main.py analyze <TICKER>' to analyze a specific market[/dim]")
        
    finally:
        kalshi.close()


def list_markets(category: str = None):
    """List active markets"""
    console.print(f"\n[bold]Listing active markets{f' in {category}' if category else ''}[/bold]\n")
    
    kalshi = KalshiClient()
    
    try:
        with console.status("[bold green]Fetching markets..."):
            markets = kalshi.list_active_markets(category=category, limit=25)
        
        if not markets:
            console.print("[yellow]No active markets found[/yellow]")
            return
        
        table = Table(
            title=f"Active Markets ({len(markets)})",
            box=box.ROUNDED,
        )
        table.add_column("Ticker", style="cyan", width=25)
        table.add_column("Title", style="white", width=45)
        table.add_column("YES", style="green", justify="right")
        table.add_column("24h Vol", style="dim", justify="right")
        table.add_column("Closes", style="dim", width=12)
        
        for market in markets:
            close_str = market.close_time.strftime("%m/%d %H:%M") if market.close_time else "N/A"
            table.add_row(
                market.ticker,
                market.title[:45] + ("..." if len(market.title) > 45 else ""),
                f"{market.yes_price:.0f}¢",
                f"{market.volume_24h:,}",
                close_str,
            )
        
        console.print(table)
        console.print("\n[dim]Use 'python main.py analyze <TICKER>' to analyze a specific market[/dim]")
        
    finally:
        kalshi.close()


def interactive_mode():
    """Run in interactive mode"""
    console.print(Panel(
        "[bold]🤖 KalshiBot - Prediction Market Analyzer[/bold]\n\n"
        "Commands:\n"
        "  [cyan]analyze <ticker>[/cyan] - Analyze a specific market\n"
        "  [cyan]search <query>[/cyan]   - Search for markets\n"
        "  [cyan]list[/cyan]             - List active markets\n"
        "  [cyan]quit[/cyan]             - Exit the bot\n",
        border_style="blue",
    ))
    
    # Show configuration warnings
    warnings = config.validate()
    if warnings:
        for warning in warnings:
            console.print(f"[yellow]⚠️ {warning}[/yellow]")
        console.print()
    
    while True:
        try:
            command = console.input("[bold blue]kalshi>[/bold blue] ").strip()
            
            if not command:
                continue
            
            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd == "quit" or cmd == "exit":
                console.print("[dim]Goodbye![/dim]")
                break
            elif cmd == "analyze":
                if not args:
                    console.print("[red]Please provide a ticker: analyze <TICKER>[/red]")
                else:
                    analyze_market(args.upper())
            elif cmd == "search":
                if not args:
                    console.print("[red]Please provide a search query: search <query>[/red]")
                else:
                    search_markets(args)
            elif cmd == "list":
                list_markets(args if args else None)
            elif cmd == "help":
                console.print(
                    "Commands:\n"
                    "  analyze <ticker> - Analyze a market\n"
                    "  search <query>   - Search markets\n"
                    "  list [category]  - List markets\n"
                    "  quit             - Exit"
                )
            else:
                console.print(f"[red]Unknown command: {cmd}[/red]")
                console.print("[dim]Type 'help' for available commands[/dim]")
                
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="KalshiBot - Intelligent prediction market analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                        # Interactive mode
  python main.py analyze KXBTC-25JAN31  # Analyze specific market
  python main.py search "bitcoin"       # Search for markets
  python main.py list                   # List active markets
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        choices=["analyze", "search", "list"],
        help="Command to run"
    )
    parser.add_argument(
        "argument",
        nargs="?",
        help="Ticker for analyze, query for search, or category for list"
    )
    
    args = parser.parse_args()
    
    # Show header
    console.print("\n[bold blue]🤖 KalshiBot[/bold blue] - Prediction Market Analyzer\n")
    
    if args.command is None:
        interactive_mode()
    elif args.command == "analyze":
        if not args.argument:
            console.print("[red]Error: Please provide a market ticker[/red]")
            console.print("Usage: python main.py analyze <TICKER>")
            sys.exit(1)
        analyze_market(args.argument.upper())
    elif args.command == "search":
        if not args.argument:
            console.print("[red]Error: Please provide a search query[/red]")
            console.print("Usage: python main.py search <query>")
            sys.exit(1)
        search_markets(args.argument)
    elif args.command == "list":
        list_markets(args.argument)


if __name__ == "__main__":
    main()
