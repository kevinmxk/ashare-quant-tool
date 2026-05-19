from __future__ import annotations

from datetime import date, timedelta

from ashare_quant.models import DailyBar, QuoteSnapshot
from ashare_quant.providers.base import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic offline provider for local development."""

    def __init__(self) -> None:
        self._quotes = [
            QuoteSnapshot("600519", "贵州茅台", 1688.0, 1.6, 0.42, 6.2e9, 1.1, 25.0, 8.9, 2.1e12, "白酒"),
            QuoteSnapshot("000858", "五粮液", 149.8, 2.3, 0.95, 3.9e9, 1.4, 18.2, 5.1, 5.8e11, "白酒"),
            QuoteSnapshot("300750", "宁德时代", 212.4, 3.2, 1.25, 9.7e9, 1.8, 21.5, 4.8, 9.3e11, "新能源"),
            QuoteSnapshot("601127", "赛力斯", 97.6, 4.8, 3.65, 8.4e9, 2.2, None, 7.4, 1.5e11, "汽车"),
            QuoteSnapshot("002594", "比亚迪", 258.5, 1.1, 1.15, 7.1e9, 1.3, 24.4, 5.9, 7.6e11, "汽车"),
            QuoteSnapshot("600036", "招商银行", 34.1, 0.6, 0.51, 2.0e9, 0.9, 6.2, 0.92, 8.6e11, "银行"),
            QuoteSnapshot("600030", "中信证券", 21.4, 1.9, 1.42, 4.5e9, 1.7, 14.1, 1.28, 3.1e11, "券商"),
            QuoteSnapshot("002415", "海康威视", 33.6, 2.1, 1.08, 2.7e9, 1.5, 19.7, 3.6, 3.1e11, "安防"),
            QuoteSnapshot("002230", "科大讯飞", 51.2, 5.2, 4.12, 6.6e9, 2.8, 62.0, 6.1, 1.2e11, "AI"),
            QuoteSnapshot("688981", "中芯国际", 49.8, 3.5, 2.04, 5.3e9, 2.0, 41.0, 2.7, 3.9e11, "半导体"),
        ]

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        return self._quotes[:limit]

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        for quote in self._quotes:
            if quote.symbol == symbol:
                return quote
        raise KeyError(f"Unknown symbol: {symbol}")

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        quote = self.get_quote(symbol)
        today = date.today()
        bars: list[DailyBar] = []
        base = quote.latest_price * 0.82
        slope = (quote.latest_price - base) / max(lookback, 1)

        for offset in range(lookback):
            trade_date = today - timedelta(days=lookback - offset)
            close_price = round(base + slope * offset + (offset % 5 - 2) * 0.35, 2)
            open_price = round(close_price * 0.995, 2)
            high_price = round(close_price * 1.012, 2)
            low_price = round(close_price * 0.988, 2)
            volume = 1_000_000 + offset * 18_000
            amount = volume * close_price
            bars.append(
                DailyBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=volume,
                    amount=amount,
                )
            )
        return bars
