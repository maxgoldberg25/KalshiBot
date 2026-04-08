"""One-shot scan cycle: Kalshi + Odds API + matcher + scanner."""

from __future__ import annotations

from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter
from kalshi_odds.core.matcher import MarketMatcher
from kalshi_odds.core.scanner import Scanner, aggregate_opportunities
from kalshi_odds.models.comparison import Alert, Opportunity


async def run_scan_cycle(
    sport: str,
    matcher: MarketMatcher,
    scanner: Scanner,
    kalshi: KalshiAdapter,
    odds_api: OddsAPIAdapter,
) -> tuple[list[Alert], list[Opportunity]]:
    """Fetch odds, compare all mapped markets, return alerts and aggregated opportunities."""
    raw_events = await odds_api.get_odds(sport=sport)
    quotes = odds_api.parse_odds_to_quotes(raw_events)
    all_alerts: list[Alert] = []
    for market_key in matcher.get_all_market_keys():
        mapping = matcher.get_mapping(market_key)
        if not mapping:
            continue
        kalshi_data = mapping.get("kalshi", {})
        contract_id = kalshi_data.get("contract_id")
        if not contract_id:
            continue
        tob = await kalshi.get_top_of_book(contract_id)
        if not tob:
            continue
        odds_data = mapping.get("odds", {})
        event_id = odds_data.get("event_id", "")
        market_type = odds_data.get("market_type", "")
        relevant_quotes = [
            q for q in quotes
            if q.event_id == event_id and q.market_type.value == market_type
        ]
        if not relevant_quotes:
            continue
        alerts = scanner.compare(market_key, tob, relevant_quotes, mapping)
        all_alerts.extend(alerts)
    opportunities = aggregate_opportunities(all_alerts)
    return all_alerts, opportunities
