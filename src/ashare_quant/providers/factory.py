from __future__ import annotations

from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.cache.sqlite_cache import SqliteMarketCache
from ashare_quant.config import Settings
from ashare_quant.providers.akshare_provider import AkshareMarketDataProvider
from ashare_quant.providers.baostock_provider import BaostockMarketDataProvider
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.composite_provider import CompositeMarketDataProvider
from ashare_quant.providers.mock_provider import MockMarketDataProvider
from ashare_quant.providers.sina_provider import SinaMarketDataProvider
from ashare_quant.providers.tushare_provider import TushareMarketDataProvider


def build_provider(settings: Settings) -> MarketDataProvider:
    provider = _build_raw_provider(settings)
    _attach_provider_diagnostics(provider, settings)
    if not settings.persistent_cache_enabled:
        return provider

    cache = SqliteMarketCache(settings.persistent_cache_path)
    wrapped = PersistentCacheMarketDataProvider(
        provider=provider,
        cache=cache,
        quote_ttl_seconds=settings.persistent_quote_ttl_seconds,
        bar_ttl_seconds=settings.persistent_bar_ttl_seconds,
        allow_stale_on_error=settings.persistent_cache_allow_stale_on_error,
    )
    _attach_provider_diagnostics(wrapped, settings)
    return wrapped


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

    if settings.provider in {"sina", "sina-finance"}:
        try:
            return SinaMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)
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
        providers.append(SinaMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds))
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


def get_provider_diagnostics(settings: Settings) -> list[dict[str, str | bool]]:
    checks: list[dict[str, str | bool]] = []
    checks.append(_check_provider("akshare", _build_akshare, settings))
    checks.append(_check_provider("sina", _build_sina, settings))
    checks.append(_check_provider("tushare", _build_tushare, settings))
    checks.append(_check_provider("baostock", _build_baostock, settings))
    return checks


def _attach_provider_diagnostics(provider: MarketDataProvider, settings: Settings) -> None:
    diagnostics = get_provider_diagnostics(settings)
    setattr(provider, "_provider_diagnostics", diagnostics)


def _check_provider(
    provider_id: str,
    builder,
    settings: Settings,
) -> dict[str, str | bool]:
    try:
        instance = builder(settings)
    except Exception as exc:
        return {
            "provider": provider_id,
            "enabled": False,
            "reason": str(exc),
        }

    return {
        "provider": provider_id,
        "enabled": True,
        "reason": "ok",
        "provider_name": instance.provider_name,
    }


def _build_akshare(settings: Settings) -> MarketDataProvider:
    return AkshareMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)


def _build_tushare(settings: Settings) -> MarketDataProvider:
    return TushareMarketDataProvider(
        token=settings.tushare_token,
        cache_ttl_seconds=max(settings.provider_cache_ttl_seconds, 300),
    )


def _build_sina(settings: Settings) -> MarketDataProvider:
    return SinaMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)


def _build_baostock(settings: Settings) -> MarketDataProvider:
    return BaostockMarketDataProvider()
