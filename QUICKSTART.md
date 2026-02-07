# Quick Start Guide

Get up and running with the Kalshi vs Sportsbook odds scanner in 5 minutes.

---

## Step 1: Install

```bash
cd /Users/maxgoldberg/Documents/GitHub/KalshiBot/KalshiBot
source venv/bin/activate
pip install -e ".[dev]"
```

✅ Already done if you followed setup above.

---

## Step 2: Get API Keys

### Kalshi

1. Go to https://kalshi.com
2. Sign up / log in
3. Navigate to Settings → API
4. Create API key
5. Download the private key file (`kalshi_private_key.pem`)
6. Save it somewhere secure (e.g., `~/.keys/kalshi_private_key.pem`)

### The Odds API

1. Go to https://the-odds-api.com/
2. Click "Get API Key"
3. Sign up (free tier: 500 requests/month)
4. Copy your API key

---

## Step 3: Configure

```bash
# Copy example
cp .env.example .env

# Edit .env
nano .env
```

Add your credentials:

```bash
KALSHI_ODDS_KALSHI_API_KEY_ID=your-kalshi-api-key-id
KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH=/Users/you/.keys/kalshi_private_key.pem
KALSHI_ODDS_ODDS_API_KEY=your-odds-api-key
```

---

## Step 4: Sync Data

```bash
# Fetch Kalshi contracts (takes ~30 seconds)
kalshi-odds sync-kalshi

# Fetch NFL odds (uses 1 API request)
kalshi-odds sync-odds --sport americanfootball_nfl
```

You should see tables showing contracts and odds.

---

## Step 5: Create Mappings

```bash
cp mappings.example.yaml mappings.yaml
```

Edit `mappings.yaml` to map Kalshi contracts to sportsbook events.

**Example:**

```yaml
markets:
  - market_key: "super_bowl_chiefs_win"
    kalshi:
      contract_id: "SUPERBOWL-KC-YES"  # From sync-kalshi output
      side: "YES"
    odds:
      event_id: "abc123..."  # From sync-odds output
      market_type: "h2h"
      selection: "Kansas City Chiefs"
```

**How to find IDs:**
- Kalshi contract_id: Look at `sync-kalshi` output, find the ticker
- Odds event_id: Look at `sync-odds` output, find the event
- Selection: Exact team/player name from odds output

---

## Step 6: Run Scanner (Alert-Only)

```bash
kalshi-odds run --sport americanfootball_nfl
```

The scanner will:
- Poll Kalshi and sportsbooks every 60 seconds (configurable)
- Compare prices for mapped markets
- Display alerts when edges exceed threshold (default: 50 bps = 0.5%)

**Example alert:**

```
🚨 ALERT DETECTED
Market: super_bowl_chiefs_win
Direction: kalshi_cheap
Edge: 250 bps (2.5%)
Confidence: high
Kalshi YES: 0.450
Book no-vig: 0.500
```

---

## Step 7: Review Alerts

```bash
# Show last 20 alerts
kalshi-odds show

# Show last 50
kalshi-odds show --last 50
```

Alerts are also saved to:
- `alerts.jsonl` (JSONL log)
- `kalshi_odds.db` (SQLite database)

---

## Example Workflow

```bash
# Morning: sync data
kalshi-odds sync-kalshi
kalshi-odds sync-odds --sport americanfootball_nfl

# Start scanner
kalshi-odds run --sport americanfootball_nfl

# In another terminal: watch alerts in real-time
watch -n 10 "kalshi-odds show --last 10"

# Manual execution (when alert triggers):
# 1. Check Kalshi website - verify price still valid
# 2. Check sportsbook website - verify odds still valid
# 3. Manually place both sides if edge is still present
```

---

## Troubleshooting

### No alerts appearing

Check:
1. `mappings.yaml` has valid entries
2. Markets are actually open/active
3. `min_edge_bps` isn't too high (try lowering to 25)
4. Liquidity meets threshold (default: 10 shares)

### API errors

- **Kalshi 401**: Check API key ID and private key path
- **The Odds API 401**: Check API key
- **The Odds API 429**: You hit rate limit (free tier: 500 req/month)

### "No mappings found"

Create `mappings.yaml` with at least one valid mapping (see Step 5).

---

## Next Steps

- Add more markets to `mappings.yaml`
- Try different sports: `--sport basketball_nba`, `--sport soccer_epl`
- Lower `min_edge_bps` to see more alerts (may have false positives)
- Review `README.md` for full documentation

---

## Important Notes

- This system is **alert-only**
- No automated sportsbook execution
- Manual execution required
- Prices can move between alert and execution
- Always verify prices before manually executing

Happy hunting! 🎯
