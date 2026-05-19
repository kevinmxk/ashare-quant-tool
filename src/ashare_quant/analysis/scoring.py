from __future__ import annotations

from ashare_quant.analysis.factors import (
    distance_to_ma,
    liquidity_score,
    momentum_20d,
    range_position,
    recent_drawdown_from_high,
    risk_score,
    trend_strength,
    valuation_score,
)
from ashare_quant.models import DailyBar, FactorSet, QuoteSnapshot

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


def list_supported_strategies() -> list[dict[str, str]]:
    return [
        {"id": key, "name": value, "description": STRATEGY_DESCRIPTIONS.get(key)}
        for key, value in STRATEGY_DEFINITIONS.items()
    ]


def build_factor_set(quote: QuoteSnapshot, bars: list[DailyBar], strategy: str = "trend") -> FactorSet:
    strategy_id = normalize_strategy(strategy)
    if strategy_id == "trend":
        return _build_trend_factor_set(quote, bars)
    if strategy_id == "pullback":
        return _build_pullback_factor_set(quote, bars)
    return _build_value_factor_set(quote, bars)


def normalize_strategy(strategy: str | None) -> str:
    key = str(strategy or "trend").strip().lower()
    if key not in STRATEGY_DEFINITIONS:
        return "trend"
    return key


def _build_trend_factor_set(quote: QuoteSnapshot, bars: list[DailyBar]) -> FactorSet:
    momentum = momentum_20d(bars)
    trend = trend_strength(bars)
    liquidity = liquidity_score(quote)
    valuation = valuation_score(quote)
    risk = risk_score(quote, bars)

    momentum_score = _normalize(momentum, low=-15, high=25)
    total_score = (
        momentum_score * 0.28
        + trend * 0.32
        + liquidity * 0.20
        + valuation * 0.08
        + risk * 0.12
    )

    explanations: list[str] = []
    failed_filters: list[str] = []
    risk_flags: list[str] = []

    if trend < 100:
        failed_filters.append("趋势条件不足：尚未形成 MA20 上穿 MA60 的完整多头结构")
    if momentum <= 3:
        failed_filters.append("动量偏弱：近 20 日涨幅不足 3%")
    if liquidity < 45:
        failed_filters.append("流动性不足：成交活跃度偏弱")
    if risk < 40:
        failed_filters.append("风险偏高：短线波动过大")

    if momentum > 8:
        explanations.append("近 20 日动量较强")
    if trend >= 100:
        explanations.append("价格站上 MA20，且 MA20 高于 MA60")
    elif trend >= 50:
        explanations.append("价格处于短期均线之上")
    if liquidity >= 70:
        explanations.append("成交额、换手率和量比处于活跃区间")
    if risk < 45:
        explanations.append("短线波动较大，追涨时需控制仓位")
        risk_flags.append("波动偏高，突破后容易出现回撤")
    if quote.volume_ratio >= 2.5:
        risk_flags.append("量比过高，需防止情绪化放量冲高回落")
    if quote.turnover_rate >= 8:
        risk_flags.append("换手率过高，短线博弈意味较浓")

    eligible = not failed_filters
    if eligible and momentum >= 8 and quote.volume_ratio >= 1.2:
        entry_signal = "可考虑顺势跟随，优先等放量突破后分批介入"
    elif eligible:
        entry_signal = "趋势达标，但更适合等待下一次放量确认"
    else:
        entry_signal = "暂不追涨，先等待趋势、动量和流动性同步改善"

    if trend < 50:
        exit_signal = "若跌回 MA20 下方且趋势破坏，优先减仓"
    elif momentum < 0:
        exit_signal = "若动能转负，可考虑分批止盈"
    else:
        exit_signal = "继续持有时重点观察 MA20 支撑和量能是否持续"

    return FactorSet(
        strategy_id="trend",
        strategy_name=STRATEGY_DEFINITIONS["trend"],
        momentum_20d=round(momentum, 2),
        trend_strength=round(trend, 2),
        liquidity_score=round(liquidity, 2),
        valuation_score=round(valuation, 2),
        risk_score=round(risk, 2),
        total_score=round(total_score, 2),
        eligible=eligible,
        entry_signal=entry_signal,
        exit_signal=exit_signal,
        failed_filters=failed_filters,
        risk_flags=risk_flags,
        explanations=explanations,
    )


def _build_pullback_factor_set(quote: QuoteSnapshot, bars: list[DailyBar]) -> FactorSet:
    momentum = momentum_20d(bars)
    trend = trend_strength(bars)
    liquidity = liquidity_score(quote)
    valuation = valuation_score(quote)
    risk = risk_score(quote, bars)

    ma20_distance = distance_to_ma(bars, 20)
    pullback = recent_drawdown_from_high(bars, 20)
    pullback_quality = _pullback_quality_score(ma20_distance, pullback)
    momentum_score = _normalize(momentum, low=-10, high=20)
    total_score = (
        trend * 0.30
        + pullback_quality * 0.28
        + liquidity * 0.18
        + risk * 0.14
        + momentum_score * 0.10
    )

    explanations: list[str] = []
    failed_filters: list[str] = []
    risk_flags: list[str] = []

    if trend < 100:
        failed_filters.append("趋势条件不足：中期趋势不够强")
    if not (-12 <= pullback <= -2):
        failed_filters.append("回撤幅度不合适：不是理想的中继回调区间")
    if not (-4 <= ma20_distance <= 3):
        failed_filters.append("偏离 MA20 过大：不属于均线附近低吸形态")
    if liquidity < 40:
        failed_filters.append("流动性不足：回调后成交承接偏弱")
    if risk < 40:
        failed_filters.append("波动过大：回调可能演变成破位")

    if trend >= 100:
        explanations.append("中期趋势保持向上")
    if -4 <= ma20_distance <= 2:
        explanations.append("股价回到 MA20 附近，具备观察低吸的形态")
    if -12 <= pullback <= -3:
        explanations.append("相对短期高点已有适度回撤")
    if liquidity >= 65:
        explanations.append("流动性尚可，便于执行回调交易")
    if risk < 45:
        explanations.append("回调中波动偏大，需防止趋势失真")
        risk_flags.append("回调阶段波动偏大，容易继续下探")
    if pullback < -10:
        risk_flags.append("回撤偏深，需确认不是趋势反转")
    if ma20_distance < -3:
        risk_flags.append("股价偏离均线过深，左侧接法风险较大")

    eligible = not failed_filters
    if eligible and -2 <= ma20_distance <= 1:
        entry_signal = "可在 MA20 附近缩量企稳后分批试错"
    elif eligible:
        entry_signal = "形态接近达标，等待回调止跌确认更稳妥"
    else:
        entry_signal = "先观察，不宜把普通下跌误当作回调低吸机会"

    if trend < 50 or pullback < -15:
        exit_signal = "若趋势跌坏或回撤扩大到 15% 以上，应优先离场"
    else:
        exit_signal = "入场后若反弹无量或再次失守 MA20，应收缩仓位"

    return FactorSet(
        strategy_id="pullback",
        strategy_name=STRATEGY_DEFINITIONS["pullback"],
        momentum_20d=round(momentum, 2),
        trend_strength=round(trend, 2),
        liquidity_score=round(liquidity, 2),
        valuation_score=round(valuation, 2),
        risk_score=round(risk, 2),
        total_score=round(total_score, 2),
        eligible=eligible,
        entry_signal=entry_signal,
        exit_signal=exit_signal,
        failed_filters=failed_filters,
        risk_flags=risk_flags,
        explanations=explanations,
    )


def _build_value_factor_set(quote: QuoteSnapshot, bars: list[DailyBar]) -> FactorSet:
    momentum = momentum_20d(bars)
    trend = trend_strength(bars)
    liquidity = liquidity_score(quote)
    valuation = valuation_score(quote)
    risk = risk_score(quote, bars)

    range_score = range_position(bars, 60)
    momentum_score = _normalize(momentum, low=-20, high=15)
    stability_score = min((risk * 0.7 + (100 - abs(range_score - 50)) * 0.3), 100)
    total_score = (
        valuation * 0.40
        + stability_score * 0.22
        + trend * 0.18
        + liquidity * 0.10
        + momentum_score * 0.10
    )

    explanations: list[str] = []
    failed_filters: list[str] = []
    risk_flags: list[str] = []

    if valuation < 65:
        failed_filters.append("估值吸引力不足：当前不属于更友好的估值区间")
    if risk < 55:
        failed_filters.append("稳定性不足：波动仍偏大")
    if trend < 50:
        failed_filters.append("趋势偏弱：股价已有明显走坏迹象")
    if liquidity < 25:
        failed_filters.append("流动性过低：不适合较大资金进出")
    if momentum < -12:
        failed_filters.append("近期跌势过急：仍需等待修复")

    if valuation >= 75:
        explanations.append("估值处于更友好的区间")
    if trend >= 50:
        explanations.append("股价没有明显走坏")
    if stability_score >= 65:
        explanations.append("波动相对可控，适合稳健观察")
    if liquidity < 45:
        explanations.append("流动性一般，建仓时不宜过急")
    if momentum < -5:
        explanations.append("近期走势偏弱，需要等待修复信号")
        risk_flags.append("走势仍在修复期，过早抄底容易继续被套")
    if quote.pb is not None and quote.pb > 5:
        risk_flags.append("虽然总评分可用，但市净率偏高，价值保护不足")
    if range_score > 85:
        risk_flags.append("价格已接近阶段高位，性价比在下降")

    eligible = not failed_filters
    if eligible and momentum >= -3:
        entry_signal = "估值与稳定性达标，可考虑分批低吸或中线观察"
    elif eligible:
        entry_signal = "基本面风格达标，但更适合等走势止跌后再配置"
    else:
        entry_signal = "当前不满足稳健低估框架，暂时以观察为主"

    if valuation < 55 or trend < 50:
        exit_signal = "若估值优势消失且趋势走弱，应降低持仓"
    else:
        exit_signal = "持有期重点观察估值修复后的滞涨和趋势破坏"

    return FactorSet(
        strategy_id="value",
        strategy_name=STRATEGY_DEFINITIONS["value"],
        momentum_20d=round(momentum, 2),
        trend_strength=round(trend, 2),
        liquidity_score=round(liquidity, 2),
        valuation_score=round(valuation, 2),
        risk_score=round(risk, 2),
        total_score=round(total_score, 2),
        eligible=eligible,
        entry_signal=entry_signal,
        exit_signal=exit_signal,
        failed_filters=failed_filters,
        risk_flags=risk_flags,
        explanations=explanations,
    )


def _pullback_quality_score(ma20_distance: float, pullback: float) -> float:
    ma_score = 100 - min(abs(ma20_distance) * 16, 80)
    target_drawdown = -7.0
    drawdown_score = 100 - min(abs(pullback - target_drawdown) * 8, 80)
    if pullback > -2:
        drawdown_score -= 15
    if pullback < -15:
        drawdown_score -= 20
    return max(0.0, min((ma_score * 0.55 + drawdown_score * 0.45), 100.0))


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    clamped = max(low, min(value, high))
    return (clamped - low) / (high - low) * 100
