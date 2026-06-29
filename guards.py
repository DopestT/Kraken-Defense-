from typing import Dict, Any, List
from .models import PositionSnapshot


def position_profit_guard(pos: PositionSnapshot, config: Dict[str, Any]) -> Dict[str, Any]:
    rules = config["position_rules"]
    actions: List[Dict[str, Any]] = []

    pnl_pct = pos.unrealized_pnl_pct
    if pnl_pct is None or pnl_pct <= 0:
        return {"actions": actions, "status": "no_profit_to_protect"}

    for tier in rules["profit_tiers"]:
        if pnl_pct >= tier["min_profit_pct"] and pnl_pct < tier["max_profit_pct"]:
            profit = max(pos.unrealized_pnl or 0, 0)
            sell_value = profit * tier["sell_profit_pct"]
            if sell_value > 5:
                actions.append({
                    "type": "PROTECT_PROFIT",
                    "symbol": pos.symbol,
                    "side": "sell",
                    "suggested_value_usd": round(sell_value, 2),
                    "reason": f"Position is up {pnl_pct:.1%}; protect {tier['sell_profit_pct']:.0%} of unrealized profit.",
                    "confidence": 0.72,
                })
            break

    # trailing guard
    if pos.drawdown_from_high_pct >= rules["trailing_drawdown_pct"]:
        actions.append({
            "type": "TRAILING_PROFIT_GUARD",
            "symbol": pos.symbol,
            "side": "sell",
            "suggested_position_pct": rules["trailing_sell_position_pct"],
            "suggested_value_usd": round(pos.value * rules["trailing_sell_position_pct"], 2),
            "reason": f"Profitable position drew down {pos.drawdown_from_high_pct:.1%} from recent high.",
            "confidence": 0.78,
        })

    return {"actions": actions, "status": "profit_checked"}


def portfolio_profit_guard(total_value: float, state: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    portfolio_state = state.setdefault("portfolio", {})
    weekly_start = portfolio_state.get("weekly_start_value")

    if weekly_start is None:
        portfolio_state["weekly_start_value"] = total_value
        return {"actions": [], "status": "weekly_baseline_initialized"}

    weekly_gain = total_value - weekly_start
    if weekly_gain <= 0:
        return {"actions": [], "status": "no_weekly_profit"}

    min_pct = config["portfolio_rules"]["weekly_profit_protect_min_pct"]
    max_pct = config["portfolio_rules"]["weekly_profit_protect_max_pct"]

    return {
        "actions": [{
            "type": "PORTFOLIO_PROFIT_GUARD",
            "side": "sell_to_usdc",
            "suggested_value_usd_range": [round(weekly_gain * min_pct, 2), round(weekly_gain * max_pct, 2)],
            "reason": f"Portfolio is up ${weekly_gain:.2f} from weekly baseline; protect {min_pct:.0%}-{max_pct:.0%}.",
            "confidence": 0.75,
        }],
        "status": "weekly_profit_available",
    }


def usdc_reserve_guard(usdc_value: float, total_value: float, config: Dict[str, Any], market_regime: str) -> Dict[str, Any]:
    if total_value <= 0:
        return {"ok": False, "target": 0, "current_pct": 0, "reason": "No portfolio value."}

    rules = config["portfolio_rules"]
    if market_regime == "panic":
        target = rules["panic_usdc_reserve_pct_target"]
    elif market_regime == "bear":
        target = rules["bear_usdc_reserve_pct_target"]
    elif market_regime == "chop":
        target = rules["chop_usdc_reserve_pct_target"]
    else:
        target = rules["normal_usdc_reserve_pct_target"]

    current_pct = usdc_value / total_value
    return {
        "ok": current_pct >= rules["normal_usdc_reserve_pct_min"],
        "target": target,
        "current_pct": current_pct,
        "deficit_usd": max((target * total_value) - usdc_value, 0),
        "reason": "USDC reserve checked.",
    }
