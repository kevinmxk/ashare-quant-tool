from __future__ import annotations

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from ashare_quant.models import DailyBar, ProviderCallMeta, QuoteSnapshot
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.services.market_service import MarketService


class StubProvider(MarketDataProvider):
    def __init__(self) -> None:
        self._bars = [
            DailyBar(
                symbol="600519",
                trade_date=date(2024, 1, 2),
                open_price=100.0,
                high_price=105.0,
                low_price=99.0,
                close_price=103.0,
                volume=1000.0,
                amount=103000.0,
            )
        ]

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        return []

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        return QuoteSnapshot(
            symbol=symbol,
            name="Stub",
            latest_price=103.0,
            pct_change=1.0,
            turnover_rate=2.0,
            amount=103000.0,
            volume_ratio=1.1,
        )

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        self._set_last_call_meta(
            ProviderCallMeta(
                operation="get_daily_bars",
                resolved_provider=self.provider_name,
                source_provider=self.provider_name,
            )
        )
        return self._bars[:lookback]


class TestMarketService(unittest.TestCase):
    def test_get_stock_bars_returns_bars_and_meta(self) -> None:
        provider = StubProvider()
        service = MarketService(provider)

        result = service.get_stock_bars("600519", lookback=60)

        self.assertEqual(result.symbol, "600519")
        self.assertEqual(len(result.bars), 1)
        self.assertEqual(result.bars[0].close_price, 103.0)
        self.assertIsNotNone(result.bars_meta)
        self.assertEqual(result.bars_meta.operation, "get_daily_bars")


if __name__ == "__main__":
    unittest.main()
