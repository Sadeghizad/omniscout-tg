"""
Unit tests for config.settings (Settings singleton and BaseSettings schema).
"""

from pathlib import Path

import pytest

from config.settings import Settings, settings


@pytest.mark.offline
def test_settings_singleton_defaults():
    """Verify default values for the global settings singleton."""
    assert settings.b_ai_jev_model == "jev-latest"
    assert settings.b_ai_deepseek_model == "deepseek-v4.1-flash"
    assert settings.b_ai_base_url == "https://api.b.ai/v1"
    assert settings.b_ai_timeout_seconds == 30.0
    assert settings.b_ai_max_retries == 3
    assert settings.b_ai_retry_backoff == 1.5

    # Telegram forwards
    assert settings.tgstat_base_url == "https://api.tgstat.ru"
    assert settings.tgstat_timeout_seconds == 30.0
    assert settings.tgmarket_mcp_url == "https://tgmarket.io/mcp"
    assert settings.tgmarket_timeout_seconds == 30.0

    # Economics defaults
    assert settings.default_target_cac == 50.0
    assert settings.default_cvr_est == 0.02
    assert settings.default_ctr_min == 0.01
    assert settings.default_ctr_max == 0.025
    assert settings.default_risk_buffer == 0.15
    assert settings.test_reserve_percentage == 0.20

    # Encoding & App
    assert settings.pythonutf8 == 1
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert isinstance(settings.output_dir, Path)


@pytest.mark.offline
def test_settings_case_insensitive_access():
    """Verify transparent attribute access via both lowercase and uppercase names."""
    assert settings.B_AI_JEV_MODEL == settings.b_ai_jev_model
    assert settings.B_AI_DEEPSEEK_MODEL == settings.b_ai_deepseek_model
    assert settings.B_AI_BASE_URL == settings.b_ai_base_url
    assert settings.B_AI_TIMEOUT_SECONDS == settings.b_ai_timeout_seconds
    assert settings.DEFAULT_TARGET_CAC == settings.default_target_cac
    assert settings.DEFAULT_CVR_EST == settings.default_cvr_est
    assert settings.PYTHONUTF8 == settings.pythonutf8


@pytest.mark.offline
def test_settings_override_via_kwargs():
    """Verify custom Settings instantiation with keyword argument overrides."""
    custom_settings = Settings(
        b_ai_api_key="test-key-123",
        b_ai_jev_model="custom-jev-model",
        b_ai_timeout_seconds=45.0,
        default_target_cac=75.0,
    )
    assert custom_settings.b_ai_api_key == "test-key-123"
    assert custom_settings.B_AI_API_KEY == "test-key-123"
    assert custom_settings.b_ai_jev_model == "custom-jev-model"
    assert custom_settings.B_AI_JEV_MODEL == "custom-jev-model"
    assert custom_settings.b_ai_timeout_seconds == 45.0
    assert custom_settings.default_target_cac == 75.0


@pytest.mark.offline
def test_settings_nonexistent_attribute_raises():
    """Verify accessing an unknown attribute raises AttributeError."""
    with pytest.raises(AttributeError):
        _ = settings.nonexistent_unknown_attribute
