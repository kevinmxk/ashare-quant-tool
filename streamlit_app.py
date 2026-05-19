from __future__ import annotations

import json
import os
import sys
import html
from dataclasses import asdict, is_dataclass
from datetime import datetime

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
        st.markdown("## 量化工作台")
        selected_view = st.radio(
            "视图",
            options=["单股诊断", "策略榜单", "自选池", "系统状态"],
            index=0,
        )
        selected_name = st.radio(
            "策略",
            options=[item["name"] for item in strategies],
            index=0,
        )
        selected_strategy = normalize_ui_strategy(strategy_map[selected_name]["id"])
        st.caption(strategy_map[selected_name]["description"])
        st.divider()

        if selected_view == "策略榜单":
            ranking_limit = st.slider("榜单数量", min_value=10, max_value=50, value=20, step=5)
            watchlist_text = DEFAULT_WATCHLIST
            stock_symbol = "600519"
        elif selected_view == "自选池":
            ranking_limit = 20
            watchlist_text = st.text_area("股票代码", value=DEFAULT_WATCHLIST, height=116)
            stock_symbol = "600519"
        elif selected_view == "单股诊断":
            ranking_limit = 20
            watchlist_text = DEFAULT_WATCHLIST
            stock_symbol = st.text_input("股票代码", value="600519")
        else:
            ranking_limit = 20
            watchlist_text = DEFAULT_WATCHLIST
            stock_symbol = "600519"

        refresh = st.button("刷新数据", use_container_width=True)
        if refresh:
            st.cache_resource.clear()
            st.cache_data.clear()
            settings, provider, service = bootstrap()

    status = provider_status(provider, settings)
    _render_workspace_header(selected_view, selected_name, status)
    _render_provider_banner(status)

    if selected_view == "策略榜单":
        try:
            with st.spinner("正在加载策略榜单..."):
                rankings = load_rankings(service, ranking_limit, selected_strategy)
        except Exception as exc:
            _render_runtime_error("策略榜单", exc, status)
            return
        summary = summarize_rankings(rankings)
        metric_cols = st.columns(4)
        metric_cols[0].metric("样本数", summary["total"])
        metric_cols[1].metric("可执行", summary["eligible_count"])
        metric_cols[2].metric("平均分", summary["avg_score"])
        metric_cols[3].metric("最高分", summary["top_score"])
        st.markdown("### 策略榜单")
        st.dataframe(
            _rankings_dataframe(rankings),
            use_container_width=True,
            hide_index=True,
            column_config={
                "排名": st.column_config.NumberColumn(width="small"),
                "代码": st.column_config.TextColumn(width="small"),
                "名称": st.column_config.TextColumn(width="medium"),
                "板块": st.column_config.TextColumn(width="medium"),
                "总分": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                "涨跌幅": st.column_config.NumberColumn(format="%.2f%%", width="small"),
                "可执行": st.column_config.TextColumn(width="small"),
            },
        )

        if rankings.universe_meta is not None:
            with st.expander("数据来源", expanded=False):
                _meta_block("榜单数据来源", rankings.universe_meta)
    elif selected_view == "单股诊断":
        st.markdown("### 单股诊断")
        try:
            with st.spinner("正在加载单股诊断..."):
                diagnosis = load_diagnosis(service, stock_symbol, selected_strategy)
        except KeyError:
            _render_lookup_error(stock_symbol, status)
        except Exception as exc:
            _render_runtime_error("单股诊断", exc, status)
        else:
            _render_diagnosis(diagnosis_to_dict(diagnosis))
    elif selected_view == "自选池":
        st.markdown("### 自选池观察")
        watchlist = parse_watchlist(watchlist_text)
        if watchlist:
            try:
                with st.spinner("正在加载自选池..."):
                    rows = load_watchlist_rows(service, tuple(watchlist), selected_strategy)
            except Exception as exc:
                _render_runtime_error("自选池", exc, status)
            else:
                st.dataframe(
                    _watchlist_dataframe(rows),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "代码": st.column_config.TextColumn(width="small"),
                        "名称": st.column_config.TextColumn(width="medium"),
                        "总分": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                        "最新价": st.column_config.TextColumn(width="small"),
                        "涨跌幅": st.column_config.TextColumn(width="small"),
                        "可执行": st.column_config.TextColumn(width="small"),
                    },
                )
        else:
            st.info("在左侧输入一组股票代码后，这里会显示自选池诊断结果。")
    else:
        st.markdown("### 系统状态")
        _render_system_status(status, strategies)


def _render_workspace_header(view: str, strategy_name: str, status: dict) -> None:
    provider_name = str(status.get("active_provider_chain") or status.get("active_provider") or "unknown")
    health = "模拟数据" if "mock" in provider_name.lower() else "实时数据"
    cache_label = "缓存开" if status.get("persistent_cache_enabled") else "缓存关"
    rendered_at = datetime.now().strftime("%H:%M")
    st.markdown(
        """
        <div class="workspace-header">
          <div>
            <div class="page-kicker">{view}</div>
            <h1>A 股量化分析台</h1>
          </div>
          <div class="status-strip">
            <span>{strategy}</span>
            <span>{health}</span>
            <span>{cache}</span>
            <span>{time}</span>
          </div>
        </div>
        """.format(
            view=html.escape(view),
            strategy=html.escape(strategy_name),
            health=health,
            cache=cache_label,
            time=rendered_at,
        ),
        unsafe_allow_html=True,
    )


def _rankings_dataframe(rankings) -> pd.DataFrame:
    table = pd.DataFrame(build_rankings_table(rankings))
    if table.empty:
        return table
    return table.rename(
        columns={
            "rank": "排名",
            "symbol": "代码",
            "name": "名称",
            "sector": "板块",
            "score": "总分",
            "eligible": "可执行",
            "pct_change": "涨跌幅",
            "entry_signal": "入场提示",
            "risk_flags": "风险",
        }
    )


def _watchlist_dataframe(rows: list[dict]) -> pd.DataFrame:
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table = table.rename(
        columns={
            "symbol": "代码",
            "name": "名称",
            "score": "总分",
            "eligible": "可执行",
            "latest_price": "最新价",
            "pct_change": "涨跌幅",
            "entry_signal": "入场提示",
            "failed_filters": "未通过过滤",
        }
    )
    if "最新价" in table.columns:
        table["最新价"] = table["最新价"].map(_display_price)
    if "涨跌幅" in table.columns:
        table["涨跌幅"] = table["涨跌幅"].map(_display_pct)
    return table


def _display_price(value: object) -> str:
    if isinstance(value, float):
        return "{value:.2f}".format(value=value)
    return str(value)


def _display_pct(value: object) -> str:
    if isinstance(value, float):
        return "{value:.2f}%".format(value=value)
    return str(value)


def _signal_card(title: str, body: str, tone: str) -> None:
    st.markdown(
        """
        <div class="signal-card {tone}">
          <div class="signal-title">{title}</div>
          <div class="signal-body">{body}</div>
        </div>
        """.format(
            title=html.escape(title),
            body=html.escape(body),
            tone=tone,
        ),
        unsafe_allow_html=True,
    )


def _compact_list(title: str, values: list[str], empty_text: str) -> None:
    items = values or [empty_text]
    rendered_items = "".join(
        "<li>{item}</li>".format(item=html.escape(str(item))) for item in items[:4]
    )
    st.markdown(
        """
        <div class="compact-block">
          <div class="compact-title">{title}</div>
          <ul>{items}</ul>
        </div>
        """.format(title=html.escape(title), items=rendered_items),
        unsafe_allow_html=True,
    )


def _render_system_status(status: dict, strategies: list[dict[str, str]]) -> None:
    routes = status.get("provider_routes") or {}
    route_rows = [
        {"模块": "榜单", "数据源": routes.get("ranking", "-")},
        {"模块": "单股诊断", "数据源": routes.get("diagnosis", "-")},
        {"模块": "自选池", "数据源": routes.get("watchlist", "-")},
    ]

    top_cols = st.columns(3)
    top_cols[0].metric("配置数据源", status.get("configured_provider", "-"))
    top_cols[1].metric("实际数据源", status.get("active_provider_chain") or status.get("active_provider", "-"))
    top_cols[2].metric("持久缓存", "开启" if status.get("persistent_cache_enabled") else "关闭")

    left, right = st.columns([1.05, 1])
    with left:
        st.markdown("#### 数据路由")
        st.dataframe(pd.DataFrame(route_rows), use_container_width=True, hide_index=True)
    with right:
        st.markdown("#### 策略")
        st.dataframe(
            pd.DataFrame(
                [
                    {"策略": item.get("name"), "说明": item.get("description") or ""}
                    for item in strategies
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    diagnostics = status.get("provider_diagnostics")
    if diagnostics:
        with st.expander("Provider diagnostics", expanded=False):
            st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)

    with st.expander("完整状态 JSON", expanded=False):
        st.json(status, expanded=False)


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
        _signal_card("入场", factors["entry_signal"], "positive")
        _signal_card("退出", factors["exit_signal"], "warning")

    with top_right:
        _compact_list("核心解释", factors["explanations"], "当前没有明显加分项。")
        _compact_list("未通过过滤", factors["failed_filters"], "已通过该策略的硬过滤。")
        _compact_list("风险提示", factors["risk_flags"], "当前没有额外风险警示。")

    detail_cols = st.columns(5)
    detail_cols[0].metric("20日动量", "{value:.2f}".format(value=factors["momentum_20d"]))
    detail_cols[1].metric("趋势强度", "{value:.2f}".format(value=factors["trend_strength"]))
    detail_cols[2].metric("流动性", "{value:.2f}".format(value=factors["liquidity_score"]))
    detail_cols[3].metric("估值评分", "{value:.2f}".format(value=factors["valuation_score"]))
    detail_cols[4].metric("风险评分", "{value:.2f}".format(value=factors["risk_score"]))

    with st.expander("数据来源与原始诊断", expanded=False):
        meta_cols = st.columns(2)
        with meta_cols[0]:
            if result["quote_meta"] is not None:
                _meta_block("报价来源", result["quote_meta"])
        with meta_cols[1]:
            if result["bars_meta"] is not None:
                _meta_block("日线来源", result["bars_meta"])
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


def _render_runtime_error(module_name: str, exc: Exception, status: dict) -> None:
    st.error("{module} 当前加载失败。".format(module=module_name))
    st.code(str(exc) or exc.__class__.__name__)
    st.info("建议先查看“系统状态”页里的数据源路由和 provider_diagnostics，确认当前主源和回退源是否都可用。")

    routes = status.get("provider_routes")
    if routes:
        st.markdown(
            """
            <div class="meta-card">
              <div class="meta-title">当前路由</div>
              <div>榜单：{ranking}</div>
              <div>单股诊断：{diagnosis}</div>
              <div>自选池：{watchlist}</div>
            </div>
            """.format(
                ranking=routes.get("ranking"),
                diagnosis=routes.get("diagnosis"),
                watchlist=routes.get("watchlist"),
            ),
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
            background: #f4f6f8;
            color: #172033;
            font-family: "Segoe UI Variable", "Aptos", "Noto Sans SC", sans-serif;
        }
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2rem;
            max-width: 1280px;
        }
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #dfe5ec;
        }
        section[data-testid="stSidebar"] h2 {
            margin-bottom: 0.25rem;
            font-size: 1.25rem;
        }
        .workspace-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.25rem;
            padding: 0.8rem 1rem;
            margin-bottom: 0.8rem;
            border: 1px solid #dce3ea;
            border-left: 4px solid #2f6f7e;
            border-radius: 8px;
            background: #ffffff;
        }
        .workspace-header h1 {
            margin: 0.1rem 0 0;
            font-size: 1.35rem;
            line-height: 1.1;
            font-weight: 750;
            letter-spacing: 0;
        }
        .page-kicker {
            color: #5a6678;
            font-size: 0.82rem;
            font-weight: 650;
        }
        .status-strip {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 0.45rem;
        }
        .status-strip span {
            padding: 0.28rem 0.5rem;
            border-radius: 999px;
            background: #eef3f5;
            color: #314052;
            border: 1px solid #dce5e8;
            font-size: 0.78rem;
            font-weight: 650;
            white-space: nowrap;
        }
        .meta-card {
            padding: 0.75rem 0.85rem;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid #dfe5ec;
            margin-bottom: 0.65rem;
            color: #314052;
        }
        .meta-title {
            font-weight: 700;
            margin-bottom: 0.35rem;
            color: #172033;
        }
        .signal-card {
            padding: 0.85rem 0.95rem;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid #dfe5ec;
            margin-bottom: 0.7rem;
        }
        .signal-card.positive {
            border-left: 4px solid #25746b;
        }
        .signal-card.warning {
            border-left: 4px solid #b26d1b;
        }
        .signal-title, .compact-title {
            margin-bottom: 0.35rem;
            color: #5a6678;
            font-size: 0.82rem;
            font-weight: 700;
        }
        .signal-body {
            color: #172033;
            font-size: 1rem;
            font-weight: 650;
            line-height: 1.45;
        }
        .compact-block {
            padding: 0.72rem 0.85rem;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid #dfe5ec;
            margin-bottom: 0.65rem;
        }
        .compact-block ul {
            margin: 0;
            padding-left: 1.1rem;
        }
        .compact-block li {
            margin: 0.15rem 0;
            color: #263548;
            line-height: 1.38;
        }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #dfe5ec;
            padding: 0.75rem 0.85rem;
            border-radius: 8px;
            box-shadow: none;
        }
        [data-testid="stMetricLabel"] {
            color: #687385;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #dfe5ec;
            border-radius: 8px;
            overflow: hidden;
            background: #ffffff;
        }
        button[kind="secondary"], .stButton button {
            border-radius: 8px;
        }
        @media (max-width: 760px) {
            .workspace-header {
                align-items: flex-start;
                flex-direction: column;
            }
            .status-strip {
                justify-content: flex-start;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
