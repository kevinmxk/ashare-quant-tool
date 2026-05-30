from __future__ import annotations

from ashare_quant.analysis.strategies.common import STRATEGY_DEFINITIONS, STRATEGY_DESCRIPTIONS
from ashare_quant.analysis.strategies.pullback import _build_pullback_factor_set
from ashare_quant.analysis.strategies.trend import _build_trend_factor_set
from ashare_quant.analysis.strategies.value import _build_value_factor_set
from ashare_quant.models import DailyBar, FactorSet, QuoteSnapshot


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


__all__ = ["build_factor_set", "list_supported_strategies", "normalize_strategy"]
