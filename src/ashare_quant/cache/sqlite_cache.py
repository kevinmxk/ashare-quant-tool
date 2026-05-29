from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Iterator

from ashare_quant.models import DailyBar, QuoteSnapshot
from ashare_quant.providers.shared_cleaner import parse_trade_date, safe_float, safe_text


class SqliteMarketCache:
    """Persistent cache for quotes and daily bars backed by sqlite."""

    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.abspath(db_path)
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._initialize()

    def save_universe(self, provider_name: str, quotes: list[QuoteSnapshot], source_provider: str | None = None) -> None:
        if not quotes:
            return
        fetched_at = utcnow_text()
        actual_source = source_provider or provider_name
        with self._connect() as conn:
            for quote in quotes:
                self._upsert_quote(conn, provider_name, quote, fetched_at, actual_source)
            batch_id = conn.execute(
                """
                INSERT INTO universe_batches (provider_name, source_provider, fetched_at, item_count)
                VALUES (?, ?, ?, ?)
                """,
                (provider_name, actual_source, fetched_at, len(quotes)),
            ).lastrowid
            conn.executemany(
                """
                INSERT INTO universe_batch_items (batch_id, symbol, position)
                VALUES (?, ?, ?)
                """,
                [(batch_id, quote.symbol, index) for index, quote in enumerate(quotes)],
            )

    def load_universe(self, provider_name: str, max_age_seconds: int, limit: int) -> list[QuoteSnapshot]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, fetched_at
                FROM universe_batches
                WHERE provider_name = ?
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (provider_name,),
            ).fetchone()
            if row is None:
                return []
            if _seconds_since(row["fetched_at"]) > max_age_seconds:
                return []
            rows = conn.execute(
                """
                SELECT q.*
                FROM universe_batch_items u
                JOIN quote_cache q
                  ON q.provider_name = ?
                 AND q.symbol = u.symbol
                WHERE u.batch_id = ?
                ORDER BY u.position ASC
                LIMIT ?
                """,
                (provider_name, row["id"], limit),
            ).fetchall()
            return [self._row_to_quote(item) for item in rows]

    def get_universe_cache_meta(self, provider_name: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT source_provider, fetched_at, item_count
                FROM universe_batches
                WHERE provider_name = ?
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (provider_name,),
            ).fetchone()
            if row is None:
                return None
            return {
                "source_provider": str(row["source_provider"] or provider_name),
                "updated_at": str(row["fetched_at"]),
                "age_seconds": _seconds_since(row["fetched_at"]),
                "item_count": int(row["item_count"]),
            }

    def load_latest_quote(self, provider_name: str, symbol: str, max_age_seconds: int) -> QuoteSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM quote_cache
                WHERE provider_name = ? AND symbol = ?
                LIMIT 1
                """,
                (provider_name, symbol),
            ).fetchone()
            if row is None:
                return None
            if _seconds_since(row["updated_at"]) > max_age_seconds:
                return None
            return self._row_to_quote(row)

    def load_latest_quote_any_age(self, provider_name: str, symbol: str) -> QuoteSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM quote_cache
                WHERE provider_name = ? AND symbol = ?
                LIMIT 1
                """,
                (provider_name, symbol),
            ).fetchone()
            return self._row_to_quote(row) if row is not None else None

    def get_quote_cache_meta(self, provider_name: str, symbol: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT source_provider, updated_at
                FROM quote_cache
                WHERE provider_name = ? AND symbol = ?
                LIMIT 1
                """,
                (provider_name, symbol),
            ).fetchone()
            if row is None:
                return None
            return {
                "source_provider": str(row["source_provider"] or provider_name),
                "updated_at": str(row["updated_at"]),
                "age_seconds": _seconds_since(row["updated_at"]),
            }

    def save_quote(self, provider_name: str, quote: QuoteSnapshot, source_provider: str | None = None) -> None:
        with self._connect() as conn:
            self._upsert_quote(conn, provider_name, quote, utcnow_text(), source_provider or provider_name)

    def save_daily_bars(
        self,
        provider_name: str,
        symbol: str,
        bars: list[DailyBar],
        source_provider: str | None = None,
    ) -> None:
        if not bars:
            return
        updated_at = utcnow_text()
        actual_source = source_provider or provider_name
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_bar_cache (
                    provider_name, symbol, trade_date, updated_at, source_provider,
                    open_price, high_price, low_price, close_price, volume, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_name, symbol, trade_date) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    source_provider = excluded.source_provider,
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    close_price = excluded.close_price,
                    volume = excluded.volume,
                    amount = excluded.amount
                """,
                [
                    (
                        provider_name,
                        symbol,
                        bar.trade_date.isoformat(),
                        updated_at,
                        actual_source,
                        bar.open_price,
                        bar.high_price,
                        bar.low_price,
                        bar.close_price,
                        bar.volume,
                        bar.amount,
                    )
                    for bar in bars
                ],
            )

    def load_daily_bars(self, provider_name: str, symbol: str, lookback: int, max_age_seconds: int) -> list[DailyBar]:
        rows = self._load_daily_bar_rows(provider_name, symbol, lookback)
        if len(rows) < lookback:
            return []
        latest_update = rows[-1]["updated_at"]
        if _seconds_since(latest_update) > max_age_seconds:
            return []
        return [self._row_to_bar(item) for item in rows]

    def load_daily_bars_any_age(self, provider_name: str, symbol: str, lookback: int) -> list[DailyBar]:
        rows = self._load_daily_bar_rows(provider_name, symbol, lookback)
        return [self._row_to_bar(item) for item in rows]

    def get_daily_bars_cache_meta(self, provider_name: str, symbol: str, lookback: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT source_provider, MAX(updated_at) AS updated_at, COUNT(*) AS count
                FROM daily_bar_cache
                WHERE provider_name = ? AND symbol = ?
                """,
                (provider_name, symbol),
            ).fetchone()
            if row is None or int(row["count"] or 0) < lookback:
                return None
            return {
                "source_provider": str(row["source_provider"] or provider_name),
                "updated_at": str(row["updated_at"]),
                "age_seconds": _seconds_since(row["updated_at"]),
                "count": int(row["count"]),
            }

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

    def _load_daily_bar_rows(self, provider_name: str, symbol: str, lookback: int):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM daily_bar_cache
                WHERE provider_name = ? AND symbol = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (provider_name, symbol, lookback),
            ).fetchall()
        return list(reversed(rows))

    def _upsert_quote(
        self,
        conn: sqlite3.Connection,
        provider_name: str,
        quote: QuoteSnapshot,
        updated_at: str,
        source_provider: str,
    ) -> None:
        payload = asdict(quote)
        conn.execute(
            """
            INSERT INTO quote_cache (
                provider_name, symbol, updated_at, source_provider, name, latest_price, pct_change,
                turnover_rate, amount, volume_ratio, pe_ttm, pb, market_cap, sector
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_name, symbol) DO UPDATE SET
                updated_at = excluded.updated_at,
                source_provider = excluded.source_provider,
                name = excluded.name,
                latest_price = excluded.latest_price,
                pct_change = excluded.pct_change,
                turnover_rate = excluded.turnover_rate,
                amount = excluded.amount,
                volume_ratio = excluded.volume_ratio,
                pe_ttm = excluded.pe_ttm,
                pb = excluded.pb,
                market_cap = excluded.market_cap,
                sector = excluded.sector
            """,
            (
                provider_name,
                quote.symbol,
                updated_at,
                source_provider,
                payload["name"],
                payload["latest_price"],
                payload["pct_change"],
                payload["turnover_rate"],
                payload["amount"],
                payload["volume_ratio"],
                payload["pe_ttm"],
                payload["pb"],
                payload["market_cap"],
                payload["sector"],
            ),
        )

    def _row_to_quote(self, row) -> QuoteSnapshot:
        return QuoteSnapshot(
            symbol=str(row["symbol"]),
            name=str(row["name"]),
            latest_price=safe_float(row["latest_price"], default=0.0) or 0.0,
            pct_change=safe_float(row["pct_change"], default=0.0) or 0.0,
            turnover_rate=safe_float(row["turnover_rate"], default=0.0) or 0.0,
            amount=safe_float(row["amount"], default=0.0) or 0.0,
            volume_ratio=safe_float(row["volume_ratio"], default=0.0) or 0.0,
            pe_ttm=safe_float(row["pe_ttm"]),
            pb=safe_float(row["pb"]),
            market_cap=safe_float(row["market_cap"]),
            sector=safe_text(row["sector"]),
        )

    def _row_to_bar(self, row) -> DailyBar:
        trade_date = parse_trade_date(row["trade_date"])
        if trade_date is None:
            raise ValueError("Invalid trade_date in cache: {value}".format(value=row["trade_date"]))
        return DailyBar(
            symbol=str(row["symbol"]),
            trade_date=trade_date,
            open_price=safe_float(row["open_price"], default=0.0) or 0.0,
            high_price=safe_float(row["high_price"], default=0.0) or 0.0,
            low_price=safe_float(row["low_price"], default=0.0) or 0.0,
            close_price=safe_float(row["close_price"], default=0.0) or 0.0,
            volume=safe_float(row["volume"], default=0.0) or 0.0,
            amount=safe_float(row["amount"], default=0.0) or 0.0,
        )

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
