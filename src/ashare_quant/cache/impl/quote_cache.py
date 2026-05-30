from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import asdict
from datetime import datetime
from typing import Callable

from ashare_quant.models import QuoteSnapshot
from ashare_quant.providers.shared_cleaner import safe_float, safe_text


class QuoteCache:
    def __init__(self, connect: Callable[[], AbstractContextManager[sqlite3.Connection]]) -> None:
        self._connect = connect

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


def utcnow_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _seconds_since(timestamp_text: str) -> float:
    then = datetime.fromisoformat(str(timestamp_text))
    return (datetime.utcnow() - then).total_seconds()
