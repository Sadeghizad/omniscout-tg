"""
Unit tests for 8-Sheet Excel Media Plan Generator (src/reporting/excel_generator.py).
"""

from pathlib import Path

import openpyxl
import pytest

from src.models.schemas import CampaignBrief, ChannelEntity, EconomicCeiling, JevTriageDecision
from src.reporting.excel_generator import ExcelMediaPlanGenerator


@pytest.mark.offline
def test_excel_generator_creates_8_sheets_with_rtl(tmp_path: Path):
    """Verify that the generator creates an Excel file with exactly 8 sheets, RTL enabled, and valid data."""
    generator = ExcelMediaPlanGenerator(output_dir=tmp_path)

    brief = CampaignBrief(
        campaign_name="Fintech Launch 2026",
        target_persona="Traders and financial analysts",
        product_category="Finance",
        seed_channels=["@parvazcapital_tel"],
        total_budget_usd=3000.0,
        target_cac_usd=60.0,
    )

    channel = ChannelEntity(
        id="@parvazcapital_tel",
        title="Parvaz Capital",
        participants_count=85000,
        reach_24h=14000,
        err24=4.5,
        aar=0.165,
    )

    triage = {
        channel.id: JevTriageDecision(
            channel_id=channel.id,
            brand_safe=True,
            category="finance_investing",
            icp_score=5,
            icp_score_label="Direct Match",
            passed_triage=True,
        )
    }

    economics = {
        channel.id: EconomicCeiling(
            channel_id=channel.id,
            cpm_ceiling=22.50,
            bid_target_cpm=16.80,
            confidence_score=90.0,
            recommendation="BUY",
        )
    }

    creatives = {
        channel.id: {
            "rationale_fa": "کانال پرواز کپیتال به دلیل تمرکز بالا بر تحلیل تکنیکال برای کمپین انتخاب شد.",
            "rationale_en": "Parvaz Capital was shortlisted due to strong engagement and verified trader audience.",
            "recommended_format": "24h Pinned Post + Notification",
            "creative_angle": "Live case study highlighting algorithmic trading strategies.",
        }
    }

    file_path = generator.generate(
        brief=brief,
        channels=[channel],
        triage_decisions=triage,
        economics=economics,
        creatives=creatives,
        filename="test_plan.xlsx",
    )

    assert file_path.exists()

    # Load workbook and verify sheets
    wb = openpyxl.load_workbook(file_path)
    expected_sheets = [
        "1. Executive Summary",
        "2. Recommended Plan",
        "3. Test Reserve Cell",
        "4. Candidate Database",
        "5. Exclusion Audit Log",
        "6. Creative & Hooks",
        "7. Scenario Modeler",
        "8. Attribution Tracker",
    ]
    assert wb.sheetnames == expected_sheets

    # Verify RTL enabled on all sheets
    for sheet_name in expected_sheets:
        ws = wb[sheet_name]
        assert ws.sheet_view.rightToLeft is True
