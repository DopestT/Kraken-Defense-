from dataclasses import dataclass
from typing import Optional


@dataclass
class WatchAsset:
    symbol: str
    pair: str
    asset_key: str
    tier: int
    thesis: str


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
