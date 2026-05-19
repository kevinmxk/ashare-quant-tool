from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass

sys.path.insert(0, os.path.abspath("src"))

import pandas as pd
import streamlit as st

from ashare_quant.config import get_settings
from ashare_quant.providers.factory import build_provider_bundle
from ashare_quant.services.market_service import MarketService
from ashare_quant.ui.dashboard_data import (
    build_rankings_table,
    build_watchlist_rows,
    diagnosis_to_dict,
    normalize_ui_strategy,
    parse_watchlist,
    provider_status,
    summarize_rankings,
)

DEFAULT_WATCHLIST = "600519,300750,000858,002594,688981"


@st.cache_resource
def bootstrap() -> tuple:
    settings = get_settings()
    bundle = build_provider_bundle(settings)
    provider = bundle.default_provider
    service = MarketService(
        provider,
        universe_provider=bundle.universe_provider,
        ranking_provider=bundle.ranking_provider,
        diagnosis_provider=bundle.diagnosis_provider,
        watchlist_provider=bundle.watchlist_provider,
    )
    return settings, provider, service


@st.cache_data(ttl=30, show_spinner=False)
def load_rankings(_service: MarketService, limit: int, strategy: str):
    return _service.rank_universe(limit=limit, strategy=strategy)


@st.cache_data(ttl=30, show_spinner=False)
def load_diagnosis(_service: MarketService, symbol: str, strategy: str):
    return _service.diagnose_stock(symbol, strategy=strategy)


@st.cache_data(ttl=30, show_spinner=False)
def load_watchlist_rows(_service: MarketService, symbols: tuple[str, ...], strategy: str):
    return build_watchlist_rows(_service, list(symbols), strategy)


def main() -> None:
    st.set_page_config(
        page_title="A 股量化分析台",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    settings, provider, service = bootstrap()
    strategies = service.list_strategies()
    strategy_map = {item["name"]: item for item in strategies}

    with st.sidebar:
        st.markdown("## A 股量化分析台")
        st.caption("研究型选股仪表盘")
        selected_view = st.radio(
            "查看模块",
            options=["单股诊断", "策略榜单", "自选池", "系统状态"],
            index=0,
        )
        selected_name = st.radio(
            "选择策略",
            options=[item["name"] for item in strategies],
            index=0,
        )
        selected_strategy = normalize_ui_strategy(strategy_map[selected_name]["id"])
        ranking_limit = st.slider("榜单数量", min_value=10, max_value=50, value=20, step=5)
        watchlist_text = st.text_area("自选池代码", value=DEFAULT_WATCHLIST, height=120)
        stock_symbol = st.text_input("单股诊断代码", value="600519")
        refresh = st.button("刷新面板", use_container_width=True)
        if refresh:
            st.cache_resource.clear()
            st.cache_data.clear()
            settings, provider, service = bootstrap()

    status = provider_status(provider, settings)
    _render_provider_banner(status)

    st.markdown(
        """
        <div class="hero-panel">
          <div>
            <div class="eyebrow">A 股研究仪表盘</div>
            <h1>三套策略，一个操作视图</h1>
            <p>先看谁能进池，再看为什么入选，以及当前更适合追踪、低吸还是等待。</p>
          </div>
          <div class="hero-tag">{strategy}</div>
        </div>
        """.format(strategy=strategy_map[selected_name]["description"]),
        unsafe_allow_html=True,
    )

    if selected_view == "策略榜单":
        with st.spinner("正在加载策略榜单..."):
            rankings = load_rankings(service, ranking_limit, selected_strategy)
        summary = summarize_rankings(rankings)
        metric_cols = st.columns(4)
        metric_cols[0].metric("策略", selected_name)
        metric_cols[1].metric("可执行候选", summary["eligible_count"])
        metric_cols[2].metric("平均分", summary["avg_score"])
        metric_cols[3].metric("最高分", summary["top_score"])
        st.markdown("### 策略榜单")
        st.caption("同策略下先排通过硬过滤的股票，再按总分排序。")
        st.dataframe(
            pd.DataFrame(build_rankings_table(rankings)),
            use_container_width=True,
            hide_index=True,
        )

        if rankings.universe_meta is not None:
            _meta_block("榜单数据来源", rankings.universe_meta)
    elif selected_view == "单股诊断":
        st.markdown("### 单股诊断")
        try:
            with st.spinner("正在加载单股诊断..."):
                diagnosis = load_diagnosis(service, stock_symbol, selected_strategy)
        except KeyError:
            _render_lookup_error(stock_symbol, status)
        else:
            _render_diagnosis(diagnosis_to_dict(diagnosis))
    elif selected_view == "自选池":
        st.markdown("### 自选池观察")
        watchlist = parse_watchlist(watchlist_text)
        if watchlist:
            with st.spinner("正在加载自选池..."):
                rows = load_watchlist_rows(service, tuple(watchlist), selected_strategy)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("在左侧输入一组股票代码后，这里会显示自选池诊断结果。")
    else:
        st.markdown("### 系统状态")
        left, right = st.columns([1.15, 1])
        with left:
            st.json(status, expanded=True)
        with right:
            st.markdown("#### 当前策略说明")
            for item in strategies:
                st.markdown(
                    """
                    <div class="strategy-card">
                      <strong>{name}</strong>
                      <div>{desc}</div>
                    </div>
                    """.format(name=item["name"], desc=item.get("description") or ""),
                    unsafe_allow_html=True,
                )
            st.markdown("#### 使用建议")
            st.markdown(
                "- `trend` 更适合盯盘和顺势跟随\n"
                "- `pullback` 更适合盘后筛出低吸候选\n"
                "- `value` 更适合做中线观察清单"
            )


def _render_diagnosis(result: dict) -> None:
    quote = result["quote"]
    factors = result["factors"]
    cards = st.columns(4)
    cards[0].metric("总分", factors["total_score"])
    cards[1].metric("当前价", quote["latest_price"])
    cards[2].metric("涨跌幅", "{value:.2f}%".format(value=quote["pct_change"]))
    cards[3].metric("是否可执行", "是" if factors["eligible"] else "否")

    top_left, top_right = st.columns([1.1, 1])
    with top_left:
        st.markdown("#### 入场提示")
        st.success(factors["entry_signal"])
        st.markdown("#### 退出提示")
        st.warning(factors["exit_signal"])

        st.markdown("#### 核心解释")
        if factors["explanations"]:
            for item in factors["explanations"]:
                st.markdown("- {item}".format(item=item))
        else:
            st.markdown("- 当前没有明显加分项。")

    with top_right:
        st.markdown("#### 过滤未通过项")
        if factors["failed_filters"]:
            for item in factors["failed_filters"]:
                st.markdown("- {item}".format(item=item))
        else:
            st.markdown("- 当前已通过该策略的硬过滤。")

        st.markdown("#### 风险提示")
        if factors["risk_flags"]:
            for item in factors["risk_flags"]:
                st.markdown("- {item}".format(item=item))
        else:
            st.markdown("- 当前没有额外风险警示。")

    detail_cols = st.columns(5)
    detail_cols[0].metric("20日动量", "{value:.2f}".format(value=factors["momentum_20d"]))
    detail_cols[1].metric("趋势强度", "{value:.2f}".format(value=factors["trend_strength"]))
    detail_cols[2].metric("流动性", "{value:.2f}".format(value=factors["liquidity_score"]))
    detail_cols[3].metric("估值评分", "{value:.2f}".format(value=factors["valuation_score"]))
    detail_cols[4].metric("风险评分", "{value:.2f}".format(value=factors["risk_score"]))

    meta_cols = st.columns(2)
    with meta_cols[0]:
        if result["quote_meta"] is not None:
            _meta_block("报价来源", result["quote_meta"])
    with meta_cols[1]:
        if result["bars_meta"] is not None:
            _meta_block("日线来源", result["bars_meta"])

    st.markdown("#### 原始诊断数据")
    st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")


def _render_lookup_error(symbol: str, status: dict) -> None:
    active_provider = str(status.get("active_provider") or "unknown")
    configured_provider = str(status.get("configured_provider") or "unknown")
    is_mock = "mock" in active_provider.lower()

    if is_mock:
        st.error(
            "当前环境正在使用模拟数据源，暂时不支持诊断 `{symbol}` 这类未内置的股票代码。".format(
                symbol=symbol
            )
        )
        st.info(
            "建议先到“系统状态”页确认数据源，再在部署环境安装并启用真实数据依赖，例如 `AKShare`、`Tushare` 或 `BaoStock`。"
        )
    else:
        st.error("当前数据源里没有找到 `{symbol}`，暂时无法完成单股诊断。".format(symbol=symbol))
        st.info("你可以先检查股票代码格式，或在“系统状态”页确认当前数据源是否正常。")

    st.markdown(
        """
        <div class="meta-card">
          <div class="meta-title">当前数据源状态</div>
          <div>配置值：{configured}</div>
          <div>实际生效：{active}</div>
        </div>
        """.format(configured=configured_provider, active=active_provider),
        unsafe_allow_html=True,
    )


def _render_provider_banner(status: dict) -> None:
    active_chain = str(status.get("active_provider_chain") or status.get("active_provider") or "")
    diagnostics = status.get("provider_diagnostics") or []
    if "mock" not in active_chain.lower():
        return

    unavailable = [
        item
        for item in diagnostics
        if isinstance(item, dict) and not item.get("enabled")
    ]
    if unavailable:
        reason_lines = "\n".join(
            "- {provider}: {reason}".format(
                provider=item.get("provider", "unknown"),
                reason=item.get("reason", "unknown"),
            )
            for item in unavailable
        )
        st.warning(
            "当前正在使用模拟数据源，真实数据源还没有成功启用。\n\n可能原因：\n{reasons}".format(
                reasons=reason_lines
            )
        )
        return

    st.warning("当前正在使用模拟数据源，单股诊断和自选池只对内置样本股有效。")


def _meta_block(title: str, meta: object) -> None:
    meta_dict = _normalize_meta(meta)

    if meta_dict is None:
        st.info("{title} 暂无可展示的来源信息。".format(title=title))
        return

    cache_text = "缓存" if meta_dict.get("from_cache") else "实时拉取"
    stale_text = "，已使用旧缓存兜底" if meta_dict.get("used_stale_cache") else ""
    age = meta_dict.get("cache_age_seconds")
    age_text = ""
    if age is not None:
        age_text = "，缓存年龄约 {age:.0f} 秒".format(age=age)

    st.markdown(
        """
        <div class="meta-card">
          <div class="meta-title">{title}</div>
          <div>来源：{source}</div>
          <div>解析链路：{resolved}</div>
          <div>模式：{cache_text}{stale_text}{age_text}</div>
        </div>
        """.format(
            title=title,
            source=meta_dict.get("source_provider"),
            resolved=meta_dict.get("resolved_provider"),
            cache_text=cache_text,
            stale_text=stale_text,
            age_text=age_text,
        ),
        unsafe_allow_html=True,
    )


def _normalize_meta(meta: object) -> dict | None:
    if meta is None:
        return None
    if isinstance(meta, dict):
        return meta
    if is_dataclass(meta):
        return asdict(meta)
    if hasattr(meta, "__dict__"):
        return dict(vars(meta))
    return None


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(25,117,210,0.15), transparent 32%),
                radial-gradient(circle at top right, rgba(255,179,71,0.14), transparent 28%),
                linear-gradient(180deg, #f5f7fb 0%, #eef2f8 100%);
            color: #18212f;
            font-family: "Segoe UI Variable", "Aptos", "Noto Sans SC", sans-serif;
        }
        .hero-panel {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            padding: 1.3rem 1.4rem;
            margin-bottom: 1rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #0b1f3a 0%, #153e75 60%, #225f9e 100%);
            color: #f7fbff;
            box-shadow: 0 18px 42px rgba(14, 32, 59, 0.18);
        }
        .hero-panel h1 {
            margin: 0.2rem 0 0.45rem 0;
            font-size: 2rem;
            line-height: 1.1;
        }
        .hero-panel p {
            margin: 0;
            max-width: 54rem;
            color: rgba(247,251,255,0.86);
        }
        .eyebrow {
            font-size: 0.82rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(247,251,255,0.72);
        }
        .hero-tag {
            align-self: center;
            padding: 0.8rem 1rem;
            border-radius: 18px;
            max-width: 18rem;
            background: rgba(255,255,255,0.14);
            color: #fff3d6;
            font-size: 0.95rem;
        }
        .meta-card, .strategy-card {
            padding: 0.9rem 1rem;
            border-radius: 18px;
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(16, 56, 108, 0.08);
            box-shadow: 0 8px 24px rgba(24, 33, 47, 0.06);
            margin-bottom: 0.8rem;
        }
        .meta-title {
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.88);
            border: 1px solid rgba(16, 56, 108, 0.08);
            padding: 0.9rem 1rem;
            border-radius: 18px;
            box-shadow: 0 10px 26px rgba(24, 33, 47, 0.05);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
