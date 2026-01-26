"""
Configuration management using pydantic-settings.
All secrets and parameters are loaded from environment variables.
"""

from datetime import time
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    """Trading mode: paper (simulated) or live (real money)."""
    PAPER = "paper"
    LIVE = "live"
    DRY_RUN = "dry_run"  # Print trades without executing


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All sensitive values (API keys) MUST be set via environment.
    Risk parameters have safe defaults but should be reviewed.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="KALSHI_BOT_",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars from other configs
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # API CREDENTIALS (required for live trading)
    # Kalshi uses RSA key signing - you need both an API Key ID and Private Key
    # Get these from: https://kalshi.com → Account & Security → API Keys
    # ─────────────────────────────────────────────────────────────────────────
    
    kalshi_api_key_id: str = Field(
        default="",
        description="Kalshi API Key ID (UUID from API Keys page)"
    )
    kalshi_private_key_path: str = Field(
        default="",
        description="Path to your Kalshi private key file (.pem or .key)"
    )
    kalshi_api_base_url: str = Field(
        default="https://api.elections.kalshi.com/trade-api/v2",
        description="Kalshi API base URL (use demo.kalshi.com for testing)"
    )
    
    # Legacy field for backwards compatibility
    kalshi_api_key: str = Field(
        default="",
        description="Deprecated - use kalshi_api_key_id instead"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRADING MODE
    # ─────────────────────────────────────────────────────────────────────────
    
    mode: TradingMode = Field(
        default=TradingMode.PAPER,
        description="Trading mode: paper, live, or dry_run"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # SCHEDULING
    # ─────────────────────────────────────────────────────────────────────────
    
    timezone: str = Field(
        default="America/New_York",
        description="Timezone for scheduling and market hours"
    )
    run_time: str = Field(
        default="08:30",
        description="Daily run time in HH:MM format (local timezone)"
    )
    trading_cutoff_minutes: int = Field(
        default=30,
        description="Stop opening new positions N minutes before market close"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # MARKET FILTERS
    # ─────────────────────────────────────────────────────────────────────────
    
    min_volume_24h: int = Field(
        default=100,
        description="Minimum 24h volume to consider a market"
    )
    max_spread_cents: int = Field(
        default=10,
        description="Maximum bid-ask spread in cents"
    )
    min_orderbook_depth: int = Field(
        default=50,
        description="Minimum contracts at best bid + ask"
    )
    category_whitelist: list[str] = Field(
        default_factory=list,
        description="Only trade these categories (empty = all)"
    )
    category_blacklist: list[str] = Field(
        default_factory=lambda: ["sports"],  # Sports often have external info edge
        description="Never trade these categories"
    )
    market_blacklist: list[str] = Field(
        default_factory=list,
        description="Specific market tickers to avoid"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # RISK MANAGEMENT (CRITICAL - review carefully)
    # ─────────────────────────────────────────────────────────────────────────
    
    max_daily_loss_dollars: float = Field(
        default=50.0,
        description="Stop trading if daily loss exceeds this amount"
    )
    max_per_market_exposure_dollars: float = Field(
        default=20.0,
        description="Maximum position size per market"
    )
    max_total_exposure_dollars: float = Field(
        default=100.0,
        description="Maximum total capital at risk"
    )
    max_open_positions: int = Field(
        default=10,
        description="Maximum number of simultaneous positions"
    )
    max_trades_per_day: int = Field(
        default=20,
        description="Maximum trades to place per day"
    )
    default_position_size_dollars: float = Field(
        default=5.0,
        description="Default position size if Kelly sizing is disabled"
    )
    use_kelly_sizing: bool = Field(
        default=True,
        description="Use Kelly criterion for position sizing"
    )
    kelly_fraction: float = Field(
        default=0.25,
        description="Fraction of Kelly to use (0.25 = quarter Kelly)"
    )
    use_limit_orders_only: bool = Field(
        default=True,
        description="Only use limit orders (safer than market orders)"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # STRATEGY THRESHOLDS
    # ─────────────────────────────────────────────────────────────────────────
    
    min_expected_value: float = Field(
        default=0.02,
        description="Minimum expected value (edge) to trade (2% = 0.02)"
    )
    min_win_rate: float = Field(
        default=0.70,
        description="Minimum backtested win rate to trade"
    )
    min_backtest_samples: int = Field(
        default=30,
        description="Minimum historical samples for backtest to be valid"
    )
    max_drawdown_percent: float = Field(
        default=0.20,
        description="Maximum drawdown allowed in backtest (20% = 0.20)"
    )
    confidence_threshold: float = Field(
        default=0.60,
        description="Minimum strategy confidence to trade"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # DATA & PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────────
    
    database_url: str = Field(
        default="sqlite:///kalshi_bot.db",
        description="Database connection string"
    )
    snapshot_interval_minutes: int = Field(
        default=5,
        description="Interval for recording orderbook snapshots"
    )
    data_retention_days: int = Field(
        default=90,
        description="Days to retain historical data"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # OBSERVABILITY
    # ─────────────────────────────────────────────────────────────────────────
    
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_format: str = Field(
        default="console",
        description="Log format: json or console"
    )
    slack_webhook_url: Optional[str] = Field(
        default=None,
        description="Slack webhook for alerts (optional)"
    )
    enable_daily_report: bool = Field(
        default=True,
        description="Generate daily performance report"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────────────────────────────────
    
    @model_validator(mode="after")
    def sync_api_key_fields(self):
        """Use legacy kalshi_api_key as fallback for kalshi_api_key_id."""
        if not self.kalshi_api_key_id and self.kalshi_api_key:
            self.kalshi_api_key_id = self.kalshi_api_key
        return self
    
    @field_validator("min_win_rate")
    @classmethod
    def validate_win_rate(cls, v: float) -> float:
        if not 0.5 <= v <= 1.0:
            raise ValueError("min_win_rate must be between 0.5 and 1.0")
        return v
    
    @field_validator("kelly_fraction")
    @classmethod
    def validate_kelly(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError("kelly_fraction must be between 0 and 1")
        return v
    
    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: TradingMode) -> TradingMode:
        return v
    
    def is_live(self) -> bool:
        """Check if running in live trading mode."""
        return self.mode == TradingMode.LIVE
    
    def is_paper(self) -> bool:
        """Check if running in paper trading mode."""
        return self.mode == TradingMode.PAPER
    
    def is_dry_run(self) -> bool:
        """Check if running in dry-run mode (no execution)."""
        return self.mode == TradingMode.DRY_RUN
    
    def get_run_time(self) -> time:
        """Parse run time string to time object."""
        parts = self.run_time.split(":")
        return time(int(parts[0]), int(parts[1]))


# Global settings instance
settings = Settings()
