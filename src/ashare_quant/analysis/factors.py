from __future__ import annotations

from ashare_quant.models import DailyBar, QuoteSnapshot


def moving_average(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    if len(values) < window:
        window = len(values)
    subset = values[-window:]
    return sum(subset) / len(subset)


def closes_from_bars(bars: list[DailyBar]) -> list[float]:
    return [bar.close_price for bar in bars]


def momentum_20d(bars: list[DailyBar]) -> float:
    closes = closes_from_bars(bars)
    if len(closes) < 20 or closes[-20] == 0:
        return 0.0
    return (closes[-1] / closes[-20] - 1.0) * 100


def trend_strength(bars: list[DailyBar]) -> float:
    closes = closes_from_bars(bars)
    if len(closes) < 20:
        return 0.0
    ma20 = moving_average(closes, 20)
    ma60 = moving_average(closes, 60)
    last = closes[-1]
    score = 0.0
    if last > ma20:
        score += 50
    if ma20 > ma60:
        score += 50
    return score


def liquidity_score(quote: QuoteSnapshot) -> float:
    amount_score = min(quote.amount / 5_000_000_000 * 50, 50)
    turnover_score = min(quote.turnover_rate / 5 * 25, 25)
    volume_ratio_score = min(quote.volume_ratio / 3 * 25, 25)
    return amount_score + turnover_score + volume_ratio_score


def valuation_score(quote: QuoteSnapshot) -> float:
    score = 50.0
    if quote.pe_ttm is not None:
        if 0 < quote.pe_ttm <= 25:
            score += 25
        elif quote.pe_ttm > 60:
            score -= 20
    if quote.pb is not None:
        if 0 < quote.pb <= 3:
            score += 25
        elif quote.pb > 8:
            score -= 15
    return max(0.0, min(score, 100.0))


def risk_score(quote: QuoteSnapshot, bars: list[DailyBar]) -> float:
    closes = closes_from_bars(bars[-20:])
    if len(closes) < 2:
        return 50.0
    avg_move = sum(abs(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))) / (len(closes) - 1)
    volatility_penalty = min(avg_move * 1000, 60)
    turnover_penalty = max(0.0, quote.turnover_rate - 8) * 3
    return max(0.0, 100.0 - volatility_penalty - turnover_penalty)


def latest_close(bars: list[DailyBar]) -> float:
    if not bars:
        return 0.0
    return bars[-1].close_price


def distance_to_ma(bars: list[DailyBar], window: int) -> float:
    closes = closes_from_bars(bars)
    if not closes:
        return 0.0
    ma = moving_average(closes, window)
    if ma == 0:
        return 0.0
    return (closes[-1] / ma - 1.0) * 100


def recent_drawdown_from_high(bars: list[DailyBar], window: int = 20) -> float:
    closes = closes_from_bars(bars)
    if not closes:
        return 0.0
    subset = closes[-window:] if len(closes) >= window else closes
    high = max(subset)
    if high == 0:
        return 0.0
    return (closes[-1] / high - 1.0) * 100


def range_position(bars: list[DailyBar], window: int = 60) -> float:
    closes = closes_from_bars(bars)
    if not closes:
        return 0.0
    subset = closes[-window:] if len(closes) >= window else closes
    low = min(subset)
    high = max(subset)
    if high <= low:
        return 50.0
    return (subset[-1] - low) / (high - low) * 100
