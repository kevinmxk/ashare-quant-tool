# A股量化分析工具 V2（前后端分离）

一个面向个人研究场景的 A 股股票数据量化分析工具，采用**双数据源智能路由**架构，兼顾速度与准确性。支持 **FastAPI + Vue 3 前后端分离** 和 **Streamlit 一体化** 两种模式。

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Vue 3 + TypeScript + Vite | Composition API，响应式布局 |
| **UI 框架** | Tailwind CSS v4 | 深色金融风格（TradingView 配色） |
| **图表** | ECharts | K 线图 + 成交量 + MA20 |
| **后端** | FastAPI + uvicorn | RESTful API，端口 8000 |
| **数据采集** | EastMoney HTTP + BaoStock SDK | 双源智能路由 |
| **缓存** | SQLite（持久）+ 内存 TTL | 冷热缓存分离，后台刷新 |
| **备选前端** | Streamlit | 纯 Python 一体化方案（保留） |

---

## 核心特性

### 数据源
- **双源并用**：实时行情走 EastMoney 直调（0.07s），历史日线走 BaoStock（数据准、带复权）
- **智能路由**：实时类数据 → EastMoney HTTP，历史类数据 → BaoStock，失败时自动回退
- **多源回退链**：`EastMoney → Sina → AKShare → BaoStock → Mock`
- **失败冷却**：坏源短时间自动跳过，不反复重试

### 性能
- **冷缓存自选池 5 只**：< 0.4s（首次加载即快速渲染）
- **冷缓存榜单 20 只**：< 0.7s
- **后台静默刷新**：首屏 EastMoney 快速渲染，后台 BaoStock 精准刷新并写入 SQLite
- **SQLite WAL 模式**：支持并发读写不锁表

### 缓存策略
| 缓存层 | 有效期 | 说明 |
|--------|--------|------|
| API 内存缓存 | 30s~120s | FastAPI 层，替代 Streamlit cache_data |
| SQLite 行情快照 | 15min | 持久化到磁盘 |
| SQLite 日线数据 | 12h | 持久化到磁盘 |
| Provider 内存缓存 | 5min | BaoStock 进程内缓存 |

> **SQLite 缓存持久在磁盘**，重启后缓存仍在，没过期就不调 API。

---

## 项目结构

```text
.
├── .env                          # 配置文件
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts         # Axios 实例
│   │   │   └── types.ts          # TypeScript 类型
│   │   ├── components/
│   │   │   ├── AppSidebar.vue    # 侧边栏导航
│   │   │   ├── KlineChart.vue    # ECharts K线图
│   │   │   ├── MetricCard.vue    # 指标卡片
│   │   │   ├── LoadingSpinner.vue
│   │   │   └── ErrorAlert.vue
│   │   ├── views/
│   │   │   ├── DiagnosisView.vue # 个股诊断
│   │   │   ├── RankingsView.vue  # 策略榜单
│   │   │   ├── WatchlistView.vue # 自选池
│   │   │   └── StatusView.vue    # 系统状态
│   │   ├── router/index.ts
│   │   ├── App.vue
│   │   └── main.ts
│   ├── vite.config.ts            # Vite 配置（代理 /api → 8000）
│   └── package.json
├── src/ashare_quant/             # Python 核心
│   ├── api/                      # FastAPI 后端
│   │   ├── main.py               # API 路由
│   │   ├── schemas.py            # Pydantic Schema
│   │   └── cache.py              # 内存缓存
│   ├── providers/                # 数据源
│   │   ├── eastmoney_provider.py # 东方财富直调（HTTP 0.07s）
│   │   ├── baostock_provider.py  # BaoStock 日线
│   │   ├── routing_provider.py   # 双源路由
│   │   ├── sina_provider.py      # 新浪财经
│   │   ├── akshare_provider.py   # AKShare
│   │   ├── tushare_provider.py   # Tushare
│   │   ├── mock_provider.py      # 模拟数据
│   │   ├── composite_provider.py # 多源组合
│   │   └── factory.py            # Provider 工厂
│   ├── services/
│   │   └── market_service.py     # 核心业务
│   ├── cache/
│   │   ├── sqlite_cache.py       # SQLite 持久缓存
│   │   └── provider_cache.py     # 缓存 Provider
│   ├── ui/
│   │   └── dashboard_data.py     # UI 数据转换
│   └── analysis/
│       └── scoring.py            # 因子评分
├── data/cache/
│   └── market_cache.sqlite3      # 缓存文件
├── streamlit_app.py              # Streamlit 备选前端
├── start_quant_tool.bat          # 一键启动脚本
└── README.md
```

---

## 快速开始

### 方式 1：Vue 前端（推荐）

**终端 1 — 后端**
```bash
cd C:\Users\soap\.openclaw\workspace\ashare-quant-tool
uvicorn src.ashare_quant.api.main:app --reload --port 8000
```

**终端 2 — 前端**
```bash
cd C:\Users\soap\.openclaw\workspace\ashare-quant-tool\frontend
npm install   # 仅首次
npm run dev
```

浏览器打开 **http://localhost:5173**

### 方式 2：Streamlit（备选）
```bash
cd C:\Users\soap\.openclaw\workspace\ashare-quant-tool
streamlit run streamlit_app.py
```

浏览器打开 **http://localhost:8501**

### 方式 3：一键启动（Windows）
双击 `start_quant_tool.bat`，自动启动后端 + 前端 + 打开浏览器。

---

## 后端 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/strategies` | GET | 策略列表 |
| `/api/rankings?limit=20&strategy=trend` | GET | 策略榜单 |
| `/api/stocks/{symbol}?strategy=trend` | GET | 个股诊断 |
| `/api/watchlist` | POST | 自选池批量诊断 |
| `/api/stocks/{symbol}/bars?lookback=60` | GET | 历史日线 |
| `/api/status` | GET | 系统状态 |

---

## 策略说明

| 策略 | 说明 |
|------|------|
| `trend` | 趋势突破，强势股跟随 |
| `pullback` | 回调低吸，强趋势回撤观察 |
| `value` | 价值稳健，低估值低波动 |

每只股票输出：`total_score`（0~100）、`eligible`、`entry_signal`、`exit_signal`、`failed_filters`、`risk_flags`

---

## 配置

`.env` 文件配置：

| 变量 | 默认 | 说明 |
|------|------|------|
| `ASHARE_QUANT_PROVIDER` | `dual` | 数据源模式（dual / auto / mock） |
| `ASHARE_QUANT_PROVIDER_CACHE_TTL_SECONDS` | `120` | 缓存 TTL |
| `ASHARE_QUANT_PERSISTENT_CACHE_ENABLED` | `true` | SQLite 持久缓存 |
| `ASHARE_QUANT_TUSHARE_TOKEN` | — | Tushare Token（可选） |

---

## V1 → V2 更新日志

### v2.0（2026-05-29）前后端分离重构
- 🆕 新增 Vue 3 + Vite 前端（Tailwind CSS + ECharts）
- 🆕 新增 FastAPI 后端（RESTful API + 内存缓存）
- 🆕 修复个股诊断后端 `asdict` 500 错误
- 🆕 修复 Windows 下 localhost 代理解析问题
- 🆕 新增 `start_quant_tool.bat` 一键启动脚本
- ✅ Streamlit 备选前端保留不变

### v1.5 性能优化
- 🆕 新增 EastMoney 直调 Provider（0.07s）
- 🆕 新增 OperationRouting 双源路由
- 🆕 自选池/榜单并发加载（0.4s 内返回）
- 🆕 冷缓存后台刷新机制
- 🆕 SQLite WAL 模式支持并发读写
- 🆕 Provider 失败冷却机制

### v1.0 初始版本
- Streamlit 仪表盘
- AKShare / Sina / Tushare / BaoStock 多源支持
- SQLite 持久缓存
- 基础因子评分策略
