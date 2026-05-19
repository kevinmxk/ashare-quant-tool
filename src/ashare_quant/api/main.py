from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException

from ashare_quant.api.schemas import (
    DiagnosisResponse,
    FactorResponse,
    ProviderMetaResponse,
    QuoteResponse,
    RankingsResponse,
    StrategyResponse,
    UniverseResponse,
)
from ashare_quant.config import get_settings
from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.providers.factory import build_provider
from ashare_quant.services.market_service import MarketService

settings = get_settings()
provider = build_provider(settings)
market_service = MarketService(provider)

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict:
    diagnostics = getattr(provider, "_provider_diagnostics", None)
    response = {
        "status": "ok",
        "configured_provider": settings.provider,
        "active_provider": provider.provider_name,
        "persistent_cache_enabled": settings.persistent_cache_enabled,
    }
    if isinstance(provider, PersistentCacheMarketDataProvider):
        response["cache"] = {
            "path": provider.cache.db_path,
            "stats": provider.cache.get_stats(),
        }
        if diagnostics is None:
            diagnostics = getattr(provider.provider, "_provider_diagnostics", None)
        response["active_provider_chain"] = provider.provider.provider_name
    if diagnostics is not None:
        response["provider_diagnostics"] = diagnostics
    return response


@app.get("/universe")
def universe(limit: int = 20) -> UniverseResponse:
    result = market_service.get_universe(limit=limit)
    return UniverseResponse(
        items=[QuoteResponse(**asdict(quote)) for quote in result.items],
        meta=_to_meta_response(result.meta),
    )


@app.get("/strategies")
def strategies() -> list[StrategyResponse]:
    return [StrategyResponse(**item) for item in market_service.list_strategies()]


@app.get("/rankings")
def rankings(limit: int = 20, strategy: str = "trend") -> RankingsResponse:
    result = market_service.rank_universe(limit=limit, strategy=strategy)
    return RankingsResponse(
        items=[_to_response(item) for item in result.items],
        universe_meta=_to_meta_response(result.universe_meta),
    )


@app.get("/stocks/{symbol}")
def stock_detail(symbol: str, strategy: str = "trend") -> DiagnosisResponse:
    try:
        diagnosis = market_service.diagnose_stock(symbol, strategy=strategy)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(diagnosis)


def _to_response(diagnosis) -> DiagnosisResponse:
    return DiagnosisResponse(
        quote=QuoteResponse(**asdict(diagnosis.quote)),
        factors=FactorResponse(**asdict(diagnosis.factors)),
        quote_meta=_to_meta_response(diagnosis.quote_meta),
        bars_meta=_to_meta_response(diagnosis.bars_meta),
    )


def _to_meta_response(meta) -> ProviderMetaResponse | None:
    if meta is None:
        return None
    return ProviderMetaResponse(**asdict(meta))
