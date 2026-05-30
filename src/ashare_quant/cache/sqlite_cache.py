from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from ashare_quant.cache.impl.bar_cache import BarCache
from ashare_quant.cache.impl.quote_cache import QuoteCache
from ashare_quant.cache.impl.universe_cache import UniverseCache
from ashare_quant.cache.impl.watchlist_cache import WatchlistCache
from ashare_quant.models import DailyBar, QuoteSnapshot


class SqliteMarketCache:
    """Persistent cache for quotes and daily bars backed by sqlite."""

    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.abspath(db_path)
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._quote_cache = QuoteCache(self._connect)
        self._bar_cache = BarCache(self._connect)
        self._universe_cache = UniverseCache(self._connect, self._quote_cache)
        self._watchlist_cache = WatchlistCache(self._connect)
        self._initialize()

    def save_universe(self, provider_name: str, quotes: list[QuoteSnapshot], source_provider: str | None = None) -> None:
        self._universe_cache.save_universe(provider_name, quotes, source_provider)

    def load_universe(self, provider_name: str, max_age_seconds: int, limit: int) -> list[QuoteSnapshot]:
        return self._universe_cache.load_universe(provider_name, max_age_seconds, limit)

    def get_universe_cache_meta(self, provider_name: str) -> dict | None:
        return self._universe_cache.get_universe_cache_meta(provider_name)

    def load_latest_quote(self, provider_name: str, symbol: str, max_age_seconds: int) -> QuoteSnapshot | None:
        return self._quote_cache.load_latest_quote(provider_name, symbol, max_age_seconds)

    def load_latest_quote_any_age(self, provider_name: str, symbol: str) -> QuoteSnapshot | None:
        return self._quote_cache.load_latest_quote_any_age(provider_name, symbol)

    def get_quote_cache_meta(self, provider_name: str, symbol: str) -> dict | None:
        return self._quote_cache.get_quote_cache_meta(provider_name, symbol)

    def save_quote(self, provider_name: str, quote: QuoteSnapshot, source_provider: str | None = None) -> None:
        self._quote_cache.save_quote(provider_name, quote, source_provider)

    def save_daily_bars(
        self,
        provider_name: str,
        symbol: str,
        bars: list[DailyBar],
        source_provider: str | None = None,
    ) -> None:
        self._bar_cache.save_daily_bars(provider_name, symbol, bars, source_provider)

    def load_daily_bars(self, provider_name: str, symbol: str, lookback: int, max_age_seconds: int) -> list[DailyBar]:
        return self._bar_cache.load_daily_bars(provider_name, symbol, lookback, max_age_seconds)

    def load_daily_bars_any_age(self, provider_name: str, symbol: str, lookback: int) -> list[DailyBar]:
        return self._bar_cache.load_daily_bars_any_age(provider_name, symbol, lookback)

    def get_daily_bars_cache_meta(self, provider_name: str, symbol: str, lookback: int) -> dict | None:
        return self._bar_cache.get_daily_bars_cache_meta(provider_name, symbol, lookback)

    def get_stats(self) -> dict[str, int]:
        with self._connect() as conn:
            quote_rows = conn.execute("SELECT COUNT(*) AS count FROM quote_cache").fetchone()["count"]
            bar_rows = conn.execute("SELECT COUNT(*) AS count FROM daily_bar_cache").fetchone()["count"]
            batch_rows = conn.execute("SELECT COUNT(*) AS count FROM universe_batches").fetchone()["count"]
        return {
            "quote_rows": int(quote_rows),
            "daily_bar_rows": int(bar_rows),
            "universe_batches": int(batch_rows),
        }

    def list_watchlist_symbols(self) -> list[str]:
        return self._watchlist_cache.list_watchlist_symbols()

    def add_watchlist_symbol(self, symbol: str, note: str | None = None) -> None:
        self._watchlist_cache.add_watchlist_symbol(symbol, note)

    def remove_watchlist_symbol(self, symbol: str) -> bool:
        return self._watchlist_cache.remove_watchlist_symbol(symbol)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS quote_cache (
                    provider_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_provider TEXT,
                    name TEXT NOT NULL,
                    latest_price REAL NOT NULL,
                    pct_change REAL NOT NULL,
                    turnover_rate REAL NOT NULL,
                    amount REAL NOT NULL,
                    volume_ratio REAL NOT NULL,
                    pe_ttm REAL,
                    pb REAL,
                    market_cap REAL,
                    sector TEXT,
                    PRIMARY KEY (provider_name, symbol)
                );

                CREATE TABLE IF NOT EXISTS universe_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT NOT NULL,
                    source_provider TEXT,
                    fetched_at TEXT NOT NULL,
                    item_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS universe_batch_items (
                    batch_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (batch_id, position),
                    FOREIGN KEY (batch_id) REFERENCES universe_batches(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS daily_bar_cache (
                    provider_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_provider TEXT,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL NOT NULL,
                    PRIMARY KEY (provider_name, symbol, trade_date)
                );

                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL UNIQUE,
                    note TEXT,
                    added_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_universe_batches_provider_time
                ON universe_batches(provider_name, fetched_at DESC);

                CREATE INDEX IF NOT EXISTS idx_daily_bar_cache_lookup
                ON daily_bar_cache(provider_name, symbol, trade_date DESC);
                """
            )
            self._ensure_column(conn, "quote_cache", "source_provider", "TEXT")
            self._ensure_column(conn, "universe_batches", "source_provider", "TEXT")
            self._ensure_column(conn, "daily_bar_cache", "source_provider", "TEXT")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA journal_mode = WAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
        rows = conn.execute("PRAGMA table_info({table})".format(table=table_name)).fetchall()
        existing = {str(row["name"]) for row in rows}
        if column_name not in existing:
            conn.execute(
                "ALTER TABLE {table} ADD COLUMN {column} {column_type}".format(
                    table=table_name,
                    column=column_name,
                    column_type=column_type,
                )
            )


def utcnow_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _seconds_since(timestamp_text: str) -> float:
    then = datetime.fromisoformat(str(timestamp_text))
    return (datetime.utcnow() - then).total_seconds()
