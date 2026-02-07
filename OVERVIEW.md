# System Overview: Kalshi vs Sportsbook Odds Scanner

**Complete rebuild** from arbitrage scanner to alert-only price comparison system.

---

## What Changed

### Old System (arb_scanner)
- Cross-venue arbitrage: Kalshi ↔ Polymarket
- Optional trade execution on both sides
- Focus: guaranteed profit via simultaneous fills

### New System (kalshi_odds)
- Price comparison: Kalshi ↔ Sportsbooks
- **Alert-only** (no sportsbook execution)
- Focus: detecting mispricings for manual review

---

## Project Stats

- **17 Python files** (~2,650 lines)
- **20 unit tests** (all passing)
- **5 CLI commands**
- **4 data models** (Kalshi, Odds, Probability, Alert)
- **2 adapters** (Kalshi RSA auth, The Odds API)

---

## File Structure

```
src/kalshi_odds/
├── __init__.py              # Package root
├── __main__.py              # Entry point
├── config.py                # Pydantic-settings config
├── cli.py                   # Typer CLI (5 commands)
├── db.py                    # SQLite persistence
├── models/                  # Data models (4 files)
│   ├── kalshi.py            # KalshiContract, KalshiTopOfBook
│   ├── odds.py              # OddsQuote, MarketType, OddsFormat
│   ├── probability.py       # NormalizedProb, VigMethod
│   └── comparison.py        # Comparison, Alert, Direction, Confidence
├── adapters/                # Data ingestion (2 files)
│   ├── kalshi.py            # Kalshi REST + RSA auth
│   └── odds_api.py          # The Odds API aggregator
└── core/                    # Business logic (3 files)
    ├── odds_math.py         # Odds conversion & vig removal
    ├── matcher.py           # Market mapping (YAML + fuzzy)
    └── scanner.py           # Comparison engine

tests/                       # Unit tests (2 files)
├── test_odds_math.py        # Odds conversion tests (15 tests)
└── test_scanner.py          # Edge detection tests (5 tests)

config.example.yaml          # Reference configuration
mappings.example.yaml        # Example market mappings
mappings.yaml                # Your mappings (empty by default)
QUICKSTART.md                # 5-minute setup guide
README.md                    # Full documentation
```

---

## Key Features

### 1. Odds Math (Rigorous)
- American ↔ Decimal ↔ Probability conversion
- Proportional vig removal for two-way markets
- Overround calculation
- Multi-way market support (with documented limitations)

### 2. Edge Detection
Computes edges in **both directions**:
- **Kalshi cheap**: Kalshi YES < sportsbook no-vig prob
- **Kalshi rich**: Kalshi YES > sportsbook no-vig prob

Conservative buffers:
- Kalshi slippage: 0.5% (configurable)
- Sportsbook friction: 1% (configurable)

### 3. Confidence Scoring
4-factor scoring system (0-1):
- Edge size (0-0.4)
- Data freshness (0-0.3)
- Liquidity (0-0.2)
- Overround quality (0-0.1)

Levels: **LOW** / **MED** / **HIGH**

### 4. Market Mapping
- **Manual YAML** for precise pairing
- **Fuzzy matching** for candidate suggestions (review-only)
- Format:
  ```yaml
  markets:
    - market_key: "unique_id"
      kalshi:
        contract_id: "TICKER-YES"
        side: "YES"
      odds:
        event_id: "evt_123"
        market_type: "h2h"
        selection: "Team Name"
  ```

### 5. Data Sources
- **Kalshi**: Direct API with RSA authentication
- **The Odds API**: Aggregator covering DraftKings, FanDuel, BetMGM, etc.

### 6. Persistence
SQLite database stores:
- Kalshi contracts
- Odds quotes
- Alerts history

Plus JSONL log for time-series analysis.

---

## CLI Commands

```bash
# Data sync
kalshi-odds sync-kalshi               # Fetch Kalshi contracts
kalshi-odds sync-odds --sport nfl     # Fetch sportsbook odds

# Matching
kalshi-odds match-candidates --fuzzy  # Show fuzzy match suggestions

# Scanner
kalshi-odds run --sport nfl           # Start alert loop (default 60s interval)

# Review
kalshi-odds show --last 50            # Show recent alerts
```

---

## Configuration

All via environment variables (`KALSHI_ODDS_` prefix):

```bash
# Required
KALSHI_ODDS_KALSHI_API_KEY_ID=...
KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH=/path/to/key.pem
KALSHI_ODDS_ODDS_API_KEY=...

# Optional (with defaults)
KALSHI_ODDS_MIN_EDGE_BPS=50.0         # Min 50 bps (0.5%) edge to alert
KALSHI_ODDS_MIN_LIQUIDITY=10          # Min 10 shares liquidity
KALSHI_ODDS_KALSHI_SLIPPAGE_BUFFER=0.005  # 0.5% buffer
```

---

## Testing

```bash
pytest                      # Run all 20 tests
pytest --cov=kalshi_odds    # With coverage
```

**All 20 tests pass.**

---

## Safety Features

1. **Alert-only by design**: No sportsbook execution code
2. **Conservative buffers**: Accounts for slippage and friction
3. **Staleness filtering**: Rejects data >60s old
4. **Liquidity filtering**: Requires minimum size
5. **Confidence scoring**: Flags data quality issues

---

## What It Does NOT Do

- ❌ Place bets on sportsbooks
- ❌ Automate any browser/mobile app interactions
- ❌ Guarantee profits
- ❌ Handle multi-leg execution
- ❌ Manage sportsbook account balances

---

## What It DOES Do

- ✅ Detect price discrepancies
- ✅ Remove vig from sportsbook odds
- ✅ Account for Kalshi fees and slippage
- ✅ Score confidence levels
- ✅ Log all alerts with full context
- ✅ Provide structured data for analysis

---

## Example Alert

```json
{
  "alert_id": "a1b2c3d4",
  "timestamp": "2026-02-07T12:34:56",
  "market_key": "superbowl_chiefs_win",
  "direction": "kalshi_cheap",
  "edge_pct": 2.5,
  "edge_bps": 250,
  "confidence": "high",
  "confidence_score": 0.82,
  "kalshi_contract_id": "SUPERBOWL-KC-YES",
  "kalshi_side": "YES",
  "kalshi_price": 0.450,
  "kalshi_liquidity": 150,
  "sportsbook_bookmaker": "draftkings",
  "sportsbook_selection": "Kansas City Chiefs",
  "sportsbook_p_no_vig": 0.500,
  "kalshi_data_age_seconds": 5.2,
  "sportsbook_data_age_seconds": 3.8
}
```

**Interpretation:**
- Kalshi YES at 45¢ (+ 0.5% slippage = 45.5¢)
- DraftKings implies 50% no-vig probability
- Edge: ~4.5% (250 bps after friction)
- High confidence (fresh data, good liquidity, low vig)
- **Action**: Consider buying YES on Kalshi at 45¢

---

## Next Steps

1. ✅ Install and configure (Steps 1-3)
2. ✅ Sync data (Step 4)
3. ✅ Create mappings (Step 5)
4. ✅ Run scanner (Step 6)
5. 📊 Analyze alerts and build strategy
6. 🔄 Add more sports/markets as needed

See `QUICKSTART.md` for detailed walkthrough.
See `README.md` for full documentation.

---

## Support

Questions? Check:
- `README.md` — Full docs
- `QUICKSTART.md` — Setup guide
- Test files — Usage examples
