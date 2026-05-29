from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.cache.sqlite_cache import SqliteMarketCache
from ashare_quant.config import Settings
from ashare_quant.providers.akshare_provider import AkshareMarketDataProvider
from ashare_quant.providers.baostock_provider import BaostockMarketDataProvider
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.providers.composite_provider import CompositeMarketDataProvider
from ashare_quant.providers.eastmoney_provider import EastMoneyMarketDataProvider
from ashare_quant.providers.mock_provider import MockMarketDataProvider
from ashare_quant.providers.routing_provider import OperationRoutingMarketDataProvider
from ashare_quant.providers.sina_provider import SinaMarketDataProvider
from ashare_quant.providers.tushare_provider import TushareMarketDataProvider


@dataclass(frozen=True)
class ProviderBundle:
    default_provider: MarketDataProvider
    universe_provider: MarketDataProvider
    ranking_provider: MarketDataProvider
    diagnosis_provider: MarketDataProvider
    watchlist_provider: MarketDataProvider


def build_provider(settings: Settings) -> MarketDataProvider:
    return build_provider_bundle(settings).default_provider


def build_provider_bundle(settings: Settings) -> ProviderBundle:
    instances: dict[str, MarketDataProvider] = {}

    def resolve(provider_name: str) -> MarketDataProvider:
        normalized = (provider_name or "auto").strip().lower()
        if normalized not in instances:
            instances[normalized] = _build_named_provider(normalized, settings)
        return instances[normalized]

    default_name = settings.provider
    universe_name = settings.universe_provider or default_name
    ranking_name = settings.ranking_provider or universe_name
    diagnosis_name = settings.diagnosis_provider or default_name
    watchlist_name = settings.watchlist_provider or universe_name

    bundle = ProviderBundle(
        default_provider=resolve(default_name),
        universe_provider=resolve(universe_name),
        ranking_provider=resolve(ranking_name),
        diagnosis_provider=resolve(diagnosis_name),
        watchlist_provider=resolve(watchlist_name),
    )

    route_summary = {
        "default": bundle.default_provider.provider_name,
        "universe": bundle.universe_provider.provider_name,
        "ranking": bundle.ranking_provider.provider_name,
        "diagnosis": bundle.diagnosis_provider.provider_name,
        "watchlist": bundle.watchlist_provider.provider_name,
    }
    for provider in instances.values():
        setattr(provider, "_provider_routes", route_summary)
    return bundle


def _build_named_provider(provider_name: str, settings: Settings) -> MarketDataProvider:
    if provider_name == "auto":
        providers: list[MarketDataProvider] = []
        providers.extend(_build_real_providers(settings))
        if settings.use_mock_when_provider_fails or not providers:
            providers.append(MockMarketDataProvider())
        provider = CompositeMarketDataProvider(providers)
        return _wrap_provider(provider, settings)

    if provider_name in {"mock"}:
        return _wrap_provider(MockMarketDataProvider(), settings)

    if provider_name in {"dual", "eastmoney-baostock", "em-bs"}:
        return _wrap_provider(_build_dual_source_provider(settings), settings)

    if provider_name in {"eastmoney", "em", "east-money"}:
        return _wrap_provider(_build_preferred_runtime_chain("eastmoney", settings), settings)

    if provider_name in {"akshare", "ak"}:
        return _wrap_provider(_build_preferred_runtime_chain("akshare", settings), settings)

    if provider_name in {"sina", "sina-finance"}:
        return _wrap_provider(_build_preferred_runtime_chain("sina", settings), settings)

    if provider_name in {"tushare", "ts"}:
        return _wrap_provider(_build_preferred_runtime_chain("tushare", settings), settings)

    if provider_name in {"baostock", "bs"}:
        return _wrap_provider(_build_preferred_runtime_chain("baostock", settings), settings)

    return _wrap_provider(MockMarketDataProvider(), settings)


def _build_real_providers(settings: Settings) -> list[MarketDataProvider]:
    providers: list[MarketDataProvider] = []

    try:
        providers.append(EastMoneyMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds))
    except Exception:
        pass

    try:
        providers.append(SinaMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds))
    except Exception:
        pass

    try:
        providers.append(AkshareMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds))
    except Exception:
        pass

    try:
        providers.append(BaostockMarketDataProvider())
    except Exception:
        pass

    return providers


def _build_preferred_runtime_chain(preferred: str, settings: Settings) -> MarketDataProvider:
    ordered_names: list[str] = []
    fallback_names = ["eastmoney", "sina", "akshare", "baostock"]
    if preferred == "tushare":
        fallback_names.insert(1, "tushare")
    for name in [preferred, *fallback_names]:
        normalized = name.strip().lower()
        if normalized not in ordered_names:
            ordered_names.append(normalized)

    providers: list[MarketDataProvider] = []
    for name in ordered_names:
        try:
            providers.append(_build_single_runtime_provider(name, settings))
        except Exception:
            continue

    if not providers and not settings.use_mock_when_provider_fails:
        raise RuntimeError(
            "No runtime providers are available for preferred provider: {name}".format(name=preferred)
        )

    if settings.use_mock_when_provider_fails:
        providers.append(MockMarketDataProvider())

    if len(providers) == 1:
        return providers[0]
    return CompositeMarketDataProvider(providers)


def _build_single_runtime_provider(provider_name: str, settings: Settings) -> MarketDataProvider:
    if provider_name in {"eastmoney", "em", "east-money"}:
        return EastMoneyMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)
    if provider_name in {"akshare", "ak"}:
        return AkshareMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)
    if provider_name in {"sina", "sina-finance"}:
        return SinaMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)
    if provider_name in {"tushare", "ts"}:
        return TushareMarketDataProvider(
            token=settings.tushare_token,
            cache_ttl_seconds=max(settings.provider_cache_ttl_seconds, 300),
        )
    if provider_name in {"baostock", "bs"}:
        return BaostockMarketDataProvider()
    if provider_name == "mock":
        return MockMarketDataProvider()
    raise RuntimeError("Unsupported provider: {name}".format(name=provider_name))


def _build_dual_source_provider(settings: Settings) -> MarketDataProvider:
    quote_provider = _build_composite_from_names(
        ["eastmoney", "sina", "akshare"],
        settings,
    )
    bars_provider = _build_composite_from_names(
        ["baostock", "eastmoney", "sina", "akshare"],
        settings,
    )
    return OperationRoutingMarketDataProvider(
        quote_provider=quote_provider,
        bars_provider=bars_provider,
        fast_bars_provider=EastMoneyMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds),
        name="EastMoneyBaoStock",
    )


def _build_composite_from_names(names: list[str], settings: Settings) -> MarketDataProvider:
    providers: list[MarketDataProvider] = []
    for name in names:
        try:
            providers.append(_build_single_runtime_provider(name, settings))
        except Exception:
            continue

    if settings.use_mock_when_provider_fails:
        providers.append(MockMarketDataProvider())

    if not providers:
        raise RuntimeError("No runtime providers are available")
    if len(providers) == 1:
        return providers[0]
    return CompositeMarketDataProvider(providers)


def _wrap_provider(provider: MarketDataProvider, settings: Settings) -> MarketDataProvider:
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


def get_provider_diagnostics(settings: Settings) -> list[dict[str, str | bool]]:
    return _get_provider_diagnostics_cached(settings)


@lru_cache(maxsize=8)
def _get_provider_diagnostics_cached(settings: Settings) -> list[dict[str, str | bool]]:
    checks: list[dict[str, str | bool]] = []
    checks.append(_check_provider("eastmoney", _build_eastmoney, settings))
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


def _build_eastmoney(settings: Settings) -> MarketDataProvider:
    return EastMoneyMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)


def _build_tushare(settings: Settings) -> MarketDataProvider:
    return TushareMarketDataProvider(
        token=settings.tushare_token,
        cache_ttl_seconds=max(settings.provider_cache_ttl_seconds, 300),
    )


def _build_sina(settings: Settings) -> MarketDataProvider:
    return SinaMarketDataProvider(cache_ttl_seconds=settings.provider_cache_ttl_seconds)


def _build_baostock(settings: Settings) -> MarketDataProvider:
    return BaostockMarketDataProvider()
