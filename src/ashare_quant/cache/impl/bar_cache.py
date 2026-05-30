from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Callable

from ashare_quant.models import DailyBar
from ashare_quant.providers.shared_cleaner import parse_trade_date, safe_float


class BarCache:
    def __init__(self, connect: Callable[[], AbstractContextManager[sqlite3.Connection]]) -> None:
        self._connect = connect

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


def utcnow_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _seconds_since(timestamp_text: str) -> float:
    then = datetime.fromisoformat(str(timestamp_text))
    return (datetime.utcnow() - then).total_seconds()
