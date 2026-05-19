# A 股量化分析工具 V1

这是一个面向个人研究场景的 A 股股票数据量化分析工具骨架，目标是帮助完成：

- 股票池筛选
- 买卖点辅助判断
- 板块与市场强弱分析
- 回测前的因子研究与评分验证

当前版本重点是先搭好 `V1` 的技术框架与最小可运行能力：

- 支持数据源适配器抽象
- 内置 `Mock` 数据源，方便离线开发
- 已接入 `AKShare`、`Tushare`、`BaoStock` 适配入口
- 提供基础因子计算与评分逻辑
- 提供一个简单的 API 服务

## 当前目录结构

```text
docs/
  AKShare接入与兼容性说明.md
  本地持久化缓存层设计说明.md
  多数据源回退设计说明.md
  V1技术设计书-上半部分.md
src/
  ashare_quant/
    analysis/
    api/
    providers/
    services/
scripts/
  demo_run.py
```

## 快速开始

1. 安装依赖

```bash
pip install -e .
```

2. 运行演示脚本

```bash
python scripts/demo_run.py
```

3. 运行 `AKShare` 清洗自检

```bash
python scripts/akshare_parser_check.py
```

4. 运行多源兼容自检

```bash
python scripts/multi_provider_parser_check.py
```

5. 运行缓存烟雾测试

```bash
python scripts/cache_smoke_test.py
```

6. 运行前端数据烟雾测试

```bash
python scripts/ui_data_smoke_test.py
```

7. 启动前端界面

```bash
streamlit run streamlit_app.py
```

8. 启动 API

```bash
uvicorn ashare_quant.api.main:app --reload
```

## 当前能力

- `GET /health`
- `GET /strategies`
- `GET /universe?limit=20`
- `GET /rankings?limit=20&strategy=trend`
- `GET /stocks/{symbol}?strategy=value`
- `Streamlit` 仪表盘前端：榜单、自选池、单股诊断、系统状态

当未安装 `akshare` 或未开启真实数据模式时，系统自动回退到内置的模拟数据源，方便先把分析链路跑通。

## 当前策略

- `trend`：趋势突破，偏强势股跟随
- `pullback`：回调低吸，偏强趋势中的回撤观察
- `value`：价值稳健，偏低估值和低波动筛选

当前每套策略除了总分，还会返回：

- `eligible`：是否通过该策略的硬过滤条件
- `entry_signal`：当前更适合怎样观察或介入
- `exit_signal`：走势走坏时优先看什么退出
- `failed_filters`：哪些硬条件没有通过
- `risk_flags`：当前最需要注意的风险点

## 兼容性说明

- 默认 `provider=auto`
- `auto` 模式会依次尝试 `AKShare -> Tushare -> BaoStock -> Mock`
- 当前机器缺少依赖时自动回退到 `Mock`
- 股票代码支持 `000001`、`sz000001`、`SH600519` 等常见格式
- `AKShare` 列名清洗统一收敛在 `src/ashare_quant/providers/akshare_cleaner.py`
- 跨数据源的代码格式和日期处理统一收敛在 `src/ashare_quant/providers/shared_cleaner.py`
- 本地持久化缓存默认开启，缓存文件默认落在 `data/cache/market_cache.sqlite3`

## 下一步

- 完善真实数据联调与缓存命中观察
- 完善行业、板块、资金流因子
- 增加回测模块
- 增加前端页面
