from __future__ import annotations

from pydantic import BaseModel


class QuoteResponse(BaseModel):
    symbol: str
    name: str
    latest_price: float
    pct_change: float
    turnover_rate: float
    amount: float
    volume_ratio: float
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    sector: str | None = None


class FactorResponse(BaseModel):
    strategy_id: str
    strategy_name: str
    momentum_20d: float
    trend_strength: float
    liquidity_score: float
    valuation_score: float
    risk_score: float
    total_score: float
    eligible: bool
    entry_signal: str
    exit_signal: str
    failed_filters: list[str]
    risk_flags: list[str]
    explanations: list[str]


class ProviderMetaResponse(BaseModel):
    operation: str
    resolved_provider: str
    source_provider: str
    from_cache: bool
    used_stale_cache: bool
    cache_age_seconds: float | None = None
    cache_backend: str | None = None
    attempted_providers: list[str]
    note: str | None = None


class DiagnosisResponse(BaseModel):
    quote: QuoteResponse
    factors: FactorResponse
    quote_meta: ProviderMetaResponse | None = None
    bars_meta: ProviderMetaResponse | None = None


class UniverseResponse(BaseModel):
    items: list[QuoteResponse]
    meta: ProviderMetaResponse | None = None


class RankingsResponse(BaseModel):
    items: list[DiagnosisResponse]
    universe_meta: ProviderMetaResponse | None = None


class StrategyResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
