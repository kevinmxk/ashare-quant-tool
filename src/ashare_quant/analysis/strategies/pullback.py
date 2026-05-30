from __future__ import annotations

from ashare_quant.analysis.factors import (
    distance_to_ma,
    liquidity_score,
    momentum_20d,
    recent_drawdown_from_high,
    risk_score,
    trend_strength,
    valuation_score,
)
from ashare_quant.analysis.strategies.common import (
    STRATEGY_DEFINITIONS,
    _format_percent,
    _format_ratio,
    _normalize,
    _pullback_quality_score,
)
from ashare_quant.models import DailyBar, FactorSet, QuoteSnapshot


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
