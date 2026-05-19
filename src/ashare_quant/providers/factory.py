from __future__ import annotations

from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.cache.sqlite_cache import SqliteMarketCache
from ashare_quant.config import Settings
from ashare_quant.providers.akshare_provider import AkshareMarketDataProvider
from ashare_quant.providers.baostock_provider import BaostockMarketDataProvider
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.composite_provider import CompositeMarketDataProvider
from ashare_quant.providers.mock_provider import MockMarketDataProvider
from ashare_quant.providers.tushare_provider import TushareMarketDataProvider


def build_provider(settings: Settings) -> MarketDataProvider:
    provider = _build_raw_provider(settings)
    if not settings.persistent_cache_enabled:
        return provider

    cache = SqliteMarketCache(settings.persistent_cache_path)
    return PersistentCacheMarketDataProvider(
        provider=provider,
        cache=cache,
        quote_ttl_seconds=settings.persistent_quote_ttl_seconds,
        bar_ttl_seconds=settings.persistent_bar_ttl_seconds,
        allow_stale_on_error=settings.persistent_cache_allow_stale_on_error,
    )


def _build_raw_provider(settings: Settings) -> MarketDataProvider:
    if settings.provider == "auto":
        providers: list[MarketDataProvider] = []
        providers.extend(_build_real_providers(settings))
        if settings.use_mock_when_provider_fails or not providers:
            providers.append(MockMarketDataProvider())
        return CompositeMarketDataProvider(providers)

    if settings.provider in {"akshare", "ak"}:
        try:
            return AkshareMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)
        except Exception:
            if not settings.use_mock_when_provider_fails:
                raise
            return MockMarketDataProvider()

    if settings.provider in {"tushare", "ts"}:
        try:
            return TushareMarketDataProvider(
                token=settings.tushare_token,
                cache_ttl_seconds=max(settings.provider_cache_ttl_seconds, 300),
            )
        except Exception:
            if not settings.use_mock_when_provider_fails:
                raise
            return MockMarketDataProvider()

    if settings.provider in {"baostock", "bs"}:
        try:
            return BaostockMarketDataProvider()
        except Exception:
            if not settings.use_mock_when_provider_fails:
                raise
            return MockMarketDataProvider()

    return MockMarketDataProvider()


def _build_real_providers(settings: Settings) -> list[MarketDataProvider]:
    providers: list[MarketDataProvider] = []

    try:
        providers.append(AkshareMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds))
    except Exception:
        pass

    try:
        providers.append(
            TushareMarketDataProvider(
                token=settings.tushare_token,
                cache_ttl_seconds=max(settings.provider_cache_ttl_seconds, 300),
            )
        )
    except Exception:
        pass

    try:
        providers.append(BaostockMarketDataProvider())
    except Exception:
        pass

    return providers
