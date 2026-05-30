from __future__ import annotations

from ashare_quant.analysis.factors import liquidity_score, momentum_20d, range_position, risk_score, trend_strength, valuation_score
from ashare_quant.analysis.strategies.common import STRATEGY_DEFINITIONS, _format_percent, _normalize
from ashare_quant.models import DailyBar, FactorSet, QuoteSnapshot


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
