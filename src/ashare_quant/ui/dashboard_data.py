from __future__ import annotations

from dataclasses import asdict

from ashare_quant.analysis.scoring import normalize_strategy
from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.config import Settings
from ashare_quant.models import RankingsResult, StockDiagnosisResult
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.services.market_service import MarketService


def parse_watchlist(raw_text: str) -> list[str]:
    values = []
    for chunk in raw_text.replace("\n", ",").split(","):
        symbol = chunk.strip()
        if symbol:
            values.append(symbol)
    deduped: list[str] = []
    seen = set()
    for symbol in values:
        if symbol not in seen:
            deduped.append(symbol)
            seen.add(symbol)
    return deduped


def build_rankings_table(rankings: RankingsResult) -> list[dict]:
    rows: list[dict] = []
    for index, item in enumerate(rankings.items, start=1):
        rows.append(
            {
                "rank": index,
                "symbol": item.quote.symbol,
                "name": item.quote.name,
                "sector": item.quote.sector or "-",
                "score": item.factors.total_score,
                "eligible": "是" if item.factors.eligible else "否",
                "pct_change": item.quote.pct_change,
                "entry_signal": item.factors.entry_signal,
                "risk_flags": "；".join(item.factors.risk_flags) or "-",
            }
        )
    return rows


def build_watchlist_rows(service: MarketService, symbols: list[str], strategy: str) -> list[dict]:
    rows: list[dict] = []
    for symbol in symbols:
        try:
            result = service.diagnose_watchlist_stock(symbol, strategy=strategy)
        except KeyError:
            rows.append(
                {
                    "symbol": symbol,
                    "name": "未找到",
                    "score": 0.0,
                    "eligible": "否",
                    "latest_price": "-",
                    "pct_change": "-",
                    "entry_signal": "当前数据源未收录该股票代码",
                    "failed_filters": "请检查数据源或股票代码格式",
                }
            )
            continue

        rows.append(
            {
                "symbol": result.quote.symbol,
                "name": result.quote.name,
                "score": result.factors.total_score,
                "eligible": "是" if result.factors.eligible else "否",
                "latest_price": result.quote.latest_price,
                "pct_change": result.quote.pct_change,
                "entry_signal": result.factors.entry_signal,
                "failed_filters": "；".join(result.factors.failed_filters) or "-",
            }
        )
    rows.sort(key=lambda row: (row["eligible"] == "是", row["score"]), reverse=True)
    return rows


def summarize_rankings(rankings: RankingsResult) -> dict[str, float | int]:
    items = rankings.items
    eligible_count = sum(1 for item in items if item.factors.eligible)
    avg_score = round(sum(item.factors.total_score for item in items) / len(items), 2) if items else 0.0
    top_score = max((item.factors.total_score for item in items), default=0.0)
    return {
        "total": len(items),
        "eligible_count": eligible_count,
        "avg_score": avg_score,
        "top_score": top_score,
    }


def provider_status(provider: MarketDataProvider, settings: Settings) -> dict:
    diagnostics = getattr(provider, "_provider_diagnostics", None)
    active_provider = provider
    payload = {
        "configured_provider": settings.provider,
        "active_provider": provider.provider_name,
        "persistent_cache_enabled": settings.persistent_cache_enabled,
    }
    if isinstance(provider, PersistentCacheMarketDataProvider):
        active_provider = provider.provider
        payload["cache"] = {
            "path": provider.cache.db_path,
            "stats": provider.cache.get_stats(),
            "quote_ttl_seconds": provider.quote_ttl_seconds,
            "bar_ttl_seconds": provider.bar_ttl_seconds,
            "allow_stale_on_error": provider.allow_stale_on_error,
        }
        if diagnostics is None:
            diagnostics = getattr(provider.provider, "_provider_diagnostics", None)
    payload["active_provider_chain"] = active_provider.provider_name
    if diagnostics is not None:
        payload["provider_diagnostics"] = diagnostics
    routes = getattr(provider, "_provider_routes", None)
    if routes is not None:
        payload["provider_routes"] = routes
    return payload


def diagnosis_to_dict(result: StockDiagnosisResult) -> dict:
    return {
        "quote": asdict(result.quote),
        "factors": asdict(result.factors),
        "quote_meta": asdict(result.quote_meta) if result.quote_meta is not None else None,
        "bars_meta": asdict(result.bars_meta) if result.bars_meta is not None else None,
    }


def normalize_ui_strategy(strategy: str) -> str:
    return normalize_strategy(strategy)
