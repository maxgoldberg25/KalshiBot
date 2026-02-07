# Getting The Odds API Key

The scanner uses [The Odds API](https://the-odds-api.com/) to fetch sportsbook odds from multiple books (DraftKings, FanDuel, BetMGM, Caesars, etc.).

---

## Quick Setup

### Step 1: Get API Key (2 minutes)

1. Go to https://the-odds-api.com/
2. Click "Get API Key" (top right)
3. Enter your email
4. Click the confirmation link in your email
5. Copy your API key

**Free tier**: 500 requests per month

---

### Step 2: Add to `.env`

```bash
KALSHI_ODDS_ODDS_API_KEY=your-api-key-here
```

---

### Step 3: Test It

```bash
kalshi-odds sync-odds --sport americanfootball_nfl
```

You should see a table of odds from multiple sportsbooks.

---

## Rate Limits

| Tier | Requests/Month | Cost |
|------|----------------|------|
| Free | 500 | $0 |
| Starter | 10,000 | $30/mo |
| Pro | 100,000 | $150/mo |

**How many requests do you need?**

Each `sync-odds` call uses **1 request per sport**.

Example daily usage:
- Morning sync (4 sports): 4 requests
- Run scanner for 8 hours (polls every 60s): ~480 requests
- Total: ~484 requests/day

**Free tier is too small for continuous scanning.**

For production use:
- Get Starter plan ($30/mo)
- Or increase poll interval to 5-10 minutes

---

## Supported Sports

Common sports on The Odds API:

| Sport Key | Description |
|-----------|-------------|
| `americanfootball_nfl` | NFL |
| `americanfootball_ncaaf` | College Football |
| `basketball_nba` | NBA |
| `basketball_ncaab` | College Basketball |
| `baseball_mlb` | MLB |
| `icehockey_nhl` | NHL |
| `soccer_epl` | English Premier League |
| `soccer_usa_mls` | MLS |
| `mma_mixed_martial_arts` | MMA/UFC |

Full list: https://the-odds-api.com/sports-odds-data/sports-apis.html

---

## Markets Available

- `h2h` — Head-to-head (moneyline)
- `spreads` — Point spreads
- `totals` — Over/under
- `outrights` — Futures (e.g., Super Bowl winner)
- `player_props` — Player props (limited availability)

**Note:** Not all markets are available for all sports. Check the API docs.

---

## Bookmakers Covered (US)

- DraftKings
- FanDuel
- BetMGM
- Caesars
- PointsBet
- BetRivers
- Unibet
- WynnBET
- And more...

---

## Example API Response

```json
[
  {
    "id": "abc123",
    "sport_key": "americanfootball_nfl",
    "commence_time": "2026-02-09T23:30:00Z",
    "home_team": "Kansas City Chiefs",
    "away_team": "Philadelphia Eagles",
    "bookmakers": [
      {
        "key": "draftkings",
        "title": "DraftKings",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              {"name": "Kansas City Chiefs", "price": -110},
              {"name": "Philadelphia Eagles", "price": -110}
            ]
          }
        ]
      }
    ]
  }
]
```

---

## Troubleshooting

### Error: "Invalid API key"

- Check the key in `.env` (no extra spaces)
- Verify you clicked the email confirmation link
- Try regenerating the key on the website

### Error: "429 Too Many Requests"

You've exceeded your monthly quota.

**Solutions:**
- Wait until next month (free tier resets)
- Upgrade to paid plan
- Increase poll interval
- Reduce number of sports monitored

### "No odds data returned"

- Check the sport key is valid
- Some sports may not have active events
- Try a major sport: `americanfootball_nfl`

---

## Best Practices

1. **Cache aggressively**: The Odds API charges per request
2. **Monitor usage**: Check remaining requests in API response headers
3. **Pick your spots**: Focus on 1-2 high-value sports
4. **Longer poll intervals**: 2-5 minutes is usually sufficient

---

## Alternative: Other Odds APIs

If The Odds API doesn't meet your needs, alternatives include:

- **BetOnline API** (proprietary)
- **Odds Shark** (scraping required)
- **SportsDataIO** (paid)
- **RapidAPI Sports Odds** (various providers)

To integrate a different API:
1. Create `src/kalshi_odds/adapters/new_api.py`
2. Implement similar interface to `OddsAPIAdapter`
3. Update CLI to support new source

---

## Cost Optimization

Free tier (500 req/month) strategies:

**Option A: Manual sync**
```bash
# Sync once per day
kalshi-odds sync-odds --sport americanfootball_nfl  # 1 request
# Use cached data all day
```

**Option B: Targeted scanning**
```bash
# Only scan during game days
kalshi-odds run --sport americanfootball_nfl --interval 300  # 5 min polls
```

**Option C: Event-based**
- Only sync before placing a manual trade
- Don't run continuous loop

---

## Next Steps

After getting your API key:

1. Add to `.env`: `KALSHI_ODDS_ODDS_API_KEY=...`
2. Test: `kalshi-odds sync-odds --sport americanfootball_nfl`
3. See data: Check the output table
4. Create mappings: Add Kalshi contracts to `mappings.yaml`
5. Run scanner: `kalshi-odds run`

See `QUICKSTART.md` for complete walkthrough.
