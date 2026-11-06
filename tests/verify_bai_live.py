"""
OmniScout-TG: b.ai Gateway Live Verification Script
Verifies both:
1. Jev Decision Engine (POST /v1/decisions with model: "jev-latest", questions: choice, noul, score)
2. DeepSeek Chat Completions (POST /v1/chat/completions with model: "deepseek-v4.1-flash")
Can run in live mode (with B_AI_API_KEY in .env) or mock mode.
"""

import os
import sys

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import get_settings
from src.clients.bai_client import BaiClient
from src.models.schemas import ChannelEntity


def run_verification():
    settings = get_settings()
    is_live = settings.is_bai_live_enabled
    mode_str = "LIVE b.ai GATEWAY" if is_live else "OFFLINE MOCK MODE (B_AI_API_KEY not configured)"

    print("=" * 75)
    print(f" OmniScout-TG: b.ai AI Gateway Verification [{mode_str}]")
    print(f" Gateway Base URL : {settings.b_ai_base_url}")
    print(f" Jev Model        : {settings.b_ai_jev_model}")
    print(f" DeepSeek Model   : {settings.b_ai_deepseek_model}")
    print("=" * 75)

    client = BaiClient(settings)

    # --------------------------------------------------------------------------
    # 1. Test Jev Fast Decision Engine (choice, noul, score)
    # --------------------------------------------------------------------------
    print("\n[Step 1/2] Testing Jev Decision Engine (POST /v1/decisions)...")
    sample_channel = ChannelEntity(
        id="@parvazcapital_tel",
        title="پرواز کپیتال | تحلیل تکنیکال و بازارهای مالی",
        about="تحلیل بنیادی و تکنیکال سهام بورس تهران، فارکس و کریپتوکارنسی",
        participants_count=85000,
        recent_posts_text_sample="تحلیل روند بیت‌کوین و شاخص کل بورس در معاملات امروز",
    )

    try:
        triage_result = client.triage_channel(
            channel=sample_channel,
            target_persona="Investors and traders interested in financial education and algorithmic trading",
        )
        print("  ✓ Jev Decision Succeeded:")
        print(f"    - Channel ID         : {triage_result.channel_id}")
        print(f"    - Brand Safe (noul)  : {triage_result.brand_safe} (Confidence: {triage_result.brand_safety_confidence:.2f})")
        print(f"    - Category (choice)  : {triage_result.category} (Confidence: {triage_result.category_confidence:.2f})")
        print(f"    - ICP Fit (score)    : {triage_result.icp_score}/5 [{triage_result.icp_score_label}]")
        print(f"    - Passed Triage Gate : {triage_result.passed_triage}")
    except Exception as exc:
        print(f"  ✗ Jev Decision Failed: {exc}")
        return False

    # --------------------------------------------------------------------------
    # 2. Test DeepSeek Chat Completions (deepseek-v4.1-flash)
    # --------------------------------------------------------------------------
    print("\n[Step 2/2] Testing DeepSeek Text Generation (POST /v1/chat/completions)...")
    try:
        hooks = client.generate_creative_hook_and_rationale(
            channel=sample_channel,
            campaign_name="Automated Wealth Bot 2026",
            target_persona="Professional traders looking for algorithmic execution tools",
        )
        print("  ✓ DeepSeek Generation Succeeded:")
        print(f"    - Format Angle    : {hooks.get('recommended_format')}")
        print(f"    - Creative Hook   : {hooks.get('creative_angle')}")
        print(f"    - Persian Rationale: {hooks.get('rationale_fa')}")
        print(f"    - English Rationale: {hooks.get('rationale_en')}")
    except Exception as exc:
        print(f"  ✗ DeepSeek Generation Failed: {exc}")
        return False

    print("\n" + "=" * 75)
    print(" ✓ All b.ai Gateway Interfaces Successfully Verified!")
    print("=" * 75)
    return True


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
