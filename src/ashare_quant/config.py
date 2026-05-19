from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str = "A-Share Quant Tool"
    provider: str = "auto"
    ranking_limit: int = 20
    use_mock_when_provider_fails: bool = True
    provider_cache_ttl_seconds: int = 15
    tushare_token: str | None = None
    persistent_cache_enabled: bool = True
    persistent_cache_path: str = "data/cache/market_cache.sqlite3"
    persistent_quote_ttl_seconds: int = 900
    persistent_bar_ttl_seconds: int = 43200
    persistent_cache_allow_stale_on_error: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("ASHARE_QUANT_APP_NAME", "A-Share Quant Tool"),
        provider=os.getenv("ASHARE_QUANT_PROVIDER", "auto").strip().lower(),
        ranking_limit=int(os.getenv("ASHARE_QUANT_RANKING_LIMIT", "20")),
        use_mock_when_provider_fails=os.getenv(
            "ASHARE_QUANT_USE_MOCK_WHEN_PROVIDER_FAILS",
            "true",
        ).lower()
        in {"1", "true", "yes", "y"},
        provider_cache_ttl_seconds=int(os.getenv("ASHARE_QUANT_PROVIDER_CACHE_TTL_SECONDS", "15")),
        tushare_token=os.getenv("ASHARE_QUANT_TUSHARE_TOKEN") or os.getenv("TUSHARE_TOKEN"),
        persistent_cache_enabled=os.getenv(
            "ASHARE_QUANT_PERSISTENT_CACHE_ENABLED",
            "true",
        ).lower()
        in {"1", "true", "yes", "y"},
        persistent_cache_path=os.getenv(
            "ASHARE_QUANT_PERSISTENT_CACHE_PATH",
            "data/cache/market_cache.sqlite3",
        ),
        persistent_quote_ttl_seconds=int(
            os.getenv("ASHARE_QUANT_PERSISTENT_QUOTE_TTL_SECONDS", "900")
        ),
        persistent_bar_ttl_seconds=int(
            os.getenv("ASHARE_QUANT_PERSISTENT_BAR_TTL_SECONDS", "43200")
        ),
        persistent_cache_allow_stale_on_error=os.getenv(
            "ASHARE_QUANT_PERSISTENT_CACHE_ALLOW_STALE_ON_ERROR",
            "true",
        ).lower()
        in {"1", "true", "yes", "y"},
    )
