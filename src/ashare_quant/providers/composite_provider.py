from __future__ import annotations

from dataclasses import replace

from ashare_quant.models import DailyBar, ProviderCallMeta, QuoteSnapshot
from ashare_quant.providers.base import MarketDataProvider


class CompositeMarketDataProvider(MarketDataProvider):
    """Try multiple providers in order, returning the first successful result."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        if not providers:
            raise ValueError("CompositeMarketDataProvider requires at least one provider")
        self.providers = providers

    @property
    def provider_name(self) -> str:
        names = [provider.provider_name for provider in self.providers]
        return "Composite({names})".format(names=" -> ".join(names))

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        return self._first_success("list_universe", limit=limit)

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        return self._first_success("get_quote", symbol=symbol)

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        return self._first_success("get_daily_bars", symbol=symbol, lookback=lookback)

    def _first_success(self, method_name: str, **kwargs):
        last_error: Exception | None = None
        attempted: list[str] = []
        for provider in self.providers:
            attempted.append(provider.provider_name)
            method = getattr(provider, method_name)
            try:
                result = method(**kwargs)
            except Exception as exc:
                last_error = exc
                continue
            if result:
                child_meta = provider.get_last_call_meta()
                if child_meta is None:
                    meta = ProviderCallMeta(
                        operation=method_name,
                        resolved_provider=self.provider_name,
                        source_provider=provider.provider_name,
                        attempted_providers=attempted[:],
                    )
                else:
                    meta = replace(
                        child_meta,
                        resolved_provider=self.provider_name,
                        attempted_providers=attempted[:],
                    )
                self._set_last_call_meta(meta)
                return result
        if last_error is not None:
            raise last_error
        raise RuntimeError("No provider returned data for {method}".format(method=method_name))
