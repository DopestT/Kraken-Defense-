import argparse
import os
from typing import Dict, Any, List

import yaml
from dotenv import load_dotenv

from .kraken_client import KrakenClient, KrakenAPIError
from .models import WatchAsset, PositionSnapshot
from .state import load_state, save_state, audit
from .orchestrator import decide


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def last_price(ticker: Dict[str, Any]) -> float:
    # Kraken Ticker: c = [last trade closed price, lot volume]
    return float(ticker["c"][0])


def build_positions(
    client: KrakenClient,
    balances: Dict[str, float],
    config: Dict[str, Any],
    state: Dict[str, Any],
) -> List[PositionSnapshot]:
    positions: List[PositionSnapshot] = []
    watch_assets = [WatchAsset(**x) for x in config["watchlist"]]

    for asset in watch_assets:
        qty = float(balances.get(asset.asset_key, 0.0))
        if qty <= 0:
            continue

        # Route price fetch: Kraken public ticker OR Yahoo Finance for .EQ equities
        try:
            if asset.price_source == "yahoo" and asset.yahoo_ticker:
                price = client.stock_price(asset.yahoo_ticker)
            else:
                ticker = client.public_ticker(asset.pair)
                price = last_price(ticker)
        except KrakenAPIError as exc:
            print(f"[WARN] Could not fetch price for {asset.symbol}: {exc}")
            continue

        value = qty * price

        pstate = state.setdefault("positions", {}).setdefault(asset.symbol, {})
        avg_entry = pstate.get("avg_entry")
        cost_basis = None
        pnl = None
        pnl_pct = None

        if avg_entry:
            cost_basis = qty * float(avg_entry)
            pnl = value - cost_basis
            pnl_pct = pnl / cost_basis if cost_basis else None

        positions.append(PositionSnapshot(
            symbol=asset.symbol,
            pair=asset.pair,
            asset_key=asset.asset_key,
            qty=qty,
            price=price,
            value=value,
            tier=asset.tier,
            thesis=asset.thesis,
            avg_entry=avg_entry,
            cost_basis=cost_basis,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
            price_source=asset.price_source,
        ))

    return positions


def estimate_total_value(
    client: KrakenClient,
    balances: Dict[str, float],
    positions: List[PositionSnapshot],
    config: Dict[str, Any],
) -> float:
    stable_assets = set(config["bot"]["stable_assets"])
    stable_value = sum(float(v) for k, v in balances.items() if k in stable_assets)
    watched_value = sum(p.value for p in positions)
    return stable_value + watched_value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.example.yaml")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Simulate orders without sending to Kraken (default: on)")
    args = parser.parse_args()

    load_dotenv()
    config = load_config(args.config)
    state = load_state(config["state"]["path"])

    client = KrakenClient(
        api_key=os.getenv("KRAKEN_API_KEY"),
        api_secret=os.getenv("KRAKEN_API_SECRET"),
        dry_run=args.dry_run,
    )

    balances = client.balances()
    positions = build_positions(client, balances, config, state)
    total_value = estimate_total_value(client, balances, positions, config)

    report = decide(
        positions=positions,
        balances=balances,
        total_value=total_value,
        state=state,
        config=config,
    )

    audit(state, {
        "type": "daily_run",
        "portfolio_status": report["portfolio_status"],
        "profit_moves_count": len(report["profit_moves"]),
        "buy_rebuy_moves_count": len(report["buy_rebuy_moves"]),
    })

    save_state(config["state"]["path"], state)

    import json
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
