"""证券清单 (A股 + ETF + 基金 + 指数)
====================================

全市场清单走 baostock (不限流), 启动时缓存到本地 JSON.
实时行情走 腾讯/新浪 (realtime.py).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import baostock as bs


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")
CACHE_FILE = os.path.join(CACHE_DIR, "stock_list.json")
CACHE_META = os.path.join(CACHE_DIR, "stock_list.meta.json")


@dataclass
class StockItem:
    code: str          # baostock 形态: sh.600519
    name: str
    ipo_date: str
    industry: str = ""
    type: str = "stock"  # stock / index / etf / fund

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "StockItem":
        return cls(**d)


def _bs_to_std(code: str) -> str:
    """BaoStock 代码 (sh.600519 / sz.000001) 转火麒麟标准代码 (600519.SH / 000001.SZ)"""
    if "." not in code:
        return code
    mk, num = code.split(".", 1)
    return f"{num}.{mk.upper()}"


def _std_to_bs(code: str) -> str:
    """600519.SH → sh.600519"""
    if "." not in code:
        return code
    num, mk = code.split(".", 1)
    return f"{mk.lower()}.{num}"


def fetch_all(timeout: int = 90) -> list[StockItem]:
    """拉 baostock 全市场清单 (不区分股票/基金/指数)"""
    lg = bs.login()
    items: list[StockItem] = []
    if lg.error_code == "0":
        rs = bs.query_stock_basic()
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            code, name, ipo = row[0], row[1], row[2]
            # baostock status 字段对沪深京不一致, 直接按代码前段判定类型
            num = code.split(".", 1)[1] if "." in code else code
            if num.startswith(("0", "3", "6", "9")):
                t = "stock"           # 沪深 A 股
            elif num.startswith(("5", "1")):
                t = "etf"             # 上交所 ETF/基金
            elif num.startswith(("15", "16", "18")):
                t = "fund"            # 深交所 LOF/分级基金
            elif num.startswith(("00", "39")):
                t = "index"           # 深证指数
            else:
                t = "stock"
            items.append(StockItem(code=code, name=name, ipo_date=ipo, type=t))
        # 行业归并
        rs2 = bs.query_stock_industry()
        ind_map: dict[str, str] = {}
        while rs2.error_code == "0" and rs2.next():
            row = rs2.get_row_data()
            ind_map[row[0]] = row[1]
        for it in items:
            it.industry = ind_map.get(it.code, "")
        bs.logout()

    items = [it for it in items if it.code.startswith(("sh.", "sz.", "bj."))]
    return items


def load_or_refresh(force: bool = False) -> list[StockItem]:
    """本地缓存命中用缓存, 否则拉一次"""
    if not force and os.path.exists(CACHE_FILE):
        age = 0
        if os.path.exists(CACHE_META):
            try:
                meta = json.loads(open(CACHE_META, encoding="utf-8").read())
                import time
                age = time.time() - meta.get("ts", 0)
            except Exception:  # noqa: BLE001
                age = 0
        if age < 7 * 86400:  # 7 天
            return [StockItem.from_dict(d) for d in json.loads(open(CACHE_FILE, encoding="utf-8").read())]
    items = fetch_all()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump([it.to_dict() for it in items], f, ensure_ascii=False)
    with open(CACHE_META, "w", encoding="utf-8") as f:
        json.dump({"ts": __import__("time").time(), "count": len(items)}, f)
    return items


def find_by_query(items: list[StockItem], q: str, limit: int = 20) -> list[StockItem]:
    """模糊搜索 (代码/名称)"""
    q = q.lower().strip()
    hits: list[StockItem] = []
    for it in items:
        if q in it.code.lower() or q in it.name:
            hits.append(it)
            if len(hits) >= limit:
                break
    return hits


if __name__ == "__main__":
    items = load_or_refresh(force=True)
    print("total:", len(items))
    stocks = [it for it in items if it.type == "stock"]
    print("stocks:", len(stocks))
    for it in stocks[:5]:
        print(_bs_to_std(it.code), it.name, it.industry)