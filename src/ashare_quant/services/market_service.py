from __future__ import annotations

from ashare_quant.analysis.scoring import build_factor_set, list_supported_strategies, normalize_strategy
from ashare_quant.models import RankingsResult, StockDiagnosisResult, UniverseResult
from ashare_quant.providers.base import MarketDataProvider


class MarketService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def get_universe(self, limit: int = 20) -> UniverseResult:
        items = self.provider.list_universe(limit=limit)
        meta = self.provider.get_last_call_meta()
        return UniverseResult(items=items, meta=meta)

    def rank_universe(self, limit: int = 20, strategy: str = "trend") -> RankingsResult:
        strategy_id = normalize_strategy(strategy)
        universe = self.provider.list_universe(limit=limit)
        universe_meta = self.provider.get_last_call_meta()
        diagnoses: list[StockDiagnosisResult] = []
        for quote in universe:
            bars = self.provider.get_daily_bars(quote.symbol, lookback=60)
            bars_meta = self.provider.get_last_call_meta()
            factors = build_factor_set(quote, bars, strategy=strategy_id)
            diagnoses.append(
                StockDiagnosisResult(
                    quote=quote,
                    factors=factors,
                    quote_meta=universe_meta,
                    bars_meta=bars_meta,
                )
            )
        ordered = sorted(
            diagnoses,
            key=lambda item: (item.factors.eligible, item.factors.total_score),
            reverse=True,
        )
        return RankingsResult(items=ordered, universe_meta=universe_meta)

    def diagnose_stock(self, symbol: str, strategy: str = "trend") -> StockDiagnosisResult:
        strategy_id = normalize_strategy(strategy)
        quote = self.provider.get_quote(symbol)
        quote_meta = self.provider.get_last_call_meta()
        bars = self.provider.get_daily_bars(symbol, lookback=60)
        bars_meta = self.provider.get_last_call_meta()
        factors = build_factor_set(quote, bars, strategy=strategy_id)
        return StockDiagnosisResult(
            quote=quote,
            factors=factors,
            quote_meta=quote_meta,
            bars_meta=bars_meta,
        )

    def list_strategies(self) -> list[dict[str, str]]:
        return list_supported_strategies()
