"""
Auto-mapper: match Kalshi game-winner tickers to Odds API events by team name.

Fetches Kalshi markets by series (e.g. KXNBAGAME), Odds API events for the sport,
matches by team name similarity, and writes/merges mappings.yaml.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter


# Sport key (Odds API) -> Kalshi series_ticker for game-winner markets
SPORT_TO_SERIES: dict[str, str] = {
    "basketball_nba": "KXNBAGAME",
    "americanfootball_nfl": "KXNFLGAME",
    "basketball_ncaab": "KXNCAABGAME",
}

# Kalshi team code (e.g. OKC, HOU) -> keywords to match Odds API team names (substring match)
TEAM_CODE_KEYWORDS: dict[str, list[str]] = {
    # NBA
    "ATL": ["Atlanta", "Hawks"],
    "BKN": ["Brooklyn", "Nets"],
    "BOS": ["Boston", "Celtics"],
    "CHA": ["Charlotte", "Hornets"],
    "CHI": ["Chicago", "Bulls"],
    "CLE": ["Cleveland", "Cavaliers"],
    "DAL": ["Dallas", "Mavericks"],
    "DEN": ["Denver", "Nuggets"],
    "DET": ["Detroit", "Pistons"],
    "GSW": ["Golden State", "Warriors", "GS "],
    "HOU": ["Houston", "Rockets"],
    "IND": ["Indiana", "Pacers"],
    "LAC": ["LA Clippers", "Clippers"],
    "LAL": ["Lakers", "Los Angeles Lakers"],
    "MEM": ["Memphis", "Grizzlies"],
    "MIA": ["Miami", "Heat"],
    "MIL": ["Milwaukee", "Bucks"],
    "MIN": ["Minnesota", "Timberwolves"],
    "NOP": ["New Orleans", "Pelicans"],
    "NYK": ["New York", "Knicks"],
    "OKC": ["Oklahoma City", "Thunder"],
    "ORL": ["Orlando", "Magic"],
    "PHI": ["Philadelphia", "76ers", "Sixers"],
    "PHX": ["Phoenix", "Suns"],
    "POR": ["Portland", "Trail Blazers", "Blazers"],
    "SAC": ["Sacramento", "Kings"],
    "SAS": ["San Antonio", "Spurs"],
    "TOR": ["Toronto", "Raptors"],
    "UTA": ["Utah", "Jazz"],
    "WAS": ["Washington", "Wizards"],
    # NFL (common)
    "SEA": ["Seattle", "Seahawks"],
    "NE": ["New England", "Patriots"],
    "KC": ["Kansas City", "Chiefs"],
    "SF": ["San Francisco", "49ers"],
    "BUF": ["Buffalo", "Bills"],
    "BAL": ["Baltimore", "Ravens"],
    "CIN": ["Cincinnati", "Bengals"],
    "CLE": ["Cleveland", "Browns"],
    "HOU": ["Houston", "Texans"],
    "IND": ["Indianapolis", "Colts"],
    "JAX": ["Jacksonville", "Jaguars"],
    "LV": ["Las Vegas", "Raiders"],
    "LAC": ["Los Angeles Chargers", "Chargers"],
    "MIA": ["Miami", "Dolphins"],
    "NYJ": ["New York Jets", "Jets"],
    "NYG": ["New York Giants", "Giants"],
    "PHI": ["Philadelphia", "Eagles"],
    "PIT": ["Pittsburgh", "Steelers"],
    "LAR": ["Los Angeles Rams", "Rams"],
    "TB": ["Tampa Bay", "Buccaneers"],
    "TEN": ["Tennessee", "Titans"],
    "MIN": ["Minnesota", "Vikings"],
    "CHI": ["Chicago", "Bears"],
    "DET": ["Detroit", "Lions"],
    "GB": ["Green Bay", "Packers"],
    "ATL": ["Atlanta", "Falcons"],
    "CAR": ["Carolina", "Panthers"],
    "NO": ["New Orleans", "Saints"],
    "DAL": ["Dallas", "Cowboys"],
    "NYG": ["New York Giants", "Giants"],
    "WAS": ["Washington", "Commanders"],
}


def _team_matches(code: str, team_name: str) -> bool:
    """True if team_name matches the given Kalshi team code (substring keywords)."""
    if not team_name:
        return False
    keywords = TEAM_CODE_KEYWORDS.get(code, [code])
    return any(kw.lower() in team_name.lower() for kw in keywords)


def parse_kalshi_ticker(ticker: str) -> Optional[tuple[str, str, str]]:
    """
    Parse Kalshi game-winner ticker into (date_part, game_code, side_code).
    Example: KXNBAGAME-26FEB07HOUOKC-OKC -> ("26FEB07", "HOUOKC", "OKC").
    Returns None if format unrecognized.
    """
    if not ticker or "-" not in ticker:
        return None
    parts = ticker.split("-")
    if len(parts) < 3:
        return None
    # parts[0] = series, parts[1] = date+game e.g. 26FEB07HOUOKC, parts[2] = side e.g. OKC
    date_game = parts[1]
    side_code = parts[2]
    # date is typically 7 chars: 26FEB07
    if len(date_game) < 8:
        return None
    date_part = date_game[:7]
    game_code = date_game[7:]
    if len(game_code) < 4:
        return None
    return (date_part, game_code, side_code)


def _game_codes_from_ticker(ticker: str) -> Optional[tuple[str, str]]:
    """
    Get the two team codes from a game ticker (e.g. HOUOKC -> (HOU, OKC)).
    Assumes 6-char game code = two 3-letter codes.
    """
    parsed = parse_kalshi_ticker(ticker)
    if not parsed:
        return None
    _date, game_code, _side = parsed
    if len(game_code) == 6:
        return (game_code[:3], game_code[3:])
    if len(game_code) == 4:
        return (game_code[:2], game_code[2:])
    return None


def _match_event_to_codes(home_team: str, away_team: str, code_a: str, code_b: str) -> Optional[tuple[str, str]]:
    """
    If event (home_team, away_team) matches team codes (code_a, code_b), return (name_for_a, name_for_b).
    Otherwise return None.
    """
    a_matches_home = _team_matches(code_a, home_team)
    a_matches_away = _team_matches(code_a, away_team)
    b_matches_home = _team_matches(code_b, home_team)
    b_matches_away = _team_matches(code_b, away_team)
    if a_matches_home and b_matches_away:
        return (home_team, away_team)
    if a_matches_away and b_matches_home:
        return (away_team, home_team)
    return None


def _market_key_from_ticker(ticker: str, date_part: str, side_code: str, game_code: str) -> str:
    """Generate a stable market_key for YAML (e.g. nba_20260207_houokc_okc)."""
    # Normalize date: 26FEB07 -> 20260207
    m = re.match(r"(\d{2})([A-Z]{3})(\d{2})", date_part)
    month_map = {"JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
                 "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"}
    if m:
        year = "20" + m.group(1)
        month = month_map.get(m.group(2), "01")
        day = m.group(3)
    else:
        year, month, day = "2026", "01", "01"
    date_str = f"{year}{month}{day}"
    prefix = "nba" if "NBA" in ticker or "KXNBAGAME" in ticker else "nfl" if "NFL" in ticker or "KXNFLGAME" in ticker else "game"
    return f"{prefix}_{date_str}_{game_code.lower()}_{side_code.lower()}"


async def build_mappings(
    kalshi: KalshiAdapter,
    odds_api: OddsAPIAdapter,
    sport: str,
    mapping_path: Path,
    *,
    merge_with_existing: bool = True,
) -> list[dict]:
    """
    Fetch Kalshi game markets and Odds API events, match by team names, build mapping entries.
    Optionally merge with existing mappings (by market_key / contract_id).
    Returns list of mapping dicts (each with market_key, kalshi, odds).
    """
    series_ticker = SPORT_TO_SERIES.get(sport)
    if not series_ticker:
        raise ValueError(f"No Kalshi series for sport {sport}. Supported: {list(SPORT_TO_SERIES)}")

    contracts = await kalshi.list_contracts(series_ticker=series_ticker, limit=200)
    events = await odds_api.list_events(sport)

    existing_list: list[dict] = []
    existing_by_contract: dict[str, dict] = {}
    if merge_with_existing and mapping_path.exists():
        with open(mapping_path) as f:
            data = yaml.safe_load(f) or {}
        existing_list = data.get("markets", [])
        for entry in existing_list:
            cid = (entry.get("kalshi") or {}).get("contract_id", "")
            if cid:
                existing_by_contract[cid] = entry

    new_mappings: list[dict] = []
    seen_contracts: set[str] = set()

    for contract in contracts:
        ticker = contract.contract_id
        if ticker in seen_contracts:
            continue
        parsed = parse_kalshi_ticker(ticker)
        if not parsed:
            continue
        date_part, game_code, side_code = parsed
        codes = _game_codes_from_ticker(ticker)
        if not codes:
            continue
        code_a, code_b = codes

        for ev in events:
            event_id = ev.get("id", "")
            home_team = ev.get("home_team", "")
            away_team = ev.get("away_team", "")
            names = _match_event_to_codes(home_team, away_team, code_a, code_b)
            if not names:
                continue
            name_a, name_b = names
            selection = name_a if side_code.upper() == code_a.upper() else name_b
            market_key = _market_key_from_ticker(ticker, date_part, side_code, game_code)
            entry = {
                "market_key": market_key,
                "kalshi": {"contract_id": ticker, "side": "YES"},
                "odds": {"event_id": event_id, "market_type": "h2h", "selection": selection},
            }
            if merge_with_existing and ticker in existing_by_contract:
                entry = {**existing_by_contract[ticker], **entry}
            new_mappings.append(entry)
            seen_contracts.add(ticker)
            break

    # When merging, keep existing entries whose contract_id we did not auto-match
    if merge_with_existing and existing_list:
        kept = [e for e in existing_list if (e.get("kalshi") or {}).get("contract_id") not in seen_contracts]
        new_mappings = kept + new_mappings

    return new_mappings


def write_mappings(mapping_path: Path, mappings: list[dict]) -> None:
    """Write mappings to YAML file."""
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "markets": mappings,
    }
    with open(mapping_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


async def auto_map(
    kalshi: KalshiAdapter,
    odds_api: OddsAPIAdapter,
    sport: str,
    mapping_path: Path,
    *,
    merge_with_existing: bool = True,
    write: bool = True,
) -> list[dict]:
    """
    Run auto-mapper: build mappings and optionally write to mapping_path.
    Returns list of mapping entries.
    """
    mappings = await build_mappings(
        kalshi, odds_api, sport, mapping_path, merge_with_existing=merge_with_existing
    )
    if write and mappings:
        write_mappings(mapping_path, mappings)
    return mappings
