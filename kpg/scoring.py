from typing import Dict, Any
from .models import PositionSnapshot


def score_position_advocacy(pos: PositionSnapshot, market_regime: str, usdc_reserve_ok: bool) -> Dict[str, Any]:
    """
    V1 scoring is intentionally conservative.
    Later versions should replace trend/volume placeholders with real OHLC indicators.
    """

    score = 0
    reasons = []

    # Trend validity placeholder.
    if market_regime in ("bull", "chop"):
        score += 18
        reasons.append("Market regime does not automatically invalidate the position.")
    elif market_regime == "bear":
        score += 8
        reasons.append("Bear regime weakens position defense.")
    else:
        reasons.append("Panic regime gives no trend defense.")

    # PnL / risk-reward proxy.
    if pos.unrealized_pnl_pct is None:
        score += 8
        reasons.append("Missing cost basis limits conviction.")
    elif pos.unrealized_pnl_pct >= 0.20:
        score += 16
        reasons.append("Position is profitable but needs profit protection.")
    elif pos.unrealized_pnl_pct >= 0:
        score += 12
        reasons.append("Position is green but not strongly profitable.")
    elif pos.unrealized_pnl_pct > -0.08:
        score += 8
        reasons.append("Loss is still within review zone.")
    else:
        score += 2
        reasons.append("Loss is large enough to weaken defense.")

    # Volume confirmation placeholder.
    score += 7
    reasons.append("Volume confirmation not implemented in v1; score capped.")

    # Position size.
    score += 12
    reasons.append("Position size accepted unless portfolio risk layer flags it.")

    # Thesis still intact.
    if pos.thesis:
        score += 14
        reasons.append(f"Thesis exists: {pos.thesis}.")
    else:
        score += 0
        reasons.append("No thesis, weak defense.")

    # Profit protection.
    if usdc_reserve_ok:
        score += 9
        reasons.append("USDC reserve is acceptable.")
    else:
        score += 2
        reasons.append("USDC reserve is low; protection takes priority.")

    # Tier quality.
    if pos.tier == 1:
        score += 10
        reasons.append("Tier 1 asset gets more room.")
    elif pos.tier == 2:
        score += 6
        reasons.append("Tier 2 asset gets balanced defense.")
    else:
        score += 2
        reasons.append("Tier 3/hype asset gets limited defense.")

    # Cap at 79 when technical indicators are not fully implemented.
    score = min(score, 79)

    verdict = "PROBATION"
    if score >= 80:
        verdict = "DEFEND"
    elif score >= 60:
        verdict = "HOLD"
    elif score >= 40:
        verdict = "PROBATION"
    elif score >= 20:
        verdict = "REDUCE"
    else:
        verdict = "EXIT"

    return {
        "advocacy_score": score,
        "court_verdict": verdict,
        "reasons": reasons,
    }
