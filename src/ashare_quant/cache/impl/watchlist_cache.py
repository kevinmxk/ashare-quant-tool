from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Callable


class WatchlistCache:
    def __init__(self, connect: Callable[[], AbstractContextManager[sqlite3.Connection]]) -> None:
        self._connect = connect

    def list_watchlist_symbols(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT symbol
                FROM watchlist
                ORDER BY added_at ASC, id ASC
                """
            ).fetchall()
            return [str(row["symbol"]) for row in rows]

    def add_watchlist_symbol(self, symbol: str, note: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist (symbol, note, added_at)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    note = COALESCE(excluded.note, watchlist.note)
                """,
                (symbol, note, utcnow_text()),
            )

    def remove_watchlist_symbol(self, symbol: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM watchlist
                WHERE symbol = ?
                """,
                (symbol,),
            )
            return cursor.rowcount > 0


def utcnow_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()
