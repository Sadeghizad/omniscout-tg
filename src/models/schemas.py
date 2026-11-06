"""
OmniScout-TG: Core Pydantic Schemas & Domain Models
Implements validated data structures for Campaign Briefs, Channel Entities,
Jev Triage Decisions, and Graph Discovery results.
"""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def canonicalize_telegram_handle(channel_ref: str) -> str:
    """
    Normalizes any Telegram channel reference into standard '@username' format.
    Handles:
      '@username' -> '@username'
      'username' -> '@username'
      'https://t.me/username' -> '@username'
      'https://t.me/s/username' -> '@username'
      't.me/s/username/1234' -> '@username'
      'tg://resolve?domain=username' -> '@username'
    """
    if not channel_ref:
        return ""
    clean = str(channel_ref).strip()
    m = re.search(
        r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([a-zA-Z0-9_]{4,32})",
        clean,
        re.IGNORECASE,
    )
    if m:
        return f"@{m.group(1).lower()}"
    m_domain = re.search(r"domain=([a-zA-Z0-9_]{4,32})", clean, re.IGNORECASE)
    if m_domain:
        return f"@{m_domain.group(1).lower()}"
    clean = clean.lstrip("@").strip().lower()
    clean = clean.split("/")[0].split("?")[0]
    return f"@{clean}" if clean else ""


class PostMetrics(BaseModel):
    """Metrics for an individual Telegram post."""
    model_config = ConfigDict(extra="ignore")

    post_id: int
    date: datetime
    views: int = Field(default=0, ge=0)
    forwards: int = Field(default=0, ge=0)
    reactions: int = Field(default=0, ge=0)
    text_snippet: str | None = None
    forwarded_from_chat_id: str | None = None
    mentions: list[str] = Field(default_factory=list)


class ChannelEntity(BaseModel):
    """Canonical Telegram channel entity with harvested metrics and graph relationships."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Canonical ID or username (e.g. '@parvazcapital_tel')")
    title: str = Field(description="Channel title")
    username: str | None = None
    about: str | None = Field(default="", description="Channel description / bio")
    participants_count: int = Field(default=0, ge=0, description="Total subscribers")

    # In-house computed metrics ($0 extraction)
    reach_24h: int = Field(default=0, ge=0, description="Median 24h advertising post reach")
    err24: float = Field(default=0.0, ge=0.0, description="Engagement Rate on 24h Reach (%)")
    aar: float = Field(default=0.0, ge=0.0, description="Ad Attention Ratio (reach_24h / subscribers)")

    # Discovery provenance
    source: Literal["seed", "recommendation_graph", "forward_network", "web_preview"] = "recommendation_graph"
    depth: int = Field(default=1, ge=0, description="Graph traversal depth (0=seed, 1=direct rec, 2=depth-2 rec)")
    seed_parent: str | None = Field(default=None, description="Seed channel that led to this discovery")

    # Recent post samples for AI evaluation
    recent_posts: list[PostMetrics] = Field(default_factory=list)
    recent_posts_text_sample: str = Field(default="", description="Aggregated text snippet for LLM triage")

    # Strict Zero-Tolerance Validation
    validation_status: str = Field(default="PENDING", description="Status: PUBLIC_WEB_VALIDATED | REJECTED_*")
    validation_caveat: str = Field(default="", description="Operational caveat e.g. REQUIRES_MANUAL_CHECK_IN_ADS_PANEL")
    is_verified_live: bool = Field(default=False, description="True if passed live validation and has >=1000 members")
    last_post_date: datetime | None = Field(default=None, description="Timestamp of latest active post")

    # Hybrid RAG Scoring
    bm25_score: float = Field(default=0.0, description="BM25 lexical matching score")
    dense_score: float = Field(default=0.0, description="Dense semantic cosine similarity score")
    executive_fit_score: float = Field(default=0.0, description="Reciprocal Rank Fusion (RRF) Executive Fit Score (0-100)")

    @field_validator("id")
    @classmethod
    def normalize_id(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("@") and not v.startswith("https://t.me/"):
            v = f"@{v}"
        return v


class CampaignBrief(BaseModel):
    """Marketing campaign specifications and financial targets."""
    model_config = ConfigDict(extra="ignore")

    campaign_name: str
    target_persona: str = Field(description="Detailed description of Ideal Customer Profile (ICP)")
    product_category: str = Field(description="Industry / vertical (e.g., Finance, Tech, Crypto, Education)")
    seed_channels: list[str] = Field(
        min_length=1,
        description="1 to 3 anchor channels to bootstrap graph recommendation traversal (e.g., ['@parvazcapital_tel'])"
    )
    total_budget_usd: float = Field(default=1000.0, gt=0)
    target_cac_usd: float = Field(default=50.0, gt=0, description="Allowable Customer Acquisition Cost ($)")
    est_cvr: float = Field(default=0.02, gt=0, le=1.0, description="Historical or expected conversion rate (default 2%)")
    est_ctr_min: float = Field(default=0.01, gt=0, le=1.0, description="Conservative CTR lower bound (1%)")
    est_ctr_max: float = Field(default=0.025, gt=0, le=1.0, description="Conservative CTR upper bound (2.5%)")
    risk_buffer: float = Field(default=0.15, ge=0.0, le=0.5, description="Safety haircut buffer on CPM bidding")
    bilingual_rationales: bool = Field(default=True, description="Generate rationales in both Persian and English")


class JevQuestionSchema(BaseModel):
    """Schema for an individual question in a Jev decision request."""
    type: Literal["noul", "choice", "score"]
    instructions: str
    criteria: Any | None = None


class JevDecisionRequest(BaseModel):
    """Payload contract for POST https://api.b.ai/v1/decisions."""
    model: str = "jev-latest"
    state: dict[str, Any]
    questions: dict[str, JevQuestionSchema]


class JevTriageDecision(BaseModel):
    """Output decision returned by Jev System 1 screening."""
    model_config = ConfigDict(extra="ignore")

    channel_id: str
    brand_safe: bool = Field(description="True if channel passes anti-spam/anti-fraud check")
    brand_safety_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    category: str = Field(description="Classified vertical / topic category")
    category_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    icp_score: int = Field(default=3, ge=1, le=5, description="1 (Irrelevant) to 5 (Direct Match)")
    icp_score_label: str = Field(default="Moderate Relevance")
    icp_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    passed_triage: bool = Field(default=False, description="True if safe and icp_score >= 3")
    raw_response: dict[str, Any] | None = None


class EconomicCeiling(BaseModel):
    """Calculated financial ceiling and target bidding boundaries."""
    model_config = ConfigDict(extra="ignore")

    channel_id: str
    cpm_ceiling: float = Field(description="Maximum allowable CPM ($) before acquisition becomes unprofitable")
    bid_target_cpm: float = Field(description="Target negotiation bid ($) with confidence haircut")
    confidence_score: float = Field(default=80.0, ge=0.0, le=100.0, description="Data confidence score C_data (0-100)")
    recommendation: Literal["BUY", "NEGOTIATE", "TEST_CELL", "REJECT"] = "BUY"
    est_qualified_clicks: int = Field(default=0, ge=0)
    est_leads: int = Field(default=0, ge=0)
    rationale_note: str = ""


class GraphClusterResult(BaseModel):
    """Results from Depth-2 recommendation graph snowballing."""
    model_config = ConfigDict(extra="ignore")

    seed_channels: list[str]
    total_discovered: int
    depth_1_count: int
    depth_2_count: int
    network_mentions_count: int
    channels: list[ChannelEntity]
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
