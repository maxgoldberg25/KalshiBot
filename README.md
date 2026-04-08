# KalshiBot — Kalshi vs Sportsbook Odds Scanner

Automated edge detection between Kalshi prediction markets and traditional sportsbooks. Finds price discrepancies, ranks them by edge, and surfaces them in a real-time web dashboard. Optional Kalshi-side execution with manual sportsbook hedging.

> **Disclaimer:** This tool detects *theoretical* price discrepancies. Sportsbook execution is manual. No guarantees of profit. Use for research and informational purposes only.

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install
pip install -e ".[dev]"

# 3. Configure credentials
cp .env.example .env
# Edit .env — add Kalshi API keys and at least one odds API key

# 4. Launch the dashboard
kalshi-odds dashboard
# Open http://127.0.0.1:8080
```

The dashboard auto-maps Kalshi game contracts to sportsbook events on startup and begins scanning immediately.

---

## Architecture

```
src/kalshi_odds/
├── adapters/                  # External API integrations
│   ├── kalshi.py              # Kalshi REST API (RSA-PSS auth)
│   ├── odds_api.py            # The Odds API (primary, 500 req/month free)
│   ├── oddspapi.py            # OddsPapi (fallback, 250 req/month free)
│   ├── espn.py                # ESPN unofficial API (free, no key needed)
│   └── odds_provider.py       # FallbackOddsProvider — auto-routes across tiers
├── core/                      # Business logic
│   ├── automapper.py          # Auto-match Kalshi contracts to sportsbook events
│   ├── matcher.py             # Load & query mappings.yaml
│   ├── odds_math.py           # Odds conversion & vig removal
│   ├── scan_runner.py         # Scan cycle: fetch → match → compare
│   ├── scanner.py             # Edge detection, confidence scoring, alert generation
│   ├── sizing.py              # Kelly Criterion position sizing
│   └── portfolio.py           # Portfolio-level risk management
├── models/                    # Pydantic data models
│   ├── kalshi.py              # KalshiContract, KalshiTopOfBook
│   ├── odds.py                # OddsQuote, MarketType, OddsFormat
│   ├── probability.py         # NormalizedProb, VigMethod
│   └── comparison.py         # Alert, Opportunity, Direction, Confidence
├── dashboard/
│   ├── server.py              # FastAPI app — REST API + SPA serving
│   └── templates/index.html   # Single-page app (Tabler + ApexCharts)
├── config.py                  # Pydantic-settings (env-based config)
├── db.py                      # SQLite persistence via aiosqlite
├── execution.py               # Kalshi order placement
└── cli.py                     # Typer CLI
```

---

## Odds Provider Tiers

The system cascades automatically across three tiers — no manual intervention required:

| Tier | Provider | Cost | Notes |
|------|----------|------|-------|
| 1 | **The Odds API** | 500 req/month free | Primary. `list_events` (free endpoint) always tried first even when credits are exhausted |
| 2 | **OddsPapi** | 250 req/month free | Fallback when Odds API `get_odds` credits run out |
| 3 | **ESPN (unofficial)** | Free, no key | Final fallback. Real DraftKings moneyline odds. No rate limits |

`FallbackOddsProvider` handles routing transparently. `list_events` (used for auto-mapping) is always served from The Odds API since it's a free endpoint. `get_odds` (used for scanning) escalates through the tiers until one succeeds.

---

## Setup

### 1. Credentials

```bash
cp .env.example .env
```

**Required:**

```dotenv
KALSHI_ODDS_KALSHI_API_KEY_ID=your-kalshi-key-id
KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH=/path/to/kalshi_private.pem
```

**Odds API (at least one):**

```dotenv
# Tier 1 — https://the-odds-api.com/  (500 req/month free)
KALSHI_ODDS_ODDS_API_KEY=your-odds-api-key

# Tier 2 — https://oddspapi.io/  (250 req/month free, optional)
KALSHI_ODDS_ODDSPAPI_API_KEY=your-oddspapi-key
```

ESPN (Tier 3) requires no configuration — it is always available as a final fallback.

### 2. Generate Kalshi RSA Key

In your Kalshi account settings, generate an RSA key pair. Download the private key (`.pem`) and note the Key ID. Set both in `.env`.

### 3. Keep secrets out of git

`.env` and `*.pem` are already in `.gitignore`. Never commit them.

---

## Usage

### Dashboard (recommended)

```bash
kalshi-odds dashboard
```

Opens `http://127.0.0.1:8080`. The dashboard:
- Auto-maps Kalshi game contracts to sportsbook events on startup
- Runs continuous scans on `poll_interval_seconds` cadence (default: 60s)
- Displays ranked opportunities with edge bars, confidence badges, and Kelly sizing
- Supports inline dry-run and live execution (requires `KALSHI_ODDS_EXECUTION_ENABLED=true`)

### CLI

```bash
# One-shot scan — display ranked opportunities and exit
kalshi-odds scan --sport basketball_nba

# Continuous scanner loop (alerts only, no dashboard)
kalshi-odds run --sport basketball_nba,baseball_mlb

# Show recent alerts from the database
kalshi-odds show --last 50

# Manual execution of Kalshi leg
kalshi-odds execute --index 1 --shares 100 --dry-run

# Detailed breakdown for one opportunity
kalshi-odds detail --index 1

# Re-build mappings.yaml from Kalshi + Odds API
kalshi-odds sync-kalshi
kalshi-odds sync-odds --sport basketball_nba

# Show fuzzy-match candidates for manual review
kalshi-odds match-candidates --fuzzy
```

Multiple sports: pass a comma-separated list to `--sport`:

```bash
kalshi-odds scan --sport basketball_nba,baseball_mlb
```

Or set a default in `.env`:

```dotenv
KALSHI_ODDS_DEFAULT_SPORT=basketball_nba,baseball_mlb
```

---

## Auto-Mapping

The auto-mapper (`core/automapper.py`) connects Kalshi game contracts to sportsbook events automatically:

1. Fetches active Kalshi markets for a sport series (e.g., `KXNBAGAME`)
2. Fetches upcoming events from the odds provider
3. Parses team codes from Kalshi tickers (e.g., `KXNBAGAME-26APR10CLEATL-CLE` → teams `CLE`, `ATL`)
4. Matches by team name keywords (configurable in `automapper.py`)
5. Writes or merges into `mappings.yaml`

The dashboard re-maps automatically every 360 scans (~6 hours at default interval) and on startup. You can also trigger it manually from the dashboard UI or CLI.

### mappings.yaml format

```yaml
markets:
  - market_key: nba_20260410_cleatl_cle
    kalshi:
      contract_id: KXNBAGAME-26APR10CLEATL-CLE
      side: YES
    odds:
      event_id: 3fe42fd427985fed1fee7c2e58935a67
      market_type: h2h
      selection: Cleveland Cavaliers
```

---

## Edge Detection

Edge is computed in both directions for each (Kalshi contract, sportsbook quote) pair:

### Kalshi Cheap (buy YES on Kalshi, hedge on sportsbook)

```
edge = sportsbook_p_no_vig × (1 − friction) − (kalshi_yes_ask + slippage)
```

If positive, Kalshi is pricing the contract below the sportsbook's fair probability.

### Kalshi Rich (sell YES on Kalshi, bet on sportsbook)

```
edge = (kalshi_yes_bid − slippage) − sportsbook_p_no_vig × (1 − friction)
```

If positive, Kalshi is pricing the contract above the sportsbook's fair probability.

### Default buffers

| Parameter | Default | Description |
|-----------|---------|-------------|
| `kalshi_slippage_buffer` | 0.5% | Applied to Kalshi bid/ask prices |
| `sportsbook_execution_friction` | 1.0% | Accounts for sportsbook execution difficulty |
| `min_edge_bps` | 50 bps | Minimum edge to surface an alert |
| `min_liquidity` | 10 shares | Minimum Kalshi orderbook size |

### Signal mode

When Kalshi has no active market makers (empty orderbook), the scanner enters **signal mode**: it synthesizes a Kalshi price at ~90% of the sportsbook's no-vig probability — a common discount in thin markets to attract initial buyers. These opportunities are marked `~EST` in the dashboard with a full explanation. They are watchlist items only; do not execute them.

---

## Confidence Scoring

Each alert is scored 0–1:

| Factor | Weight | Condition |
|--------|--------|-----------|
| Edge size | 0–0.4 | ≥200 bps → 0.4, ≥100 → 0.3, ≥50 → 0.2 |
| Data freshness | 0–0.3 | <10s → 0.3, <30s → 0.2, <60s → 0.1 |
| Kalshi liquidity | 0–0.2 | ≥100 shares → 0.2, ≥50 → 0.15, ≥20 → 0.1 |
| Overround | 0–0.1 | <1.03 → 0.1, <1.05 → 0.05 |

**Levels:** HIGH ≥ 0.75 · MED ≥ 0.50 · LOW < 0.50

---

## Position Sizing

Uses **fractional Kelly Criterion** (default: quarter-Kelly):

```
kelly_shares = (edge_bps / 10000) / kalshi_price × bankroll × kelly_fraction
```

Capped by `max_notional_per_trade` and available Kalshi liquidity. Configure via `.env`:

```dotenv
KALSHI_ODDS_BANKROLL_DOLLARS=500.0
KALSHI_ODDS_KELLY_FRACTION=0.25
KALSHI_ODDS_MAX_NOTIONAL_PER_TRADE=100.0
```

---

## Dashboard API

The dashboard exposes a REST API alongside the web UI:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard (SPA) |
| `/api/state` | GET | Full scanner state: opportunities, positions, P&L, settings |
| `/api/health` | GET | System health: Kalshi, odds providers, database, scanner |
| `/api/config` | GET | Current configuration values |
| `/api/scan` | POST | Trigger a manual scan |
| `/api/auto-map` | POST | Re-build market mappings |
| `/api/execute` | POST | Place Kalshi order (requires `EXECUTION_ENABLED=true`) |
| `/api/alerts/recent` | GET | Last 20 alerts from database |

---

## Configuration Reference

All settings use the `KALSHI_ODDS_` prefix in `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `KALSHI_API_KEY_ID` | — | Kalshi API Key ID |
| `KALSHI_PRIVATE_KEY_PATH` | — | Path to Kalshi RSA private key (.pem) |
| `ODDS_API_KEY` | — | The Odds API key |
| `ODDSPAPI_API_KEY` | — | OddsPapi key (optional fallback) |
| `DEFAULT_SPORT` | `basketball_nba` | Comma-separated sport keys to scan |
| `MIN_EDGE_BPS` | `50.0` | Minimum edge in basis points to surface |
| `MIN_LIQUIDITY` | `10` | Minimum Kalshi orderbook size (shares) |
| `POLL_INTERVAL_SECONDS` | `60.0` | Seconds between automatic scan cycles |
| `MAX_STALENESS_SECONDS` | `60.0` | Max data age before a quote is discarded |
| `KALSHI_SLIPPAGE_BUFFER` | `0.005` | Slippage buffer applied to Kalshi prices |
| `SPORTSBOOK_EXECUTION_FRICTION` | `0.01` | Friction buffer for sportsbook execution |
| `BANKROLL_DOLLARS` | `500.0` | Total bankroll for Kelly sizing |
| `KELLY_FRACTION` | `0.25` | Fraction of full Kelly to size |
| `MAX_NOTIONAL_PER_TRADE` | `100.0` | Dollar cap per single Kalshi order |
| `EXECUTION_ENABLED` | `false` | Must be `true` to place real Kalshi orders |
| `AUTO_EXECUTE_MIN_CONFIDENCE` | `high` | Minimum confidence for auto-execute in `run` loop |
| `MAPPING_FILE` | `mappings.yaml` | Path to market mapping file |
| `FUZZY_MATCH_ENABLED` | `false` | Enable fuzzy string matching for team names |
| `DASHBOARD_PORT` | `8080` | Port for the web dashboard |
| `DATABASE_URL` | `sqlite+aiosqlite:///kalshi_odds.db` | Database connection URL |
| `OUTPUT_JSONL` | `alerts.jsonl` | Path for alert output log |

---

## Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=kalshi_odds --cov-report=term-missing

# Specific module
pytest tests/test_odds_math.py -v
pytest tests/test_scanner.py -v
```

Tests cover: odds conversion, vig removal, edge detection, confidence scoring, staleness/liquidity filtering, alert aggregation into opportunities.

---

## Output Files

| File | Description |
|------|-------------|
| `mappings.yaml` | Auto-generated market mapping (Kalshi ↔ sportsbook) |
| `alerts.jsonl` | Append-only log of all triggered alerts |
| `kalshi_odds.db` | SQLite database (alerts, positions, settled trades) |
| `.last_opportunities.json` | Last scan's opportunities, used for dashboard persistence across restarts |

---

## Risk & Limitations

- **No sportsbook automation.** The sportsbook leg must be placed manually.
- **Execution risk.** Prices can move between detection and execution on either side.
- **Partial fills.** Kalshi liquidity may be lower than displayed.
- **Kalshi fees.** Approximately 7% (taker + maker + settlement).
- **Settlement rules.** Kalshi and sportsbooks may settle the same event differently.
- **Estimated signals.** When Kalshi has no active market makers, the system shows synthetic opportunities based on sportsbook odds. These are for monitoring only.

---

## Supported Sports

| Sport key | League | Kalshi series |
|-----------|--------|---------------|
| `basketball_nba` | NBA | `KXNBAGAME` |
| `baseball_mlb` | MLB | `KXMLBGAME` |
| `americanfootball_nfl` | NFL | `KXNFLGAME` |
| `basketball_ncaab` | NCAAB | `KXNCAABGAME` |

Add new sports by extending `SPORT_TO_SERIES` in `core/automapper.py` and `SPORT_TO_ESPN_PATH` in `adapters/espn.py`.

---

## FAQ

**Q: The dashboard shows `~EST` badges on all opportunities — what does that mean?**
A: Kalshi has no active market makers for those contracts (empty orderbook). The system synthesizes a price at ~90% of the sportsbook's fair value to show what an opportunity *would* look like. Do not execute these — they are watchlist items. When Kalshi opens a live market, real opportunities will appear automatically.

**Q: I see "Odds API quota exhausted" — what do I do?**
A: Your Odds API monthly credits are used up. Options: (1) wait for the monthly reset, (2) get a new free key at [the-odds-api.com](https://the-odds-api.com/), (3) add an `ODDSPAPI_API_KEY`. The ESPN fallback still provides basic NBA/NFL odds for free.

**Q: Why are there 0 opportunities with no `~EST` badges?**
A: Check: (1) `mappings.yaml` exists and has entries, (2) the odds provider returned data (check the credits display), (3) `min_edge_bps` isn't too high, (4) Kalshi liquidity meets `min_liquidity`.

**Q: Can this place bets on sportsbooks automatically?**
A: No. Only the Kalshi leg can be placed via API. Sportsbook execution is manual.

**Q: How do I add a new sport?**
A: Add the sport key → Kalshi series mapping in `core/automapper.py` (`SPORT_TO_SERIES`) and the team code → name keywords in `TEAM_CODE_KEYWORDS`. Also add the ESPN path in `adapters/espn.py` (`SPORT_TO_ESPN_PATH`).

---

## License

For personal and educational use. Review each venue's API Terms of Service before deploying commercially.
