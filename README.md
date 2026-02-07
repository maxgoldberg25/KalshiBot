# Kalshi vs Sportsbook Odds Scanner

**Alert-only** price comparison system for detecting discrepancies between Kalshi prediction markets and traditional sportsbooks. No sportsbook execution — alerts only.

> **Disclaimer:** This tool detects *theoretical* price discrepancies. Sportsbook execution is manual. No guarantees of profit. Use for research and informational purposes only.

---

## Architecture

```
src/kalshi_odds/
├── models/              # Normalized data models
│   ├── kalshi.py        # KalshiContract, KalshiTopOfBook
│   ├── odds.py          # OddsQuote, MarketType, OddsFormat
│   ├── probability.py   # NormalizedProb, VigMethod
│   └── comparison.py    # Comparison, Alert, Confidence
├── adapters/            # Data ingestion
│   ├── kalshi.py        # Kalshi REST API (RSA auth)
│   └── odds_api.py      # The Odds API aggregator
├── core/                # Business logic
│   ├── odds_math.py     # Odds conversion & vig removal
│   ├── matcher.py       # Market mapping (manual YAML + fuzzy)
│   └── scanner.py       # Comparison logic & alert generation
├── config.py            # Pydantic-settings configuration
├── db.py                # SQLite persistence
└── cli.py               # Typer CLI
```

---

## Setup

### 1. Install

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required:**
- `KALSHI_ODDS_KALSHI_API_KEY_ID` — Kalshi API Key ID
- `KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH` — Path to Kalshi RSA private key (.pem)
- `KALSHI_ODDS_ODDS_API_KEY` — The Odds API key ([get free key](https://the-odds-api.com/))

### 3. Create market mappings

```bash
cp mappings.example.yaml mappings.yaml
# Edit mappings.yaml to pair Kalshi contracts with sportsbook events
```

### 4. Keep keys out of git (optional but recommended)

Never commit `.env`, `kalshi.key`, or any file with API keys. They are listed in `.gitignore`. To block accidental commits, install the pre-commit hook:

```bash
cp scripts/pre-commit.no-keys .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

---

## Usage

### CLI Commands

```bash
# Fetch Kalshi contracts and save to database
kalshi-odds sync-kalshi

# Fetch sportsbook odds (default: NFL)
kalshi-odds sync-odds --sport americanfootball_nfl

# Show fuzzy match candidates for manual review
kalshi-odds match-candidates --fuzzy

# Start continuous scanner (alerts only)
kalshi-odds run --sport americanfootball_nfl

# Show recent alerts
kalshi-odds show --last 50
```

---

## Market Mapping

The scanner requires a manual mapping file (`mappings.yaml`) that pairs Kalshi contracts with sportsbook selections.

### Example mapping:

```yaml
markets:
  - market_key: "superbowl_2026_chiefs"
    kalshi:
      contract_id: "SUPERBOWL-KC-YES"
      side: "YES"
    odds:
      event_id: "abc123def456"    # From The Odds API
      market_type: "h2h"           # Head-to-head (moneyline)
      selection: "Kansas City Chiefs"
```

### How to find IDs:

**Kalshi:**
1. Run `kalshi-odds sync-kalshi`
2. Contract ID is the ticker (e.g., "SUPERBOWL-KC-YES")

**The Odds API:**
1. Run `kalshi-odds sync-odds --sport americanfootball_nfl`
2. `event_id` is returned by the API
3. `selection` is the team/player name

### Fuzzy matching:

```bash
kalshi-odds match-candidates --fuzzy
```

This shows potential matches based on title similarity. **Review manually** and add confirmed matches to `mappings.yaml`.

---

## Odds Math

### American Odds → Probability

```python
# Favorite (-110): prob = 110 / (110 + 100) = 52.38%
# Underdog (+150): prob = 100 / (150 + 100) = 40%
```

### Decimal Odds → Probability

```python
# 2.00: prob = 1 / 2.00 = 50%
# 1.50: prob = 1 / 1.50 = 66.67%
```

### Vig Removal (Two-Way Markets)

```python
# Both -110 (52.38% each) → overround = 1.0476 (4.76% vig)
# No-vig: 52.38% / 1.0476 = 50% each
```

Uses **proportional normalization** method. For multi-way markets, see limitations in code comments.

---

## Edge Detection

The scanner computes edges in **both directions**:

### Direction 1: Kalshi Cheap

```
Edge = sportsbook_p_no_vig × (1 - execution_friction) - kalshi_yes_ask - slippage_buffer
```

**If positive**, Kalshi YES is cheap relative to the sportsbook.

### Direction 2: Kalshi Rich

```
Edge = kalshi_yes_bid - slippage_buffer - sportsbook_p_no_vig × (1 - execution_friction)
```

**If positive**, Kalshi YES is expensive relative to the sportsbook.

### Buffers

- `kalshi_slippage_buffer`: Default 0.5% (0.005) — accounts for price movement on Kalshi
- `sportsbook_execution_friction`: Default 1% (0.01) — conservative buffer for sportsbook execution difficulty

---

## Confidence Scoring

Each alert receives a confidence score (0-1) based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| **Edge size** | 0-0.4 | Larger edge = higher confidence |
| **Data freshness** | 0-0.3 | Fresher data = higher confidence |
| **Liquidity** | 0-0.2 | Higher Kalshi liquidity = higher confidence |
| **Overround** | 0-0.1 | Lower vig = more reliable odds |

**Confidence levels:**
- **HIGH**: score ≥ 0.75
- **MED**: score ≥ 0.50
- **LOW**: score < 0.50

---

## Risk & Limitations

### ⚠️ This is an alert-only system

- No automated sportsbook execution
- Manual execution required
- Fills can be partial
- Prices can move between alert and execution

### Execution considerations

- **Kalshi**: Can trade via API, but incurs ~7% fees
- **Sportsbook**: Manual execution via website/app
  - Account limits may apply
  - Execution not guaranteed
  - Odds may change before you place bet

### "Guaranteed" profit caveats

1. **Execution risk**: Must successfully place both sides
2. **Partial fills**: Liquidity may be lower than displayed
3. **Price movement**: Odds/prices can move unfavorably
4. **Fees**: Kalshi ~7%, sportsbook varies by book
5. **Settlement**: Different settlement rules/timing
6. **Withdrawal friction**: Moving funds between platforms takes time

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=kalshi_odds

# Specific test file
pytest tests/test_odds_math.py -v
```

**Test coverage:**
- Odds conversion (American ↔ Decimal ↔ Probability)
- Vig removal (two-way proportional method)
- Edge detection logic
- Confidence scoring
- Staleness filtering
- Liquidity filtering

---

## Configuration

All settings via environment variables (prefix: `KALSHI_ODDS_`):

| Setting | Default | Description |
|---------|---------|-------------|
| `KALSHI_SLIPPAGE_BUFFER` | 0.005 | Kalshi slippage buffer (0.5%) |
| `SPORTSBOOK_EXECUTION_FRICTION` | 0.01 | Sportsbook friction (1%) |
| `MIN_EDGE_BPS` | 50 | Min edge to alert (0.5%) |
| `MIN_LIQUIDITY` | 10 | Min Kalshi liquidity (shares) |
| `MAX_STALENESS_SECONDS` | 60 | Max data age (seconds) |
| `FUZZY_MATCH_THRESHOLD` | 0.75 | Fuzzy match similarity threshold |

---

## Data Sources

### Kalshi
- **API**: https://trading-api.readme.io/reference
- **Auth**: RSA-PSS signing
- **Rate limit**: ~5 req/s recommended
- **Fees**: ~7% (taker + maker + settlement)

### The Odds API
- **Website**: https://the-odds-api.com/
- **Free tier**: 500 requests/month
- **Coverage**: Major US sportsbooks (DraftKings, FanDuel, BetMGM, etc.)
- **Sports**: NFL, NBA, MLB, NHL, Soccer, etc.

---

## Output

### Console
Live-updating Rich table showing alerts with:
- Market key
- Direction (kalshi_cheap / kalshi_rich)
- Edge (basis points)
- Confidence (low / med / high)
- Kalshi price
- Sportsbook no-vig probability

### JSONL Log
Append-only log (`alerts.jsonl`) containing full alert objects:
```json
{
  "alert_id": "a1b2c3d4",
  "timestamp": "2026-02-07T12:34:56",
  "market_key": "superbowl_2026_chiefs",
  "direction": "kalshi_cheap",
  "edge_pct": 2.5,
  "edge_bps": 250,
  "confidence": "high",
  "confidence_score": 0.82,
  "kalshi_contract_id": "SUPERBOWL-KC-YES",
  "kalshi_price": 0.45,
  "sportsbook_bookmaker": "draftkings",
  "sportsbook_p_no_vig": 0.50,
  ...
}
```

### SQLite Database
Persists:
- Kalshi contracts
- Odds quotes
- Alerts history

Query with standard SQL tools or via Python.

---

## Extending

### Add new sports

```bash
kalshi-odds sync-odds --sport basketball_nba
kalshi-odds sync-odds --sport soccer_epl
```

See [The Odds API sports list](https://the-odds-api.com/sports-odds-data/sports-apis.html).

### Add new odds aggregators

1. Create `src/kalshi_odds/adapters/new_aggregator.py`
2. Implement similar interface to `OddsAPIAdapter`
3. Update CLI to support new source

---

## License

For personal/educational use. Review each venue's API terms before deploying.

---

## FAQ

**Q: Can this system place bets automatically on sportsbooks?**
A: No. This is alert-only. Sportsbook execution is manual.

**Q: How accurate are the no-vig probabilities?**
A: Proportional vig removal is accurate for two-way markets. Multi-way markets have limitations (see code comments).

**Q: Why are there no alerts?**
A: Check:
1. `mappings.yaml` has valid entries
2. Data is fresh (< 60s old)
3. `min_edge_bps` threshold isn't too high
4. Kalshi liquidity meets `min_liquidity`

**Q: Can I use this for live betting?**
A: The system supports live odds, but execution speed limitations (manual sportsbook entry) make it impractical for fast-moving lines.

**Q: What about arbitrage between sportsbooks?**
A: This tool is Kalshi-focused. For sportsbook-only arb, use dedicated tools.

---

## Support

- Issues: [GitHub Issues](https://github.com/...)
- Kalshi API: https://trading-api.readme.io/reference
- The Odds API: https://the-odds-api.com/
