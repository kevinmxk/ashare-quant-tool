from __future__ import annotations

import atexit
from datetime import date, timedelta
import time
from threading import RLock
from typing import Any

from ashare_quant.models import DailyBar, QuoteSnapshot
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.shared_cleaner import (
    normalize_symbol,
    parse_trade_date,
    safe_float,
    safe_text,
    to_baostock_code,
)


class BaostockMarketDataProvider(MarketDataProvider):
    """BaoStock provider used mainly for historical backup and fallback."""

    def __init__(self) -> None:
        try:
            import baostock as bs  # type: ignore
        except ImportError as exc:  # pragma: no cover - import failure depends on env
            raise RuntimeError("baostock is not installed") from exc

        self._bs = bs
        login_result = bs.login()
        if str(login_result.error_code) != "0":
            raise RuntimeError("BaoStock login failed: {msg}".format(msg=login_result.error_msg))
        atexit.register(self._safe_logout)
        self._lock = RLock()
        self._universe_cache: list[dict[str, Any]] = []
        self._history_cache: dict[tuple[str, int], tuple[float, list[dict[str, Any]]]] = {}

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        records = self._get_universe_records()
        quotes: list[QuoteSnapshot] = []
        for record in records:
            if len(quotes) >= limit:
                break
            try:
                quote = self.get_quote(record.get("code") or "")
            except Exception:
                continue
            if not quote.name:
                quote.name = str(record.get("code_name") or quote.symbol)
            quotes.append(quote)
        if not quotes:
            raise RuntimeError("BaoStock did not return valid quotes")
        return quotes

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        bs_code = to_baostock_code(symbol)
        info = self._find_universe_record(bs_code)
        bars = self.get_daily_bars(symbol, lookback=30)
        latest_bar = bars[-1]
        raw_metrics = self._fetch_history_metric_records(bs_code, lookback=30)
        latest_metric = raw_metrics[-1] if raw_metrics else {}
        previous_close = bars[-2].close_price if len(bars) >= 2 else latest_bar.close_price

        pct_change = safe_float(latest_metric.get("pctChg"))
        if pct_change is None:
            pct_change = (latest_bar.close_price / previous_close - 1.0) * 100 if previous_close else 0.0

        return QuoteSnapshot(
            symbol=normalize_symbol(symbol),
            name=str(info.get("code_name") or info.get("name") or normalize_symbol(symbol)),
            latest_price=latest_bar.close_price,
            pct_change=round(pct_change, 2),
            turnover_rate=safe_float(latest_metric.get("turn"), default=0.0) or 0.0,
            amount=latest_bar.amount,
            volume_ratio=0.0,
            pe_ttm=safe_float(latest_metric.get("peTTM")),
            pb=safe_float(latest_metric.get("pbMRQ")),
            market_cap=None,
            sector=safe_text(info.get("industry")),
        )

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        bs_code = to_baostock_code(symbol)
        records = self._fetch_history_metric_records(bs_code, lookback=lookback)
        bars: list[DailyBar] = []
        for row in records:
            trade_date = parse_trade_date(row.get("date"))
            open_price = safe_float(row.get("open"))
            high_price = safe_float(row.get("high"))
            low_price = safe_float(row.get("low"))
            close_price = safe_float(row.get("close"))
            volume = safe_float(row.get("volume"), default=0.0)
            amount = safe_float(row.get("amount"), default=0.0)
            if trade_date is None or None in (open_price, high_price, low_price, close_price):
                continue
            bars.append(
                DailyBar(
                    symbol=normalize_symbol(symbol),
                    trade_date=trade_date,
                    open_price=open_price or 0.0,
                    high_price=high_price or 0.0,
                    low_price=low_price or 0.0,
                    close_price=close_price or 0.0,
                    volume=volume or 0.0,
                    amount=amount or 0.0,
                )
            )
        if not bars:
            raise KeyError("No valid historical bars found for symbol: {symbol}".format(symbol=symbol))
        return bars[-lookback:]

    def _get_universe_records(self) -> list[dict[str, Any]]:
        if self._universe_cache:
            return self._universe_cache
        with self._lock:
            if self._universe_cache:
                return self._universe_cache
            day = date.today().strftime("%Y-%m-%d")
            result = self._bs.query_all_stock(day=day)
            records = _resultset_to_records(result)
            if not records:
                result = self._bs.query_all_stock()
                records = _resultset_to_records(result)
            filtered = [row for row in records if _is_a_share_code(str(row.get("code") or ""))]
            if not filtered:
                raise RuntimeError("BaoStock query_all_stock returned no A-share records")
            self._universe_cache = filtered
            return filtered

    def _find_universe_record(self, bs_code: str) -> dict[str, Any]:
        for record in self._get_universe_records():
            if str(record.get("code") or "").lower() == bs_code.lower():
                return record
        return {}

    def _fetch_history_metric_records(self, bs_code: str, lookback: int = 60) -> list[dict[str, Any]]:
        cache_key = (bs_code.lower(), lookback)
        cached = self._history_cache.get(cache_key)
        now = time.time()
        if cached is not None and now - cached[0] <= 300:
            return cached[1]
        start_date = (date.today() - timedelta(days=max(lookback * 3, 180))).strftime("%Y-%m-%d")
        end_date = date.today().strftime("%Y-%m-%d")
        fields = ",".join(
            [
                "date",
                "code",
                "open",
                "high",
                "low",
                "close",
                "preclose",
                "volume",
                "amount",
                "turn",
                "pctChg",
                "peTTM",
                "pbMRQ",
                "isST",
            ]
        )
        with self._lock:
            cached = self._history_cache.get(cache_key)
            now = time.time()
            if cached is not None and now - cached[0] <= 300:
                return cached[1]
            result = self._bs.query_history_k_data_plus(
                bs_code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",
            )
            records = _resultset_to_records(result)
            if not records:
                raise RuntimeError("BaoStock history query returned no records for {code}".format(code=bs_code))
            records.sort(key=lambda row: str(row.get("date") or ""))
            self._history_cache[cache_key] = (now, records)
            return records

    def _safe_logout(self) -> None:
        try:
            with self._lock:
                self._bs.logout()
        except Exception:
            pass


def _resultset_to_records(result) -> list[dict[str, Any]]:
    if str(getattr(result, "error_code", "")) != "0":
        raise RuntimeError("BaoStock query failed: {msg}".format(msg=getattr(result, "error_msg", "")))

    fields = list(getattr(result, "fields", []) or [])
    rows: list[dict[str, Any]] = []
    while result.next():
        values = list(result.get_row_data())
        rows.append(dict(zip(fields, values)))
    return rows


def _is_a_share_code(bs_code: str) -> bool:
    code = bs_code.lower()
    return code.startswith(
        (
            "sh.600",
            "sh.601",
            "sh.603",
            "sh.605",
            "sh.688",
            "sz.000",
            "sz.001",
            "sz.002",
            "sz.003",
            "sz.300",
            "sz.301",
            "bj.",
        )
    )
