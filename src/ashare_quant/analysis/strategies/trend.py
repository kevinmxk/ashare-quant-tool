from __future__ import annotations

from ashare_quant.analysis.factors import liquidity_score, momentum_20d, risk_score, trend_strength, valuation_score
from ashare_quant.analysis.strategies.common import STRATEGY_DEFINITIONS, _format_percent, _format_ratio, _normalize
from ashare_quant.models import DailyBar, FactorSet, QuoteSnapshot


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
