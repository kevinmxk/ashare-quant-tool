from __future__ import annotations

from datetime import date, timedelta
import time

from ashare_quant.models import DailyBar, QuoteSnapshot
from ashare_quant.providers.akshare_cleaner import (
    dataframe_to_records,
    map_bar_row,
    map_quote_row,
)
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.shared_cleaner import normalize_symbol, to_sina_symbol


class SinaMarketDataProvider(MarketDataProvider):
    """Sina-backed provider implemented through AKShare's public adapter."""

    def __init__(self, cache_ttl_seconds: int = 15, adjust: str = "qfq") -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:  # pragma: no cover - import failure depends on env
            raise RuntimeError("akshare is not installed, so Sina provider is unavailable") from exc

        self._ak = ak
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0)
        self._adjust = adjust
        self._spot_cache_records: list[dict] = []
        self._spot_cache_at: float = 0.0

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        rows = self._get_spot_rows()
        quotes: list[QuoteSnapshot] = []
        for row in rows:
            quote = map_quote_row(row)
            if quote is None:
                continue
            quotes.append(quote)
            if len(quotes) >= limit:
                break
        if not quotes:
            raise RuntimeError("Sina provider did not return valid quotes")
        return quotes

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        normalized_symbol = normalize_symbol(symbol)
        target_sina_symbol = to_sina_symbol(symbol).lower()

        for row in self._get_spot_rows():
            quote = map_quote_row(row)
            if quote is not None and quote.symbol == normalized_symbol:
                return quote

            row_symbol = str(row.get("symbol") or row.get("code") or "").strip().lower()
            if row_symbol == target_sina_symbol:
                quote = map_quote_row(row)
                if quote is not None:
                    return quote

        raise KeyError(f"Unknown symbol: {symbol}")

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        normalized_symbol = normalize_symbol(symbol)
        sina_symbol = to_sina_symbol(symbol)
        start_date = (date.today() - timedelta(days=max(lookback * 3, 180))).strftime("%Y-%m-%d")
        end_date = date.today().strftime("%Y-%m-%d")

        data = self._ak.stock_zh_a_daily(
            symbol=sina_symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=self._adjust,
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

        data = self._ak.stock_zh_a_spot()
        rows = dataframe_to_records(data)
        self._spot_cache_records = rows
        self._spot_cache_at = now
        return rows
