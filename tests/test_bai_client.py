"""
Unit tests for b.ai Unified Gateway Client (src/clients/bai_client.py).
Tests both Jev decisions (choice, noul, score) and DeepSeek completions.
"""

import pytest

from src.clients.bai_client import BaiClient
from src.models.schemas import ChannelEntity


@pytest.mark.offline
def test_bai_client_initialization():
    """Verify BaiClient initializes with defaults."""
    client = BaiClient()
    assert client.base_url == "https://api.b.ai/v1"
    assert client.timeout == 30.0


@pytest.mark.offline
def test_bai_client_mock_jev_decide():
    """Verify Jev decision engine returns typed decision for choice, noul, score."""
    client = BaiClient()
    state = {
        "channel_title": "آموزش برنامه‌نویسی پایتون",
        "channel_about": "پایتون و هوش مصنوعی",
        "target_persona": "Python developers",
    }
    questions = {
        "brand_safety": {
            "type": "noul",
            "instructions": "Is this channel clean?",
        },
        "category": {
            "type": "choice",
            "instructions": "Select primary category.",
            "criteria": {"tech_programming": "Tech", "other": None},
        },
        "icp_alignment": {
            "type": "score",
            "instructions": "Evaluate ICP match.",
            "criteria": ["Irrelevant", "Moderate", "High", "Direct Match"],
        },
    }

    res = client.decide(state=state, questions=questions)
    assert res["model"] == "jev-latest"
    decisions = res["decisions"]
    assert "brand_safety" in decisions
    assert decisions["brand_safety"]["answer"] is True
    assert "category" in decisions
    assert "icp_alignment" in decisions


@pytest.mark.offline
def test_bai_client_triage_channel():
    """Verify triage_channel returns structured JevTriageDecision."""
    client = BaiClient()
    channel = ChannelEntity(
        id="@parvazcapital_tel",
        title="Parvaz Capital | آموزش بورس و ارز دیجیتال",
        about="تحلیل بنیادی و تکنیکال بازارهای مالی",
        participants_count=75000,
    )
    decision = client.triage_channel(channel, target_persona="Crypto and stock investors")
    assert decision.channel_id == "@parvazcapital_tel"
    assert decision.brand_safe is True
    assert decision.icp_score >= 3
    assert decision.passed_triage is True


@pytest.mark.offline
def test_bai_client_chat_completion_and_creative_hooks():
    """Verify DeepSeek completions and creative hooks generation."""
    client = BaiClient()
    channel = ChannelEntity(
        id="@parvazcapital_tel",
        title="Parvaz Capital",
        participants_count=75000,
    )
    hooks = client.generate_creative_hook_and_rationale(
        channel=channel,
        campaign_name="Crypto Pro",
        target_persona="Investors",
    )
    assert "rationale_fa" in hooks
    assert "rationale_en" in hooks
    assert "recommended_format" in hooks
    assert "creative_angle" in hooks
    assert len(hooks["rationale_fa"]) > 10
