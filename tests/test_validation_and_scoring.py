"""
Unit tests for strict zero-tolerance validation and hybrid RAG scoring.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.models.schemas import CampaignBrief, ChannelEntity, PostMetrics
from src.pipeline.hybrid_scorer import HybridRAGScorer, PureOkapiBM25, tokenize_persian
from src.pipeline.validator import ChannelLiveValidator


@pytest.mark.offline
def test_validator_sub_1000_members_rejection():
    """Verify channels with < 1,000 members are strictly rejected for Telegram Ads."""
    validator = ChannelLiveValidator()

    # Small channel under 1,000 members
    small_channel = ChannelEntity(
        id="@small_startup",
        title="Small Startup Group",
        participants_count=850,
        recent_posts=[
            PostMetrics(post_id=1, date=datetime.now(UTC), views=50)
        ],
    )

    is_valid, entity, reason = validator.validate("@small_startup", existing_entity=small_channel)
    assert is_valid is False
    assert reason == "REJECTED_UNDER_1000_MEMBERS"
    assert entity.validation_status == "REJECTED_UNDER_1000_MEMBERS"
    assert entity.is_verified_live is False


@pytest.mark.offline
def test_validator_inactive_channel_rejection():
    """Verify channels without posts in the last 14 days are rejected."""
    validator = ChannelLiveValidator()

    old_date = datetime.now(UTC) - timedelta(days=25)
    inactive_channel = ChannelEntity(
        id="@dormant_channel",
        title="Dormant Financial News",
        participants_count=12000,
        recent_posts=[
            PostMetrics(post_id=1, date=old_date, views=500)
        ],
        last_post_date=old_date,
    )

    is_valid, entity, reason = validator.validate("@dormant_channel", existing_entity=inactive_channel)
    assert is_valid is False
    assert reason == "REJECTED_INACTIVE"
    assert entity.validation_status == "REJECTED_INACTIVE"
    assert entity.is_verified_live is False


@pytest.mark.offline
def test_validator_active_channel_qualification():
    """Verify active channels with >= 1,000 members are qualified as PUBLIC_WEB_VALIDATED."""
    validator = ChannelLiveValidator()

    active_channel = ChannelEntity(
        id="@tehranchamber",
        title="اتاق بازرگانی تهران",
        participants_count=25300,
        recent_posts=[
            PostMetrics(post_id=1, date=datetime.now(UTC), views=700)
        ],
        last_post_date=datetime.now(UTC),
    )

    is_valid, entity, reason = validator.validate("@tehranchamber", existing_entity=active_channel)
    assert is_valid is True
    assert reason == "PUBLIC_WEB_VALIDATED"
    assert entity.validation_status == "PUBLIC_WEB_VALIDATED"
    assert entity.validation_caveat == "REQUIRES_MANUAL_CHECK_IN_ADS_PANEL"
    assert entity.is_verified_live is True


@pytest.mark.offline
def test_pure_okapi_bm25_lexical_matching():
    """Verify Okapi BM25 scores executive documents higher than student documents."""
    docs = [
        "جلسه هیئت مدیره شرکت جهت بررسی قراردادهای تجاری و امضای اسناد رسمی صادرات",
        "جزوه و سوالات کنکور کارشناسی ارشد و آزمون وکالت دانشجویان",
    ]
    tokenized = [tokenize_persian(d) for d in docs]
    bm25 = PureOkapiBM25(tokenized)

    exec_query = ["هیئت", "مدیره", "قرارداد", "امضا", "صادرات"]
    score_exec = bm25.score_document(0, exec_query)
    score_student = bm25.score_document(1, exec_query)

    assert score_exec > score_student
    assert score_exec > 0.0


@pytest.mark.offline
def test_hybrid_rag_scorer_penalizes_student_content():
    """Verify HybridRAGScorer penalizes student channels and promotes executive channels."""
    brief = CampaignBrief(
        campaign_name="PlusDesign Round 2",
        target_persona="مدیران عامل و قراردادهای حقوقی",
        product_category="Executive Branding",
        seed_channels=["@test"],
    )

    c_exec = ChannelEntity(
        id="@chamber_exec",
        title="اتاق بازرگانی و صنایع",
        about="هلدینگ‌های سرمایه‌گذاری و قراردادهای تجاری بین‌المللی و هیئت مدیره",
        participants_count=20000,
        recent_posts_text_sample="امضای توافق‌نامه بازرگانی و توسعه صادرات رسمی",
        validation_status="PUBLIC_WEB_VALIDATED",
        is_verified_live=True,
    )

    c_student = ChannelEntity(
        id="@law_students",
        title="دانشجویان حقوق و کنکور وکالت",
        about="دانلود جزوه دانشجویی کنکور آزمون وکالت کارآموز کارآموزی پایان نامه",
        participants_count=35000,
        recent_posts_text_sample="تست‌های کنکور ارشد حقوق و آزمون وکالت دانشجویان",
        validation_status="PUBLIC_WEB_VALIDATED",
        is_verified_live=True,
    )

    scorer = HybridRAGScorer()
    scored = scorer.score_channels([c_exec, c_student], brief)

    assert scored[0].id == "@chamber_exec"
    assert scored[0].executive_fit_score > scored[1].executive_fit_score
    assert scored[0].executive_fit_score >= 80.0
    assert scored[1].executive_fit_score <= 35.0


@pytest.mark.offline
def test_canonicalize_telegram_handle_variants():
    """Verify telegram handle canonicalization handles all formats including /s/ URLs."""
    from src.models.schemas import canonicalize_telegram_handle

    assert canonicalize_telegram_handle("@parvazcapital_tel") == "@parvazcapital_tel"
    assert canonicalize_telegram_handle("parvazcapital_tel") == "@parvazcapital_tel"
    assert canonicalize_telegram_handle("https://t.me/parvazcapital_tel") == "@parvazcapital_tel"
    assert canonicalize_telegram_handle("https://t.me/s/parvazcapital_tel") == "@parvazcapital_tel"
    assert canonicalize_telegram_handle("t.me/s/parvazcapital_tel/1234") == "@parvazcapital_tel"
    assert canonicalize_telegram_handle("tg://resolve?domain=parvazcapital_tel") == "@parvazcapital_tel"
    assert canonicalize_telegram_handle("") == ""


@pytest.mark.offline
def test_compute_tied_ranks():
    """Verify tied ranks are handled identically rather than arbitrary ordering."""
    from src.pipeline.hybrid_scorer import compute_tied_ranks

    scores = [10.0, 5.0, 5.0, 0.0]
    ranks = compute_tied_ranks(scores)
    assert ranks[0] == 1.0
    assert ranks[1] == 2.0
    assert ranks[2] == 2.0  # Tied with index 1
    assert ranks[3] == 4.0


@pytest.mark.offline
def test_validator_missing_date_rejection():
    """Verify channel with posts but missing parseable dates is rejected."""
    validator = ChannelLiveValidator()

    channel_no_date = ChannelEntity(
        id="@undated_channel",
        title="Undated Channel",
        participants_count=5000,
        recent_posts=[
            PostMetrics(post_id=1, date=datetime.now(UTC), views=100)
        ],
        last_post_date=None,
    )
    # Clear the date to simulate unparseable timestamp
    channel_no_date.recent_posts[0].date = None  # type: ignore

    is_valid, entity, reason = validator.validate("@undated_channel", existing_entity=channel_no_date)
    assert is_valid is False
    assert reason == "REJECTED_NO_DATE"
