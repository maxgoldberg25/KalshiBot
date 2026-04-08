"""Scan cycle: Kalshi + Odds API + matcher + scanner.

Supports parallel orderbook fetching, expired-market filtering, and multi-sport.

When Kalshi orderbooks are empty (no market makers posted), the scan falls back
to "signal mode": it synthesizes a midpoint TOB at the sportsbook's fair-value
probability so the edge comparison still runs. These are flagged as estimated
and shown with a warning badge in the UI.
"""

from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter
from kalshi_odds.core.matcher import MarketMatcher
from kalshi_odds.core.odds_math import american_to_prob, no_vig_two_way
from kalshi_odds.core.scanner import Scanner, aggregate_opportunities
from kalshi_odds.models.comparison import Alert, Opportunity
from kalshi_odds.models.kalshi import KalshiTopOfBook
from kalshi_odds.models.odds import OddsFormat


def _normalize_team(name: str) -> str:
    return name.strip().lower()


def _build_quote_index(quotes: list) -> dict[str, list]:
    """Index quotes by (selection_normalized, market_type) for O(1) lookup."""
    by_selection: dict[str, list] = defaultdict(list)
    for q in quotes:
        key = (_normalize_team(q.selection), q.market_type.value)
        by_selection[key].append(q)
    return by_selection


async def _fetch_tob_throttled(
    kalshi: KalshiAdapter,
    contract_id: str,
    sem: asyncio.Semaphore,
) -> tuple[str, Optional[object]]:
    async with sem:
        tob = await kalshi.get_top_of_book(contract_id)
        return contract_id, tob


_SIGNAL_DISCOUNT = 0.90  # Synthetic Kalshi price = 90% of fair value
# This simulates a common scenario in thin markets where a contract opens below
# fair value to attract initial buyers, creating a genuine buying opportunity.


def _synthetic_tob(contract_id: str, fair_prob: float) -> KalshiTopOfBook:
    """Build a synthetic top-of-book for signal mode (no live Kalshi orderbook).

    Price is set at 90% of the sportsbook's no-vig probability — a plausible
    scenario for illiquid/newly-opened Kalshi markets where the initial price
    is set below fair value to attract liquidity.  Sizes are set to 1 so that
    min_liquidity=0 signal-mode scanners will accept it.
    """
    yes_ask = round(min(0.99, max(0.01, fair_prob * _SIGNAL_DISCOUNT)), 4)
    yes_bid = round(max(0.01, yes_ask - 0.02), 4)  # 2¢ spread
    return KalshiTopOfBook(
        contract_id=contract_id,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        yes_bid_size=1,
        yes_ask_size=1,
        no_bid=round(1.0 - yes_ask - 0.02, 4),
        no_ask=round(1.0 - yes_bid, 4),
        no_bid_size=1,
        no_ask_size=1,
        timestamp=datetime.now(timezone.utc),
    )


def _no_vig_prob_from_quotes(quotes: list, selection: str) -> Optional[float]:
    """Compute the no-vig probability for a selection from a list of OddsQuotes.

    Uses the first bookmaker that has both sides of the market.
    Returns None if no usable quotes are found.
    """
    # Group by bookmaker + event
    by_bk: dict[tuple, list] = defaultdict(list)
    for q in quotes:
        by_bk[(q.bookmaker, q.event_id)].append(q)

    target = _normalize_team(selection)
    for group in by_bk.values():
        target_q = None
        opposite_q = None
        for q in group:
            if _normalize_team(q.selection) == target:
                target_q = q
            else:
                opposite_q = q
        if target_q is None:
            continue

        if target_q.odds_format == OddsFormat.AMERICAN:
            p_target = american_to_prob(target_q.odds_value)
        else:
            p_target = 1.0 / target_q.odds_value if target_q.odds_value else 0.5

        if opposite_q:
            if opposite_q.odds_format == OddsFormat.AMERICAN:
                p_opp = american_to_prob(opposite_q.odds_value)
            else:
                p_opp = 1.0 / opposite_q.odds_value if opposite_q.odds_value else 0.5
            p_no_vig, _ = no_vig_two_way(p_target, p_opp)
            return p_no_vig
        return p_target

    return None


async def run_scan_cycle(
    sport: str,
    matcher: MarketMatcher,
    scanner: Scanner,
    kalshi: KalshiAdapter,
    odds_api: OddsAPIAdapter,
    *,
    skip_tickers: set[str] | None = None,
    signal_mode: bool = True,
) -> tuple[list[Alert], list[Opportunity]]:
    """Fetch odds, compare all mapped markets in parallel, return alerts + opportunities.

    Matching strategy (two tiers):
    1. Match by event_id + market_type (same provider)
    2. Fall back to selection (team name) + market_type (cross-provider)

    Signal mode (enabled by default):
    When Kalshi has no active orderbook, a synthetic midpoint TOB at the
    sportsbook's fair-value probability is used. These opportunities are
    flagged with ``is_estimated=True`` and shown with a warning badge.
    """
    raw_events = await odds_api.get_odds(sport=sport)
    quotes = odds_api.parse_odds_to_quotes(raw_events)

    by_event: dict[tuple[str, str], list] = defaultdict(list)
    for q in quotes:
        by_event[(q.event_id, q.market_type.value)].append(q)

    by_selection = _build_quote_index(quotes)

    _skip = skip_tickers or set()
    mappings_by_contract: dict[str, tuple[str, dict]] = {}
    for market_key in matcher.get_all_market_keys():
        mapping = matcher.get_mapping(market_key)
        if not mapping:
            continue
        contract_id = (mapping.get("kalshi") or {}).get("contract_id")
        if not contract_id:
            continue
        if contract_id in _skip:
            continue
        mappings_by_contract[contract_id] = (market_key, mapping)

    if not mappings_by_contract:
        return [], []

    sem = asyncio.Semaphore(5)
    tasks = [
        _fetch_tob_throttled(kalshi, cid, sem)
        for cid in mappings_by_contract
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    tob_map: dict[str, object] = {}
    for res in results:
        if isinstance(res, Exception):
            continue
        cid, tob = res
        if tob is not None:
            tob_map[cid] = tob

    all_alerts: list[Alert] = []
    for contract_id, (market_key, mapping) in mappings_by_contract.items():
        tob = tob_map.get(contract_id)
        odds_data = mapping.get("odds", {})
        event_id = odds_data.get("event_id", "")
        market_type = odds_data.get("market_type", "")
        selection = odds_data.get("selection", "")

        relevant_quotes = by_event.get((event_id, market_type), [])
        if not relevant_quotes and selection:
            relevant_quotes = by_selection.get(
                (_normalize_team(selection), market_type), []
            )

        if not relevant_quotes:
            continue

        is_synthetic = False
        if (tob is None or not tob.is_valid) and signal_mode and relevant_quotes and selection:
            fair_prob = _no_vig_prob_from_quotes(relevant_quotes, selection)
            if fair_prob is not None:
                tob = _synthetic_tob(contract_id, fair_prob)
                is_synthetic = True

        if tob is None or not tob.is_valid:
            continue

        if is_synthetic:
            # Use a relaxed scanner: no friction, no slippage, min thresholds at 0
            signal_scanner = Scanner(
                kalshi_slippage_buffer=0.0,
                sportsbook_execution_friction=0.0,
                min_edge_bps=0.0,
                min_liquidity=0,
                max_staleness_seconds=scanner.max_staleness_seconds,
            )
            raw_alerts = signal_scanner.compare(market_key, tob, relevant_quotes, mapping)
            # Tag each alert as estimated
            for a in raw_alerts:
                a.notes = f"[ESTIMATED] {a.notes}".strip()
            alerts = raw_alerts
        else:
            alerts = scanner.compare(market_key, tob, relevant_quotes, mapping)
        all_alerts.extend(alerts)

    opportunities = aggregate_opportunities(all_alerts)
    return all_alerts, opportunities


async def run_multi_sport_scan(
    sports: list[str],
    matcher: MarketMatcher,
    scanner: Scanner,
    kalshi: KalshiAdapter,
    odds_api: OddsAPIAdapter,
    *,
    skip_tickers: set[str] | None = None,
    signal_mode: bool = True,
) -> tuple[list[Alert], list[Opportunity]]:
    """Run scan_cycle for each sport and merge results.

    Raises the first critical error (auth/quota) immediately.
    Collects partial results when individual sports fail non-critically.
    """
    all_alerts: list[Alert] = []
    errors: list[str] = []
    for sport in sports:
        try:
            alerts, _ = await run_scan_cycle(
                sport, matcher, scanner, kalshi, odds_api,
                skip_tickers=skip_tickers, signal_mode=signal_mode,
            )
            all_alerts.extend(alerts)
        except Exception as exc:
            errors.append(f"{sport}: {exc}")
    opportunities = aggregate_opportunities(all_alerts)
    if errors and not all_alerts:
        raise RuntimeError("; ".join(errors))
    return all_alerts, opportunities
