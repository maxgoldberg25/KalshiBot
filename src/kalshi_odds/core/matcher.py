"""
Market matcher – pairs Kalshi contracts with sportsbook selections.

Manual YAML mapping + optional fuzzy candidate suggestions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from rapidfuzz import fuzz

from kalshi_odds.models.kalshi import KalshiContract
from kalshi_odds.models.odds import OddsQuote


class MarketMatcher:
    """
    Maps Kalshi contracts to sportsbook selections.
    
    Primary: manual YAML mappings.
    Optional: fuzzy title matching for candidate suggestions (log-only).
    """

    def __init__(
        self,
        mapping_file: Optional[Path] = None,
        fuzzy_enabled: bool = False,
        fuzzy_threshold: float = 0.75,
    ) -> None:
        self._mapping_file = mapping_file
        self._fuzzy_enabled = fuzzy_enabled
        self._fuzzy_threshold = fuzzy_threshold
        
        # market_key → mapping dict
        self._mappings: dict[str, dict] = {}
        
        # Reverse indexes
        self._kalshi_to_key: dict[str, str] = {}  # contract_id → market_key
        self._odds_to_key: dict[tuple[str, str, str], str] = {}  # (event_id, market_type, selection) → market_key

    def load_mappings(self) -> int:
        """
        Load manual mappings from YAML.
        
        Returns count of mappings loaded.
        """
        if self._mapping_file is None or not self._mapping_file.exists():
            return 0

        with open(self._mapping_file) as f:
            data = yaml.safe_load(f) or {}

        markets = data.get("markets", [])
        count = 0

        for entry in markets:
            market_key = entry.get("market_key", "")
            if not market_key:
                continue

            self._mappings[market_key] = entry

            # Index Kalshi side
            kalshi = entry.get("kalshi", {})
            kalshi_contract_id = kalshi.get("contract_id", "")
            if kalshi_contract_id:
                self._kalshi_to_key[kalshi_contract_id] = market_key

            # Index odds side
            odds = entry.get("odds", {})
            event_id = odds.get("event_id", "")
            market_type = odds.get("market_type", "")
            selection = odds.get("selection", "")
            if event_id and market_type and selection:
                self._odds_to_key[(event_id, market_type, selection)] = market_key

            count += 1

        return count

    def get_market_key_for_kalshi(self, contract_id: str) -> Optional[str]:
        """Get market_key for a Kalshi contract ID."""
        return self._kalshi_to_key.get(contract_id)

    def get_market_key_for_odds(
        self, event_id: str, market_type: str, selection: str
    ) -> Optional[str]:
        """Get market_key for a sportsbook selection."""
        return self._odds_to_key.get((event_id, market_type, selection))

    def get_mapping(self, market_key: str) -> Optional[dict]:
        """Get full mapping dict for a market_key."""
        return self._mappings.get(market_key)

    def get_all_market_keys(self) -> list[str]:
        """Return all mapped market keys."""
        return list(self._mappings.keys())

    # ── Fuzzy matching (candidate suggestions) ─────────────────────────────

    def find_fuzzy_candidates(
        self,
        kalshi_contracts: list[KalshiContract],
        odds_quotes: list[OddsQuote],
    ) -> list[tuple[KalshiContract, OddsQuote, float]]:
        """
        Find potential matches using fuzzy title similarity.
        
        Returns list of (contract, quote, score) tuples.
        
        NOTE: This is for manual review only. Do NOT auto-map.
        """
        if not self._fuzzy_enabled:
            return []

        candidates: list[tuple[KalshiContract, OddsQuote, float]] = []

        for contract in kalshi_contracts:
            # Skip if already mapped
            if contract.contract_id in self._kalshi_to_key:
                continue

            for quote in odds_quotes:
                # Skip if already mapped
                key = (quote.event_id, quote.market_type.value, quote.selection)
                if key in self._odds_to_key:
                    continue

                # Compare titles
                score = fuzz.token_sort_ratio(
                    contract.title.lower(),
                    quote.event_title.lower(),
                ) / 100.0

                if score >= self._fuzzy_threshold:
                    candidates.append((contract, quote, score))

        # Sort by score descending
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        return candidates[:50]  # Limit to top 50
