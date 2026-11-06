"""
Unit tests for Telegram Auth Wizard (scripts/telegram_auth_wizard.py).
"""

import asyncio

import pytest

from scripts.telegram_auth_wizard import check_session_status


@pytest.mark.offline
def test_auth_wizard_check_nonexistent_session():
    """Verify check_session_status returns False when session file does not exist."""
    is_valid = asyncio.run(
        check_session_status(
            session_name="nonexistent_test_session_xyz",
            api_id=12345,
            api_hash="fake_hash",
        )
    )
    assert is_valid is False
