from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ashare_quant.analysis.scoring import build_factor_set, list_supported_strategies, normalize_strategy
from ashare_quant.models import RankingsResult, StockBarsResult, StockDiagnosisResult, UniverseResult
from ashare_quant.providers.base import MarketDataProvider


class MarketService:
    def __init__(
        self,
        provider: MarketDataProvider,
        *,
        universe_provider: MarketDataProvider | None = None,
        ranking_provider: MarketDataProvider | None = None,
        diagnosis_provider: MarketDataProvider | None = None,
        watchlist_provider: MarketDataProvider | None = None,
    ) -> None:
        self.provider = provider
        self.universe_provider = universe_provider or provider
        self.ranking_provider = ranking_provider or self.universe_provider
        self.diagnosis_provider = diagnosis_provider or provider
        self.watchlist_provider = watchlist_provider or self.universe_provider

    def get_universe(self, limit: int = 20) -> UniverseResult:
        items = self.universe_provider.list_universe(limit=limit)
        meta = self.universe_provider.get_last_call_meta()
        return UniverseResult(items=items, meta=meta)

    def rank_universe(self, limit: int = 20, strategy: str = "trend") -> RankingsResult:
        strategy_id = normalize_strategy(strategy)
        universe = self.ranking_provider.list_universe(limit=limit)
        universe_meta = self.ranking_provider.get_last_call_meta()
        diagnoses = self._build_rank_diagnoses_concurrently(universe, strategy_id, universe_meta)
        ordered = sorted(
            diagnoses,
            key=lambda item: (item.factors.eligible, item.factors.total_score),
            reverse=True,
        )
        return RankingsResult(items=ordered, universe_meta=universe_meta)

    def diagnose_stock(self, symbol: str, strategy: str = "trend") -> StockDiagnosisResult:
        return self._diagnose_with_provider(
            self.diagnosis_provider,
            symbol=symbol,
            strategy=strategy,
        )

    def diagnose_watchlist_stock(self, symbol: str, strategy: str = "trend") -> StockDiagnosisResult:
        return self._diagnose_with_provider(
            self.watchlist_provider,
            symbol=symbol,
            strategy=strategy,
        )

    def get_stock_bars(self, symbol: str, lookback: int = 60) -> StockBarsResult:
        bars = self.diagnosis_provider.get_daily_bars(symbol, lookback=lookback)
        bars_meta = self.diagnosis_provider.get_last_call_meta()
        return StockBarsResult(
            symbol=symbol,
            bars=bars,
            bars_meta=bars_meta,
        )

    def _diagnose_with_provider(
        self,
        provider: MarketDataProvider,
        *,
        symbol: str,
        strategy: str,
    ) -> StockDiagnosisResult:
        strategy_id = normalize_strategy(strategy)
        quote = provider.get_quote(symbol)
        quote_meta = provider.get_last_call_meta()
        bars = provider.get_daily_bars(symbol, lookback=60)
        bars_meta = provider.get_last_call_meta()
        factors = build_factor_set(quote, bars, strategy=strategy_id)
        return StockDiagnosisResult(
            quote=quote,
            factors=factors,
            quote_meta=quote_meta,
            bars_meta=bars_meta,
        )

    def list_strategies(self) -> list[dict[str, str]]:
        return list_supported_strategies()

    def _build_rank_diagnoses_concurrently(
        self,
        universe,
        strategy_id: str,
        universe_meta,
    ) -> list[StockDiagnosisResult]:
        if not universe:
            return []
        max_workers = min(8, max(1, len(universe)))
        results: list[StockDiagnosisResult] = []

        def build_item(quote):
            bars = self.ranking_provider.get_daily_bars(quote.symbol, lookback=60)
            bars_meta = self.ranking_provider.get_last_call_meta()
            factors = build_factor_set(quote, bars, strategy=strategy_id)
            return StockDiagnosisResult(
                quote=quote,
                factors=factors,
                quote_meta=universe_meta,
                bars_meta=bars_meta,
            )

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ranking-bars") as pool:
            futures = [pool.submit(build_item, quote) for quote in universe]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception:
                    continue
        return results
