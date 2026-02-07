"""Venue adapters for data ingestion."""

from kalshi_odds.adapters.kalshi import KalshiAdapter
from kalshi_odds.adapters.odds_api import OddsAPIAdapter

__all__ = ["KalshiAdapter", "OddsAPIAdapter"]
