from __future__ import annotations

from abc import ABC, abstractmethod

from ashare_quant.models import DailyBar, ProviderCallMeta, QuoteSnapshot


class MarketDataProvider(ABC):
    """Unified interface for multiple market data backends."""

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__

    def get_last_call_meta(self) -> ProviderCallMeta | None:
        return getattr(self, "_last_call_meta", None)

    def _set_last_call_meta(self, meta: ProviderCallMeta) -> None:
        self._last_call_meta = meta

    @abstractmethod
    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, symbol: str) -> QuoteSnapshot:
        raise NotImplementedError

    @abstractmethod
    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        raise NotImplementedError
