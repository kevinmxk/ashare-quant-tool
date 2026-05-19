from __future__ import annotations

from datetime import date, timedelta
import time

from ashare_quant.models import DailyBar, QuoteSnapshot
from ashare_quant.providers.akshare_cleaner import (
    dataframe_to_records,
    map_bar_row,
    map_quote_row,
    normalize_symbol,
)
from ashare_quant.providers.base import MarketDataProvider


class AkshareMarketDataProvider(MarketDataProvider):
    """AKShare provider with column normalization and lightweight caching."""

    def __init__(self, cache_ttl_seconds: int = 15) -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:  # pragma: no cover - import failure depends on env
            raise RuntimeError("akshare is not installed") from exc
        self._ak = ak
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0)
        self._spot_cache_records: list[dict] = []
        self._spot_cache_at: float = 0.0

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        rows = self._get_spot_rows()
        quotes: list[QuoteSnapshot] = []
        for row in rows:
            quote = map_quote_row(row)
            if quote is not None:
                quotes.append(quote)
            if len(quotes) >= limit:
                break
        return quotes

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        normalized_symbol = normalize_symbol(symbol)
        for row in self._get_spot_rows():
            quote = map_quote_row(row)
            if quote is not None and quote.symbol == normalized_symbol:
                return quote
        raise KeyError(f"Unknown symbol: {symbol}")

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        normalized_symbol = normalize_symbol(symbol)
        start_date = (date.today() - timedelta(days=max(lookback * 3, 120))).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")
        data = self._ak.stock_zh_a_hist(
            symbol=normalized_symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        rows = dataframe_to_records(data)
        if not rows:
            raise KeyError(f"No history found for symbol: {symbol}")

        bars: list[DailyBar] = []
        for row in rows[-lookback:]:
            bar = map_bar_row(row, fallback_symbol=normalized_symbol)
            if bar is not None:
                bars.append(bar)
        if not bars:
            raise KeyError(f"No valid historical bars found for symbol: {symbol}")
        return bars

    def _get_spot_rows(self) -> list[dict]:
        now = time.time()
        if self._spot_cache_records and now - self._spot_cache_at <= self._cache_ttl_seconds:
            return self._spot_cache_records

        data = self._ak.stock_zh_a_spot_em()
        rows = dataframe_to_records(data)
        self._spot_cache_records = rows
        self._spot_cache_at = now
        return rows
