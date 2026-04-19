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
    kalshi_private_key_path: str = Field(default="", description="Path to Kalshi RSA private key (PEM file)")
    kalshi_private_key_pem: str = Field(
        default="",
        description=(
            "Raw PEM text for Kalshi RSA private key (use on Render when you cannot mount a file). "
            "If set, this takes precedence over kalshi_private_key_path. Use \\n for newlines in a single-line env value."
        ),
    )
    kalshi_base_url: str = Field(default="https://api.elections.kalshi.com/trade-api/v2")
    kalshi_requests_per_second: float = Field(default=5.0)

    # ── The Odds API ────────────────────────────────────────────────────────
    odds_api_key: str = Field(default="", description="The Odds API key")
    odds_api_base_url: str = Field(default="https://api.the-odds-api.com/v4")
    odds_api_requests_per_second: float = Field(default=1.0)

    # ── OddsPapi (fallback) ─────────────────────────────────────────────
    oddspapi_api_key: str = Field(default="", description="OddsPapi API key (fallback when Odds API is exhausted)")

    # ── Matching ────────────────────────────────────────────────────────────
    mapping_file: str = Field(default="mappings.yaml")
    fuzzy_match_enabled: bool = Field(default=False)
    fuzzy_match_threshold: float = Field(default=0.75)

    # ── Scanner ─────────────────────────────────────────────────────────────
    background_scan_enabled: bool = Field(
        default=False,
        description=(
            "If True, the dashboard runs the periodic Kalshi+Odds sportsbook scan loop "
            "(uses Odds API / OddsPapi on every poll). If False, only a Kalshi connection "
            "is kept for Insider Watch / tape; set True to restore full scanner behavior."
        ),
    )
    poll_interval_seconds: float = Field(default=60.0, description="Seconds between poll cycles")
    kalshi_slippage_buffer: float = Field(default=0.005, description="Slippage buffer for Kalshi (0.005 = 0.5%)")
    sportsbook_execution_friction: float = Field(default=0.01, description="Execution friction buffer for sportsbook")
    min_edge_bps: float = Field(default=50.0, description="Min edge in basis points to alert")
    min_liquidity: int = Field(default=10, description="Min Kalshi liquidity (shares)")
    max_staleness_seconds: float = Field(default=60.0, description="Max data age in seconds")
    poly_enabled: bool = Field(default=True, description="Enable Kalshi vs Polymarket arb scan")
    poly_min_edge_bps: float = Field(default=20.0, description="Min edge in bps for PM arb")
    poly_min_liquidity_usd: float = Field(default=100.0, description="Min PM liquidity in USD")
    poly_match_threshold: float = Field(default=82.0, description="RapidFuzz threshold for PM matching (0-100)")

    # ── Persistence ─────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///kalshi_odds.db",
        description=(
            "SQLite file URL (local/default) or Postgres URL for Neon, e.g. "
            "postgresql://user:pass@host/db?sslmode=require"
        ),
    )

    # ── Output ──────────────────────────────────────────────────────────────
    output_jsonl: str = Field(default="alerts.jsonl")

    # ── Execution & automation ──────────────────────────────────────────────
    max_notional_per_trade: float = Field(default=100.0, description="Max dollars per Kalshi order when executing")
    execution_enabled: bool = Field(default=False, description="Allow execute command (must be explicitly enabled)")
    auto_map_enabled: bool = Field(default=True, description="Allow auto-mapping of games to odds events")
    default_sport: str = Field(
        default="basketball_nba",
        description="Comma-separated sport keys for scan/run (e.g. basketball_nba,baseball_mlb)",
    )
    bankroll_dollars: float = Field(default=500.0, description="Bankroll for Kelly sizing")
    kelly_fraction: float = Field(default=0.25, description="Fraction of full Kelly (e.g. 0.25 = quarter-Kelly)")
    dashboard_port: int = Field(default=8080, description="Port for KalshiInsider dashboard")
    auto_execute_min_confidence: str = Field(
        default="high",
        description="Minimum confidence for auto-execute in run loop: low, med, high",
    )

    # ── Web / security ──────────────────────────────────────────────────────
    cors_origins: str = Field(
        default="",
        description="Comma-separated allowed origins for CORS (exact matches). Use with cors_origin_regex for preview URLs.",
    )
    cors_origin_regex: str = Field(
        default="",
        description=(
            "Optional regex for allowed Origin (e.g. https://.*\\.vercel\\.app for all Vercel deploys). "
            "Set this OR cors_origins when the SPA is on another domain."
        ),
    )
    session_cookie_secure: bool = Field(
        default=False,
        description="Mark session cookie as Secure (required when serving over HTTPS).",
    )
    session_cookie_samesite: str = Field(
        default="lax",
        description='Session cookie SameSite attribute: "lax", "strict", or "none". Use "none" for cross-site (requires secure=true).',
    )
    public_registration_enabled: bool = Field(
        default=False,
        description="If False, /api/auth/register requires a valid invite token issued from the waitlist.",
    )
    admin_bootstrap_usernames: str = Field(
        default="",
        description="Comma-separated usernames automatically promoted to admin on startup.",
    )
    invite_ttl_hours: int = Field(
        default=168,
        description="How long an approved invite token remains valid (default 7 days).",
    )

    # ── Helpers ─────────────────────────────────────────────────────────────

    @property
    def kalshi_configured(self) -> bool:
        if not self.kalshi_api_key_id:
            return False
        if (self.kalshi_private_key_pem or "").strip():
            return True
        return bool(self.kalshi_private_key_path)

    @property
    def odds_api_configured(self) -> bool:
        return bool(self.odds_api_key) or bool(self.oddspapi_api_key)

    @property
    def mapping_path(self) -> Path:
        return Path(self.mapping_file)

    @property
    def sport_list(self) -> list[str]:
        return [s.strip() for s in self.default_sport.split(",") if s.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_origin_regex_stripped(self) -> str:
        return (self.cors_origin_regex or "").strip()

    @property
    def admin_bootstrap_list(self) -> list[str]:
        return [u.strip().lower() for u in self.admin_bootstrap_usernames.split(",") if u.strip()]

    @property
    def session_samesite_normalized(self) -> str:
        value = (self.session_cookie_samesite or "lax").strip().lower()
        if value not in {"lax", "strict", "none"}:
            return "lax"
        return value


def get_settings(**overrides) -> Settings:  # type: ignore
    """Factory with optional overrides."""
    return Settings(**overrides)
