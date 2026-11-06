"""
Unit tests for OmniScout-TG Pydantic Data Models (src/models/schemas.py & economics.py).
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.economics import (
    calculate_economic_ceiling,
)
from src.models.schemas import (
    CampaignBrief,
    ChannelEntity,
    JevTriageDecision,
    PostMetrics,
)


@pytest.mark.offline
def test_campaign_brief_validation():
    """Verify CampaignBrief creates valid objects and enforces boundaries."""
    brief = CampaignBrief(
        campaign_name="Crypto Bootcamp 2026",
        target_persona="Junior investors and day traders",
        product_category="Finance",
        seed_channels=["@parvazcapital_tel"],
        total_budget_usd=2500.0,
        target_cac_usd=60.0,
        est_cvr=0.025,
    )
    assert brief.campaign_name == "Crypto Bootcamp 2026"
    assert brief.total_budget_usd == 2500.0
    assert brief.target_cac_usd == 60.0
    assert brief.seed_channels == ["@parvazcapital_tel"]

    # Test invalid budget
    with pytest.raises(ValidationError):
        CampaignBrief(
            campaign_name="Invalid",
            target_persona="Test",
            product_category="Test",
            seed_channels=[],  # min_length=1
        )


@pytest.mark.offline
def test_channel_entity_normalization():
    """Verify ChannelEntity normalizes IDs and validates metrics."""
    channel = ChannelEntity(
        id="parvazcapital_tel",  # Should normalize to @parvazcapital_tel
        title="Parvaz Capital",
        participants_count=85000,
        reach_24h=14000,
        err24=4.2,
        aar=0.165,
    )
    assert channel.id == "@parvazcapital_tel"
    assert channel.participants_count == 85000
    assert channel.reach_24h == 14000


@pytest.mark.offline
def test_jev_triage_decision_model():
    """Verify JevTriageDecision passes valid triage when safe and score >= 3."""
    decision = JevTriageDecision(
        channel_id="@parvazcapital_tel",
        brand_safe=True,
        brand_safety_confidence=0.99,
        category="finance_investing",
        category_confidence=0.95,
        icp_score=4,
        icp_score_label="High Relevance",
        passed_triage=True,
    )
    assert decision.passed_triage is True
    assert decision.icp_score == 4


@pytest.mark.offline
def test_economic_ceiling_calculation():
    """Verify deterministic CPM ceiling and haircut bidding formulas."""
    channel = ChannelEntity(
        id="@parvazcapital_tel",
        title="Parvaz Capital",
        participants_count=100000,
        reach_24h=15000,
        err24=4.5,
        aar=0.15,
        recent_posts=[
            PostMetrics(post_id=i, date=datetime.now(UTC), views=15000)
            for i in range(12)
        ],
    )
    brief = CampaignBrief(
        campaign_name="Test Campaign",
        target_persona="Finance",
        product_category="Finance",
        seed_channels=["@parvazcapital_tel"],
        target_cac_usd=50.0,
        est_cvr=0.02,
        est_ctr_min=0.01,
        est_ctr_max=0.025,
        risk_buffer=0.15,
    )

    eco = calculate_economic_ceiling(channel, brief)
    # CPM ceiling = 1000 * CTR * CVR * Target CAC
    # Approx: 1000 * 0.0175 * 0.02 * 50 = $17.50
    assert eco.cpm_ceiling > 10.0
    assert eco.cpm_ceiling < 30.0
    assert eco.bid_target_cpm < eco.cpm_ceiling
    assert eco.confidence_score >= 80.0
    assert eco.recommendation == "BUY"
