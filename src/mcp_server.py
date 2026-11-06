"""
OmniScout-TG: Model Context Protocol (MCP) server.

Exposes the media-planning engine to any MCP-capable agent (Claude Desktop, Cursor,
VS Code / Cline, DSH, ...) over stdio:

    python -m src.mcp_server

Tools
-----
- estimate_economics  : offline, deterministic CPM ceiling / target bid math ($ and TON)
- validate_channels   : live Telegram Ads eligibility gate (public, >=1000 members, active)
- discover_channels   : recommendation-graph discovery from seed channels
- run_media_plan      : full 6-stage pipeline + Excel/CSV deliverables
"""

import os
import sys

# Add project root to sys.path so `config` and `src` import when launched by an MCP client.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import UTC, datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from config.settings import get_settings
from src.models.economics import calculate_economic_ceiling
from src.models.payload import TON_USD_RATE, result_payload
from src.models.schemas import CampaignBrief, ChannelEntity, PostMetrics
from src.pipeline.graph_discovery import RecommendationGraphDiscovery
from src.pipeline.orchestrator import OmniScoutPipeline
from src.pipeline.validator import ChannelLiveValidator

mcp = FastMCP(
    name="omniscout-tg",
    instructions=(
        "OmniScout-TG is a media-planning decision engine for Telegram Ads. "
        "It discovers real public channels from seed channels, validates them against the "
        "Telegram Ads hard rules (public, >=1000 members, posted within 14 days), scores them "
        "against a target persona, and prices every channel with a deterministic CPM ceiling "
        "and target bid in USD and TON. Use `estimate_economics` for instant offline math, "
        "`validate_channels` to gate a list of handles, `discover_channels` to expand a seed "
        "channel into its neighbourhood, and `run_media_plan` for the full pipeline plus "
        "Excel/CSV deliverables."
    ),
)


def _brief(
    campaign_name: str = "OmniScout Campaign",
    target_persona: str = "Business owners and decision makers",
    product_category: str = "Business",
    seed_channels: list[str] | None = None,
    total_budget_usd: float = 1000.0,
    target_cac_usd: float = 50.0,
    est_cvr: float = 0.02,
    est_ctr_min: float = 0.01,
    est_ctr_max: float = 0.025,
    risk_buffer: float = 0.15,
) -> CampaignBrief:
    """Builds a validated CampaignBrief, defaulting the seed list when empty."""
    return CampaignBrief(
        campaign_name=campaign_name,
        target_persona=target_persona,
        product_category=product_category,
        seed_channels=seed_channels or ["@parvazcapital_tel"],
        total_budget_usd=total_budget_usd,
        target_cac_usd=target_cac_usd,
        est_cvr=est_cvr,
        est_ctr_min=est_ctr_min,
        est_ctr_max=est_ctr_max,
        risk_buffer=risk_buffer,
    )


@mcp.tool()
def estimate_economics(
    subscribers: int,
    reach_24h: int,
    err24: float = 0.0,
    recent_posts_count: int = 20,
    depth: int = 1,
    target_cac_usd: float = 50.0,
    est_cvr: float = 0.02,
    est_ctr_min: float = 0.01,
    est_ctr_max: float = 0.025,
    risk_buffer: float = 0.15,
    quoted_cpm: float | None = None,
) -> dict[str, Any]:
    """
    Instant, offline price of a single Telegram channel. No network, no API key.

    Returns the maximum profitable CPM ceiling ($ and TON), the confidence-haircut target
    bid, the data-confidence score, and a BUY / NEGOTIATE / TEST_CELL / REJECT verdict.
    Pass `quoted_cpm` when you already know the price the channel owner is asking.
    """
    brief = _brief(
        target_cac_usd=target_cac_usd,
        est_cvr=est_cvr,
        est_ctr_min=est_ctr_min,
        est_ctr_max=est_ctr_max,
        risk_buffer=risk_buffer,
    )
    channel = ChannelEntity(
        id="@estimate",
        title="Estimate",
        participants_count=max(0, subscribers),
        reach_24h=max(0, reach_24h),
        err24=max(0.0, err24),
        aar=(reach_24h / subscribers) if subscribers else 0.0,
        depth=max(0, depth),
        recent_posts=[
            PostMetrics(post_id=i, date=datetime.now(UTC), views=int(reach_24h or 0))
            for i in range(max(0, recent_posts_count))
        ],
    )
    eco = calculate_economic_ceiling(channel=channel, brief=brief, quoted_cpm=quoted_cpm)
    return {
        "cpm_ceiling_usd": eco.cpm_ceiling,
        "cpm_ceiling_ton": round(eco.cpm_ceiling / TON_USD_RATE, 2),
        "bid_target_cpm_usd": eco.bid_target_cpm,
        "bid_target_cpm_ton": round(eco.bid_target_cpm / TON_USD_RATE, 2),
        "confidence_score": eco.confidence_score,
        "recommendation": eco.recommendation,
        "est_clicks_per_1k_impressions": eco.est_qualified_clicks,
        "est_leads_per_1k_impressions": eco.est_leads,
        "rationale": eco.rationale_note,
    }


@mcp.tool()
def validate_channels(handles: list[str]) -> dict[str, Any]:
    """
    Runs the zero-tolerance live Telegram Ads gate over a list of channel handles.

    Each handle may be `@name`, `name`, `https://t.me/name`, or `https://t.me/s/name`.
    A channel passes only if the public web preview answers HTTP 200, it has a real title,
    it has at least 1,000 subscribers, and it posted within the last 14 days. Requires
    network access; takes a few seconds per handle.
    """
    settings = get_settings()
    validator = ChannelLiveValidator(settings=settings)

    results: list[dict[str, Any]] = []
    for handle in handles:
        is_valid, entity, reason = validator.validate(handle)
        results.append(
            {
                "handle": handle,
                "valid": is_valid,
                "reason": reason,
                "id": entity.id if entity else None,
                "title": entity.title if entity else None,
                "subscribers": entity.participants_count if entity else None,
                "last_post_date": entity.last_post_date.isoformat()
                if entity and entity.last_post_date
                else None,
                "caveat": entity.validation_caveat if entity else None,
            }
        )
    return {"passed": sum(1 for r in results if r["valid"]), "results": results}


@mcp.tool()
def discover_channels(seed_channels: list[str], target_cluster_size: int = 50) -> dict[str, Any]:
    """
    Expands seed channels into their live neighbourhood: forwards, mentions, and curated
    B2B seeds, every candidate gated by the live validator. No relevance scoring, no report.

    Use this when you only need the candidate universe; use `run_media_plan` when you also
    want scoring, pricing, and the Excel deliverable. Requires network access; takes a
    couple of minutes.
    """
    settings = get_settings()
    discovery = RecommendationGraphDiscovery(settings=settings)
    cluster = discovery.discover(
        seed_channel_ids=seed_channels or ["@parvazcapital_tel"],
        target_cluster_size=target_cluster_size,
    )
    return {
        "total_discovered": cluster.total_discovered,
        "depth_1_count": cluster.depth_1_count,
        "depth_2_count": cluster.depth_2_count,
        "channels": [
            {
                "id": ch.id,
                "title": ch.title,
                "subscribers": ch.participants_count,
                "reach_24h": ch.reach_24h,
                "validation_status": ch.validation_status,
                "source": ch.source,
                "depth": ch.depth,
            }
            for ch in cluster.channels
        ],
    }


@mcp.tool()
def run_media_plan(
    campaign_name: str,
    target_persona: str,
    seed_channels: list[str],
    product_category: str = "Business",
    total_budget_usd: float = 1000.0,
    target_cac_usd: float = 50.0,
    est_cvr: float = 0.02,
    est_ctr_min: float = 0.01,
    est_ctr_max: float = 0.025,
    risk_buffer: float = 0.15,
) -> dict[str, Any]:
    """
    Runs the full 6-stage OmniScout pipeline and writes the deliverable files.

    Stages: live discovery -> hybrid BM25 + dense RAG scoring -> persona triage ->
    creative rationales -> deterministic CPM/bid gating -> 8-sheet RTL Excel + CSV export.
    Returns the KPI summary, per-channel recommendations, and the absolute paths of the
    generated .xlsx and .csv files. Requires network access; typically 2-10 minutes.
    """
    brief = _brief(
        campaign_name=campaign_name,
        target_persona=target_persona,
        product_category=product_category,
        seed_channels=seed_channels,
        total_budget_usd=total_budget_usd,
        target_cac_usd=target_cac_usd,
        est_cvr=est_cvr,
        est_ctr_min=est_ctr_min,
        est_ctr_max=est_ctr_max,
        risk_buffer=risk_buffer,
    )
    result = OmniScoutPipeline(settings=get_settings()).execute(brief)
    payload = result_payload(result)
    return {
        "campaign": payload["campaign"],
        "summary": payload["summary"],
        "files": payload["files"],
        "channels": payload["channels"],
    }


def main() -> None:
    """Starts the stdio MCP server (safe to import and unit-test without starting it)."""
    mcp.run()


if __name__ == "__main__":
    main()
