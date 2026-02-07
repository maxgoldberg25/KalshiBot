"""
Odds conversion and vig removal mathematics.

All probability values are decimals in [0, 1].
American odds are integers (e.g., -110, +150).
Decimal odds are floats >= 1.0 (e.g., 1.91, 2.50).
"""

from __future__ import annotations


def american_to_prob(odds: float) -> float:
    """
    Convert American odds to implied probability.
    
    Args:
        odds: American odds (-110, +150, etc.)
        
    Returns:
        Implied probability in [0, 1]
        
    Examples:
        >>> american_to_prob(-110)  # Favorite
        0.5238...
        >>> american_to_prob(+150)  # Underdog
        0.4
    """
    if odds < 0:
        # Favorite: prob = |odds| / (|odds| + 100)
        return abs(odds) / (abs(odds) + 100)
    else:
        # Underdog: prob = 100 / (odds + 100)
        return 100 / (odds + 100)


def decimal_to_prob(odds: float) -> float:
    """
    Convert decimal odds to implied probability.
    
    Args:
        odds: Decimal odds (1.91, 2.50, etc.)
        
    Returns:
        Implied probability in [0, 1]
        
    Examples:
        >>> decimal_to_prob(2.00)
        0.5
        >>> decimal_to_prob(1.91)
        0.5235...
    """
    if odds <= 0:
        raise ValueError(f"Decimal odds must be > 0, got {odds}")
    return 1.0 / odds


def prob_to_american(prob: float) -> float:
    """
    Convert probability to American odds.
    
    Args:
        prob: Probability in [0, 1]
        
    Returns:
        American odds
    """
    if prob <= 0 or prob >= 1:
        raise ValueError(f"Probability must be in (0, 1), got {prob}")
    
    if prob >= 0.5:
        # Favorite (negative odds)
        return -100 * prob / (1 - prob)
    else:
        # Underdog (positive odds)
        return 100 * (1 - prob) / prob


def prob_to_decimal(prob: float) -> float:
    """
    Convert probability to decimal odds.
    
    Args:
        prob: Probability in [0, 1]
        
    Returns:
        Decimal odds
    """
    if prob <= 0 or prob >= 1:
        raise ValueError(f"Probability must be in (0, 1), got {prob}")
    return 1.0 / prob


def no_vig_two_way(p_a: float, p_b: float) -> tuple[float, float]:
    """
    Remove vig from two-way market using proportional method.
    
    Args:
        p_a: Implied probability of outcome A
        p_b: Implied probability of outcome B
        
    Returns:
        (p_a_no_vig, p_b_no_vig) tuple
        
    Examples:
        >>> no_vig_two_way(0.5238, 0.5238)  # Both -110
        (0.5, 0.5)
    """
    overround = p_a + p_b
    
    if overround <= 0:
        raise ValueError(f"Overround must be > 0, got {overround}")
    
    p_a_nv = p_a / overround
    p_b_nv = p_b / overround
    
    return p_a_nv, p_b_nv


def no_vig_multi_way(probs: list[float]) -> tuple[list[float], float]:
    """
    Remove vig from multi-way market using proportional normalization.
    
    Args:
        probs: List of implied probabilities
        
    Returns:
        (no_vig_probs, overround) tuple
        
    Note:
        For markets with >2 outcomes, different vig removal methods can
        produce different results. Proportional is most common but has
        limitations. See:
        https://www.pinnacle.com/en/betting-articles/betting-strategy/how-to-remove-vig
    """
    if not probs:
        raise ValueError("Must provide at least one probability")
    
    overround = sum(probs)
    
    if overround <= 0:
        raise ValueError(f"Overround must be > 0, got {overround}")
    
    no_vig_probs = [p / overround for p in probs]
    
    return no_vig_probs, overround


def get_overround(probs: list[float]) -> float:
    """
    Calculate overround (vigorish) from implied probabilities.
    
    Args:
        probs: List of implied probabilities
        
    Returns:
        Overround value (1.0 = no vig, >1.0 = vig present)
        
    Examples:
        >>> get_overround([0.5, 0.5])  # Fair odds
        1.0
        >>> get_overround([0.5238, 0.5238])  # Both -110
        1.0476...
    """
    return sum(probs)


def get_vig_pct(overround: float) -> float:
    """
    Convert overround to vig percentage.
    
    Args:
        overround: Overround value
        
    Returns:
        Vig as percentage
        
    Examples:
        >>> get_vig_pct(1.0476)  # -110 / -110 market
        4.76
    """
    return (overround - 1.0) * 100.0
