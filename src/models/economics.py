"""
OmniScout-TG: Deterministic Financial Gating & Portfolio Optimization
Enforces mathematical CPM ceilings, haircut target bids, and test reserve allocations.
"""

from src.models.schemas import CampaignBrief, ChannelEntity, EconomicCeiling


def calculate_data_confidence(channel: ChannelEntity) -> float:
    """
    Computes data confidence score C_data (0 to 100).
    Deducts penalty points for:
    - Low post count (< 10 posts): -20 pts
    - Zero reach or zero subscribers: -50 pts
    - High variance or short history: -15 pts
    """
    score = 100.0

    if channel.participants_count <= 0 or channel.reach_24h <= 0:
        return 20.0

    if len(channel.recent_posts) < 10:
        score -= 20.0

    if channel.err24 < 1.0:
        score -= 15.0

    if channel.depth > 1:
        score -= 10.0  # Slightly lower confidence for 2nd-degree recommendations

    return max(10.0, min(100.0, score))


def calculate_economic_ceiling(
    channel: ChannelEntity,
    brief: CampaignBrief,
    quoted_cpm: float | None = None,
) -> EconomicCeiling:
    """
    Calculates the allowable CPM ceiling and target bid using deterministic Python formulas.

    Formula:
      CPM_ceiling = 1000 * CTR_est * CVR_est * Target_CAC

      AAR = reach_24h / subscribers
      CTR_est = clamp(brief.est_ctr_min, brief.est_ctr_max, benchmark_ctr * (0.8 + 0.4 * AAR))
      Bid_target_cpm = CPM_ceiling * (0.50 + 0.50 * (C_data / 100)) * (1 - risk_buffer)
    """
    # Ad Attention Ratio scaling
    aar = channel.aar if channel.aar > 0 else (channel.reach_24h / max(1, channel.participants_count))
    base_ctr = (brief.est_ctr_min + brief.est_ctr_max) / 2.0

    # Scale CTR by Attention Ratio (capped between min and max)
    scaled_ctr = base_ctr * (0.8 + 0.4 * min(2.0, max(0.5, aar * 10.0)))
    ctr_est = max(brief.est_ctr_min, min(brief.est_ctr_max, scaled_ctr))
    cvr_est = brief.est_cvr
    target_cac = brief.target_cac_usd

    # CPM Ceiling formula
    cpm_ceiling = round(1000.0 * ctr_est * cvr_est * target_cac, 2)

    # Confidence score calculation
    c_data = calculate_data_confidence(channel)

    # Target Bid formula with confidence haircut
    confidence_factor = 0.50 + 0.50 * (c_data / 100.0)
    risk_haircut = 1.0 - brief.risk_buffer
    bid_target_cpm = round(cpm_ceiling * confidence_factor * risk_haircut, 2)

    # Estimate qualified clicks and leads per 1,000 impressions
    est_clicks = int(round(1000.0 * ctr_est))
    est_leads = max(1, int(round(est_clicks * cvr_est)))

    # Classification decision
    if quoted_cpm is not None:
        if quoted_cpm <= bid_target_cpm and c_data >= 70.0:
            recommendation = "BUY"
            note = f"Quoted CPM (${quoted_cpm}) is within target bid (${bid_target_cpm}). High confidence."
        elif quoted_cpm <= cpm_ceiling:
            recommendation = "NEGOTIATE"
            note = f"Quoted CPM (${quoted_cpm}) is above target bid (${bid_target_cpm}) but under ceiling (${cpm_ceiling}). Negotiate discount."
        elif c_data < 65.0:
            recommendation = "TEST_CELL"
            note = f"High potential exploratory channel with low data confidence ({c_data:.0f}/100). Fund via 20% test reserve."
        else:
            recommendation = "REJECT"
            note = f"Quoted CPM (${quoted_cpm}) exceeds economic ceiling (${cpm_ceiling}). Negative ROI expected."
    else:
        recommendation = "BUY" if c_data >= 65.0 else "TEST_CELL"
        note = f"Allowable ceiling: ${cpm_ceiling:.2f} | Target bid: ${bid_target_cpm:.2f} (CTR: {ctr_est*100:.2f}%, CVR: {cvr_est*100:.1f}%)"

    return EconomicCeiling(
        channel_id=channel.id,
        cpm_ceiling=cpm_ceiling,
        bid_target_cpm=bid_target_cpm,
        confidence_score=c_data,
        recommendation=recommendation,
        est_qualified_clicks=est_clicks,
        est_leads=est_leads,
        rationale_note=note,
    )
