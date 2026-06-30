from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://api.kraken.com"
TIMEOUT = 15


class KrakenAPIError(RuntimeError):
    """Raised when Kraken or Yahoo Finance returns an error payload."""


@dataclass(frozen=True)
class Candle:
    """Single OHLC candlestick from Kraken's public OHLC endpoint."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    vwap: float
    volume: float
    count: int


@dataclass(frozen=True)
class OrderResult:
    """Result of place_market_order()."""
    status: str          # "submitted" | "dry_run"
    side: str            # "buy" | "sell"
    volume: float
    pair: str
    txid: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


class KrakenClient:
    def __init__(self, api_key: str, api_secret: str, dry_run: bool = True) -> None:
        if not api_key or not api_secret:
            raise ValueError("KRAKEN_API_KEY and KRAKEN_API_SECRET must be set in .env")
        self.api_key = api_key
        self._api_secret_raw = api_secret
        self.dry_run = dry_run
        # Persistent session — reuses TCP connections across all requests.
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # Signing (Kraken HMAC-SHA512)
    # ------------------------------------------------------------------

    def _sign(self, path: str, data: Dict[str, Any]) -> str:
        encoded = (str(data["nonce"]) + urllib.parse.urlencode(data)).encode()
        message = path.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self._api_secret_raw), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode()

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    def _public_get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        resp = self.session.get(
            f"{BASE_URL}/0/public/{endpoint}", params=params, timeout=TIMEOUT
        )
        resp.raise_for_status()
        payload = resp.json()
        errors = payload.get("error", [])
        if errors:
            raise KrakenAPIError(", ".join(errors))
        return payload.get("result", {})

    def _private_post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(path, data),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = self.session.post(BASE_URL + path, headers=headers, data=data, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        errors = payload.get("error", [])
        if errors:
            raise KrakenAPIError(", ".join(errors))
        return payload.get("result", {})

    def _private(self, endpoint: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        path = f"/0/private/{endpoint}"
        data: Dict[str, Any] = {"nonce": str(int(time.time() * 1000))}
        if extra:
            data.update(extra)
        return self._private_post(path, data)

    # ------------------------------------------------------------------
    # Public Kraken API
    # ------------------------------------------------------------------

    def get_price(self, pair: str) -> float:
        """Return last trade price for a Kraken trading pair."""
        result = self._public_get("Ticker", params={"pair": pair})
        if not result:
            raise KrakenAPIError(f"No ticker data for pair={pair!r}")
        return float(next(iter(result.values()))["c"][0])

    def public_ticker(self, pair: str) -> Dict[str, Any]:
        """Return full ticker dict (backward-compat). Prefer get_price() for just the price.

        Fields of interest:
            c[0]  — last trade price
            b[0]  — best bid
            a[0]  — best ask
            v[1]  — 24 h volume
        """
        result = self._public_get("Ticker", params={"pair": pair})
        if not result:
            raise KrakenAPIError(f"No ticker data for pair={pair!r}")
        return next(iter(result.values()))

    def get_ohlc(self, pair: str, interval: int = 60, since: Optional[int] = None) -> List[Candle]:
        """Fetch OHLC candlestick data.

        interval: minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
        since: Unix timestamp — only candles after this time are returned.
        """
        params: Dict[str, Any] = {"pair": pair, "interval": interval}
        if since is not None:
            params["since"] = since
        result = self._public_get("OHLC", params=params)
        if not result:
            raise KrakenAPIError(f"No OHLC data for pair={pair!r}")
        pair_key = next((k for k in result if k != "last"), None)
        if not pair_key:
            raise KrakenAPIError(f"OHLC response missing pair key for pair={pair!r}")
        return [
            Candle(
                timestamp=int(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                vwap=float(row[5]),
                volume=float(row[6]),
                count=int(row[7]),
            )
            for row in result[pair_key]
        ]

    # ------------------------------------------------------------------
    # Yahoo Finance fallback (for Kraken tokenized equities, e.g. RXRX.EQ)
    # ------------------------------------------------------------------

    def stock_price(self, ticker: str) -> float:
        """Fetch current price from Yahoo Finance.

        Used for .EQ tokenized equity positions (RXRX, MSOS, SPCX, RDW, LUNR)
        that Kraken's public Ticker API does not expose.
        """
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        resp = self.session.get(
            url, params={"interval": "1d", "range": "1d"}, headers=headers, timeout=TIMEOUT
        )
        resp.raise_for_status()
        try:
            price = resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
            return float(price)
        except (KeyError, IndexError, TypeError) as exc:
            raise KrakenAPIError(f"Yahoo Finance: could not parse price for {ticker!r}: {exc}")

    # ------------------------------------------------------------------
    # Private Kraken API
    # ------------------------------------------------------------------

    def balances(self) -> Dict[str, float]:
        """Return {asset: float} for all non-zero balances.

        Kraken internal asset codes used as keys, e.g.:
            XXBT  → Bitcoin
            XETH  → Ethereum
            ZUSD  → USD
            SOL03.S → Staked Solana
            RXRX.EQ → Recursion Pharma tokenized equity
        Match these against asset_key in config watchlist.
        """
        raw = self._private("Balance")
        return {k: float(v) for k, v in raw.items() if float(v) > 0}

    def place_market_order(self, side: str, pair: str, volume: float) -> OrderResult:
        """Place a market order. No-ops in dry_run mode (default: True).

        Always set dry_run=False explicitly in live config before enabling.
        """
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        if volume <= 0:
            raise ValueError("volume must be > 0")
        if self.dry_run:
            return OrderResult(
                status="dry_run",
                side=side,
                volume=volume,
                pair=pair,
                txid=None,
                raw={"message": "Dry-run mode: no live order sent."},
            )
        data = {
            "nonce": str(int(time.time() * 1000)),
            "ordertype": "market",
            "type": side,
            "pair": pair,
            "volume": str(volume),
        }
        result = self._private_post("/0/private/AddOrder", data)
        txids = result.get("txid", [])
        return OrderResult(
            status="submitted",
            side=side,
            volume=volume,
            pair=pair,
            txid=txids[0] if txids else None,
            raw=result,
        )
