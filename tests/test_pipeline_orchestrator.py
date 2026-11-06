"""
Unit tests for OmniScout Pipeline Orchestrator (src/pipeline/orchestrator.py).
"""

from pathlib import Path

import pytest

from src.models.schemas import CampaignBrief
from src.pipeline.orchestrator import OmniScoutPipeline


@pytest.mark.offline
def test_pipeline_orchestrator_execution(tmp_path: Path):
    """Verify end-to-end pipeline executes cleanly and produces valid Excel output."""
    from config.settings import Settings
    from src.reporting.excel_generator import ExcelMediaPlanGenerator

    settings = Settings(output_dir=tmp_path)
    excel_gen = ExcelMediaPlanGenerator(output_dir=tmp_path)

    pipeline = OmniScoutPipeline(settings=settings, excel_generator=excel_gen)

    brief = CampaignBrief(
        campaign_name="Automated Wealth Bot 2026",
        target_persona="Crypto traders and algorithmic investors",
        product_category="Finance",
        seed_channels=["@parvazcapital_tel"],
        total_budget_usd=3000.0,
        target_cac_usd=50.0,
    )

    steps_recorded = []

    def progress_tracker(msg: str, step: int, total: int):
        steps_recorded.append((step, msg))

    result = pipeline.execute(brief, progress_callback=progress_tracker)

    # Verify all 6 stages executed
    assert len(steps_recorded) == 6
    assert result.excel_path.exists()
    assert result.csv_path.exists()
    assert result.cluster.total_discovered >= 1
    assert len(result.triage_decisions) >= 1
    assert len(result.economics) >= 1
    assert result.summary_stats["approved_buy_count"] >= 1
    assert result.summary_stats["total_qualified_reach"] > 0
