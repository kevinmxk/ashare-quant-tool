"""Tests for ashare_quant.ui.dashboard_data"""
from __future__ import annotations

import sys
import os
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from ashare_quant.models import (
    DailyBar,
    FactorSet,
    QuoteSnapshot,
    RankingsResult,
    StockDiagnosisResult,
)
from ashare_quant.ui.dashboard_data import (
    bars_to_chart_data,
    build_rankings_table,
    build_watchlist_rows,
    calculate_profitability_index,
    enrich_diagnosis_with_pi,
    get_strategies,
    normalize_ui_strategy,
    parse_watchlist,
    summarize_rankings,
)


class TestParseWatchlist(unittest.TestCase):
    def test_basic_comma_separated(self):
        self.assertEqual(parse_watchlist("600519,300750"), ["600519", "300750"])

    def test_newline_and_mixed_separators(self):
        self.assertEqual(
            parse_watchlist("600519\n300750, 000858 ,002594"),
            ["600519", "300750", "000858", "002594"],
        )

    def test_deduplication(self):
        self.assertEqual(parse_watchlist("600519,600519,300750"), ["600519", "300750"])

    def test_empty_and_whitespace(self):
        self.assertEqual(parse_watchlist("  ,  , \n "), [])

    def test_empty_string(self):
        self.assertEqual(parse_watchlist(""), [])


class TestNormalizeUIStrategy(unittest.TestCase):
    def test_valid_strategies(self):
        self.assertEqual(normalize_ui_strategy("trend"), "trend")
        self.assertEqual(normalize_ui_strategy("pullback"), "pullback")
        self.assertEqual(normalize_ui_strategy("value"), "value")

    def test_invalid_defaults_to_trend(self):
        self.assertEqual(normalize_ui_strategy("unknown"), "trend")
        self.assertEqual(normalize_ui_strategy(""), "trend")
        self.assertEqual(normalize_ui_strategy(None), "trend")


class TestGetStrategies(unittest.TestCase):
    def test_returns_non_empty_list(self):
        strategies = get_strategies()
        self.assertIsInstance(strategies, list)
        self.assertGreater(len(strategies), 0)
        for s in strategies:
            self.assertIn("id", s)
            self.assertIn("name", s)

    def test_cache_consistency(self):
        # lru_cache should return the same object on repeated calls
        a = get_strategies()
        b = get_strategies()
        self.assertEqual(a, b)


class TestSummarizeRankings(unittest.TestCase):
    def _make_result(self, scores, eligible_flags):
        items = []
        for sym, score, eligible in zip(["600519", "300750"], scores, eligible_flags):
            quote = QuoteSnapshot(
                symbol=sym,
                name=sym,
                latest_price=100.0,
                pct_change=1.0,
                turnover_rate=1.0,
                amount=1e6,
                volume_ratio=1.0,
            )
            factors = FactorSet(
                strategy_id="trend",
                strategy_name="趋势突破",
                momentum_20d=0.0,
                trend_strength=0.0,
                liquidity_score=0.0,
                valuation_score=0.0,
                risk_score=0.0,
                total_score=score,
                eligible=eligible,
                entry_signal="",
                exit_signal="",
            )
            items.append(StockDiagnosisResult(quote=quote, factors=factors))
        return RankingsResult(items=items, universe_meta=None)

    def test_empty_rankings(self):
        result = summarize_rankings(RankingsResult(items=[], universe_meta=None))
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["eligible_count"], 0)
        self.assertEqual(result["avg_score"], 0.0)
        self.assertEqual(result["top_score"], 0.0)

    def test_normal_rankings(self):
        rankings = self._make_result([80.0, 60.0], [True, False])
        summary = summarize_rankings(rankings)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["eligible_count"], 1)
        self.assertEqual(summary["avg_score"], 70.0)
        self.assertEqual(summary["top_score"], 80.0)


class TestBuildRankingsTable(unittest.TestCase):
    def test_empty_items(self):
        rankings = RankingsResult(items=[], universe_meta=None)
        table = build_rankings_table(rankings)
        self.assertEqual(table, [])

    def test_basic_fields(self):
        quote = QuoteSnapshot(
            symbol="600519",
            name="茅台",
            latest_price=1500.0,
            pct_change=2.5,
            turnover_rate=0.5,
            amount=1e8,
            volume_ratio=1.2,
            sector="白酒",
        )
        factors = FactorSet(
            strategy_id="trend",
            strategy_name="趋势突破",
            momentum_20d=5.0,
            trend_strength=70.0,
            liquidity_score=80.0,
            valuation_score=60.0,
            risk_score=50.0,
            total_score=85.0,
            eligible=True,
            entry_signal="买入",
            exit_signal="持有",
            risk_flags=["波动偏高"],
        )
        result = StockDiagnosisResult(quote=quote, factors=factors)
        rankings = RankingsResult(items=[result], universe_meta=None)
        table = build_rankings_table(rankings)
        self.assertEqual(len(table), 1)
        row = table[0]
        self.assertEqual(row["rank"], 1)
        self.assertEqual(row["symbol"], "600519")
        self.assertEqual(row["name"], "茅台")
        self.assertEqual(row["sector"], "白酒")
        self.assertEqual(row["score"], 85.0)
        self.assertEqual(row["eligible"], "是")
        self.assertEqual(row["risk_flags"], "波动偏高")


class TestProfitabilityIndex(unittest.TestCase):
    def test_all_fields_present(self):
        factors = {
            "total_score": 80.0,
            "trend_strength": 70.0,
            "momentum_20d": 10.0,
            "liquidity_score": 60.0,
        }
        pi = calculate_profitability_index(factors)
        expected = round(80.0 * 0.40 + 70.0 * 0.25 + 10.0 * 0.20 + 60.0 * 0.15, 2)
        self.assertEqual(pi, expected)
        self.assertLessEqual(pi, 100.0)

    def test_negative_momentum_treated_as_zero(self):
        factors = {
            "total_score": 50.0,
            "trend_strength": 50.0,
            "momentum_20d": -10.0,
            "liquidity_score": 50.0,
        }
        pi = calculate_profitability_index(factors)
        expected = round(50.0 * 0.40 + 50.0 * 0.25 + 0.0 + 50.0 * 0.15, 2)
        self.assertEqual(pi, expected)

    def test_missing_field_returns_none(self):
        self.assertIsNone(calculate_profitability_index({"total_score": 80.0}))

    def test_enrich_diagnosis_injects_pi(self):
        result = {
            "quote": {"symbol": "600519"},
            "factors": {
                "total_score": 80.0,
                "trend_strength": 70.0,
                "momentum_20d": 10.0,
                "liquidity_score": 60.0,
            },
        }
        enriched = enrich_diagnosis_with_pi(result)
        self.assertIn("profitability_index", enriched["factors"])
        self.assertIsInstance(enriched["factors"]["profitability_index"], float)

    def test_enrich_diagnosis_unchanged_when_pi_none(self):
        result = {"quote": {}, "factors": {}}
        enriched = enrich_diagnosis_with_pi(result)
        self.assertNotIn("profitability_index", enriched["factors"])


class TestBarsToChartData(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(bars_to_chart_data([]), [])

    def test_basic_conversion(self):
        bars = [
            DailyBar(
                symbol="600519",
                trade_date=date(2024, 1, 1),
                open_price=100.0,
                high_price=105.0,
                low_price=99.0,
                close_price=102.0,
                volume=1e6,
                amount=1e8,
            ),
            DailyBar(
                symbol="600519",
                trade_date=date(2024, 1, 2),
                open_price=102.0,
                high_price=106.0,
                low_price=101.0,
                close_price=105.0,
                volume=1.2e6,
                amount=1.2e8,
            ),
        ]
        data = bars_to_chart_data(bars)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["date"], "2024-01-01")
        self.assertEqual(data[0]["close"], 102.0)
        self.assertEqual(data[1]["date"], "2024-01-02")
        self.assertEqual(data[1]["close"], 105.0)

    def test_sorting_by_date(self):
        bars = [
            DailyBar(
                symbol="600519",
                trade_date=date(2024, 1, 3),
                open_price=0.0,
                high_price=0.0,
                low_price=0.0,
                close_price=103.0,
                volume=0.0,
                amount=0.0,
            ),
            DailyBar(
                symbol="600519",
                trade_date=date(2024, 1, 1),
                open_price=0.0,
                high_price=0.0,
                low_price=0.0,
                close_price=101.0,
                volume=0.0,
                amount=0.0,
            ),
        ]
        data = bars_to_chart_data(bars)
        self.assertEqual(data[0]["date"], "2024-01-01")
        self.assertEqual(data[1]["date"], "2024-01-03")


class TestBuildWatchlistRows(unittest.TestCase):
    def test_empty_symbols(self):
        # build_watchlist_rows expects a real service; for empty input it short-circuits via caller.
        # Here we just ensure parse_watchlist works as expected upstream.
        self.assertEqual(parse_watchlist(""), [])


if __name__ == "__main__":
    unittest.main()
