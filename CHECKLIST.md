# 📋 Your Next Steps Checklist

Use this checklist to get the scanner running. Check off each step as you complete it.

---

## ✅ Setup (One-Time)

- [ ] **Get The Odds API key**
  - Go to https://the-odds-api.com/
  - Sign up (free, 2 minutes)
  - Copy your API key
  - See `ODDS_API_SETUP.md` for help

- [ ] **Update `.env` file**
  ```bash
  nano .env  # or your preferred editor
  ```
  - Add: `KALSHI_ODDS_ODDS_API_KEY=your-key-here`
  - Verify Kalshi credentials are correct
  - Save and close

- [ ] **Test configuration**
  ```bash
  kalshi-odds sync-kalshi
  ```
  - Should show Kalshi contracts table
  - If error: check Kalshi credentials in `.env`

- [ ] **Test odds fetching**
  ```bash
  kalshi-odds sync-odds --sport americanfootball_nfl
  ```
  - Should show odds table from multiple sportsbooks
  - If error: check `KALSHI_ODDS_ODDS_API_KEY` in `.env`

---

## 🔗 Mapping (One-Time per Market)

- [ ] **Identify markets to track**
  - Pick sports events that exist on both Kalshi and sportsbooks
  - Example: Super Bowl, playoff games, major events

- [ ] **Find Kalshi contract IDs**
  - Run: `kalshi-odds sync-kalshi`
  - Look for relevant markets in the output
  - Note the `contract_id` (ticker)

- [ ] **Find sportsbook event IDs**
  - Run: `kalshi-odds sync-odds --sport americanfootball_nfl`
  - Look for matching events
  - Note the event details

- [ ] **Create mappings**
  - Edit `mappings.yaml`
  - Add mapping entries (see `mappings.example.yaml`)
  - Format:
    ```yaml
    markets:
      - market_key: "your_unique_key"
        kalshi:
          contract_id: "TICKER-YES"
          side: "YES"
        odds:
          event_id: "evt_123"
          market_type: "h2h"
          selection: "Team Name"
    ```

- [ ] **Validate mappings**
  - Run: `kalshi-odds run --sport americanfootball_nfl`
  - Should start scanning without errors
  - Ctrl+C to stop

---

## 🚀 Daily Usage

- [ ] **Morning sync** (updates market data)
  ```bash
  kalshi-odds sync-kalshi
  kalshi-odds sync-odds --sport americanfootball_nfl
  ```

- [ ] **Start scanner**
  ```bash
  kalshi-odds run --sport americanfootball_nfl
  ```
  - Leave running in terminal
  - Alerts appear when edges detected

- [ ] **Monitor alerts**
  - In another terminal:
    ```bash
    watch -n 30 "kalshi-odds show --last 10"
    ```
  - Or check `alerts.jsonl` file

- [ ] **Manual execution** (when alert triggers)
  1. Verify Kalshi price on kalshi.com
  2. Verify sportsbook odds on sportsbook website/app
  3. If edge still exists, manually place both sides
  4. Track results

---

## 🔧 Optional: Advanced

- [ ] **Add more sports**
  ```bash
  kalshi-odds sync-odds --sport basketball_nba
  kalshi-odds sync-odds --sport baseball_mlb
  ```

- [ ] **Tune thresholds**
  - Edit `.env`:
    ```bash
    KALSHI_ODDS_MIN_EDGE_BPS=25.0  # Lower = more alerts (may be noisy)
    KALSHI_ODDS_MIN_LIQUIDITY=5    # Lower = smaller positions ok
    ```

- [ ] **Database queries**
  ```bash
  sqlite3 kalshi_odds.db "SELECT * FROM alerts ORDER BY edge_bps DESC LIMIT 10;"
  ```

- [ ] **Export alerts**
  ```bash
  # JSONL to CSV
  python -c "import json, csv, sys; [print(','.join(map(str, json.loads(l).values()))) for l in sys.stdin]" < alerts.jsonl > alerts.csv
  ```

---

## ❓ Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| "Kalshi not configured" | Add `KALSHI_ODDS_KALSHI_API_KEY_ID` and `KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH` to `.env` |
| "The Odds API not configured" | Add `KALSHI_ODDS_ODDS_API_KEY` to `.env` |
| "No mappings found" | Create `mappings.yaml` with at least one entry |
| No alerts appearing | Lower `MIN_EDGE_BPS` or check if markets are open |
| API rate limit | Upgrade The Odds API plan or increase poll interval |
| Tests failing | Reinstall: `pip install -e ".[dev]"` |

---

## 📚 Documentation Index

- `BUILD_COMPLETE.md` ← You are here (checklist)
- `QUICKSTART.md` ← Detailed 5-minute guide
- `README.md` ← Full documentation
- `ODDS_API_SETUP.md` ← The Odds API help
- `OVERVIEW.md` ← Architecture deep-dive

---

## ✨ Status

- ✅ System built and tested
- ✅ All 20 tests passing
- ✅ CLI working
- ✅ Installation successful
- ⏳ Waiting for: The Odds API key
- ⏳ Waiting for: Market mappings

**You're ready to start once you complete the setup checklist above!**

---

## Quick Test (No API Keys Needed)

Want to test without API keys?

```bash
# Run the unit tests
pytest -v

# Test CLI help
kalshi-odds --help

# Test math interactively
python -c "from kalshi_odds.core.odds_math import *; print(american_to_prob(-110))"
```

All should work without credentials.
