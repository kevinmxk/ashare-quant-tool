from __future__ import annotations

from datetime import date, timedelta
import os
import time
from typing import Any

from ashare_quant.models import DailyBar, QuoteSnapshot
from ashare_quant.providers.akshare_cleaner import dataframe_to_records
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.shared_cleaner import (
    normalize_symbol,
    parse_trade_date,
    safe_float,
    safe_text,
    to_tushare_code,
)


class TushareMarketDataProvider(MarketDataProvider):
    """Tushare provider focused on daily research rather than intraday data."""

    def __init__(self, token: str | None = None, cache_ttl_seconds: int = 3600) -> None:
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:  # pragma: no cover - import failure depends on env
            raise RuntimeError("tushare is not installed") from exc

        actual_token = token or os.getenv("ASHARE_QUANT_TUSHARE_TOKEN") or os.getenv("TUSHARE_TOKEN")
        if not actual_token:
            raise RuntimeError("Tushare token is missing")

        ts.set_token(actual_token)
        self._ts = ts
        self._pro = ts.pro_api(actual_token)
        self._cache_ttl_seconds = max(cache_ttl_seconds, 60)
        self._stock_basic_cache: list[dict[str, Any]] = []
        self._stock_basic_cache_at = 0.0

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        basics = self._get_stock_basic_records()
        quotes: list[QuoteSnapshot] = []
        for basic in basics:
            if len(quotes) >= limit:
                break
            try:
                quote = self._build_quote_from_basic_record(basic)
            except Exception:
                continue
            quotes.append(quote)
        if not quotes:
            raise RuntimeError("Tushare did not return valid quotes")
        return quotes

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        basic = self._find_basic_record(symbol)
        return self._build_quote_from_basic_record(basic)

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        ts_code = to_tushare_code(symbol)
        start_date = (date.today() - timedelta(days=max(lookback * 3, 180))).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")

        records = self._fetch_qfq_daily_records(ts_code, start_date, end_date)
        bars: list[DailyBar] = []
        for row in sorted(records, key=_trade_date_key):
            trade_date = parse_trade_date(row.get("trade_date"))
            open_price = safe_float(row.get("open"))
            high_price = safe_float(row.get("high"))
            low_price = safe_float(row.get("low"))
            close_price = safe_float(row.get("close"))
            amount = safe_float(row.get("amount"), default=0.0)
            volume = safe_float(row.get("vol"), default=0.0)
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

    def _build_quote_from_basic_record(self, basic: dict[str, Any]) -> QuoteSnapshot:
        ts_code = str(basic.get("ts_code") or to_tushare_code(basic.get("symbol") or ""))
        symbol = normalize_symbol(basic.get("symbol") or ts_code)
        bars = self.get_daily_bars(symbol, lookback=30)
        latest_bar = bars[-1]
        previous_close = bars[-2].close_price if len(bars) >= 2 else latest_bar.close_price
        basic_metrics = self._fetch_daily_basic_record(ts_code)

        if previous_close:
            pct_change = (latest_bar.close_price / previous_close - 1.0) * 100
        else:
            pct_change = 0.0

        return QuoteSnapshot(
            symbol=symbol,
            name=str(basic.get("name") or symbol),
            latest_price=latest_bar.close_price,
            pct_change=round(pct_change, 2),
            turnover_rate=safe_float(basic_metrics.get("turnover_rate"), default=0.0) or 0.0,
            amount=latest_bar.amount,
            volume_ratio=safe_float(basic_metrics.get("volume_ratio"), default=0.0) or 0.0,
            pe_ttm=safe_float(basic_metrics.get("pe_ttm")),
            pb=safe_float(basic_metrics.get("pb")),
            market_cap=safe_float(basic_metrics.get("total_mv")),
            sector=safe_text(basic.get("industry")),
        )

    def _get_stock_basic_records(self) -> list[dict[str, Any]]:
        now = time.time()
        if self._stock_basic_cache and now - self._stock_basic_cache_at <= self._cache_ttl_seconds:
            return self._stock_basic_cache

        data = self._pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,industry",
        )
        records = dataframe_to_records(data)
        if not records:
            raise RuntimeError("Tushare stock_basic returned no records")
        self._stock_basic_cache = records
        self._stock_basic_cache_at = now
        return records

    def _find_basic_record(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = normalize_symbol(symbol)
        ts_code = to_tushare_code(symbol)
        for record in self._get_stock_basic_records():
            if normalize_symbol(record.get("symbol") or record.get("ts_code") or "") == normalized_symbol:
                return record
            if str(record.get("ts_code") or "").upper() == ts_code:
                return record
        data = self._pro.stock_basic(
            ts_code=ts_code,
            fields="ts_code,symbol,name,industry",
        )
        records = dataframe_to_records(data)
        if not records:
            raise KeyError("Unknown symbol: {symbol}".format(symbol=symbol))
        return records[0]

    def _fetch_qfq_daily_records(self, ts_code: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        try:
            data = self._ts.pro_bar(
                ts_code=ts_code,
                adj="qfq",
                start_date=start_date,
                end_date=end_date,
            )
            records = dataframe_to_records(data)
            if records:
                return records
        except Exception:
            pass

        fallback = self._pro.daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )
        records = dataframe_to_records(fallback)
        if not records:
            raise RuntimeError("Tushare daily/pro_bar returned no records for {code}".format(code=ts_code))
        return records

    def _fetch_daily_basic_record(self, ts_code: str) -> dict[str, Any]:
        start_date = (date.today() - timedelta(days=30)).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")
        data = self._pro.daily_basic(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields="ts_code,trade_date,turnover_rate,volume_ratio,pe_ttm,pb,total_mv",
        )
        records = dataframe_to_records(data)
        if not records:
            return {}
        records.sort(key=_trade_date_key)
        return records[-1]


def _trade_date_key(row: dict[str, Any]) -> str:
    return str(row.get("trade_date") or "")
