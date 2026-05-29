from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from functools import lru_cache

from ashare_quant.analysis.scoring import list_supported_strategies, normalize_strategy
from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.config import Settings
from ashare_quant.models import DailyBar, RankingsResult, StockDiagnosisResult
from ashare_quant.providers.base import MarketDataProvider
from ashare_quant.services.market_service import MarketService


# ---------------------------------------------------------------------------
# 策略列表（不常变化，使用 lru_cache 缓存）
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_strategies() -> list[dict[str, str]]:
    return list_supported_strategies()


# ---------------------------------------------------------------------------
# 数据获取封装（不再由 streamlit_app.py 直接调用 MarketService）
# ---------------------------------------------------------------------------
def fetch_rankings(service: MarketService, limit: int, strategy: str) -> RankingsResult:
    """获取策略榜单。"""
    if service is None:
        raise RuntimeError("MarketService 未初始化")
    if limit <= 0:
        raise ValueError("榜单数量必须大于 0")
    return service.rank_universe(limit=limit, strategy=strategy)


def fetch_diagnosis(service: MarketService, symbol: str, strategy: str) -> StockDiagnosisResult:
    """获取单股诊断结果。"""
    if service is None:
        raise RuntimeError("MarketService 未初始化")
    if not symbol or not symbol.strip():
        raise ValueError("股票代码不能为空")
    return service.diagnose_stock(symbol.strip(), strategy=strategy)


def fetch_watchlist_rows(service: MarketService, symbols: list[str], strategy: str) -> list[dict]:
    """获取自选池诊断行数据。"""
    if service is None:
        raise RuntimeError("MarketService 未初始化")
    return build_watchlist_rows(service, symbols, strategy)


# ---------------------------------------------------------------------------
# 自选池与榜单数据构造
# ---------------------------------------------------------------------------
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
    if not symbols:
        return []

    yes_text = "是"
    no_text = "否"
    rows: list[dict | None] = [None] * len(symbols)
    max_workers = min(8, max(1, len(symbols)))

    def build_row(symbol: str) -> dict:
        try:
            result = service.diagnose_watchlist_stock(symbol, strategy=strategy)
        except Exception as exc:
            return {
                "symbol": symbol,
                "name": "未找到",
                "score": 0.0,
                "eligible": no_text,
                "latest_price": "-",
                "pct_change": "-",
                "entry_signal": "当前诊断请求失败，已跳过该股票",
                "failed_filters": _format_watchlist_error(exc),
            }

        return {
            "symbol": result.quote.symbol,
            "name": result.quote.name,
            "score": result.factors.total_score,
            "eligible": yes_text if result.factors.eligible else no_text,
            "latest_price": result.quote.latest_price,
            "pct_change": result.quote.pct_change,
            "entry_signal": result.factors.entry_signal,
            "failed_filters": "；".join(result.factors.failed_filters) or "-",
        }

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="watchlist-rows") as pool:
        future_to_index = {pool.submit(build_row, symbol): index for index, symbol in enumerate(symbols)}
        for future in as_completed(future_to_index):
            rows[future_to_index[future]] = future.result()

    resolved_rows = [row for row in rows if row is not None]
    resolved_rows.sort(key=lambda row: (row["eligible"] == yes_text, row["score"]), reverse=True)
    return resolved_rows


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


# ---------------------------------------------------------------------------
# Provider 状态
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 诊断结果序列化
# ---------------------------------------------------------------------------
def diagnosis_to_dict(result: StockDiagnosisResult) -> dict:
    return {
        "quote": asdict(result.quote),
        "factors": asdict(result.factors),
        "quote_meta": asdict(result.quote_meta) if result.quote_meta is not None else None,
        "bars_meta": asdict(result.bars_meta) if result.bars_meta is not None else None,
    }


def normalize_ui_strategy(strategy: str) -> str:
    return normalize_strategy(strategy)


# ---------------------------------------------------------------------------
# PI (Profitability Index / Performance Index) 相关指标
# ---------------------------------------------------------------------------
def calculate_profitability_index(factors: dict) -> float | None:
    """
    计算盈利性指数 (Profitability Index, PI)。
    基于总分、趋势强度和动量的加权综合，用于快速衡量标的的绩效表现。
    """
    total_score = factors.get("total_score")
    trend = factors.get("trend_strength")
    momentum = factors.get("momentum_20d")
    liquidity = factors.get("liquidity_score")

    if total_score is None or trend is None or momentum is None or liquidity is None:
        return None

    # 综合绩效指数：总分权重最高，辅以趋势持续性、动量与流动性
    pi = (
        total_score * 0.40
        + trend * 0.25
        + max(0.0, momentum) * 0.20
        + liquidity * 0.15
    )
    return round(min(pi, 100.0), 2)


def enrich_diagnosis_with_pi(result: dict) -> dict:
    """为诊断结果字典注入 PI 指标。"""
    factors = result.get("factors") or {}
    pi = calculate_profitability_index(factors)
    if pi is not None:
        factors = dict(factors)
        factors["profitability_index"] = pi
        result = dict(result)
        result["factors"] = factors
    return result


# ---------------------------------------------------------------------------
# 图表数据准备（避免在 Streamlit 中直接调用 Service 获取 bars）
# ---------------------------------------------------------------------------
def fetch_diagnosis_bars(service: MarketService, symbol: str) -> list[DailyBar]:
    """获取单股诊断所需的历史日线数据，用于图表展示。"""
    if service is None:
        return []
    try:
        result = service.get_stock_bars(symbol, lookback=60)
    except Exception:
        return []
    return result.bars


def bars_to_chart_data(bars: list[DailyBar]) -> list[dict]:
    """将 DailyBar 列表转换为前端图表可用的字典列表。"""
    if not bars:
        return []
    data = []
    for bar in sorted(bars, key=lambda b: b.trade_date):
        data.append(
            {
                "date": bar.trade_date.isoformat(),
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
                "volume": bar.volume,
            }
        )
    return data


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------
def _format_watchlist_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__
