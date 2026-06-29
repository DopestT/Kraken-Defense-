import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Dict

import requests


class KrakenClient:
    BASE_URL = "https://api.kraken.com"

    def __init__(self, api_key: str, api_secret: str) -> None:
        if not api_key or not api_secret:
            raise ValueError(
                "KRAKEN_API_KEY and KRAKEN_API_SECRET must be set in .env"
            )
        self.api_key = api_key
        self._api_secret = base64.b64decode(api_secret)

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _sign(self, url_path: str, data: Dict[str, Any]) -> str:
        post_data = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + post_data).encode()
        message = url_path.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(self._api_secret, message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode()

    # ------------------------------------------------------------------
    # Private endpoint
    # ------------------------------------------------------------------

    def _private(self, endpoint: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        url_path = f"/0/private/{endpoint}"
        data: Dict[str, Any] = {"nonce": str(int(time.time() * 1000))}
        if extra:
            data.update(extra)

        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(url_path, data),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        resp = requests.post(
            self.BASE_URL + url_path, headers=headers, data=data, timeout=15
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("error"):
            raise RuntimeError(f"Kraken API error: {result['error']}")
        return result["result"]

    # ------------------------------------------------------------------
    # Public endpoint
    # ------------------------------------------------------------------

    def _public(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/0/public/{endpoint}"
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        if result.get("error"):
            raise RuntimeError(f"Kraken API error: {result['error']}")
        return result["result"]

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def public_ticker(self, pair: str) -> Dict[str, Any]:
        """Return ticker data for a trading pair.

        Kraken returns a dict keyed by their internal pair name (e.g. XXBTZUSD).
        We unwrap the outer key so callers get the ticker dict directly.
        Fields of interest:
            c[0]  — last trade price
            b[0]  — best bid
            a[0]  — best ask
            v[1]  — 24h volume
        """
        result = self._public("Ticker", params={"pair": pair})
        return next(iter(result.values()))

    # ------------------------------------------------------------------
    # Private API methods
    # ------------------------------------------------------------------

    def balances(self) -> Dict[str, float]:
        """Return {asset: float} for all non-zero balances.

        Kraken asset names use internal codes, e.g.:
            XXBT  → Bitcoin
            XETH  → Ethereum
            ZUSD  → USD
            USDC  → USD Coin
        Match these against asset_key in config watchlist.
        """
        raw = self._private("Balance")
        return {k: float(v) for k, v in raw.items() if float(v) > 0}
