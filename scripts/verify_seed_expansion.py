"""
OmniScout-TG: Seed-Channel Recommendation Graph Expansion Script
Demonstrates end-to-end traversal starting from anchor channel @parvazcapital_tel:
1. Seed Ingestion & $0 Telegram Data Harvesting
2. Recursive Depth-2 Snowballing & Forward/Mention Network Crawl
3. Fast Jev System 1 Triage (Brand Safety, Category, ICP fit)
4. Deterministic Unit Economics & Allowable CPM Ceilings
5. Automatic 8-Sheet RTL Excel Media Plan Generation
"""

import os
import sys
from pathlib import Path

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import get_settings
from src.clients.bai_client import BaiClient
from src.models.economics import calculate_economic_ceiling
from src.models.schemas import CampaignBrief
from src.pipeline.graph_discovery import RecommendationGraphDiscovery
from src.reporting.excel_generator import ExcelMediaPlanGenerator


def main():
    settings = get_settings()
    seed_handle = "@parvazcapital_tel"

    print("=" * 80)
    print(" OmniScout-TG: Telegram Native Recommendation Graph Expansion")
    print(f" Anchor Seed Channel : {seed_handle}")
    print(" Discovery Engine   : Recursive Depth-2 Snowball + $0 MTProto/Web Harvester")
    print("=" * 80)

    # 1. Define Campaign Brief
    brief = CampaignBrief(
        campaign_name="Parvaz Capital Ecosystem Campaign",
        target_persona="Investors, crypto traders, and financial analysts in the Iranian market",
        product_category="Finance & Capital Markets",
        seed_channels=[seed_handle],
        total_budget_usd=3000.0,
        target_cac_usd=50.0,
        est_cvr=0.02,
        est_ctr_min=0.01,
        est_ctr_max=0.025,
        risk_buffer=0.15,
    )

    # 2. Execute Graph Discovery
    print(f"\n[Step 1/4] Crawling Telegram Recommendation Graph from seed: {seed_handle}...")
    discovery = RecommendationGraphDiscovery(settings=settings)
    cluster = discovery.discover(seed_channel_ids=brief.seed_channels, target_cluster_size=100)

    print(f"  ✓ Discovered {cluster.total_discovered} total candidate channels in recommendation graph:")
    print(f"    - Depth-1 Recommendations : {cluster.depth_1_count}")
    print(f"    - Depth-2 Snowball Hubs   : {cluster.depth_2_count}")
    print(f"    - Forward/Mention Network : {cluster.network_mentions_count}")

    # 3. Fast Jev AI Triage & DeepSeek Creative Generation
    print("\n[Step 2/4] Running b.ai Gateway (Jev Fast Triage & DeepSeek Creative Hooks)...")
    bai = BaiClient(settings)
    triage_decisions = {}
    creatives = {}

    for ch in cluster.channels:
        tri = bai.triage_channel(ch, target_persona=brief.target_persona)
        triage_decisions[ch.id] = tri
        if tri.passed_triage:
            cr = bai.generate_creative_hook_and_rationale(
                channel=ch,
                campaign_name=brief.campaign_name,
                target_persona=brief.target_persona,
            )
            creatives[ch.id] = cr

    passed_count = sum(1 for t in triage_decisions.values() if t.passed_triage)
    print(f"  ✓ Jev Screened {len(cluster.channels)} channels: {passed_count} Passed Brand Safety & ICP Gate.")

    # 4. Enforce Deterministic Unit Economics
    print("\n[Step 3/4] Enforcing Deterministic CPM Ceiling & Haircut Bidding Formulas...")
    economics = {}
    for ch in cluster.channels:
        eco = calculate_economic_ceiling(channel=ch, brief=brief)
        economics[ch.id] = eco

    # Display Top Shortlisted Channels
    print("\n" + "-" * 80)
    print(f"{'Channel Handle':<24} | {'Subscribers':<10} | {'Reach 24h':<10} | {'ERR24':<7} | {'CPM Ceil':<8} | {'Bid CPM':<8} | {'Status'}")
    print("-" * 80)
    for ch in cluster.channels[:10]:
        eco = economics[ch.id]
        tri = triage_decisions[ch.id]
        status = "BUY" if (tri.passed_triage and eco.recommendation == "BUY") else eco.recommendation
        print(f"{ch.id:<24} | {ch.participants_count:<10,d} | {ch.reach_24h:<10,d} | {ch.err24:>5.2f}% | ${eco.cpm_ceiling:>6.2f} | ${eco.bid_target_cpm:>6.2f} | {status}")
    print("-" * 80)

    # 5. Generate 8-Sheet RTL Excel Media Plan
    print("\n[Step 4/4] Generating Institutional 8-Sheet RTL Excel Media Plan...")
    excel_gen = ExcelMediaPlanGenerator(output_dir=Path("output"))
    out_file = excel_gen.generate(
        brief=brief,
        channels=cluster.channels,
        triage_decisions=triage_decisions,
        economics=economics,
        creatives=creatives,
        filename="OmniScout_MediaPlan_ParvazCapital_SeedCluster.xlsx",
    )
    print("  ✓ Media Plan Successfully Exported to:")
    print(f"    --> {out_file.resolve()}")

    print("\n" + "=" * 80)
    print(" ✓ Seed Expansion & Cluster Extraction Verification Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
