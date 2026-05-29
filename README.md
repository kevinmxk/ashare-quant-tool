# A股量化分析工具 V2

一个面向个人研究场景的 A 股股票数据量化分析工具，采用**双数据源智能路由**架构，兼顾速度与准确性。

## 核心特性

- **双源并用**：实时行情走 EastMoney 直调（0.07s），历史日线走 BaoStock（数据准、带复权）
- **智能路由**：实时类数据（行情快照/榜单）→ EastMoney HTTP，历史类数据（K线/因子计算）→ BaoStock，失败时自动回退
- **冷热缓存分离**：Streamlit 内存缓存（30s 快速响应）+ SQLite 持久缓存（快照 15min / 日线 12h）
- **冷缓存后台刷新**：首次加载先用 EastMoney 快速渲染，后台静默用 BaoStock 精准刷新并落盘
- **并发加载**：自选池/榜单使用多线程并发拉取，冷缓存 5 只自选股 < 0.4s
- **多源回退**：`EastMoney → Sina → AKShare → BaoStock → Mock` 逐级降级，一个挂了自动切下一个
- **美观前端**：深色金融风格（TradingView 配色），Plotly K线图，卡片化布局

## 当前目录结构

```text
.
├── .env                          # 配置文件（数据源路由、Token、缓存TTL）
├── streamlit_app.py              # Streamlit 前端（深色金融风格）
├── scripts/
│   ├── demo_run.py               # 演示脚本
│   ├── cache_smoke_test.py       # 缓存测试
│   ├── ui_data_smoke_test.py     # 前端数据烟雾测试
│   └── ...
├── src/ashare_quant/
│   ├── config.py                 # 配置管理（自动加载 .env）
│   ├── models.py                 # 数据模型（QuoteSnapshot, FactorSet, DailyBar 等）
│   ├── cache/
│   │   ├── sqlite_cache.py       # SQLite 持久缓存（WAL 模式，支持并发读写）
│   │   └── provider_cache.py     # 缓存 Provider 封装（过期缓存先返回 + 后台刷新）
│   ├── providers/
│   │   ├── base.py               # MarketDataProvider 接口定义
│   │   ├── eastmoney_provider.py # 🆕 东方财富直调（HTTP，0.07s，不依赖 AKShare）
│   │   ├── baostock_provider.py  # 🆕 BaoStock 数据源（日线精准，带 RLock 并发保护）
│   │   ├── routing_provider.py   # 🆕 双数据源路由（get_quote→东财，get_daily_bars→BaoStock）
│   │   ├── sina_provider.py      # 新浪财经（通过 AKShare）
│   │   ├── akshare_provider.py   # AKShare 数据源
│   │   ├── tushare_provider.py   # Tushare 数据源
│   │   ├── mock_provider.py      # 模拟数据（离线兜底）
│   │   ├── composite_provider.py # 多源组合/失败冷却
│   │   └── factory.py            # Provider 工厂（dual 模式路由控制）
│   ├── services/
│   │   └── market_service.py     # 核心业务层（并发榜单、自选池诊断）
│   ├── ui/
│   │   └── dashboard_data.py     # UI 数据转换（并发自选池加载）
│   └── analysis/
│       └── scoring.py            # 因子计算与评分
└── data/cache/
    └── market_cache.sqlite3      # SQLite 持久缓存文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
# 建议额外安装：
pip install plotly streamlit  # 前端 + K线图
```

### 2. 配置数据源

复制 `.env.example` 为 `.env`，根据需要修改：

```ini
# 数据源模式：dual = 双源路由（推荐），auto = 自动回退
ASHARE_QUANT_PROVIDER=dual

# 个股诊断数据源（建议用 baostock，无需 Token）
ASHARE_QUANT_DIAGNOSIS_PROVIDER=dual

# 设置缓存 TTL（秒），默认 120s
ASHARE_QUANT_PROVIDER_CACHE_TTL_SECONDS=120

# Tushare Token（如需要）
# ASHARE_QUANT_TUSHARE_TOKEN=your_token_here
```

### 3. 启动前端

```bash
streamlit run streamlit_app.py
```

浏览器访问 `http://localhost:8501`

### 4. 运行测试

```bash
python scripts/ui_data_smoke_test.py     # 数据链路测试
python -m unittest discover -s tests     # 单元测试
```

## 数据源架构

### 当前路由策略（dual 模式）

```
实时（get_quote / list_universe）
  → EastMoney (HTTP 0.07s) → Sina → AKShare → Mock

历史（get_daily_bars / K 线）
  → BaoStock (0.5s, 数据准) → EastMoney → Sina → AKShare → Mock
```

### 可用数据源对比

| 数据源 | 速度 | 实时性 | 数据质量 | 用途 |
|--------|------|--------|---------|------|
| **EastMoney 直调** | **0.07s** ⚡ | 准实时 | 标准 | 实时行情、榜单、快照 |
| **BaoStock** | 0.5s | 盘后（T+1） | ⭐⭐⭐⭐⭐ 交易所级 | 历史日线、K线图、因子计算 |
| **Sina/AKShare** | 0.1~1s | 准实时 | ⭐⭐⭐ | 降级回退 |
| **Mock** | 即时 | — | 模拟数据 | 离线开发兜底 |

### 缓存策略

| 缓存层 | 有效期 | 说明 |
|--------|--------|------|
| Streamlit `@st.cache_data` | 30s | 内存级，同一用户会话内避免重复调用 |
| SQLite 行情快照 | 15min | 持久化到磁盘 |
| SQLite 日线数据 | 12h | 持久化到磁盘 |
| Provider 内存日线缓存 | 5min | BaoStock 进程内缓存 |
| **后台刷新** | — | 缓存过期时先返回旧数据，后台静默拉取新数据 |

> **SQLite 缓存持久在磁盘**，重启电脑后缓存仍在，没过期就不调 API。

## 前端功能

- **个股诊断**：搜索股票 → 总分/当前价/涨跌幅/可执行 + 入场退出信号 + 5 因子详情 + Plotly K线图
- **策略榜单**：选策略 → 统计概览 + 排名表格（代码/名称/总分/涨跌幅/板块）
- **自选池**：输入代码（逗号分隔）→ 多只股票并发对比诊断
- **系统状态**：数据源路由、Provider 健康检查、缓存统计

## 可用策略

| 策略 | 说明 |
|------|------|
| `trend` | 趋势突破，偏强势股跟随 |
| `pullback` | 回调低吸，偏强趋势中的回撤观察 |
| `value` | 价值稳健，偏低估值和低波动筛选 |

每套策略输出：
- `total_score`：总分（0~100）
- `eligible`：是否通过硬过滤
- `entry_signal` / `exit_signal`：入场/退出信号
- `failed_filters` / `risk_flags`：未通过项和风险提示

## 配置说明

环境变量全部通过 `.env` 文件配置，参见 `.env.example`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ASHARE_QUANT_PROVIDER` | `dual` | 数据源模式：dual / auto / mock |
| `ASHARE_QUANT_RANKING_LIMIT` | `20` | 榜单默认数量 |
| `ASHARE_QUANT_PROVIDER_CACHE_TTL_SECONDS` | `120` | Provider 缓存 TTL |
| `ASHARE_QUANT_USE_MOCK_WHEN_PROVIDER_FAILS` | `true` | 失败时自动 Mock 兜底 |
| `ASHARE_QUANT_PERSISTENT_CACHE_ENABLED` | `true` | 启用 SQLite 持久缓存 |
| `ASHARE_QUANT_PERSISTENT_QUOTE_TTL_SECONDS` | `900` | 快照缓存有效期（秒） |
| `ASHARE_QUANT_PERSISTENT_BAR_TTL_SECONDS` | `43200` | 日线缓存有效期（秒） |
| `ASHARE_QUANT_TUSHARE_TOKEN` | — | Tushare Token（如需） |

## 兼容性

- 股票代码支持 `000001`、`sz000001`、`SH600519`、`600519` 等常见格式
- 跨数据源代码/日期清洗统一收敛在 `shared_cleaner.py`
- AKShare 列名清洗收敛在 `akshare_cleaner.py`

## V1 → V2 主要更新

- 🆕 新增 EastMoney 直调 Provider（HTTP 直连，不依赖 AKShare，0.07s）
- 🆕 新增 OperationRouting 双源路由（实时→东财，历史→BaoStock）
- 🆕 自选池/榜单并发加载（8 线程并行，0.4s 内返回）
- 🆕 冷缓存后台刷新（首屏 EastMoney 快速渲染，后台 BaoStock 精准刷新）
- 🆕 SQLite WAL 模式（并发读写不锁表）
- 🆕 Provider 失败冷却（坏源短时间自动跳过）
- 🆕 BaoStock 线程锁 + 内存缓存（防止并发卡死）
- 🆕 深色金融风格前端（TradingView 配色，Plotly K 线图）
- 🆕 北交所 920 号段识别

## 下一步计划

- 增加行业/板块/资金流因子
- 增加回测模块
- 增加更多技术指标可视化
