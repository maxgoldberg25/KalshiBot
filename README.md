# 🤖 Kalshi Trading Bot

A production-grade automated trading system for Kalshi prediction markets.

## ⚠️ IMPORTANT DISCLAIMERS

**This bot trades real money in live mode. No profitability is guaranteed.**

- **Always start with paper trading** to validate your setup
- The 70% win rate target is a **configurable threshold**, not a guarantee
- Backtest results do not guarantee future performance
- You are responsible for all trading decisions and losses
- Review all risk parameters before enabling live trading

## Features

- **Same-Day Market Focus**: Only trades markets expiring today
- **Multiple Strategies**: Mispricing detection + Mean reversion
- **Rigorous Backtesting**: Walk-forward validation with configurable thresholds
- **Risk Management**: Position sizing, daily loss limits, exposure caps
- **Paper Trading**: Full simulation before going live
- **Idempotency**: Safe to re-run without duplicate orders
- **Observability**: Structured logging, metrics, Slack alerts
- **Database Persistence**: SQLite storage for orders, fills, snapshots

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/kalshi-bot.git
cd kalshi-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configuration

Create a `.env` file:

```bash
# Required for live trading
KALSHI_BOT_KALSHI_API_KEY=your_api_key_here

# Trading mode (paper, live, dry_run)
KALSHI_BOT_MODE=paper

# Risk limits (adjust carefully!)
KALSHI_BOT_MAX_DAILY_LOSS_DOLLARS=50
KALSHI_BOT_MAX_PER_MARKET_EXPOSURE_DOLLARS=20
KALSHI_BOT_MAX_TRADES_PER_DAY=20

# Strategy thresholds
KALSHI_BOT_MIN_WIN_RATE=0.70
KALSHI_BOT_MIN_EXPECTED_VALUE=0.02
KALSHI_BOT_MIN_BACKTEST_SAMPLES=30

# Optional: Slack alerts
KALSHI_BOT_SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### 3. Validate Setup

```bash
# Check configuration
python -m kalshi_bot config

# Validate API connectivity
python -m kalshi_bot validate
```

### 4. Paper Trading (RECOMMENDED FIRST)

```bash
# Run in paper mode
python -m kalshi_bot run --mode paper

# Or dry-run to see what would trade
python -m kalshi_bot run --mode dry_run
```

### 5. Live Trading

**Only after validating with paper trading:**

```bash
python -m kalshi_bot run --mode live
```

## Architecture

```
kalshi-bot/
├── src/kalshi_bot/
│   ├── client/          # Kalshi API client
│   ├── strategies/      # Trading strategies
│   ├── core/            # Discovery, risk, orders, backtest
│   ├── db/              # Database persistence
│   ├── scheduler/       # Main runner
│   ├── observability/   # Logging, metrics, alerts
│   ├── config.py        # Settings management
│   └── cli.py           # Command-line interface
└── tests/               # Test suite
```

## Trading Strategies

### Strategy 1: Mispricing Detection

Identifies markets where orderbook depth imbalance suggests mispricing:
- Heavy bid-side depth → price may be undervalued → buy YES
- Heavy ask-side depth → price may be overvalued → buy NO

### Strategy 2: Mean Reversion

Trades when price deviates from short-term moving average:
- Price above MA → expect reversion down → buy NO
- Price below MA → expect reversion up → buy YES

## Risk Management

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_daily_loss_dollars` | $50 | Stop trading if daily loss exceeds |
| `max_per_market_exposure` | $20 | Maximum per-market position |
| `max_total_exposure` | $100 | Maximum total capital at risk |
| `max_trades_per_day` | 20 | Maximum orders per day |
| `min_win_rate` | 70% | Minimum backtested win rate |
| `min_expected_value` | 2% | Minimum expected edge |
| `kelly_fraction` | 0.25 | Position sizing (quarter Kelly) |

## Market Filters

Markets must meet these criteria:
- Expires today (same-day)
- Minimum 24h volume: 100 contracts
- Maximum spread: 10 cents
- Minimum orderbook depth: 50 contracts
- Not in blacklisted categories
- At least 30 minutes before close

## Scheduling

### Cron (Linux/macOS)

```bash
# Run at 8:30 AM ET Monday-Friday
30 8 * * 1-5 cd /path/to/kalshi-bot && ./venv/bin/python -m kalshi_bot run --mode paper
```

### GitHub Actions

See `.github/workflows/daily_run.yml` for automated daily runs.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=kalshi_bot

# Run specific test file
pytest tests/test_risk.py -v
```

### Type Checking

```bash
mypy src/kalshi_bot
```

### Linting

```bash
ruff check src/
ruff format src/
```

## API Reference

### CLI Commands

```bash
# Run trading bot
python -m kalshi_bot run --mode [paper|live|dry_run] [--verbose]

# Take snapshots (for building backtest data)
python -m kalshi_bot snapshot --tickers TICKER1,TICKER2

# Generate report
python -m kalshi_bot report --date 2024-01-15

# Show configuration
python -m kalshi_bot config

# Validate setup
python -m kalshi_bot validate
```

### Environment Variables

All settings can be configured via environment variables with `KALSHI_BOT_` prefix:

| Variable | Type | Default |
|----------|------|---------|
| `KALSHI_BOT_KALSHI_API_KEY` | string | "" |
| `KALSHI_BOT_MODE` | paper/live/dry_run | paper |
| `KALSHI_BOT_TIMEZONE` | string | America/New_York |
| `KALSHI_BOT_MAX_DAILY_LOSS_DOLLARS` | float | 50.0 |
| `KALSHI_BOT_MIN_WIN_RATE` | float | 0.70 |
| `KALSHI_BOT_DATABASE_URL` | string | sqlite:///kalshi_bot.db |

See `src/kalshi_bot/config.py` for complete list.

## Troubleshooting

### "No tradeable markets found"

- Check if any markets expire today
- Verify your timezone configuration
- Ensure API key has read permissions

### "Rate limit hit"

- The client automatically retries with backoff
- Consider reducing request frequency

### "Insufficient backtest data"

- Run `snapshot` command first to collect historical data
- Or wait until bot collects enough snapshots

## License

MIT License - See LICENSE file.

## Disclaimer

This software is provided "as is" without warranty. Trading prediction markets involves risk of loss. The authors are not responsible for any financial losses incurred through use of this software. Always trade responsibly and only with money you can afford to lose.
