"""Normalized probability models after vig removal."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class VigMethod(str, Enum):
    """Vig removal method."""
    PROPORTIONAL = "proportional"  # Most common for 2-way
    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"


class NormalizedProb(BaseModel):
    """
    Normalized probability after vig removal.
    
    Contains both raw implied prob and no-vig prob.
    """
    # Raw
    p_implied: float = Field(ge=0, le=1, description="Raw implied probability")
    
    # No-vig
    p_no_vig: float = Field(ge=0, le=1, description="Probability after vig removal")
    
    # Metadata
    overround: float = Field(description="Overround (sum of all probs)")
    method: VigMethod
    
    # Source reference
    selection: str
    bookmaker: str
    
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
