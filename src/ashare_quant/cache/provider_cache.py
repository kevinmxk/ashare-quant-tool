from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Lock

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
        self._refresh_pool = _get_refresh_pool()

    @property
    def provider_name(self) -> str:
        return "PersistentCache({name})".format(name=self.provider.provider_name)

    def list_universe(self, limit: int = 100) -> list[QuoteSnapshot]:
        cached = self.cache.load_universe(self.provider.provider_name, self.quote_ttl_seconds, limit)
        if cached:
            self._set_cache_hit_meta("list_universe", self.cache.get_universe_cache_meta(self.provider.provider_name))
            return cached
        stale = self.cache.load_universe(self.provider.provider_name, max_age_seconds=10**12, limit=limit)
        if stale and self.allow_stale_on_error:
            self._submit_refresh(("list_universe", limit), self._refresh_universe, limit)
            self._set_cache_hit_meta(
                "list_universe",
                self.cache.get_universe_cache_meta(self.provider.provider_name),
                stale=True,
                note="stale_cache_hit_refreshing",
            )
            return stale
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
            self._set_cache_hit_meta("get_quote", self.cache.get_quote_cache_meta(self.provider.provider_name, normalized_symbol))
            return cached
        stale = self.cache.load_latest_quote_any_age(self.provider.provider_name, normalized_symbol)
        if stale is not None and self.allow_stale_on_error:
            self._submit_refresh(("get_quote", normalized_symbol), self._refresh_quote, normalized_symbol)
            self._set_cache_hit_meta(
                "get_quote",
                self.cache.get_quote_cache_meta(self.provider.provider_name, normalized_symbol),
                stale=True,
                note="stale_cache_hit_refreshing",
            )
            return stale
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
            self._set_cache_hit_meta(
                "get_daily_bars",
                self.cache.get_daily_bars_cache_meta(self.provider.provider_name, normalized_symbol, lookback),
            )
            return cached
        stale = self.cache.load_daily_bars_any_age(
            self.provider.provider_name,
            normalized_symbol,
            lookback,
        )
        if stale and self.allow_stale_on_error:
            self._submit_refresh(("get_daily_bars", normalized_symbol, lookback), self._refresh_daily_bars, normalized_symbol, lookback)
            self._set_cache_hit_meta(
                "get_daily_bars",
                self.cache.get_daily_bars_cache_meta(self.provider.provider_name, normalized_symbol, lookback),
                stale=True,
                note="stale_cache_hit_refreshing",
            )
            return stale
        fast_method = getattr(self.provider, "get_fast_daily_bars", None)
        if callable(fast_method):
            self._submit_refresh(
                ("get_daily_bars", normalized_symbol, lookback),
                self._refresh_daily_bars,
                normalized_symbol,
                lookback,
            )
            try:
                bars = fast_method(normalized_symbol, lookback=lookback)
            except Exception:
                bars = []
            if bars:
                child_meta = self.provider.get_last_call_meta()
                source_provider = child_meta.source_provider if child_meta is not None else self.provider.provider_name
                meta = _wrap_child_meta(self.provider_name, "get_daily_bars", child_meta, source_provider)
                self._set_last_call_meta(
                    replace(
                        meta,
                        note="fast_bars_precise_refresh_pending",
                    )
                )
                return bars
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

    def _set_cache_hit_meta(
        self,
        operation: str,
        cache_meta: dict | None,
        *,
        stale: bool = False,
        note: str | None = None,
    ) -> None:
        meta = cache_meta or {}
        self._set_last_call_meta(
            ProviderCallMeta(
                operation=operation,
                resolved_provider=self.provider_name,
                source_provider=str(meta.get("source_provider") or self.provider.provider_name),
                from_cache=True,
                used_stale_cache=stale,
                cache_age_seconds=meta.get("age_seconds"),
                cache_backend="sqlite",
                note=note or "fresh_cache_hit",
            )
        )

    def _submit_refresh(self, key: tuple, fn, *args) -> None:
        refresh_key = (id(self), *key)
        with _REFRESH_LOCK:
            if refresh_key in _REFRESH_IN_FLIGHT:
                return
            _REFRESH_IN_FLIGHT.add(refresh_key)

        def run() -> None:
            try:
                fn(*args)
            finally:
                with _REFRESH_LOCK:
                    _REFRESH_IN_FLIGHT.discard(refresh_key)

        self._refresh_pool.submit(run)

    def _refresh_universe(self, limit: int) -> None:
        quotes = self.provider.list_universe(limit=limit)
        child_meta = self.provider.get_last_call_meta()
        source_provider = child_meta.source_provider if child_meta is not None else self.provider.provider_name
        self.cache.save_universe(self.provider.provider_name, quotes, source_provider=source_provider)

    def _refresh_quote(self, symbol: str) -> None:
        quote = self.provider.get_quote(symbol)
        child_meta = self.provider.get_last_call_meta()
        source_provider = child_meta.source_provider if child_meta is not None else self.provider.provider_name
        self.cache.save_quote(self.provider.provider_name, quote, source_provider=source_provider)

    def _refresh_daily_bars(self, symbol: str, lookback: int) -> None:
        bars = self.provider.get_daily_bars(symbol, lookback=lookback)
        child_meta = self.provider.get_last_call_meta()
        source_provider = child_meta.source_provider if child_meta is not None else self.provider.provider_name
        self.cache.save_daily_bars(self.provider.provider_name, symbol, bars, source_provider=source_provider)


_REFRESH_LOCK = Lock()
_REFRESH_IN_FLIGHT: set[tuple] = set()
_REFRESH_POOL: ThreadPoolExecutor | None = None


def _get_refresh_pool() -> ThreadPoolExecutor:
    global _REFRESH_POOL
    if _REFRESH_POOL is None:
        _REFRESH_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="market-cache-refresh")
    return _REFRESH_POOL


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
