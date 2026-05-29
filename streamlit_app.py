from __future__ import annotations

import html
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime

sys.path.insert(0, os.path.abspath("src"))

import pandas as pd
import streamlit as st

from ashare_quant.config import get_settings
from ashare_quant.providers.factory import build_provider_bundle
from ashare_quant.services.market_service import MarketService
from ashare_quant.ui.dashboard_data import (
    bars_to_chart_data,
    build_rankings_table,
    diagnosis_to_dict,
    enrich_diagnosis_with_pi,
    fetch_diagnosis,
    fetch_diagnosis_bars,
    fetch_rankings,
    fetch_watchlist_rows,
    get_strategies,
    normalize_ui_strategy,
    parse_watchlist,
    provider_status,
    summarize_rankings,
)

DEFAULT_WATCHLIST = "600519,300750,000858,002594,688981"
RANKING_VIEW_LIMIT = 12
PLOT_HEIGHT_MAIN = 420
PLOT_HEIGHT_MINI = 120
APP_VERSION = "1.2.0"


try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False


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
    return fetch_rankings(_service, limit=limit, strategy=strategy)


@st.cache_data(ttl=30, show_spinner=False)
def load_diagnosis(_service: MarketService, symbol: str, strategy: str):
    return fetch_diagnosis(_service, symbol=symbol, strategy=strategy)


@st.cache_data(ttl=30, show_spinner=False)
def load_watchlist_rows(_service: MarketService, symbols: tuple[str, ...], strategy: str):
    return fetch_watchlist_rows(_service, list(symbols), strategy)


@st.cache_data(ttl=60, show_spinner=False)
def load_stock_bars(_service: MarketService, symbol: str):
    return fetch_diagnosis_bars(_service, symbol)


def main() -> None:
    st.set_page_config(
        page_title="A-QUANT 量化分析终端",
        page_icon=":material/monitoring:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_styles()

    settings, provider, service = bootstrap()
    strategies = get_strategies()
    strategy_map = {item["name"]: item for item in strategies}

    with st.sidebar:
        st.markdown(
            '<div class="sidebar-brand">A-QUANT</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="sidebar-sub">量化分析终端</div>', unsafe_allow_html=True
        )

        selected_view = st.radio(
            "视图",
            options=["个股诊断", "策略榜单", "自选池", "系统状态"],
            label_visibility="collapsed",
        )

        selected_name = st.selectbox(
            "策略",
            options=[item["name"] for item in strategies],
            index=0,
        )
        selected_strategy = normalize_ui_strategy(strategy_map[selected_name]["id"])

        stock_symbol = "600519"
        ranking_limit = 20
        watchlist_text = DEFAULT_WATCHLIST

        if selected_view == "个股诊断":
            stock_symbol = st.text_input("股票代码", value="600519").strip()
        elif selected_view == "策略榜单":
            ranking_limit = st.slider(
                "榜单数量", min_value=10, max_value=50, value=20, step=5
            )
        elif selected_view == "自选池":
            watchlist_text = st.text_area(
                "股票代码（逗号分隔）", value=DEFAULT_WATCHLIST, height=120
            )

        if st.button("刷新", use_container_width=True):
            st.cache_resource.clear()
            st.cache_data.clear()
            settings, provider, service = bootstrap()

        st.markdown(
            f'<div class="sidebar-version">v{APP_VERSION}</div>',
            unsafe_allow_html=True,
        )

    status = provider_status(provider, settings)
    _render_header(selected_view, selected_name, status)

    if selected_view == "个股诊断":
        _render_single_stock_view(
            service, stock_symbol or "600519", selected_strategy, status
        )
    elif selected_view == "策略榜单":
        _render_rankings_view(service, ranking_limit, selected_strategy, status)
    elif selected_view == "自选池":
        _render_watchlist_view(service, watchlist_text, selected_strategy, status)
    else:
        _render_system_view(status, strategies)


def _render_single_stock_view(
    service: MarketService, symbol: str, strategy: str, status: dict
) -> None:
    try:
        with st.spinner("正在诊断..."):
            diagnosis = load_diagnosis(service, symbol, strategy)
    except KeyError:
        _render_lookup_error(symbol, status)
        return
    except Exception as exc:
        _render_runtime_error("个股诊断", exc, status)
        return

    result = enrich_diagnosis_with_pi(diagnosis_to_dict(diagnosis))
    quote = result["quote"]
    factors = result["factors"]
    bars = load_stock_bars(service, symbol)

    pct_change = quote.get("pct_change", 0.0)
    tone = "up" if pct_change >= 0 else "down"

    # Hero card
    st.markdown(
        """
        <div class="hero-card">
          <div class="hero-top">
            <div>
              <div class="hero-kicker">个股诊断</div>
              <div class="hero-title">{name}</div>
              <div class="hero-sub">{symbol} <span>{sector}</span></div>
            </div>
            <div class="hero-price-block">
              <div class="hero-price">{price}</div>
              <div class="hero-change {tone}">{change}</div>
            </div>
          </div>
        </div>
        """.format(
            name=html.escape(quote.get("name") or symbol),
            symbol=html.escape(quote.get("symbol") or symbol),
            sector=html.escape(quote.get("sector") or "暂无板块"),
            price=f"{quote.get('latest_price', 0.0):.2f}",
            change=_display_pct(pct_change),
            tone=tone,
        ),
        unsafe_allow_html=True,
    )

    # Top metrics
    metric_cols = st.columns(5)
    _metric_card(metric_cols[0], "总分", f"{factors['total_score']:.1f}")
    _metric_card(
        metric_cols[1], "盈利指数 PI", f"{factors.get('profitability_index', 0):.1f}"
    )
    _metric_card(metric_cols[2], "可执行", "是" if factors["eligible"] else "否")
    _metric_card(metric_cols[3], "换手率", _display_pct(quote.get("turnover_rate", 0.0)))
    _metric_card(metric_cols[4], "量比", f"{quote.get('volume_ratio', 0.0):.2f}")

    left, right = st.columns([1.9, 1.1])
    with left:
        st.markdown(
            '<div class="section-label">近60日走势</div>', unsafe_allow_html=True
        )
        _render_price_panel(bars, symbol, compact=False)
    with right:
        _info_card("入场信号", factors["entry_signal"], tone="positive")
        _info_card("退出信号", factors["exit_signal"], tone="negative")
        _list_card("核心解释", factors["explanations"], "暂无强信号。")
        _list_card("未通过过滤", factors["failed_filters"], "全部通过。")
        _list_card("风险提示", factors["risk_flags"], "无额外风险。")

    # Factor detail metrics
    factor_cols = st.columns(5)
    _metric_card(factor_cols[0], "20日动量", f"{factors['momentum_20d']:.2f}")
    _metric_card(factor_cols[1], "趋势强度", f"{factors['trend_strength']:.2f}")
    _metric_card(factor_cols[2], "流动性", f"{factors['liquidity_score']:.2f}")
    _metric_card(factor_cols[3], "估值评分", f"{factors['valuation_score']:.2f}")
    _metric_card(factor_cols[4], "风险评分", f"{factors['risk_score']:.2f}")

    with st.expander("原始诊断数据", expanded=False):
        meta_cols = st.columns(2)
        with meta_cols[0]:
            if result["quote_meta"] is not None:
                _meta_block("行情数据源", result["quote_meta"])
        with meta_cols[1]:
            if result["bars_meta"] is not None:
                _meta_block("K线数据源", result["bars_meta"])
        st.json(result, expanded=False)


def _render_rankings_view(
    service: MarketService, limit: int, strategy: str, status: dict
) -> None:
    try:
        with st.spinner("正在加载榜单..."):
            rankings = load_rankings(service, limit, strategy)
    except Exception as exc:
        _render_runtime_error("策略榜单", exc, status)
        return

    summary = summarize_rankings(rankings)
    metric_cols = st.columns(4)
    _metric_card(metric_cols[0], "样本数", str(summary["total"]))
    _metric_card(metric_cols[1], "可执行数", str(summary["eligible_count"]))
    _metric_card(metric_cols[2], "均分", f"{summary['avg_score']:.2f}")
    _metric_card(metric_cols[3], "最高分", f"{summary['top_score']:.2f}")

    st.markdown(
        '<div class="section-label">精选标的卡片</div>', unsafe_allow_html=True
    )
    top_items = rankings.items[:RANKING_VIEW_LIMIT]
    for group_start in range(0, len(top_items), 3):
        cols = st.columns(3)
        for col, item in zip(cols, top_items[group_start : group_start + 3]):
            with col:
                _render_stock_card(
                    service=service,
                    symbol=item.quote.symbol,
                    name=item.quote.name,
                    sector=item.quote.sector or "-",
                    score=item.factors.total_score,
                    price=item.quote.latest_price,
                    pct_change=item.quote.pct_change,
                    eligible=item.factors.eligible,
                    subtitle=item.factors.entry_signal,
                )

    st.markdown(
        '<div class="section-label">完整排名表格</div>', unsafe_allow_html=True
    )
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
            "入场提示": st.column_config.TextColumn(width="large"),
        },
    )

    if rankings.universe_meta is not None:
        with st.expander("榜单数据源", expanded=False):
            _meta_block("全市场来源", rankings.universe_meta)


def _render_watchlist_view(
    service: MarketService, watchlist_text: str, strategy: str, status: dict
) -> None:
    symbols = parse_watchlist(watchlist_text)
    if not symbols:
        st.info("在左侧输入股票代码，以逗号分隔，即可查看自选池诊断。")
        return

    try:
        with st.spinner("正在加载自选池..."):
            rows = load_watchlist_rows(service, tuple(symbols), strategy)
    except Exception as exc:
        _render_runtime_error("自选池", exc, status)
        return

    top = st.columns(3)
    _metric_card(top[0], "股票数", str(len(symbols)))
    _metric_card(
        top[1],
        "可执行数",
        str(sum(1 for row in rows if _is_eligible_value(row.get("eligible")))),
    )
    _metric_card(
        top[2],
        "均分",
        f"{(sum(float(row.get('score', 0.0)) for row in rows) / len(rows)) if rows else 0.0:.2f}",
    )

    st.markdown(
        '<div class="section-label">自选池卡片</div>', unsafe_allow_html=True
    )
    for group_start in range(0, len(rows), 2):
        cols = st.columns(2)
        for col, row in zip(cols, rows[group_start : group_start + 2]):
            with col:
                _render_stock_card(
                    service=service,
                    symbol=str(row.get("symbol", "-")),
                    name=str(row.get("name", "-")),
                    sector="-",
                    score=float(row.get("score", 0.0))
                    if _is_number(row.get("score"))
                    else 0.0,
                    price=row.get("latest_price"),
                    pct_change=row.get("pct_change"),
                    eligible=_is_eligible_value(row.get("eligible")),
                    subtitle=str(row.get("entry_signal", "")),
                    error_text=str(row.get("failed_filters", ""))
                    if _is_not_found_value(row.get("name"))
                    else None,
                )

    st.markdown(
        '<div class="section-label">自选池表格</div>', unsafe_allow_html=True
    )
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
            "入场提示": st.column_config.TextColumn(width="large"),
        },
    )


def _render_system_view(status: dict, strategies: list[dict[str, str]]) -> None:
    top = st.columns(3)
    _metric_card(top[0], "配置数据源", str(status.get("configured_provider", "-")))
    _metric_card(
        top[1],
        "实际生效",
        str(status.get("active_provider_chain") or status.get("active_provider", "-")),
    )
    _metric_card(
        top[2],
        "持久缓存",
        "开启" if status.get("persistent_cache_enabled") else "关闭",
    )

    left, right = st.columns([1.1, 0.9])
    with left:
        st.markdown(
            '<div class="section-label">数据路由表</div>', unsafe_allow_html=True
        )
        routes = status.get("provider_routes") or {}
        st.dataframe(
            pd.DataFrame(
                [
                    {"模块": "榜单", "数据源": routes.get("ranking", "-")},
                    {"模块": "单股诊断", "数据源": routes.get("diagnosis", "-")},
                    {"模块": "自选池", "数据源": routes.get("watchlist", "-")},
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    with right:
        st.markdown(
            '<div class="section-label">策略列表</div>', unsafe_allow_html=True
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "策略": item.get("name", ""),
                        "说明": item.get("description", ""),
                    }
                    for item in strategies
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    diagnostics = status.get("provider_diagnostics")
    if diagnostics:
        with st.expander("Provider Diagnostics", expanded=False):
            st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)

    with st.expander("完整状态 JSON", expanded=False):
        st.json(status, expanded=False)


def _render_header(view: str, strategy_name: str, status: dict) -> None:
    provider_name = str(
        status.get("active_provider_chain") or status.get("active_provider") or "unknown"
    )
    live_state = "模拟" if "mock" in provider_name.lower() else "实盘"
    cache_state = "缓存开启" if status.get("persistent_cache_enabled") else "缓存关闭"
    rendered_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    st.markdown(
        """
        <div class="terminal-header">
          <div>
            <div class="terminal-kicker">A-QUANT 量化分析终端</div>
            <div class="terminal-title">{view}</div>
          </div>
          <div class="terminal-tags">
            <span>{strategy}</span>
            <span>{live_state}</span>
            <span>{cache_state}</span>
            <span>{rendered_at}</span>
          </div>
        </div>
        """.format(
            view=html.escape(view),
            strategy=html.escape(strategy_name),
            live_state=html.escape(live_state),
            cache_state=html.escape(cache_state),
            rendered_at=html.escape(rendered_at),
        ),
        unsafe_allow_html=True,
    )


def _render_stock_card(
    *,
    service: MarketService,
    symbol: str,
    name: str,
    sector: str,
    score: float,
    price: object,
    pct_change: object,
    eligible: bool,
    subtitle: str,
    error_text: str | None = None,
) -> None:
    tone = "up" if _as_float(pct_change) >= 0 else "down"
    status_text = "可执行" if eligible else "观望"
    st.markdown(
        """
        <div class="stock-card">
          <div class="stock-card-head">
            <div>
              <div class="stock-name">{name}</div>
              <div class="stock-meta">{symbol} · {sector}</div>
            </div>
            <div class="stock-badge {badge_tone}">{status}</div>
          </div>
          <div class="stock-grid">
            <div>
              <div class="small-label">最新价</div>
              <div class="small-value">{price}</div>
            </div>
            <div>
              <div class="small-label">涨跌幅</div>
              <div class="small-value {tone}">{change}</div>
            </div>
            <div>
              <div class="small-label">总分</div>
              <div class="small-value">{score}</div>
            </div>
          </div>
          <div class="stock-note">{subtitle}</div>
        </div>
        """.format(
            name=html.escape(name),
            symbol=html.escape(symbol),
            sector=html.escape(sector),
            status=html.escape(status_text),
            badge_tone="badge-up" if eligible else "badge-flat",
            price=html.escape(_display_price(price)),
            change=html.escape(_display_pct(pct_change)),
            score=f"{score:.1f}",
            subtitle=html.escape(error_text or subtitle or ""),
            tone=tone,
        ),
        unsafe_allow_html=True,
    )
    _render_price_panel(load_stock_bars(service, symbol), symbol, compact=True)


def _render_price_panel(bars: list, symbol: str, compact: bool) -> None:
    if not PLOTLY_AVAILABLE:
        st.info("Plotly 未安装，无法显示图表。请安装 plotly 以获得完整体验。")
        return

    data = bars_to_chart_data(bars)
    if not data:
        st.info(f"暂无 {symbol} 的历史数据。")
        return

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df["ma20"] = df["close"].rolling(20).mean()

    if compact:
        fig = go.Figure()
        line_color = (
            "#3fb950" if df["close"].iloc[-1] >= df["close"].iloc[0] else "#f85149"
        )
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["close"],
                mode="lines",
                line=dict(color=line_color, width=2),
                fill="tozeroy",
                fillcolor="rgba(63,185,80,0.08)"
                if line_color == "#3fb950"
                else "rgba(248,81,73,0.08)",
                hovertemplate="%{x|%Y-%m-%d}<br>收盘 %{y:.2f}<extra></extra>",
            )
        )
        fig.update_layout(
            height=PLOT_HEIGHT_MINI,
            margin=dict(l=8, r=8, t=6, b=6),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0d1117",
            font=dict(color="#b7c0cd", size=11),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
    else:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.72, 0.28],
        )
        fig.add_trace(
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="价格",
                increasing_line_color="#3fb950",
                decreasing_line_color="#f85149",
                increasing_fillcolor="#3fb950",
                decreasing_fillcolor="#f85149",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["ma20"],
                mode="lines",
                name="MA20",
                line=dict(color="#58a6ff", width=1.5),
            ),
            row=1,
            col=1,
        )

        # Volume bars
        colors = [
            "#3fb950" if df["close"].iloc[i] >= df["open"].iloc[i] else "#f85149"
            for i in range(len(df))
        ]
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["volume"],
                name="成交量",
                marker_color=colors,
                opacity=0.7,
            ),
            row=2,
            col=1,
        )

        fig.update_layout(
            height=PLOT_HEIGHT_MAIN,
            margin=dict(l=18, r=18, t=16, b=16),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0d1117",
            font=dict(color="#b7c0cd", size=11),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
            showlegend=False,
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.06)", row=1, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.06)", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _rankings_dataframe(rankings) -> pd.DataFrame:
    table = pd.DataFrame(build_rankings_table(rankings))
    if table.empty:
        return table
    table = table.rename(
        columns={
            "rank": "排名",
            "symbol": "代码",
            "name": "名称",
            "sector": "板块",
            "score": "总分",
            "eligible": "可执行",
            "pct_change": "涨跌幅",
            "entry_signal": "入场提示",
            "risk_flags": "风险标记",
        }
    )
    return table


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
            "failed_filters": "失败过滤",
        }
    )
    if "最新价" in table.columns:
        table["最新价"] = table["最新价"].map(_display_price)
    if "涨跌幅" in table.columns:
        table["涨跌幅"] = table["涨跌幅"].map(_display_pct)
    if "名称" in table.columns:
        table["名称"] = table["名称"].replace({"未找到": "未找到"})
    return table


def _metric_card(container, label: str, value: str) -> None:
    container.markdown(
        """
        <div class="metric-shell">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
        </div>
        """.format(label=html.escape(label), value=html.escape(value)),
        unsafe_allow_html=True,
    )


def _info_card(title: str, body: str, tone: str) -> None:
    st.markdown(
        """
        <div class="info-card {tone}">
          <div class="info-title">{title}</div>
          <div class="info-body">{body}</div>
        </div>
        """.format(
            title=html.escape(title),
            body=html.escape(body),
            tone=html.escape(tone),
        ),
        unsafe_allow_html=True,
    )


def _list_card(title: str, values: list[str], empty_text: str) -> None:
    items = values or [empty_text]
    rendered_items = "".join(f"<li>{html.escape(str(item))}</li>" for item in items[:5])
    st.markdown(
        """
        <div class="list-card">
          <div class="info-title">{title}</div>
          <ul>{items}</ul>
        </div>
        """.format(title=html.escape(title), items=rendered_items),
        unsafe_allow_html=True,
    )


def _render_lookup_error(symbol: str, status: dict) -> None:
    active_provider = str(status.get("active_provider") or "unknown")
    if "mock" in active_provider.lower():
        st.error(f"当前模拟数据源中找不到 `{symbol}`。")
        st.info("如需诊断任意股票，请切换到真实数据源。")
    else:
        st.error(f"无法从当前数据源解析股票代码 `{symbol}`。")
        st.info("请检查代码格式是否正确，或查看系统状态确认数据源配置。")


def _render_runtime_error(module_name: str, exc: Exception, status: dict) -> None:
    st.error(f"{module_name} 加载失败。")
    st.code(str(exc) or exc.__class__.__name__)
    routes = status.get("provider_routes")
    if routes:
        st.info(
            "榜单: {ranking} | 诊断: {diagnosis} | 自选: {watchlist}".format(
                ranking=routes.get("ranking", "-"),
                diagnosis=routes.get("diagnosis", "-"),
                watchlist=routes.get("watchlist", "-"),
            )
        )


def _meta_block(title: str, meta: object) -> None:
    meta_dict = _normalize_meta(meta)
    if meta_dict is None:
        st.info(f"{title} 暂无元数据。")
        return

    cache_text = "缓存" if meta_dict.get("from_cache") else "实时"
    if meta_dict.get("used_stale_cache"):
        cache_text += " / 过期"
    age = meta_dict.get("cache_age_seconds")
    age_text = f" / {age:.0f}秒" if age is not None else ""

    st.markdown(
        """
        <div class="meta-card">
          <div class="meta-title">{title}</div>
          <div>来源: {source}</div>
          <div>解析: {resolved}</div>
          <div>模式: {cache_text}{age_text}</div>
        </div>
        """.format(
            title=html.escape(title),
            source=html.escape(str(meta_dict.get("source_provider", "-"))),
            resolved=html.escape(str(meta_dict.get("resolved_provider", "-"))),
            cache_text=html.escape(cache_text),
            age_text=html.escape(age_text),
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


def _display_price(value: object) -> str:
    number = _as_float(value)
    if number is None:
        return str(value)
    return f"{number:.2f}"


def _display_pct(value: object) -> str:
    number = _as_float(value)
    if number is None:
        return str(value)
    return f"{number:.2f}%"


def _as_float(value: object) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return float(str(value))
    except Exception:
        return None


def _is_number(value: object) -> bool:
    return _as_float(value) is not None


def _is_eligible_value(value: object) -> bool:
    return str(value).strip().upper() in {"YES", "TRUE", "1", "是"}


def _is_not_found_value(value: object) -> bool:
    return str(value).strip().lower() in {"not found", "未找到"}


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bg: #0d1117;
            --panel: #161b22;
            --panel-2: #1c2128;
            --line: #21262d;
            --text: #e6edf3;
            --muted: #8b949e;
            --green: #3fb950;
            --red: #f85149;
            --blue: #58a6ff;
            --amber: #d29922;
        }

        .stApp {
            background: #0d1117;
            color: var(--text);
            font-family: "Inter", "Segoe UI", system-ui, sans-serif;
        }

        .block-container {
            max-width: 1380px;
            padding-top: 1.2rem;
            padding-bottom: 2.5rem;
        }

        section[data-testid="stSidebar"] {
            background: #0d1117;
            border-right: 1px solid var(--line);
        }
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 1.2rem;
        }
        .sidebar-brand {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text);
            letter-spacing: 0.06em;
        }
        .sidebar-sub {
            color: var(--muted);
            font-size: 0.78rem;
            margin-bottom: 1.2rem;
            margin-top: 0.15rem;
        }
        .sidebar-version {
            position: fixed;
            bottom: 1rem;
            color: var(--muted);
            font-size: 0.72rem;
            opacity: 0.7;
        }

        .terminal-header,
        .hero-card,
        .metric-shell,
        .stock-card,
        .meta-card,
        .info-card,
        .list-card {
            background: var(--panel);
            border: 1px solid var(--line);
        }

        .terminal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            padding: 1rem 1.15rem;
            border-radius: 12px;
            margin-bottom: 1rem;
        }
        .terminal-kicker {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.7rem;
        }
        .terminal-title {
            color: var(--text);
            font-size: 1.5rem;
            font-weight: 700;
            margin-top: 0.15rem;
        }
        .terminal-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            justify-content: flex-end;
        }
        .terminal-tags span {
            padding: 0.35rem 0.65rem;
            border-radius: 6px;
            border: 1px solid var(--line);
            background: #0d1117;
            color: var(--muted);
            font-size: 0.74rem;
            font-weight: 600;
        }

        .hero-card {
            border-radius: 12px;
            padding: 1.2rem 1.2rem 1rem;
            margin-bottom: 0.9rem;
        }
        .hero-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
        }
        .hero-kicker {
            color: var(--muted);
            font-size: 0.72rem;
            letter-spacing: 0.10em;
            text-transform: uppercase;
        }
        .hero-title {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--text);
            margin-top: 0.18rem;
        }
        .hero-sub {
            color: var(--muted);
            font-size: 0.92rem;
            margin-top: 0.22rem;
        }
        .hero-sub span {
            color: var(--blue);
        }
        .hero-price-block {
            text-align: right;
        }
        .hero-price {
            color: var(--text);
            font-size: 1.9rem;
            font-weight: 700;
        }
        .hero-change {
            margin-top: 0.2rem;
            font-size: 0.95rem;
            font-weight: 600;
        }

        .section-label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.72rem;
            font-weight: 700;
            margin: 0.75rem 0 0.55rem;
        }

        .metric-shell {
            border-radius: 10px;
            padding: 0.85rem 1rem;
            min-height: 88px;
            margin-bottom: 0.8rem;
        }
        .metric-label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.7rem;
            font-weight: 700;
        }
        .metric-value {
            color: var(--text);
            font-size: 1.35rem;
            font-weight: 700;
            margin-top: 0.3rem;
        }

        .stock-card {
            border-radius: 10px;
            padding: 0.95rem;
            margin-bottom: 0.5rem;
        }
        .stock-card-head {
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
        }
        .stock-name {
            color: var(--text);
            font-size: 1rem;
            font-weight: 700;
        }
        .stock-meta {
            color: var(--muted);
            font-size: 0.82rem;
            margin-top: 0.18rem;
        }
        .stock-badge {
            border-radius: 6px;
            padding: 0.25rem 0.55rem;
            border: 1px solid var(--line);
            font-size: 0.72rem;
            font-weight: 700;
            height: fit-content;
        }
        .badge-up {
            color: var(--green);
            background: rgba(63,185,80,0.10);
            border-color: rgba(63,185,80,0.25);
        }
        .badge-flat {
            color: var(--amber);
            background: rgba(210,153,34,0.10);
            border-color: rgba(210,153,34,0.25);
        }
        .stock-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
            margin-top: 0.85rem;
        }
        .small-label {
            color: var(--muted);
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            font-weight: 700;
        }
        .small-value {
            color: var(--text);
            font-size: 0.98rem;
            font-weight: 600;
            margin-top: 0.18rem;
        }
        .stock-note {
            color: #b0b8c1;
            font-size: 0.82rem;
            margin-top: 0.75rem;
            line-height: 1.4;
        }

        .info-card,
        .list-card,
        .meta-card {
            border-radius: 10px;
            padding: 0.85rem 1rem;
            margin-bottom: 0.6rem;
        }
        .info-card.positive {
            border-left: 3px solid var(--green);
        }
        .info-card.negative {
            border-left: 3px solid var(--red);
        }
        .info-title,
        .meta-title {
            color: var(--muted);
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }
        .info-body,
        .meta-card div {
            color: var(--text);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .list-card ul {
            margin: 0;
            padding-left: 1rem;
        }
        .list-card li {
            color: #b0b8c1;
            font-size: 0.86rem;
            margin-bottom: 0.2rem;
        }

        .up {
            color: var(--green) !important;
        }
        .down {
            color: var(--red) !important;
        }

        .stAlert,
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--line) !important;
            border-radius: 10px !important;
            background: var(--panel) !important;
        }
        div[data-testid="stDataFrame"] th {
            background: #0d1117 !important;
            color: var(--muted) !important;
            text-transform: uppercase;
            font-size: 0.7rem !important;
            font-weight: 700 !important;
        }
        div[data-testid="stDataFrame"] td {
            color: var(--text) !important;
        }
        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox div[data-baseweb="select"] > div,
        .stSlider,
        .stRadio {
            color: var(--text) !important;
        }
        .stTextInput input,
        .stTextArea textarea {
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
        }
        .stButton button {
            background: var(--blue);
            border: none;
            color: #ffffff;
            border-radius: 8px;
            font-weight: 700;
        }
        .stButton button:hover {
            background: #4f9eff;
        }
        details {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 10px;
        }
        @media (max-width: 900px) {
            .terminal-header,
            .hero-top {
                flex-direction: column;
                align-items: flex-start;
            }
            .terminal-tags {
                justify-content: flex-start;
            }
            .hero-price-block {
                text-align: left;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
