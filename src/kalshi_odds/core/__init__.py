"""Core utilities."""

from kalshi_odds.core.odds_math import (
    american_to_prob,
    decimal_to_prob,
    prob_to_american,
    prob_to_decimal,
    no_vig_two_way,
    no_vig_multi_way,
)
from kalshi_odds.core.scanner import Scanner, aggregate_opportunities
from kalshi_odds.core.automapper import auto_map, build_mappings, SPORT_TO_SERIES

__all__ = [
    "american_to_prob",
    "decimal_to_prob",
    "prob_to_american",
    "prob_to_decimal",
    "no_vig_two_way",
    "no_vig_multi_way",
    "Scanner",
    "aggregate_opportunities",
    "auto_map",
    "build_mappings",
    "SPORT_TO_SERIES",
]
