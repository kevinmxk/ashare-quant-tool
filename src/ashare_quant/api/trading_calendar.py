from __future__ import annotations

from datetime import datetime, time

try:
    import chinesecalendar  # type: ignore  # noqa: F401
except ImportError:  # The PyPI package exposes this module name in current releases.
    import chinese_calendar as _chinese_calendar  # type: ignore
else:
    _chinese_calendar = None


def is_trading_time(now: datetime | None = None) -> bool:
    """Return whether now falls in the regular A-share trading window."""
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False

    trade_day_method = getattr(now.date(), "is_trade_day", None)
    if callable(trade_day_method):
        is_trade_day = bool(trade_day_method())
    elif _chinese_calendar is not None:
        is_trade_day = bool(_chinese_calendar.is_workday(now.date()))
    else:
        is_trade_day = True

    if not is_trade_day:
        return False

    market_open = time(9, 30)
    market_close = time(15, 0)
    return market_open <= now.time() <= market_close
