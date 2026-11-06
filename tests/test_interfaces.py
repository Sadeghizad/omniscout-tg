"""
Offline tests for the two interfaces: the MCP server (src/mcp_server.py) and the
web GUI (src/web/app.py). No external network, no API keys.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from src.mcp_server import estimate_economics, mcp
from src.web.app import app


@pytest.mark.offline
def test_mcp_exposes_its_tools():
    """The four advertised tools must be registered under their documented names."""
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == {
        "estimate_economics",
        "validate_channels",
        "discover_channels",
        "run_media_plan",
    }


@pytest.mark.offline
def test_estimate_economics_matches_the_bidding_formula():
    """50k subs at 40% attention, 2% CVR, $50 CAC => $25.00 ceiling, $21.25 target bid."""
    result = estimate_economics(subscribers=50_000, reach_24h=20_000, err24=3.0)

    assert result["cpm_ceiling_usd"] == 25.0
    assert result["bid_target_cpm_usd"] == 21.25
    assert result["confidence_score"] == 100.0
    assert result["recommendation"] == "BUY"
    assert round(result["bid_target_cpm_ton"], 2) == 3.22


@pytest.mark.offline
def test_estimate_economics_negotiates_above_target_bid():
    """A quoted CPM between target bid and ceiling must produce NEGOTIATE, not BUY."""
    result = estimate_economics(subscribers=50_000, reach_24h=20_000, err24=3.0, quoted_cpm=24.0)

    assert result["recommendation"] == "NEGOTIATE"


@pytest.mark.offline
def test_web_dashboard_serves_and_reports_config():
    client = TestClient(app)

    page = client.get("/")
    assert page.status_code == 200
    assert "OmniScout" in page.text

    config = client.get("/api/config").json()
    assert set(config) >= {"bai_live", "output_dir", "defaults", "preset"}
    assert config["defaults"]["est_cvr"] > 0
    assert config["preset"]["seed_channels"]


@pytest.mark.offline
def test_download_refuses_paths_outside_the_output_directory():
    client = TestClient(app)

    assert client.get("/api/files/..%2F.env").status_code == 404
    assert client.get("/api/files/does-not-exist.xlsx").status_code == 404
