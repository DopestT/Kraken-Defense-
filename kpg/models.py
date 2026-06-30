from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WatchAsset:
    symbol: str
    pair: str
    asset_key: str
    tier: int
    thesis: str
    # "kraken" uses public_ticker(); "yahoo" uses stock_price() via Yahoo Finance.
    # Tokenized equities (*.EQ assets) must use "yahoo" since Kraken's public
    # Ticker API does not expose them.
    price_source: str = "kraken"
    yahoo_ticker: Optional[str] = None


@dataclass
class PositionSnapshot:
    symbol: str
    pair: str
    asset_key: str
    qty: float
    price: float
    value: float
    tier: int
    thesis: str
    avg_entry: Optional[float] = None
    cost_basis: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    recent_high_value: Optional[float] = None
    drawdown_from_high_pct: float = 0.0
    price_source: str = "kraken"
