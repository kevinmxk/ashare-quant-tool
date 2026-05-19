from __future__ import annotations

from typing import Any

from ashare_quant.models import DailyBar, QuoteSnapshot
from ashare_quant.providers.shared_cleaner import (
    normalize_symbol,
    parse_trade_date,
    safe_float,
    safe_text,
)

QUOTE_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "symbol": ("代码", "股票代码", "证券代码", "symbol", "code"),
    "name": ("名称", "股票简称", "证券简称", "name"),
    "latest_price": ("最新价", "最新", "收盘", "trade", "price"),
    "pct_change": ("涨跌幅", "涨幅", "changepercent", "pct_change"),
    "turnover_rate": ("换手率", "换手", "turnoverratio", "turnover_rate"),
    "amount": ("成交额", "金额", "amount"),
    "volume_ratio": ("量比", "volume_ratio"),
    "pe_ttm": ("市盈率-动态", "动态市盈率", "pe_ttm", "per"),
    "pb": ("市净率", "pb"),
    "market_cap": ("总市值", "market_cap", "mktcap"),
    "sector": ("所属行业", "行业", "sector", "industry"),
}

BAR_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "trade_date": ("日期", "交易日期", "date"),
    "symbol": ("股票代码", "代码", "symbol"),
    "open_price": ("开盘", "open"),
    "close_price": ("收盘", "close"),
    "high_price": ("最高", "high"),
    "low_price": ("最低", "low"),
    "volume": ("成交量", "volume"),
    "amount": ("成交额", "amount"),
}
def normalize_column_name(name: Any) -> str:
    text = str(name).strip()
    return "".join(text.split())


def pick_value(row: dict[str, Any], aliases: tuple[str, ...], default: Any = None) -> Any:
    normalized_map = {normalize_column_name(key): value for key, value in row.items()}
    for alias in aliases:
        if alias in row:
            return row[alias]
        compact_alias = normalize_column_name(alias)
        if compact_alias in normalized_map:
            return normalized_map[compact_alias]
    return default


def map_quote_row(row: dict[str, Any]) -> QuoteSnapshot | None:
    symbol = normalize_symbol(pick_value(row, QUOTE_COLUMN_ALIASES["symbol"], ""))
    latest_price = safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["latest_price"]))
    if not symbol or latest_price is None or latest_price <= 0:
        return None

    name = str(pick_value(row, QUOTE_COLUMN_ALIASES["name"], "") or "").strip()
    return QuoteSnapshot(
        symbol=symbol,
        name=name,
        latest_price=latest_price,
        pct_change=safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["pct_change"]), default=0.0) or 0.0,
        turnover_rate=safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["turnover_rate"]), default=0.0) or 0.0,
        amount=safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["amount"]), default=0.0) or 0.0,
        volume_ratio=safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["volume_ratio"]), default=0.0) or 0.0,
        pe_ttm=safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["pe_ttm"])),
        pb=safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["pb"])),
        market_cap=safe_float(pick_value(row, QUOTE_COLUMN_ALIASES["market_cap"])),
        sector=safe_text(pick_value(row, QUOTE_COLUMN_ALIASES["sector"])),
    )


def map_bar_row(row: dict[str, Any], fallback_symbol: str) -> DailyBar | None:
    trade_date = parse_trade_date(pick_value(row, BAR_COLUMN_ALIASES["trade_date"]))
    if trade_date is None:
        return None

    symbol = normalize_symbol(pick_value(row, BAR_COLUMN_ALIASES["symbol"], fallback_symbol))
    open_price = safe_float(pick_value(row, BAR_COLUMN_ALIASES["open_price"]))
    close_price = safe_float(pick_value(row, BAR_COLUMN_ALIASES["close_price"]))
    high_price = safe_float(pick_value(row, BAR_COLUMN_ALIASES["high_price"]))
    low_price = safe_float(pick_value(row, BAR_COLUMN_ALIASES["low_price"]))
    volume = safe_float(pick_value(row, BAR_COLUMN_ALIASES["volume"]), default=0.0)
    amount = safe_float(pick_value(row, BAR_COLUMN_ALIASES["amount"]), default=0.0)

    prices = (open_price, close_price, high_price, low_price)
    if any(value is None for value in prices):
        return None

    return DailyBar(
        symbol=symbol,
        trade_date=trade_date,
        open_price=open_price or 0.0,
        close_price=close_price or 0.0,
        high_price=high_price or 0.0,
        low_price=low_price or 0.0,
        volume=volume or 0.0,
        amount=amount or 0.0,
    )


def dataframe_to_records(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    to_dict = getattr(data, "to_dict", None)
    if callable(to_dict):
        records = to_dict(orient="records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    raise TypeError("AKShare result is not a tabular object with to_dict(orient='records')")
