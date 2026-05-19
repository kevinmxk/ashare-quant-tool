from __future__ import annotations

from dataclasses import replace

from ashare_quant.cache.sqlite_cache import SqliteMarketCache
from ashare_quant.models import DailyBar, ProviderCallMeta, QuoteSnapshot
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.shared_cleaner import normalize_symbol


class PersistentCacheMarketDataProvider(MarketDataProvider):
    """Wraps a provider with a local sqlite-backed persistent cache."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache: SqliteMarketCache,
        quote_ttl_seconds: int = 900,
        bar_ttl_seconds: int = 43200,
        allow_stale_on_error: bool = True,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.quote_ttl_seconds = max(quote_ttl_seconds, 1)
        self.bar_ttl_seconds = max(bar_ttl_seconds, 60)
        self.allow_stale_on_error = allow_stale_on_error

    @property
    def provider_name(self) -> str:
        return "PersistentCache({name})".format(name=self.provider.provider_name)

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        cached = self.cache.load_universe(self.provider.provider_name, self.quote_ttl_seconds, limit)
        if cached:
            cache_meta = self.cache.get_universe_cache_meta(self.provider.provider_name) or {}
            self._set_last_call_meta(
                ProviderCallMeta(
                    operation="list_universe",
                    resolved_provider=self.provider_name,
                    source_provider=str(cache_meta.get("source_provider") or self.provider.provider_name),
                    from_cache=True,
                    used_stale_cache=False,
                    cache_age_seconds=cache_meta.get("age_seconds"),
                    cache_backend="sqlite",
                    note="fresh_cache_hit",
                )
            )
            return cached
        try:
            quotes = self.provider.list_universe(limit=limit)
        except Exception:
            if not self.allow_stale_on_error:
                raise
            stale = self.cache.load_universe(self.provider.provider_name, max_age_seconds=10**12, limit=limit)
            if stale:
                cache_meta = self.cache.get_universe_cache_meta(self.provider.provider_name) or {}
                self._set_last_call_meta(
                    ProviderCallMeta(
                        operation="list_universe",
                        resolved_provider=self.provider_name,
                        source_provider=str(cache_meta.get("source_provider") or self.provider.provider_name),
                        from_cache=True,
                        used_stale_cache=True,
                        cache_age_seconds=cache_meta.get("age_seconds"),
                        cache_backend="sqlite",
                        note="stale_cache_fallback",
                    )
                )
                return stale
            raise
        child_meta = self.provider.get_last_call_meta()
        source_provider = child_meta.source_provider if child_meta is not None else self.provider.provider_name
        self.cache.save_universe(self.provider.provider_name, quotes, source_provider=source_provider)
        self._set_last_call_meta(_wrap_child_meta(self.provider_name, "list_universe", child_meta, source_provider))
        return quotes

    def get_quote(self, symbol: str) -> QuoteSnapshot:
        normalized_symbol = normalize_symbol(symbol)
        cached = self.cache.load_latest_quote(self.provider.provider_name, normalized_symbol, self.quote_ttl_seconds)
        if cached is not None:
            cache_meta = self.cache.get_quote_cache_meta(self.provider.provider_name, normalized_symbol) or {}
            self._set_last_call_meta(
                ProviderCallMeta(
                    operation="get_quote",
                    resolved_provider=self.provider_name,
                    source_provider=str(cache_meta.get("source_provider") or self.provider.provider_name),
                    from_cache=True,
                    used_stale_cache=False,
                    cache_age_seconds=cache_meta.get("age_seconds"),
                    cache_backend="sqlite",
                    note="fresh_cache_hit",
                )
            )
            return cached
        try:
            quote = self.provider.get_quote(normalized_symbol)
        except Exception:
            if not self.allow_stale_on_error:
                raise
            stale = self.cache.load_latest_quote_any_age(self.provider.provider_name, normalized_symbol)
            if stale is not None:
                cache_meta = self.cache.get_quote_cache_meta(self.provider.provider_name, normalized_symbol) or {}
                self._set_last_call_meta(
                    ProviderCallMeta(
                        operation="get_quote",
                        resolved_provider=self.provider_name,
                        source_provider=str(cache_meta.get("source_provider") or self.provider.provider_name),
                        from_cache=True,
                        used_stale_cache=True,
                        cache_age_seconds=cache_meta.get("age_seconds"),
                        cache_backend="sqlite",
                        note="stale_cache_fallback",
                    )
                )
                return stale
            raise
        child_meta = self.provider.get_last_call_meta()
        source_provider = child_meta.source_provider if child_meta is not None else self.provider.provider_name
        self.cache.save_quote(self.provider.provider_name, quote, source_provider=source_provider)
        self._set_last_call_meta(_wrap_child_meta(self.provider_name, "get_quote", child_meta, source_provider))
        return quote

    def get_daily_bars(self, symbol: str, lookback: int = 60) -> list[DailyBar]:
        normalized_symbol = normalize_symbol(symbol)
        cached = self.cache.load_daily_bars(
            self.provider.provider_name,
            normalized_symbol,
            lookback,
            self.bar_ttl_seconds,
        )
        if cached:
            cache_meta = self.cache.get_daily_bars_cache_meta(
                self.provider.provider_name,
                normalized_symbol,
                lookback,
            ) or {}
            self._set_last_call_meta(
                ProviderCallMeta(
                    operation="get_daily_bars",
                    resolved_provider=self.provider_name,
                    source_provider=str(cache_meta.get("source_provider") or self.provider.provider_name),
                    from_cache=True,
                    used_stale_cache=False,
                    cache_age_seconds=cache_meta.get("age_seconds"),
                    cache_backend="sqlite",
                    note="fresh_cache_hit",
                )
            )
            return cached
        try:
            bars = self.provider.get_daily_bars(normalized_symbol, lookback=lookback)
        except Exception:
            if not self.allow_stale_on_error:
                raise
            stale = self.cache.load_daily_bars_any_age(
                self.provider.provider_name,
                normalized_symbol,
                lookback,
            )
            if stale:
                cache_meta = self.cache.get_daily_bars_cache_meta(
                    self.provider.provider_name,
                    normalized_symbol,
                    lookback,
                ) or {}
                self._set_last_call_meta(
                    ProviderCallMeta(
                        operation="get_daily_bars",
                        resolved_provider=self.provider_name,
                        source_provider=str(cache_meta.get("source_provider") or self.provider.provider_name),
                        from_cache=True,
                        used_stale_cache=True,
                        cache_age_seconds=cache_meta.get("age_seconds"),
                        cache_backend="sqlite",
                        note="stale_cache_fallback",
                    )
                )
                return stale
            raise
        child_meta = self.provider.get_last_call_meta()
        source_provider = child_meta.source_provider if child_meta is not None else self.provider.provider_name
        self.cache.save_daily_bars(
            self.provider.provider_name,
            normalized_symbol,
            bars,
            source_provider=source_provider,
        )
        self._set_last_call_meta(_wrap_child_meta(self.provider_name, "get_daily_bars", child_meta, source_provider))
        return bars


def _wrap_child_meta(
    resolved_provider_name: str,
    operation: str,
    child_meta: ProviderCallMeta | None,
    source_provider: str,
) -> ProviderCallMeta:
    if child_meta is None:
        return ProviderCallMeta(
            operation=operation,
            resolved_provider=resolved_provider_name,
            source_provider=source_provider,
            from_cache=False,
        )
    return replace(
        child_meta,
        operation=operation,
        resolved_provider=resolved_provider_name,
        source_provider=source_provider,
        from_cache=False,
        used_stale_cache=False,
        cache_backend=child_meta.cache_backend,
    )
