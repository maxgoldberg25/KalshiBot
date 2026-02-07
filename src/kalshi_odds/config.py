"""Configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings."""

    model_config = SettingsConfigDict(
        env_prefix="KALSHI_ODDS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Kalshi ──────────────────────────────────────────────────────────────
    kalshi_api_key_id: str = Field(default="", description="Kalshi API Key ID")
    kalshi_private_key_path: str = Field(default="", description="Path to Kalshi RSA private key")
    kalshi_base_url: str = Field(default="https://api.elections.kalshi.com/trade-api/v2")
    kalshi_requests_per_second: float = Field(default=5.0)

    # ── The Odds API ────────────────────────────────────────────────────────
    odds_api_key: str = Field(default="", description="The Odds API key")
    odds_api_base_url: str = Field(default="https://api.the-odds-api.com/v4")
    odds_api_requests_per_second: float = Field(default=1.0)

    # ── Matching ────────────────────────────────────────────────────────────
    mapping_file: str = Field(default="mappings.yaml")
    fuzzy_match_enabled: bool = Field(default=False)
    fuzzy_match_threshold: float = Field(default=0.75)

    # ── Scanner ─────────────────────────────────────────────────────────────
    poll_interval_seconds: float = Field(default=60.0, description="Seconds between poll cycles")
    kalshi_slippage_buffer: float = Field(default=0.005, description="Slippage buffer for Kalshi (0.005 = 0.5%)")
    sportsbook_execution_friction: float = Field(default=0.01, description="Execution friction buffer for sportsbook")
    min_edge_bps: float = Field(default=50.0, description="Min edge in basis points to alert")
    min_liquidity: int = Field(default=10, description="Min Kalshi liquidity (shares)")
    max_staleness_seconds: float = Field(default=60.0, description="Max data age in seconds")

    # ── Persistence ─────────────────────────────────────────────────────────
    database_url: str = Field(default="sqlite+aiosqlite:///kalshi_odds.db")

    # ── Output ──────────────────────────────────────────────────────────────
    output_jsonl: str = Field(default="alerts.jsonl")

    # ── Execution & automation ──────────────────────────────────────────────
    max_notional_per_trade: float = Field(default=100.0, description="Max dollars per Kalshi order when executing")
    execution_enabled: bool = Field(default=False, description="Allow execute command (must be explicitly enabled)")
    auto_map_enabled: bool = Field(default=True, description="Allow auto-mapping of games to odds events")
    default_sport: str = Field(default="basketball_nba", description="Default sport for scan/run")

    # ── Helpers ─────────────────────────────────────────────────────────────

    @property
    def kalshi_configured(self) -> bool:
        return bool(self.kalshi_api_key_id and self.kalshi_private_key_path)

    @property
    def odds_api_configured(self) -> bool:
        return bool(self.odds_api_key)

    @property
    def mapping_path(self) -> Path:
        return Path(self.mapping_file)


def get_settings(**overrides) -> Settings:  # type: ignore
    """Factory with optional overrides."""
    return Settings(**overrides)
