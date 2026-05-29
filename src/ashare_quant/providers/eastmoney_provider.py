from __future__ import annotations

from datetime import date, timedelta
import json
import time
from threading import RLock
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ashare_quant.models import DailyBar, ProviderCallMeta, QuoteSnapshot
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.shared_cleaner import detect_exchange, normalize_symbol, parse_trade_date, safe_float


class EastMoneyMarketDataProvider(MarketDataProvider):
    """Direct EastMoney HTTP provider for fast real-time A-share quotes."""

    _QUOTE_FIELDS = "f12,f14,f2,f3,f8,f6,f10,f9,f23,f20"
    _STOCK_FIELDS = "f57,f58,f43,f170,f168,f48,f10,f164,f167,f116"
    _UNIVERSE_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    def __init__(self, cache_ttl_seconds: int = 120, timeout_seconds: float = 3.0) -> None:
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0)
        self._timeout_seconds = max(timeout_seconds, 0.5)
        self._lock = RLock()
        self._spot_cache_records: list[dict[str, Any]] = []
        self._spot_cache_at = 0.0
        self._daily_cache: dict[tuple[str, int], tuple[float, list[DailyBar]]] = {}

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        rows = self._get_spot_rows(limit=max(limit, 1))
        quotes = [_map_quote_row(row) for row in rows]
        resolved = [quote for quote in quotes if quote is not None][:limit]
        if not resolved:
            raise RuntimeError("EastMoney provider did not return valid quotes")
        self._set_last_call_meta(
            ProviderCallMeta(
                operation="list_universe",
                resolved_provider=self.provider_name,
                source_provider=self.provider_name,
            )
        )
        return resolved

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        normalized_symbol = normalize_symbol(symbol)
        for row in self._get_spot_rows():
            quote = _map_quote_row(row)
            if quote is not None and quote.symbol == normalized_symbol:
                self._set_last_call_meta(
                    ProviderCallMeta(
                        operation="get_quote",
                        resolved_provider=self.provider_name,
                        source_provider=self.provider_name,
                    )
                )
                return quote

        payload = self._request_json(
            "http://push2.eastmoney.com/api/qt/stock/get",
            {
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "secid": _to_eastmoney_secid(normalized_symbol),
                "fields": self._STOCK_FIELDS,
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise KeyError("Unknown symbol: {symbol}".format(symbol=symbol))
        quote = _map_quote_row(
            {
                "f12": data.get("f57"),
                "f14": data.get("f58"),
                "f2": data.get("f43"),
                "f3": data.get("f170"),
                "f8": data.get("f168"),
                "f6": data.get("f48"),
                "f10": data.get("f10"),
                "f9": data.get("f164"),
                "f23": data.get("f167"),
                "f20": data.get("f116"),
            }
        )
        if quote is None:
            raise KeyError("Unknown symbol: {symbol}".format(symbol=symbol))
        self._set_last_call_meta(
            ProviderCallMeta(
                operation="get_quote",
                resolved_provider=self.provider_name,
                source_provider=self.provider_name,
            )
        )
        return quote

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        normalized_symbol = normalize_symbol(symbol)
        cache_key = (normalized_symbol, lookback)
        cached = self._daily_cache.get(cache_key)
        now = time.time()
        if cached is not None and now - cached[0] <= max(self._cache_ttl_seconds, 300):
            return cached[1]

        start_date = (date.today() - timedelta(days=max(lookback * 3, 180))).strftime("%Y%m%d")
        payload = self._request_json(
            "http://push2his.eastmoney.com/api/qt/stock/kline/get",
            {
                "secid": _to_eastmoney_secid(normalized_symbol),
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": "101",
                "fqt": "1",
                "beg": start_date,
                "end": "20500101",
                "lmt": str(max(lookback, 1)),
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        rows = data.get("klines") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise KeyError("No history found for symbol: {symbol}".format(symbol=symbol))

        bars = [_map_kline(item, normalized_symbol) for item in rows[-lookback:]]
        resolved = [bar for bar in bars if bar is not None]
        if not resolved:
            raise KeyError("No valid historical bars found for symbol: {symbol}".format(symbol=symbol))
        self._daily_cache[cache_key] = (now, resolved)
        self._set_last_call_meta(
            ProviderCallMeta(
                operation="get_daily_bars",
                resolved_provider=self.provider_name,
                source_provider=self.provider_name,
            )
        )
        return resolved

    def _get_spot_rows(self, limit: int = 5000) -> list[dict[str, Any]]:
        now = time.time()
        if self._spot_cache_records and now - self._spot_cache_at <= self._cache_ttl_seconds:
            return self._spot_cache_records
        with self._lock:
            now = time.time()
            if self._spot_cache_records and now - self._spot_cache_at <= self._cache_ttl_seconds:
                return self._spot_cache_records
            payload = self._request_json(
                "http://82.push2.eastmoney.com/api/qt/clist/get",
                {
                    "pn": "1",
                    "pz": str(max(limit, 1)),
                    "po": "1",
                    "np": "1",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": "2",
                    "invt": "2",
                    "fid": "f3",
                    "fs": self._UNIVERSE_FS,
                    "fields": self._QUOTE_FIELDS,
                },
            )
            data = payload.get("data") if isinstance(payload, dict) else None
            rows = data.get("diff") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise RuntimeError("EastMoney spot endpoint returned no records")
            self._spot_cache_records = [row for row in rows if isinstance(row, dict)]
            self._spot_cache_at = now
            return self._spot_cache_records

    def _request_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        request = Request(
            "{url}?{query}".format(url=url, query=urlencode(params)),
            headers={"User-Agent": self._USER_AGENT, "Referer": "http://quote.eastmoney.com/"},
        )
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                with urlopen(request, timeout=self._timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                break
            except URLError as exc:
                last_error = exc
                time.sleep(0.05)
        else:
            raise RuntimeError("EastMoney HTTP request failed: {error}".format(error=last_error))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("EastMoney HTTP response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("EastMoney HTTP response is not an object")
        return payload


def _to_eastmoney_secid(symbol: str) -> str:
    code = normalize_symbol(symbol)
    exchange = detect_exchange(code)
    market_id = "1" if exchange == "SH" else "0"
    return "{market}.{code}".format(market=market_id, code=code)


def _map_quote_row(row: dict[str, Any]) -> QuoteSnapshot | None:
    symbol = normalize_symbol(row.get("f12") or "")
    latest_price = safe_float(row.get("f2"))
    if not symbol or latest_price is None or latest_price <= 0:
        return None
    return QuoteSnapshot(
        symbol=symbol,
        name=str(row.get("f14") or symbol),
        latest_price=latest_price,
        pct_change=safe_float(row.get("f3"), default=0.0) or 0.0,
        turnover_rate=safe_float(row.get("f8"), default=0.0) or 0.0,
        amount=safe_float(row.get("f6"), default=0.0) or 0.0,
        volume_ratio=safe_float(row.get("f10"), default=0.0) or 0.0,
        pe_ttm=safe_float(row.get("f9")),
        pb=safe_float(row.get("f23")),
        market_cap=safe_float(row.get("f20")),
        sector=None,
    )


def _map_kline(value: Any, symbol: str) -> DailyBar | None:
    parts = str(value or "").split(",")
    if len(parts) < 7:
        return None
    trade_date = parse_trade_date(parts[0])
    open_price = safe_float(parts[1])
    close_price = safe_float(parts[2])
    high_price = safe_float(parts[3])
    low_price = safe_float(parts[4])
    volume = safe_float(parts[5], default=0.0)
    amount = safe_float(parts[6], default=0.0)
    if trade_date is None or None in (open_price, close_price, high_price, low_price):
        return None
    return DailyBar(
        symbol=symbol,
        trade_date=trade_date,
        open_price=open_price or 0.0,
        high_price=high_price or 0.0,
        low_price=low_price or 0.0,
        close_price=close_price or 0.0,
        volume=volume or 0.0,
        amount=amount or 0.0,
    )
