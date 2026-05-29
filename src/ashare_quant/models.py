from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class QuoteSnapshot:
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


@dataclass
class DailyBar:
    symbol: str
    trade_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    amount: float


@dataclass
class FactorSet:
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
    failed_filters: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)


@dataclass
class StockDiagnosis:
    quote: QuoteSnapshot
    factors: FactorSet


@dataclass
class ProviderCallMeta:
    operation: str
    resolved_provider: str
    source_provider: str
    from_cache: bool = False
    used_stale_cache: bool = False
    cache_age_seconds: float | None = None
    cache_backend: str | None = None
    attempted_providers: list[str] = field(default_factory=list)
    note: str | None = None


@dataclass
class UniverseResult:
    items: list[QuoteSnapshot]
    meta: ProviderCallMeta | None = None


@dataclass
class StockDiagnosisResult:
    quote: QuoteSnapshot
    factors: FactorSet
    quote_meta: ProviderCallMeta | None = None
    bars_meta: ProviderCallMeta | None = None


@dataclass
class StockBarsResult:
    symbol: str
    bars: list[DailyBar]
    bars_meta: ProviderCallMeta | None = None


@dataclass
class RankingsResult:
    items: list[StockDiagnosisResult]
    universe_meta: ProviderCallMeta | None = None
