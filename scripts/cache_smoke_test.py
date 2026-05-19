from __future__ import annotations

import os
import tempfile

from ashare_quant.cache.provider_cache import PersistentCacheMarketDataProvider
from ashare_quant.cache.sqlite_cache import SqliteMarketCache
from ashare_quant.providers.mock_provider import MockMarketDataProvider


def main() -> None:
    temp_dir = tempfile.mkdtemp(prefix="ashare-quant-cache-")
    db_path = os.path.join(temp_dir, "market_cache.sqlite3")

    cache = SqliteMarketCache(db_path)
    provider = PersistentCacheMarketDataProvider(
        provider=MockMarketDataProvider(),
        cache=cache,
        quote_ttl_seconds=3600,
        bar_ttl_seconds=3600,
        allow_stale_on_error=True,
    )

    universe = provider.list_universe(limit=5)
    quote = provider.get_quote("600519")
    bars = provider.get_daily_bars("600519", lookback=20)
    stats = cache.get_stats()

    print("db_exists={value}".format(value=os.path.exists(db_path)))
    print("universe_count={value}".format(value=len(universe)))
    print("quote_symbol={value}".format(value=quote.symbol))
    print("bar_count={value}".format(value=len(bars)))
    print("quote_rows={value}".format(value=stats["quote_rows"]))
    print("daily_bar_rows={value}".format(value=stats["daily_bar_rows"]))


if __name__ == "__main__":
    main()
