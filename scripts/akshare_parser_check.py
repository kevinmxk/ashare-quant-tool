from __future__ import annotations

from ashare_quant.providers.akshare_cleaner import map_bar_row, map_quote_row, normalize_symbol


def main() -> None:
    quote_row = {
        "代码": "sz000001",
        "名称": "平安银行",
        "最新价": "11.23",
        "涨跌幅": "1.63",
        "换手率": "0.88",
        "成交额": "1203456789",
        "量比": "1.32",
        "市盈率-动态": "5.8",
        "市净率": "0.61",
        "总市值": "210000000000",
    }
    bar_row = {
        "日期": "2024-05-28",
        "股票代码": "000001",
        "开盘": "11.10",
        "收盘": "11.23",
        "最高": "11.30",
        "最低": "11.05",
        "成交量": "1023456",
        "成交额": "1203456789",
    }

    quote = map_quote_row(quote_row)
    bar = map_bar_row(bar_row, fallback_symbol=normalize_symbol("SZ000001"))

    print("quote_ok=", bool(quote and quote.symbol == "000001" and quote.latest_price == 11.23))
    print("bar_ok=", bool(bar and bar.symbol == "000001" and bar.close_price == 11.23))


if __name__ == "__main__":
    main()
