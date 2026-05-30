from __future__ import annotations

STRATEGY_DEFINITIONS: dict[str, str] = {
    "trend": "趋势突破",
    "pullback": "回调低吸",
    "value": "价值稳健",
}

STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "trend": "优先选择价格强于均线、动量较强且流动性充足的强势股。",
    "pullback": "优先选择中期趋势未坏、短线适度回撤到均线附近的低吸候选。",
    "value": "优先选择估值较友好、波动较可控、趋势未明显走坏的稳健标的。",
}


def _pullback_quality_score(ma20_distance: float, pullback: float) -> float:
    ma_score = 100 - min(abs(ma20_distance) * 16, 80)
    target_drawdown = -7.0
    drawdown_score = 100 - min(abs(pullback - target_drawdown) * 8, 80)
    if pullback > -2:
        drawdown_score -= 15
    if pullback < -15:
        drawdown_score -= 20
    return max(0.0, min((ma_score * 0.55 + drawdown_score * 0.45), 100.0))


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"


def _format_ratio(value: float) -> str:
    return f"{value:.1f}"


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    clamped = max(low, min(value, high))
    return (clamped - low) / (high - low) * 100
