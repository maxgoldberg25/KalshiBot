# Finding Markets to Map

This guide helps you find Kalshi contracts that match sportsbook markets.

## Quick Start

```bash
# 1. Sync both data sources
kalshi-odds sync-kalshi
kalshi-odds sync-odds --sport basketball_nba

# 2. Open the database
sqlite3 kalshi_odds.db

# 3. Run queries below to find matches
```

## Current Situation

Based on your recent sync:
- **Kalshi has**: Multi-game parlays, player props (not simple game winners)
- **Sportsbooks have**: Head-to-head game winners

**This means**: You likely won't find direct matches for tonight's NBA/NFL games.

## Best Markets to Map

Look for these types of markets that BOTH platforms offer:

1. **Championship Futures** (NBA/NFL champion)
2. **MVP Markets**
3. **Season Win Totals**
4. **Playoff Qualification**
5. **Super Bowl Winner**
6. **Conference Champions**

## SQL Queries to Find Kalshi Markets

### Search for Championship Markets
```sql
SELECT contract_id, title, close_time 
FROM kalshi_contracts 
WHERE title LIKE '%championship%' 
   OR title LIKE '%winner%'
   OR title LIKE '%champion%'
LIMIT 20;
```

### Search for MVP Markets
```sql
SELECT contract_id, title, close_time 
FROM kalshi_contracts 
WHERE title LIKE '%MVP%' 
   OR title LIKE '%most valuable%'
LIMIT 20;
```

### Search for Playoff Markets
```sql
SELECT contract_id, title, close_time 
FROM kalshi_contracts 
WHERE title LIKE '%playoff%' 
   OR title LIKE '%postseason%'
LIMIT 20;
```

### Search for Specific Teams
```sql
SELECT contract_id, title, close_time 
FROM kalshi_contracts 
WHERE (title LIKE '%Chiefs%' OR title LIKE '%Kansas City%')
  AND title NOT LIKE '%yes %yes %'  -- Exclude multi-game parlays
LIMIT 20;
```

## SQL Queries to Find Sportsbook Markets

### List All Available Events
```sql
SELECT DISTINCT event_id, selection 
FROM odds_quotes 
WHERE source = 'the-odds-api' 
ORDER BY selection;
```

### Find Specific Team Odds
```sql
SELECT event_id, bookmaker, selection, odds_format, odds_value 
FROM odds_quotes 
WHERE selection LIKE '%Thunder%' 
LIMIT 10;
```

### Get All NBA Events
```sql
SELECT DISTINCT event_id 
FROM odds_quotes 
WHERE bookmaker = 'fanduel'  -- Use one book to avoid duplicates
ORDER BY timestamp DESC 
LIMIT 20;
```

## Example: Finding a Match

Let's say you want to map **Oklahoma City Thunder** to win the NBA Championship:

### Step 1: Check if Kalshi has it
```sql
SELECT contract_id, title 
FROM kalshi_contracts 
WHERE title LIKE '%Thunder%' 
  AND title LIKE '%championship%';
```

### Step 2: Check if sportsbooks have it
First, sync championship futures:
```bash
kalshi-odds sync-odds --sport basketball_nba_championship_winner
```

Then query:
```sql
SELECT event_id, selection, odds_value 
FROM odds_quotes 
WHERE selection = 'Oklahoma City Thunder' 
  AND market_type = 'outrights';
```

### Step 3: Create the mapping
If both exist, add to `mappings.yaml`:
```yaml
markets:
  - market_key: "nba_2026_championship_thunder"
    kalshi:
      contract_id: "NBA-OKC-CHAMP-2026"  # From Step 1
      side: "YES"
    odds:
      event_id: "abc123..."                # From Step 2
      market_type: "outrights"
      selection: "Oklahoma City Thunder"
```

## Currently Available Sportsbook Events

From your last sync:

### NFL
- Event: `b64e3587d7a4cf01a568e7150a2a1aec`
- Matchup: Seattle Seahawks @ New England Patriots

### NBA (10 games synced)
- Event: `734128222c2a03269132090adb3c593d`
- Matchup: Houston Rockets @ Oklahoma City Thunder

Query for all NBA events:
```sql
SELECT DISTINCT 
    event_id,
    GROUP_CONCAT(DISTINCT selection) as teams
FROM odds_quotes 
WHERE source = 'the-odds-api'
GROUP BY event_id;
```

## Tips

1. **Start with futures markets** - They're more likely to exist on both platforms
2. **Use exact names** - Selection names must match exactly (case-sensitive)
3. **Verify timing** - Make sure both markets close around the same time
4. **Check YES vs NO** - Sometimes you need to map Kalshi YES to sportsbook's opposite team
5. **Test with one mapping first** - Add one, run the scanner, verify it works

## Next Steps

Once you find a match and add it to `mappings.yaml`:

```bash
# Run the scanner
kalshi-odds run --sport basketball_nba

# Or for continuous monitoring
kalshi-odds run --sport basketball_nba --interval 30
```

## Still Can't Find Matches?

If Kalshi doesn't have simple head-to-head markets:

1. Wait for different market types (they may add them closer to game time)
2. Focus on futures/championship markets
3. Check Kalshi's website directly to see what contract types they offer
4. Consider mapping player props if both platforms offer them
