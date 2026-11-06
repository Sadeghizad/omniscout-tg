"""
OmniScout-TG: JSON-safe serialization of pipeline results.
Single source of truth for the payload shape consumed by the web GUI and the MCP server.
"""

from typing import Any

from src.pipeline.orchestrator import PipelineResult

# Reference TON/USD conversion used for the TON-denominated bid columns.
TON_USD_RATE = 6.6


def channel_rows(result: PipelineResult) -> list[dict[str, Any]]:
    """Flattens every discovered channel into one row with scoring, economics, and status."""
    rows: list[dict[str, Any]] = []
    for ch in result.cluster.channels:
        eco = result.economics.get(ch.id)
        tri = result.triage_decisions.get(ch.id)

        recommendation = eco.recommendation if eco else "PENDING"
        if tri and not tri.passed_triage:
            recommendation = "REJECTED_TRIAGE"

        rows.append(
            {
                "id": ch.id,
                "title": ch.title,
                "subscribers": ch.participants_count,
                "reach_24h": ch.reach_24h,
                "err24": round(ch.err24, 2),
                "aar": round(ch.aar, 4),
                "fit": round(ch.executive_fit_score, 1),
                "bm25": round(ch.bm25_score, 3),
                "dense": round(ch.dense_score, 3),
                "cpm_ceiling": eco.cpm_ceiling if eco else 0.0,
                "bid_target": eco.bid_target_cpm if eco else 0.0,
                "bid_target_ton": round(eco.bid_target_cpm / TON_USD_RATE, 2) if eco else 0.0,
                "confidence": eco.confidence_score if eco else 0.0,
                "est_leads": eco.est_leads if eco else 0,
                "recommendation": recommendation,
                "icp_score": tri.icp_score if tri else 0,
                "validation_status": ch.validation_status,
                "validation_caveat": ch.validation_caveat,
                "source": ch.source,
                "depth": ch.depth,
                "seed_parent": ch.seed_parent,
            }
        )
    return rows


def result_payload(result: PipelineResult) -> dict[str, Any]:
    """Assembles the complete, JSON-serializable result document."""
    brief = result.brief
    return {
        "campaign": {
            "name": brief.campaign_name,
            "category": brief.product_category,
            "persona": brief.target_persona,
            "seed_channels": list(brief.seed_channels),
            "budget_usd": brief.total_budget_usd,
            "target_cac_usd": brief.target_cac_usd,
            "est_cvr": brief.est_cvr,
            "est_ctr_min": brief.est_ctr_min,
            "est_ctr_max": brief.est_ctr_max,
            "risk_buffer": brief.risk_buffer,
        },
        "summary": dict(result.summary_stats),
        "files": {
            "xlsx": result.excel_path.name,
            "csv": result.csv_path.name,
            "xlsx_path": str(result.excel_path.resolve()),
            "csv_path": str(result.csv_path.resolve()),
        },
        "channels": channel_rows(result),
        "creatives": result.creatives,
    }
