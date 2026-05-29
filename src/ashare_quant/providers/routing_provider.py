from __future__ import annotations

from dataclasses import replace

from ashare_quant.models import DailyBar, ProviderCallMeta, QuoteSnapshot
from ashare_quant.providers.base import MarketDataProvider


class OperationRoutingMarketDataProvider(MarketDataProvider):
    """Route real-time quote calls and historical bar calls to different providers."""

    def __init__(
        self,
        *,
        quote_provider: MarketDataProvider,
        bars_provider: MarketDataProvider,
        fast_bars_provider: MarketDataProvider | None = None,
        name: str = "DualSource",
    ) -> None:
        self.quote_provider = quote_provider
        self.bars_provider = bars_provider
        self.fast_bars_provider = fast_bars_provider or quote_provider
        self._name = name

    @property
    def provider_name(self) -> str:
        return "{name}(quote={quote}, bars={bars})".format(
            name=self._name,
            quote=self.quote_provider.provider_name,
            bars=self.bars_provider.provider_name,
        )

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        result = self.quote_provider.list_universe(limit=limit)
        self._copy_child_meta("list_universe", self.quote_provider)
        return result

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        result = self.quote_provider.get_quote(symbol)
        self._copy_child_meta("get_quote", self.quote_provider)
        return result

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        result = self.bars_provider.get_daily_bars(symbol, lookback=lookback)
        self._copy_child_meta("get_daily_bars", self.bars_provider)
        return result

    def get_fast_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        """Return fast bars for interactive cold-cache rendering.

        The normal get_daily_bars path remains routed to the accurate bars provider.
        Cache wrappers can use this method only while a precise refresh is running.
        """
        result = self.fast_bars_provider.get_daily_bars(symbol, lookback=lookback)
        self._copy_child_meta("get_fast_daily_bars", self.fast_bars_provider)
        return result

    def _copy_child_meta(self, operation: str, provider: MarketDataProvider) -> None:
        child_meta = provider.get_last_call_meta()
        if child_meta is None:
            self._set_last_call_meta(
                ProviderCallMeta(
                    operation=operation,
                    resolved_provider=self.provider_name,
                    source_provider=provider.provider_name,
                )
            )
            return
        self._set_last_call_meta(
            replace(
                child_meta,
                operation=operation,
                resolved_provider=self.provider_name,
                source_provider=child_meta.source_provider or provider.provider_name,
            )
        )
