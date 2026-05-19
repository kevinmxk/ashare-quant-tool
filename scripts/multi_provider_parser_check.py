from __future__ import annotations

from ashare_quant.providers.shared_cleaner import normalize_symbol, to_baostock_code, to_tushare_code
from ashare_quant.providers.tushare_provider import _trade_date_key


def main() -> None:
    checks = {
        "normalize_sz": normalize_symbol("sz000001") == "000001",
        "normalize_tushare": normalize_symbol("000001.SZ") == "000001",
        "to_tushare_code": to_tushare_code("600519") == "600519.SH",
        "to_baostock_code": to_baostock_code("300750") == "sz.300750",
        "trade_date_key": _trade_date_key({"trade_date": "20250103"}) == "20250103",
    }

    for name, passed in checks.items():
        print("{name}={passed}".format(name=name, passed=passed))


if __name__ == "__main__":
    main()
