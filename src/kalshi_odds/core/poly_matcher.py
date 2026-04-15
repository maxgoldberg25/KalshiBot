"""Matcher for Kalshi markets vs Polymarket questions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from rapidfuzz import fuzz, process

from kalshi_odds.adapters.polymarket import PolyMarket
from kalshi_odds.models.kalshi import KalshiContract


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "for", "on", "at", "by", "is", "will",
    "be", "and", "or", "this", "that", "with", "yes", "no", "vs", "over", "under",
}


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split(" ") if t and t not in _STOPWORDS and len(t) > 2}


def _is_sports_market(m: PolyMarket) -> bool:
    t = " ".join(m.tags)
    return any(k in t for k in ("sports", "nba", "nfl", "mlb", "nhl", "ncaab", "ncaaf"))


def infer_category(m: PolyMarket) -> str:
    t = " ".join(m.tags)
    if "sports" in t:
        return "sports"
    if any(k in t for k in ("politics", "election", "trump", "biden")):
        return "politics"
    if any(k in t for k in ("crypto", "bitcoin", "ethereum", "defi")):
        return "crypto"
    if any(k in t for k in ("economy", "finance", "fed", "rates", "inflation")):
        return "economy"
    return "other"


@dataclass
class PolyKalshiMatch:
    poly: PolyMarket
    kalshi: KalshiContract
    match_type: str
    match_confidence: float


class PolyMatcher:
    """Find best Kalshi counterpart for each Polymarket market."""

    def __init__(self, fuzzy_threshold: float = 82.0) -> None:
        self._fuzzy_threshold = fuzzy_threshold

    def match(
        self,
        poly_markets: list[PolyMarket],
        kalshi_contracts: list[KalshiContract],
    ) -> list[PolyKalshiMatch]:
        if not poly_markets or not kalshi_contracts:
            return []
        kalshi_by_norm = {_norm(k.title): k for k in kalshi_contracts if k.title}
        choices = list(kalshi_by_norm.keys())
        if not choices:
            return []

        out: list[PolyKalshiMatch] = []
        now = datetime.now(timezone.utc)
        for pm in poly_markets:
            qn = _norm(pm.question)
            if not qn:
                continue
            best = process.extractOne(qn, choices, scorer=fuzz.WRatio, score_cutoff=self._fuzzy_threshold)
            if not best:
                continue
            matched_title, score, _ = best
            kc = kalshi_by_norm.get(matched_title)
            if not kc:
                continue
            # Keyword-overlap gate to reduce false semantic collisions.
            overlap = _tokens(pm.question) & _tokens(kc.title)
            if len(overlap) < 1:
                continue

            # Keep obvious mismatches out for non-sports: end dates should be somewhat close.
            if pm.end_date and kc.close_time:
                delta_days = abs((pm.end_date - kc.close_time).days)
                if not _is_sports_market(pm) and delta_days > 30:
                    continue
                if _is_sports_market(pm) and delta_days > 3:
                    continue
            elif pm.end_date and not kc.close_time:
                continue
            elif not pm.end_date and kc.close_time and kc.close_time < now - timedelta(days=1):
                continue

            match_type = "sports_structured" if _is_sports_market(pm) and score >= 90 else "fuzzy"
            out.append(
                PolyKalshiMatch(
                    poly=pm,
                    kalshi=kc,
                    match_type=match_type,
                    match_confidence=max(0.0, min(1.0, float(score) / 100.0)),
                )
            )

        # Deduplicate by polymarket id keeping highest-confidence match.
        by_pm: dict[str, PolyKalshiMatch] = {}
        for m in out:
            cur = by_pm.get(m.poly.market_id)
            if cur is None or m.match_confidence > cur.match_confidence:
                by_pm[m.poly.market_id] = m
        return list(by_pm.values())
