from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Callable

from ashare_quant.cache.impl.quote_cache import QuoteCache
from ashare_quant.models import QuoteSnapshot


class UniverseCache:
    def __init__(
        self,
        connect: Callable[[], AbstractContextManager[sqlite3.Connection]],
        quote_cache: QuoteCache,
    ) -> None:
        self._connect = connect
        self._quote_cache = quote_cache

    def save_universe(self, provider_name: str, quotes: list[QuoteSnapshot], source_provider: str | None = None) -> None:
        if not quotes:
            return
        fetched_at = utcnow_text()
        actual_source = source_provider or provider_name
        with self._connect() as conn:
            for quote in quotes:
                self._quote_cache._upsert_quote(conn, provider_name, quote, fetched_at, actual_source)
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
            return [self._quote_cache._row_to_quote(item) for item in rows]

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


def utcnow_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _seconds_since(timestamp_text: str) -> float:
    then = datetime.fromisoformat(str(timestamp_text))
    return (datetime.utcnow() - then).total_seconds()
