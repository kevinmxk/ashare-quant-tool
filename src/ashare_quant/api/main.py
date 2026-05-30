from __future__ import annotations

import atexit
import os
import signal
import sys
from dataclasses import asdict
from datetime import datetime
import tempfile

# PID file for graceful shutdown from batch script
PID_FILE = os.path.join(tempfile.gettempdir(), "aquant_api.pid")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from ashare_quant.api.cache import APIMemoryCache
from ashare_quant.api.trading_calendar import is_trading_time
from ashare_quant.api.schemas import (
    BarsResponse,
    BarDataPoint,
    DiagnosisResponse,
    FactorResponse,
    ProviderMetaResponse,
    QuoteResponse,
    RankingRow,
    RankingsTableResponse,
    StatusResponse,
    StrategyResponse,
    SummaryResponse,
    WatchlistAddRequest,
    WatchlistAddResponse,
    WatchlistListResponse,
    WatchlistRequest,
    WatchlistRemoveResponse,
    WatchlistResponse,
    WatchlistRow,
)
from ashare_quant.cache.sqlite_cache import SqliteMarketCache
from ashare_quant.config import get_settings
from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.providers.factory import build_provider_bundle, get_provider_diagnostics
from ashare_quant.providers.shared_cleaner import normalize_symbol
from ashare_quant.services.market_service import MarketService
from ashare_quant.ui.dashboard_data import (
    bars_to_chart_data,
    build_rankings_table,
    build_watchlist_rows,
    diagnosis_to_dict,
    enrich_diagnosis_with_pi,
    parse_watchlist,
    provider_status,
    summarize_rankings,
)

sys.path.insert(0, os.path.abspath("src"))

settings = get_settings()
bundle = build_provider_bundle(settings)
provider = bundle.default_provider
market_service = MarketService(
    provider,
    universe_provider=bundle.universe_provider,
    ranking_provider=bundle.ranking_provider,
    diagnosis_provider=bundle.diagnosis_provider,
    watchlist_provider=bundle.watchlist_provider,
)

cache = APIMemoryCache(ttl_seconds=settings.provider_cache_ttl_seconds)
watchlist_cache = (
    provider.cache
    if isinstance(provider, PersistentCacheMarketDataProvider)
    else SqliteMarketCache(settings.persistent_cache_path)
)

app = FastAPI(title=settings.app_name)
market_refresh_scheduler = BackgroundScheduler(timezone="Asia/Shanghai", daemon=True)


def _refresh_watchlist_cache() -> None:
    if not is_trading_time():
        print("[market-refresh] Skipped outside trading time", flush=True)
        return

    symbols = watchlist_cache.list_watchlist_symbols()
    refreshed = 0
    for symbol in symbols:
        try:
            market_service.diagnose_watchlist_stock(symbol)
        except Exception as exc:
            print(f"[market-refresh] Failed to refresh {symbol}: {exc}", flush=True)
            continue
        refreshed += 1

    if refreshed:
        cache.clear()
    print(f"[market-refresh] Refreshed {refreshed} watchlist stocks", flush=True)


def _start_market_refresh_scheduler() -> None:
    if market_refresh_scheduler.running:
        return
    market_refresh_scheduler.add_job(
        _refresh_watchlist_cache,
        "interval",
        minutes=5,
        id="watchlist-market-refresh",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(),
        replace_existing=True,
    )
    market_refresh_scheduler.start()
    print("[market-refresh] Scheduler started", flush=True)


def _shutdown_market_refresh_scheduler() -> None:
    if market_refresh_scheduler.running:
        market_refresh_scheduler.shutdown(wait=False)
        print("[market-refresh] Scheduler stopped", flush=True)


# ---------------------------------------------------------------------------
# Graceful shutdown hooks
# ---------------------------------------------------------------------------

def _cleanup_pid_file():
    """Remove PID file on exit."""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except OSError:
        pass


def _write_pid_file():
    """Write current PID to file for stop.bat to find."""
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


@app.on_event("startup")
async def _on_startup():
    _write_pid_file()
    _start_market_refresh_scheduler()


@app.on_event("shutdown")
async def _on_shutdown():
    _shutdown_market_refresh_scheduler()
    _cleanup_pid_file()


atexit.register(_cleanup_pid_file)
atexit.register(_shutdown_market_refresh_scheduler)


def _force_cleanup(signum, frame):
    """Signal handler for SIGTERM to clean up PID file."""
    _shutdown_market_refresh_scheduler()
    _cleanup_pid_file()
    sys.exit(0)


signal.signal(signal.SIGTERM, _force_cleanup)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    diagnostics = getattr(provider, "_provider_diagnostics", None)
    routes = getattr(provider, "_provider_routes", None)
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
    if routes is not None:
        response["provider_routes"] = routes
    return response


@app.get("/api/strategies")
def strategies() -> list[StrategyResponse]:
    cached = cache.get("strategies")
    if cached is not None:
        return cached
    result = [StrategyResponse(**item) for item in market_service.list_strategies()]
    cache.set("strategies", result)
    return result


@app.get("/api/rankings")
def rankings(limit: int = 20, strategy: str = "trend") -> RankingsTableResponse:
    cache_key = f"rankings:{limit}:{strategy}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    rankings_result = market_service.rank_universe(limit=limit, strategy=strategy)
    summary = summarize_rankings(rankings_result)
    rows = build_rankings_table(rankings_result)

    response = RankingsTableResponse(
        summary=SummaryResponse(**summary),
        rows=[RankingRow(**row) for row in rows],
        universe_meta=_to_meta_response(rankings_result.universe_meta),
    )
    cache.set(cache_key, response)
    return response


@app.get("/api/stocks/{symbol}")
def stock_detail(symbol: str, strategy: str = "trend") -> DiagnosisResponse:
    cache_key = f"stock:{symbol}:{strategy}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        diagnosis = market_service.diagnose_stock(symbol, strategy=strategy)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = enrich_diagnosis_with_pi(diagnosis_to_dict(diagnosis))
    response = _dict_to_diagnosis_response(result)
    cache.set(cache_key, response)
    return response


@app.get("/api/stocks/{symbol}/bars")
def stock_bars(symbol: str, lookback: int = 60) -> BarsResponse:
    cache_key = f"bars:{symbol}:{lookback}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        bars_result = market_service.get_stock_bars(symbol, lookback=lookback)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    chart_data = bars_to_chart_data(bars_result.bars)
    response = BarsResponse(
        symbol=symbol,
        bars=[BarDataPoint(**d) for d in chart_data],
        bars_meta=_to_meta_response(bars_result.bars_meta),
    )
    cache.set(cache_key, response)
    return response


@app.post("/api/watchlist")
def watchlist(request: WatchlistRequest) -> WatchlistResponse:
    symbols = parse_watchlist(",".join(request.symbols))
    if not symbols:
        return WatchlistResponse(rows=[])

    cache_key = f"watchlist:{','.join(symbols)}:{request.strategy}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    rows = build_watchlist_rows(market_service, symbols, request.strategy)
    response = WatchlistResponse(
        rows=[WatchlistRow(**row) for row in rows],
    )
    cache.set(cache_key, response)
    return response


@app.get("/api/watchlist/list")
def watchlist_list() -> WatchlistListResponse:
    return WatchlistListResponse(symbols=watchlist_cache.list_watchlist_symbols())


@app.post("/api/watchlist/add")
def watchlist_add(request: WatchlistAddRequest) -> WatchlistAddResponse:
    symbol = _normalize_watchlist_symbol(request.symbol)
    watchlist_cache.add_watchlist_symbol(symbol, note=request.note)
    rows = build_watchlist_rows(market_service, [symbol], request.strategy)
    row = rows[0] if rows else _fallback_watchlist_row(symbol)
    response = WatchlistAddResponse(symbol=symbol, row=WatchlistRow(**row))
    cache.set(f"watchlist:{symbol}:{request.strategy}", WatchlistResponse(rows=[response.row]))
    return response


@app.delete("/api/watchlist/remove/{symbol}")
def watchlist_remove(symbol: str) -> WatchlistRemoveResponse:
    normalized = _normalize_watchlist_symbol(symbol)
    removed = watchlist_cache.remove_watchlist_symbol(normalized)
    return WatchlistRemoveResponse(symbol=normalized, removed=removed)


@app.get("/api/status")
def status() -> StatusResponse:
    cached = cache.get("status")
    if cached is not None:
        return cached

    status_dict = provider_status(provider, settings)
    diagnostics = status_dict.get("provider_diagnostics")
    routes = status_dict.get("provider_routes")
    strategies_list = market_service.list_strategies()

    response = StatusResponse(
        status="ok",
        configured_provider=status_dict.get("configured_provider", "-"),
        active_provider=status_dict.get("active_provider", "-"),
        active_provider_chain=status_dict.get("active_provider_chain"),
        persistent_cache_enabled=status_dict.get("persistent_cache_enabled", False),
        cache=status_dict.get("cache"),
        provider_routes=routes,
        provider_diagnostics=diagnostics,
        strategies=[StrategyResponse(**item) for item in strategies_list],
    )
    cache.set("status", response)
    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    if isinstance(meta, dict):
        return ProviderMetaResponse(**meta)
    return ProviderMetaResponse(**asdict(meta))


def _dict_to_diagnosis_response(data: dict) -> DiagnosisResponse:
    quote = data["quote"]
    factors = data["factors"]
    quote_meta = data.get("quote_meta")
    bars_meta = data.get("bars_meta")
    return DiagnosisResponse(
        quote=QuoteResponse(**quote),
        factors=FactorResponse(**factors),
        quote_meta=_to_meta_response(quote_meta) if quote_meta else None,
        bars_meta=_to_meta_response(bars_meta) if bars_meta else None,
    )


def _normalize_watchlist_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if not normalized:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    return normalized


def _fallback_watchlist_row(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "name": "未找到",
        "score": 0.0,
        "eligible": "否",
        "latest_price": "-",
        "pct_change": "-",
        "entry_signal": "当前诊断请求失败，已跳过该股票",
        "failed_filters": "-",
    }
