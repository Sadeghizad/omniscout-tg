"""
OmniScout-TG: Centralized Configuration Management
Loads typed configuration from environment variables and .env file.
"""

import os
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Enforce UTF-8 on Windows for Persian RTL text processing
os.environ.setdefault("PYTHONUTF8", "1")


class Settings(BaseSettings):
    """Application settings schema backed by environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --------------------------------------------------------------------------
    # 1. b.ai Unified AI Gateway Settings
    # --------------------------------------------------------------------------
    b_ai_api_key: str | None = Field(
        default=None,
        description="API key for b.ai gateway. If absent, only offline mock tests run.",
    )
    b_ai_base_url: str = Field(
        default="https://api.b.ai/v1",
        description="Base URL for b.ai Unified AI Gateway",
    )
    b_ai_jev_model: str = Field(
        default="jev-latest",
        description="Model name for System 1 fast typed decisions",
    )
    b_ai_deepseek_model: str = Field(
        default="deepseek-v4.1-flash",
        description="Model name for creative hooks and bilingual rationales",
    )
    b_ai_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout budget for HTTP requests to b.ai in seconds",
    )
    b_ai_max_retries: int = Field(
        default=3,
        description="Max retry attempts on transient HTTP gateway errors",
    )
    b_ai_retry_backoff: float = Field(
        default=1.5,
        description="Exponential backoff multiplier for retries",
    )

    # --------------------------------------------------------------------------
    # 2. Telegram Native MTProto & Web Fallback ($0 Discovery Engine)
    # --------------------------------------------------------------------------
    telegram_api_id: int | None = Field(
        default=None,
        description="Telegram API ID from my.telegram.org",
    )
    telegram_api_hash: str | None = Field(
        default=None,
        description="Telegram API Hash from my.telegram.org",
    )
    telegram_phone: str | None = Field(
        default=None,
        description="Telegram Phone Number for session authentication",
    )
    telegram_session_name: str = Field(
        default="omniscout_session",
        description="Session storage file basename for Telethon",
    )

    # --------------------------------------------------------------------------
    # 3. Optional External Intelligence Providers (Secondary / Fallback)
    # --------------------------------------------------------------------------
    tgstat_api_key: str | None = Field(
        default=None,
        description="API token for TGStat REST API (Plan S)",
    )
    tgstat_base_url: str = Field(
        default="https://api.tgstat.ru",
        description="Base URL for TGStat API",
    )
    tgstat_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout budget for TGStat API in seconds",
    )
    tgmarket_mcp_url: str = Field(
        default="https://tgmarket.io/mcp",
        description="Remote Streamable HTTP endpoint for TGMarket MCP",
    )
    tgmarket_api_key: str | None = Field(
        default=None,
        description="Optional API key for TGMarket MCP",
    )
    tgmarket_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout budget for TGMarket MCP in seconds",
    )

    # --------------------------------------------------------------------------
    # 4. Economics & Campaign Defaults (PRD Section 4)
    # --------------------------------------------------------------------------
    default_target_cac: float = Field(
        default=50.0,
        description="Default target Customer Acquisition Cost ($)",
    )
    default_cvr_est: float = Field(
        default=0.02,
        description="Conservative historical landing-page conversion rate (2.0%)",
    )
    default_ctr_min: float = Field(
        default=0.01,
        description="Conservative benchmark CTR floor (1.0%)",
    )
    default_ctr_max: float = Field(
        default=0.025,
        description="Conservative benchmark CTR ceiling (2.5%)",
    )
    default_risk_buffer: float = Field(
        default=0.15,
        description="Default risk haircut applied to CPM ceilings (15%)",
    )
    test_reserve_percentage: float = Field(
        default=0.20,
        description="Percentage of media budget reserved for exploratory cells (20%)",
    )

    # --------------------------------------------------------------------------
    # 5. Application & Logging Settings
    # --------------------------------------------------------------------------
    pythonutf8: int = Field(
        default=1,
        description="Enforces UTF-8 console and file encoding on Windows",
    )
    environment: str = Field(
        default="development",
        description="Runtime environment: development | testing | production",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG | INFO | WARNING | ERROR | CRITICAL",
    )
    log_format: str = Field(
        default="text",
        description="Log format: text | json",
    )
    output_dir: Path = Field(
        default=Path("output"),
        description="Output directory for generated Excel workbooks and reports",
    )

    def __getattr__(self, item: str) -> Any:
        """Provide transparent case-insensitive attribute access for uppercase env names."""
        lower_item = item.lower()
        if lower_item in self.__dict__:
            return self.__dict__[lower_item]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------
    @property
    def is_bai_live_enabled(self) -> bool:
        """True if b.ai credentials are configured and non-empty."""
        return bool(self.b_ai_api_key and self.b_ai_api_key.strip() and self.b_ai_api_key != "your_b_ai_api_key_here")

    @property
    def is_telegram_mtproto_enabled(self) -> bool:
        """True if Telegram MTProto credentials are fully configured."""
        return bool(self.telegram_api_id and self.telegram_api_hash and self.telegram_api_hash.strip())


# Cached global settings instance
_settings: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """Retrieve or reload cached settings instance."""
    global _settings
    if _settings is None or reload:
        _settings = Settings()
    return _settings


# Module-level convenience singleton instance
settings: Settings = get_settings()
