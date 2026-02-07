"""
Scanner – compares Kalshi prices vs sportsbook odds and generates alerts.

Implements edge detection, confidence scoring, alert generation,
and aggregation into actionable Opportunities.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from kalshi_odds.core.odds_math import american_to_prob, decimal_to_prob, no_vig_two_way
from kalshi_odds.models.kalshi import KalshiTopOfBook
from kalshi_odds.models.odds import OddsQuote, OddsFormat
from kalshi_odds.models.comparison import (
    Comparison,
    Alert,
    Opportunity,
    Direction,
    Confidence,
)
from kalshi_odds.models.probability import NormalizedProb, VigMethod


def _game_label_from_market_key(market_key: str) -> str:
    """Derive a readable game label from market_key e.g. nba_20260207_rockets_thunder_okc -> Thunder vs Rockets."""
    parts = market_key.split("_")
    # Drop sport prefix and date (digits)
    rest = [p for p in parts if not re.match(r"^\d+$", p) and p not in ("nba", "nfl", "superbowl")]
    if not rest:
        return market_key.replace("_", " ").title()
    # Last part is often the side (okc, hou, sea, ne); rest are team names
    if len(rest) >= 2:
        # e.g. rockets_thunder_okc -> Thunder vs Rockets
        team_parts = [p for p in rest if len(p) >= 2 and len(p) <= 6][:2]
        if len(team_parts) >= 2:
            return " vs ".join(t.title() for t in sorted(team_parts))
    return " vs ".join(p.title() for p in rest[:2]) if len(rest) >= 2 else rest[0].title()


def _kalshi_url_from_ticker(ticker: str) -> str:
    """Build Kalshi market URL from contract ticker."""
    ticker_lower = ticker.lower()
    if ticker_lower.startswith("kxnbagame"):
        base = "https://kalshi.com/markets/kxnbagame/professional-basketball-game"
    elif ticker_lower.startswith("kxsb"):
        base = "https://kalshi.com/markets/kxsb/super-bowl"
    elif ticker_lower.startswith("kxnfl"):
        base = "https://kalshi.com/markets/kxnflgame/professional-football-game"
    else:
        base = "https://kalshi.com/markets"
    return f"{base}/{ticker_lower}"


def aggregate_opportunities(alerts: list[Alert]) -> list[Opportunity]:
    """
    Group raw alerts by (market_key, direction) and build one Opportunity per group.
    Rank by edge_cents * sqrt(liquidity) * book_count.
    """
    if not alerts:
        return []

    groups: dict[tuple[str, str], list[Alert]] = defaultdict(list)
    for a in alerts:
        groups[(a.market_key, a.direction.value)].append(a)

    opportunities: list[Opportunity] = []
    for (market_key, direction_val), group in groups.items():
        direction = Direction(direction_val)
        a0 = group[0]

        # Kalshi side (same for all in group)
        kalshi_price = a0.kalshi_price
        kalshi_price_cents = int(round(kalshi_price * 100))
        kalshi_ticker = a0.kalshi_contract_id
        kalshi_liquidity = a0.kalshi_liquidity
        selection = a0.sportsbook_selection

        # Spread from raw snapshot if available
        kalshi_spread_cents = 0
        if a0.raw_snapshot_refs and "kalshi" in a0.raw_snapshot_refs:
            kob = a0.raw_snapshot_refs["kalshi"]
            yb = kob.get("yes_bid")
            ya = kob.get("yes_ask")
            if yb is not None and ya is not None:
                kalshi_spread_cents = int(round((float(ya) - float(yb)) * 100))

        # Book consensus
        probs = [a.sportsbook_p_no_vig for a in group]
        probs.sort()
        mid = len(probs) // 2
        book_fair_prob = (probs[mid] + probs[mid - 1]) / 2.0 if len(probs) % 2 == 0 else probs[mid]
        book_count = len(group)

        # Best/worst book by edge
        best_alert = max(group, key=lambda a: a.edge_bps)
        worst_alert = min(group, key=lambda a: a.edge_bps)
        book_best_name = best_alert.sportsbook_bookmaker.replace("_", " ").title()
        book_worst_name = worst_alert.sportsbook_bookmaker.replace("_", " ").title()

        # Odds string from raw snapshot
        def _odds_str(alert: Alert) -> str:
            if not alert.raw_snapshot_refs or "odds" not in alert.raw_snapshot_refs:
                return ""
            ov = alert.raw_snapshot_refs["odds"].get("odds_value")
            if ov is None:
                return ""
            v = float(ov)
            return f"{v:+.0f}" if abs(v) > 10 else f"{v:.2f}"

        book_best = f"{book_best_name} {_odds_str(best_alert)}".strip() or book_best_name
        book_worst = f"{book_worst_name} {_odds_str(worst_alert)}".strip() or book_worst_name

        # Edge in cents and bps (use median)
        edges_bps = [a.edge_bps for a in group]
        edges_bps.sort()
        mid_e = len(edges_bps) // 2
        median_bps = (edges_bps[mid_e] + edges_bps[mid_e - 1]) / 2.0 if len(edges_bps) % 2 == 0 else edges_bps[mid_e]
        edge_cents = median_bps / 100.0
        edge_bps = median_bps

        # Kalshi action string
        if direction == Direction.KALSHI_RICH:
            kalshi_action = f"SELL {selection} YES @ {kalshi_price_cents}c"
            hedge_action = f"Bet {selection} ML on {book_best_name} at {_odds_str(best_alert)}"
        else:
            kalshi_action = f"BUY {selection} YES @ {kalshi_price_cents}c"
            hedge_action = f"Bet opposite of {selection} on {book_best_name} at {_odds_str(best_alert)}"

        hedge_odds = _odds_str(best_alert) or "—"

        # P&L per 100 shares (edge in cents = cents per share; 100 shares = edge_cents dollars)
        pnl_per_100_shares = edge_cents
        max_shares = kalshi_liquidity

        # Confidence: best in group (HIGH > MED > LOW)
        conf_order = {Confidence.LOW: 0, Confidence.MED: 1, Confidence.HIGH: 2}
        confidence = max((a.confidence for a in group), key=lambda c: conf_order.get(c, 0))

        # Rank score: edge_cents * sqrt(liquidity) * (1 + log(book_count))
        rank_score = edge_cents * math.sqrt(max(1, kalshi_liquidity)) * (1 + math.log1p(book_count))

        game_label = _game_label_from_market_key(market_key)
        kalshi_url = _kalshi_url_from_ticker(kalshi_ticker)

        opportunities.append(
            Opportunity(
                market_key=market_key,
                game_label=game_label,
                direction=direction,
                kalshi_action=kalshi_action,
                kalshi_ticker=kalshi_ticker,
                kalshi_price_cents=kalshi_price_cents,
                kalshi_spread_cents=kalshi_spread_cents,
                kalshi_liquidity=kalshi_liquidity,
                book_fair_prob=book_fair_prob,
                book_count=book_count,
                book_best=book_best,
                book_worst=book_worst,
                edge_cents=edge_cents,
                edge_bps=edge_bps,
                hedge_action=hedge_action,
                hedge_odds=hedge_odds,
                pnl_per_100_shares=pnl_per_100_shares,
                max_shares=max_shares,
                confidence=confidence,
                rank_score=rank_score,
                raw_alert_count=len(group),
                kalshi_url=kalshi_url,
            )
        )

    opportunities.sort(key=lambda o: o.rank_score, reverse=True)
    return opportunities


class Scanner:
    """
    Core scanner for detecting Kalshi vs sportsbook discrepancies.
    
    Alert-only, no execution.
    """

    def __init__(
        self,
        kalshi_slippage_buffer: float = 0.005,  # 0.5%
        sportsbook_execution_friction: float = 0.01,  # 1%
        min_edge_bps: float = 50.0,  # 0.5%
        min_liquidity: int = 10,
        max_staleness_seconds: float = 60.0,
    ) -> None:
        self.kalshi_slippage_buffer = kalshi_slippage_buffer
        self.sportsbook_execution_friction = sportsbook_execution_friction
        self.min_edge_bps = min_edge_bps
        self.min_liquidity = min_liquidity
        self.max_staleness_seconds = max_staleness_seconds

    def compare(
        self,
        market_key: str,
        kalshi_tob: KalshiTopOfBook,
        odds_quotes: list[OddsQuote],
        market_mapping: dict,
    ) -> list[Alert]:
        """
        Compare Kalshi orderbook vs sportsbook odds quotes.
        
        Returns list of alerts if thresholds are met.
        """
        alerts: list[Alert] = []

        # Validate staleness
        now = datetime.now(timezone.utc)
        kalshi_age = (now - kalshi_tob.timestamp).total_seconds()
        if kalshi_age > self.max_staleness_seconds:
            return []

        if not kalshi_tob.is_valid:
            return []

        # Get Kalshi prices with slippage buffer
        # For "buy YES", use ask + buffer
        kalshi_yes_ask_adj = min(1.0, kalshi_tob.yes_ask + self.kalshi_slippage_buffer) if kalshi_tob.yes_ask else None  # type: ignore
        # For "sell YES" (implied), use bid - buffer
        kalshi_yes_bid_adj = max(0.0, kalshi_tob.yes_bid - self.kalshi_slippage_buffer) if kalshi_tob.yes_bid else None  # type: ignore

        if kalshi_yes_ask_adj is None:
            return []

        # Check liquidity
        if kalshi_tob.yes_ask_size < self.min_liquidity:
            return []

        # Process odds quotes (normalize naive timestamps to UTC for subtraction)
        for quote in odds_quotes:
            qt = quote.timestamp
            if qt.tzinfo is None:
                qt = qt.replace(tzinfo=timezone.utc)
            odds_age = (now - qt).total_seconds()
            if odds_age > self.max_staleness_seconds:
                continue

            # Convert odds to no-vig probability
            normalized = self._normalize_odds(quote, odds_quotes)
            if normalized is None:
                continue

            # Apply sportsbook execution friction (conservative)
            sportsbook_p_adj = normalized.p_no_vig * (1 - self.sportsbook_execution_friction)

            # Compute edges in both directions
            
            # Direction 1: Kalshi cheap (buy YES on Kalshi, implied "sell" on sportsbook)
            # Edge = sportsbook_p - kalshi_yes_ask
            edge_kalshi_cheap = sportsbook_p_adj - kalshi_yes_ask_adj
            edge_bps_cheap = edge_kalshi_cheap * 10_000

            if edge_bps_cheap >= self.min_edge_bps:
                alert = self._build_alert(
                    market_key=market_key,
                    direction=Direction.KALSHI_CHEAP,
                    kalshi_tob=kalshi_tob,
                    kalshi_price=kalshi_yes_ask_adj,
                    kalshi_side="YES",
                    kalshi_liquidity=kalshi_tob.yes_ask_size,
                    quote=quote,
                    normalized=normalized,
                    edge_bps=edge_bps_cheap,
                    kalshi_age=kalshi_age,
                    odds_age=odds_age,
                )
                alerts.append(alert)

            # Direction 2: Kalshi rich (sell YES on Kalshi, implied "buy" on sportsbook)
            # Edge = kalshi_yes_bid - sportsbook_p
            if kalshi_yes_bid_adj is not None and kalshi_tob.yes_bid_size >= self.min_liquidity:
                edge_kalshi_rich = kalshi_yes_bid_adj - sportsbook_p_adj
                edge_bps_rich = edge_kalshi_rich * 10_000

                if edge_bps_rich >= self.min_edge_bps:
                    alert = self._build_alert(
                        market_key=market_key,
                        direction=Direction.KALSHI_RICH,
                        kalshi_tob=kalshi_tob,
                        kalshi_price=kalshi_yes_bid_adj,
                        kalshi_side="YES",
                        kalshi_liquidity=kalshi_tob.yes_bid_size,
                        quote=quote,
                        normalized=normalized,
                        edge_bps=edge_bps_rich,
                        kalshi_age=kalshi_age,
                        odds_age=odds_age,
                    )
                    alerts.append(alert)

        return alerts

    def _normalize_odds(
        self,
        target_quote: OddsQuote,
        all_quotes: list[OddsQuote],
    ) -> Optional[NormalizedProb]:
        """
        Convert odds to no-vig probability.
        
        For two-way markets, finds the opposite side and removes vig.
        For multi-way, uses all outcomes (future enhancement).
        """
        # Convert to implied prob
        if target_quote.odds_format == OddsFormat.AMERICAN:
            p_implied = american_to_prob(target_quote.odds_value)
        elif target_quote.odds_format == OddsFormat.DECIMAL:
            p_implied = decimal_to_prob(target_quote.odds_value)
        else:
            return None

        # Find opposite side for two-way vig removal
        # For h2h markets, look for the other team's odds from same bookmaker
        opposite_quote = None
        for q in all_quotes:
            if (
                q.bookmaker == target_quote.bookmaker
                and q.event_id == target_quote.event_id
                and q.market_type == target_quote.market_type
                and q.selection != target_quote.selection
            ):
                opposite_quote = q
                break

        if opposite_quote:
            # Two-way vig removal
            if opposite_quote.odds_format == OddsFormat.AMERICAN:
                p_opposite = american_to_prob(opposite_quote.odds_value)
            elif opposite_quote.odds_format == OddsFormat.DECIMAL:
                p_opposite = decimal_to_prob(opposite_quote.odds_value)
            else:
                p_opposite = 1.0 - p_implied

            p_no_vig, p_opposite_nv = no_vig_two_way(p_implied, p_opposite)
            overround = p_implied + p_opposite
        else:
            # No opposite side found, use raw implied
            p_no_vig = p_implied
            overround = 1.0

        return NormalizedProb(
            p_implied=p_implied,
            p_no_vig=p_no_vig,
            overround=overround,
            method=VigMethod.PROPORTIONAL,
            selection=target_quote.selection,
            bookmaker=target_quote.bookmaker,
            timestamp=target_quote.timestamp,
        )

    def _build_alert(
        self,
        market_key: str,
        direction: Direction,
        kalshi_tob: KalshiTopOfBook,
        kalshi_price: float,
        kalshi_side: str,
        kalshi_liquidity: int,
        quote: OddsQuote,
        normalized: NormalizedProb,
        edge_bps: float,
        kalshi_age: float,
        odds_age: float,
    ) -> Alert:
        """Build an alert object."""
        edge_pct = edge_bps / 100.0

        # Confidence scoring
        confidence, confidence_score = self._compute_confidence(
            edge_bps=edge_bps,
            kalshi_age=kalshi_age,
            odds_age=odds_age,
            kalshi_liquidity=kalshi_liquidity,
            overround=normalized.overround,
        )

        return Alert(
            alert_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc),
            market_key=market_key,
            direction=direction,
            edge_pct=edge_pct,
            edge_bps=edge_bps,
            confidence=confidence,
            confidence_score=confidence_score,
            kalshi_contract_id=kalshi_tob.contract_id,
            kalshi_side=kalshi_side,
            kalshi_price=kalshi_price,
            kalshi_liquidity=kalshi_liquidity,
            sportsbook_bookmaker=quote.bookmaker,
            sportsbook_selection=quote.selection,
            sportsbook_p_no_vig=normalized.p_no_vig,
            notes=f"Overround: {normalized.overround:.4f}",
            raw_snapshot_refs={
                "kalshi": kalshi_tob.model_dump(),
                "odds": quote.model_dump(),
                "normalized": normalized.model_dump(),
            },
            kalshi_data_age_seconds=kalshi_age,
            sportsbook_data_age_seconds=odds_age,
        )

    def _compute_confidence(
        self,
        edge_bps: float,
        kalshi_age: float,
        odds_age: float,
        kalshi_liquidity: int,
        overround: float,
    ) -> tuple[Confidence, float]:
        """
        Compute confidence level and score.
        
        Factors:
        - Larger edge = higher confidence
        - Fresher data = higher confidence
        - Higher liquidity = higher confidence
        - Lower overround (less vig) = higher confidence
        """
        score = 0.0

        # Edge contribution (0-0.4)
        if edge_bps >= 200:
            score += 0.4
        elif edge_bps >= 100:
            score += 0.3
        elif edge_bps >= 50:
            score += 0.2
        else:
            score += 0.1

        # Freshness contribution (0-0.3)
        max_age = max(kalshi_age, odds_age)
        if max_age < 10:
            score += 0.3
        elif max_age < 30:
            score += 0.2
        elif max_age < 60:
            score += 0.1

        # Liquidity contribution (0-0.2)
        if kalshi_liquidity >= 100:
            score += 0.2
        elif kalshi_liquidity >= 50:
            score += 0.15
        elif kalshi_liquidity >= 20:
            score += 0.1
        else:
            score += 0.05

        # Overround contribution (0-0.1)
        # Lower overround = less vig = more reliable
        if overround < 1.03:
            score += 0.1
        elif overround < 1.05:
            score += 0.05

        # Classify
        if score >= 0.75:
            confidence = Confidence.HIGH
        elif score >= 0.50:
            confidence = Confidence.MED
        else:
            confidence = Confidence.LOW

        return confidence, score
