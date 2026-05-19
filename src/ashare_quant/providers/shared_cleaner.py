from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip()
    if not value:
        return ""

    upper = value.upper()
    lower = value.lower()

    if "." in upper:
        left, right = upper.split(".", 1)
        if right in {"SH", "SZ", "BJ"}:
            return left
    if "." in lower:
        left, _right = lower.split(".", 1)
        return left.upper()

    for prefix in ("SH", "SZ", "BJ"):
        if upper.startswith(prefix):
            return upper[len(prefix) :]

    return upper


def detect_exchange(symbol: str) -> str:
    code = normalize_symbol(symbol)
    if not code:
        return "SZ"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879", "880", "881", "882", "883", "884", "885", "886", "887", "888", "889")):
        return "BJ"
    if code.startswith(("5", "6", "9")):
        return "SH"
    return "SZ"


def to_tushare_code(symbol: str) -> str:
    code = normalize_symbol(symbol)
    exchange = detect_exchange(code)
    return "{code}.{exchange}".format(code=code, exchange=exchange)


def to_baostock_code(symbol: str) -> str:
    code = normalize_symbol(symbol)
    exchange = detect_exchange(code).lower()
    return "{exchange}.{code}".format(exchange=exchange, code=code)


def to_sina_symbol(symbol: str) -> str:
    code = normalize_symbol(symbol)
    exchange = detect_exchange(code).lower()
    return "{exchange}{code}".format(exchange=exchange, code=code)


def safe_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, "", "-", "--"):
        return default
    try:
        text = str(value).replace(",", "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def parse_trade_date(value: Any):
    if value in (None, "", "-", "--"):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def safe_text(value: Any) -> str | None:
    if value in (None, "", "-", "--"):
        return None
    text = str(value).strip()
    return text or None
