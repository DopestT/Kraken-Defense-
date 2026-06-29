from typing import Dict, Any, List
from .models import PositionSnapshot
from .scoring import score_position_advocacy
from .guards import position_profit_guard, portfolio_profit_guard, usdc_reserve_guard


def decide(
    positions: List[PositionSnapshot],
    balances: Dict[str, float],
    total_value: float,
    state: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:

    market_regime = config["market_regime"]["default"]
    stable_assets = set(config["bot"]["stable_assets"])
    usdc_value = 0.0

    # Stable valuation simplification: 1 stable/USD unit = $1.
    for k, v in balances.items():
        if k in stable_assets:
            usdc_value += float(v)

    reserve = usdc_reserve_guard(usdc_value, total_value, config, market_regime)

    profit_moves = []
    buy_moves = []
    position_reports = []

    # Portfolio-level guard.
    portfolio_guard = portfolio_profit_guard(total_value, state, config)
    profit_moves.extend(portfolio_guard.get("actions", []))

    for pos in positions:
        # Update recent high memory.
        pstate = state.setdefault("positions", {}).setdefault(pos.symbol, {})
        prev_high = pstate.get("recent_high_value")
        if prev_high is None or pos.value > prev_high:
            pstate["recent_high_value"] = pos.value
            pos.recent_high_value = pos.value
        else:
            pos.recent_high_value = prev_high

        if pos.recent_high_value and pos.recent_high_value > 0:
            pos.drawdown_from_high_pct = max((pos.recent_high_value - pos.value) / pos.recent_high_value, 0)

        court = score_position_advocacy(pos, market_regime, reserve["ok"])
        pguard = position_profit_guard(pos, config)

        # Conflict resolver: protection beats opportunity; safety beats everything.
        final_action = "HOLD"
        if market_regime == "panic":
            final_action = "ALERT_ONLY"
        elif court["court_verdict"] in ("EXIT", "REDUCE"):
            final_action = court["court_verdict"]
        elif pguard["actions"]:
            final_action = "PROTECT"
            profit_moves.extend(pguard["actions"])
        elif court["court_verdict"] == "PROBATION":
            final_action = "PROBATION"

        position_reports.append({
            "symbol": pos.symbol,
            "value": round(pos.value, 2),
            "qty": pos.qty,
            "price": pos.price,
            "pnl_usd": None if pos.unrealized_pnl is None else round(pos.unrealized_pnl, 2),
            "pnl_pct": None if pos.unrealized_pnl_pct is None else round(pos.unrealized_pnl_pct, 4),
            "advocacy_score": court["advocacy_score"],
            "court_verdict": court["court_verdict"],
            "final_action": final_action,
            "reasons": court["reasons"][:5],
        })

    # Buy/rebuy suggestions are intentionally conservative in v1.
    if not reserve["ok"]:
        buy_moves.append({
            "type": "NO_BUY",
            "reason": f"USDC reserve is {reserve['current_pct']:.1%}, below minimum. Restore reserve first.",
            "confidence": 0.90,
        })
    elif market_regime in ("chop", "bear", "panic"):
        buy_moves.append({
            "type": "WAIT_FOR_PULLBACK",
            "reason": f"Market regime is {market_regime}; avoid chasing. Buy only support/retest setups.",
            "confidence": 0.70,
        })
    else:
        buy_moves.append({
            "type": "WATCHLIST_SCAN",
            "reason": "Bull mode allows clean pullback/retest entries, but v1 scanner needs OHLC upgrade.",
            "confidence": 0.60,
        })

    risk_level = "Medium"
    if market_regime in ("bear", "panic") or not reserve["ok"]:
        risk_level = "High"
    elif reserve["current_pct"] >= reserve["target"]:
        risk_level = "Low"

    account_mode = "wait"
    if profit_moves:
        account_mode = "protect"
    elif market_regime == "bull" and reserve["ok"]:
        account_mode = "attack"

    return {
        "portfolio_status": {
            "total_value_usd": round(total_value, 2),
            "usdc_value": round(usdc_value, 2),
            "usdc_reserve_pct": round(reserve["current_pct"], 4),
            "usdc_target_pct": reserve["target"],
            "risk_level": risk_level,
            "market_regime": market_regime,
            "account_mode": account_mode,
        },
        "profit_moves": profit_moves[:3],
        "buy_rebuy_moves": buy_moves[:3],
        "positions": position_reports,
        "final_assessment": f"Account is in {account_mode.upper()} mode. Safety and profit protection outrank new buys.",
    }
