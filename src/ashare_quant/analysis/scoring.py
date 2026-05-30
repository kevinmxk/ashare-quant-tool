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
    entry_signal = _trend_entry_signal(
        eligible=eligible,
        trend=trend,
        momentum=momentum,
        volume_ratio=quote.volume_ratio,
        liquidity=liquidity,
        risk=risk,
    )

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
    entry_signal = _pullback_entry_signal(
        eligible=eligible,
        trend=trend,
        ma20_distance=ma20_distance,
        pullback=pullback,
        volume_ratio=quote.volume_ratio,
        liquidity=liquidity,
        risk=risk,
    )

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
    entry_signal = _value_entry_signal(
        eligible=eligible,
        valuation=valuation,
        risk=risk,
        stability=stability_score,
        momentum=momentum,
        trend=trend,
        liquidity=liquidity,
    )

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


def _trend_entry_signal(
    *,
    eligible: bool,
    trend: float,
    momentum: float,
    volume_ratio: float,
    liquidity: float,
    risk: float,
) -> str:
    momentum_text = _format_percent(momentum)
    volume_text = _format_ratio(volume_ratio)

    if not eligible:
        misses: list[str] = []
        if trend < 50:
            misses.append("趋势尚未形成：均线多头结构未建立")
        elif trend < 100:
            misses.append("趋势只站上短期均线：MA20 尚未确认强于 MA60")
        if momentum <= 3:
            misses.append(f"动量不足：近 20 日涨幅仅 {momentum_text}")
        if liquidity < 45:
            misses.append(f"流动性偏低：流动性评分 {liquidity:.0f}")
        if risk < 40:
            misses.append(f"波动风险偏高：风险评分 {risk:.0f}")
        if volume_ratio < 1.2:
            misses.append(f"量能未配合：量比 {volume_text}")
        return " + ".join(misses[:2]) + "，暂不追涨，等待趋势、动量或量能改善"

    trend_phrase = "均线多头排列明确" if trend >= 100 else "短期趋势已转强"
    if momentum > 8:
        momentum_phrase = f"近 20 日涨幅 {momentum_text}，动量强"
    elif momentum > 3:
        momentum_phrase = f"近 20 日涨幅 {momentum_text}，动量温和"
    else:
        momentum_phrase = f"近 20 日涨幅 {momentum_text}，动量刚达观察线"

    if volume_ratio > 2.5:
        volume_phrase = f"量比 {volume_text} 异常放大"
        action = "适合等冲高回落后再分批跟随，避免情绪化追高"
    elif volume_ratio >= 1.2:
        volume_phrase = f"量比 {volume_text} 放大配合"
        action = "可在突破确认后顺势建仓"
    else:
        volume_phrase = f"量比 {volume_text} 偏低"
        action = "更适合等待下一次放量确认"

    if liquidity >= 70 and risk >= 55:
        guard = "流动性充裕且风险评分稳健"
    elif liquidity >= 70:
        guard = "流动性充裕但波动仍需控制"
    elif risk < 55:
        guard = "流动性一般且波动偏高"
    else:
        guard = "流动性一般但风险尚可"

    return f"{trend_phrase}，{momentum_phrase}，{volume_phrase}；{guard}，{action}"


def _pullback_entry_signal(
    *,
    eligible: bool,
    trend: float,
    ma20_distance: float,
    pullback: float,
    volume_ratio: float,
    liquidity: float,
    risk: float,
) -> str:
    ma_text = _format_percent(ma20_distance)
    pullback_text = _format_percent(abs(pullback))
    volume_text = _format_ratio(volume_ratio)

    if not eligible:
        misses: list[str] = []
        if trend < 100:
            misses.append("中期趋势不够强：尚未形成完整多头结构")
        if pullback > -2:
            misses.append(f"回撤不足：近 20 日高点回落仅 {pullback_text}")
        elif pullback < -12:
            misses.append(f"回撤过深：近 20 日高点回落 {pullback_text}")
        if ma20_distance < -4:
            misses.append(f"偏离 MA20 过深：股价距 MA20 {ma_text}")
        elif ma20_distance > 3:
            misses.append(f"尚未回到均线附近：股价高于 MA20 {ma_text}")
        if liquidity < 40:
            misses.append(f"承接不足：流动性评分 {liquidity:.0f}")
        if risk < 40:
            misses.append(f"波动过大：风险评分 {risk:.0f}")
        return " + ".join(misses[:2]) + "，先观察止跌和承接变化"

    if -1 <= ma20_distance <= 1:
        ma_phrase = f"股价距 MA20 仅 {ma_text}，贴近均线"
    elif ma20_distance < -1:
        ma_phrase = f"股价低于 MA20 {ma_text}，左侧修复特征更强"
    else:
        ma_phrase = f"股价高于 MA20 {ma_text}，回踩尚未完全到位"

    if pullback <= -9:
        pullback_phrase = f"近 20 日回撤 {pullback_text}，回调偏深"
    elif pullback <= -5:
        pullback_phrase = f"近 20 日回撤 {pullback_text}，幅度适中"
    else:
        pullback_phrase = f"近 20 日回撤 {pullback_text}，回调较浅"

    if volume_ratio < 0.8:
        volume_phrase = f"量比 {volume_text}，缩量较明显"
        action = "可等待缩量企稳后的首个放量反弹再试仓"
    elif volume_ratio <= 1.5:
        volume_phrase = f"量比 {volume_text}，承接相对平稳"
        action = "适合在止跌确认后分批低吸"
    else:
        volume_phrase = f"量比 {volume_text}，回调中交投活跃"
        action = "需确认不是放量下跌后再介入"

    guard = "流动性充裕" if liquidity >= 65 else "流动性一般"
    if risk < 55:
        guard += "且波动偏高，仓位应更轻"
    else:
        guard += "且波动可控"

    return f"{ma_phrase}，{pullback_phrase}，{volume_phrase}；{guard}，{action}"


def _value_entry_signal(
    *,
    eligible: bool,
    valuation: float,
    risk: float,
    stability: float,
    momentum: float,
    trend: float,
    liquidity: float,
) -> str:
    momentum_text = _format_percent(momentum)

    if not eligible:
        misses: list[str] = []
        if valuation < 65:
            misses.append(f"估值吸引力不足：估值评分 {valuation:.0f}")
        if risk < 55:
            misses.append(f"稳定性不足：风险评分 {risk:.0f}")
        if trend < 50:
            misses.append("趋势偏弱：股价已有走坏迹象")
        if liquidity < 25:
            misses.append(f"流动性过低：流动性评分 {liquidity:.0f}")
        if momentum < -12:
            misses.append(f"跌势过急：近 20 日跌幅 {abs(momentum):.1f}%")
        return " + ".join(misses[:2]) + "，暂不纳入稳健低估配置"

    if valuation >= 75:
        valuation_phrase = f"估值评分 {valuation:.0f}，安全边际较好"
    else:
        valuation_phrase = f"估值评分 {valuation:.0f}，吸引力刚达标"

    if stability >= 70 and risk >= 65:
        stability_phrase = f"稳定性评分 {stability:.0f} 且风险评分 {risk:.0f}，波动较可控"
    elif stability >= 60:
        stability_phrase = f"稳定性评分 {stability:.0f}，适合分批观察"
    else:
        stability_phrase = f"稳定性评分 {stability:.0f}，仍需降低建仓节奏"

    if momentum >= 3:
        momentum_phrase = f"近 20 日涨幅 {momentum_text}，已有温和修复"
        action = "可用中线仓位分批配置"
    elif momentum >= -3:
        momentum_phrase = f"近 20 日涨幅 {momentum_text}，走势基本企稳"
        action = "可小步低吸并继续跟踪估值修复"
    else:
        momentum_phrase = f"近 20 日涨幅 {momentum_text}，仍在弱修复"
        action = "更适合等待止跌确认后再配置"

    liquidity_phrase = "流动性充足" if liquidity >= 45 else "流动性一般"
    return f"{valuation_phrase}，{stability_phrase}，{momentum_phrase}；{liquidity_phrase}，{action}"


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"


def _format_ratio(value: float) -> str:
    return f"{value:.1f}"


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    clamped = max(low, min(value, high))
    return (clamped - low) / (high - low) * 100
