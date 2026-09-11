"""火麒麟实时行情 / 证券清单 数据源
====================================

完全本地运行, 数据源按稳定性排序:

  1. 新浪财经  (hq.sinajs.cn)        - 全市场 A 股, 字段最全, 不限流
  2. 腾讯财经  (qt.gtimg.cn)          - 兜底, 字段一致
  3. 东方财富  (push2.eastmoney.com)   - 偶尔被风控但字段最丰富

字段: code / name / price / change_pct / volume / amount /
turnover_rate / pe_ttm / pb / market_cap / currency.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict, field
from typing import Iterable


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Huoqilin/1.0"
HEADERS_SINA = {
    "User-Agent": UA,
    "Referer": "https://finance.sina.com.cn/",
}
HEADERS_TX = {
    "User-Agent": UA,
    "Referer": "https://gu.qq.com/",
}
HEADERS_EM = {
    "User-Agent": UA,
    "Referer": "https://quote.eastmoney.com/",
}

SINA_URL = "https://hq.sinajs.cn/list={codes}"
TX_URL = "https://qt.gtimg.cn/q={codes}"
EM_BATCH_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?pn={pn}&pz={pz}&po=1&np=1&fltt=2&invt=2&fid=f12"
    "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:1+t:12,m:1+t:4,m:1+t:7"
    "&fields=f12,f14,f2,f3,f5,f6,f8,f9,f10,f20,f23"
)


@dataclass
class Quote:
    """单只股票行情 (字段对齐火麒麟单股详情面板)"""

    code: str
    name: str
    price: float = 0.0
    prev_close: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    turnover_rate: float = 0.0
    pe_ttm: float = 0.0
    pb: float = 0.0
    total_mv: float = 0.0       # 总市值(元)
    circ_mv: float = 0.0        # 流通市值(元)
    market: str = ""            # SH / SZ / BJ
    currency: str = "CNY"
    source: str = ""            # sina / tencent / eastmoney
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 新浪
# ---------------------------------------------------------------------------
def _sina_codes(codes: Iterable[str]) -> list[tuple[str, str]]:
    """把 600519.SH → sh600519, 同时保留原 code 便于回填"""
    out = []
    for c in codes:
        c = c.upper()
        if "." in c:
            num, mk = c.split(".")
            mk = mk.lower()
        elif c.startswith(("6", "9", "5")):
            num, mk = c, "sh"
        else:
            num, mk = c, "sz"
        out.append((c, f"{mk}{num}"))
    return out


def fetch_sina(codes: list[str]) -> dict[str, Quote]:
    """新浪实时报价, 批量上限 60"""
    mapping = _sina_codes(codes)
    sym_to_code = {sym: code for code, sym in mapping}
    quotes: dict[str, Quote] = {}
    if not mapping:
        return quotes

    for chunk_start in range(0, len(mapping), 60):
        chunk = mapping[chunk_start: chunk_start + 60]
        syms = ",".join(sym for _, sym in chunk)
        url = SINA_URL.format(codes=syms)
        try:
            req = urllib.request.Request(url, headers=HEADERS_SINA)
            raw = urllib.request.urlopen(req, timeout=6).read().decode("gbk", "ignore")
        except (urllib.error.URLError, TimeoutError, Exception) as e:  # noqa: BLE001
            print(f"[sina] {syms[:40]}... err {e}")
            continue

        # var hq_str_sh600519="贵州茅台,1285.150,..."
        for line in raw.splitlines():
            if '="' not in line or not line.startswith("var hq_str_"):
                continue
            sym = line.split('="', 1)[0].replace("var hq_str_", "")
            payload = line.split('="', 1)[1].rstrip('";\n')
            fields = payload.split(",")
            if len(fields) < 10:
                continue
            code = sym_to_code.get(sym, sym)
            try:
                q = Quote(
                    code=code,
                    name=fields[0],
                    price=float(fields[1] or 0),
                    prev_close=float(fields[2] or 0),
                    open=float(fields[3] or 0),
                    high=float(fields[4] or 0),
                    low=float(fields[5] or 0),
                    # 字段 6 是当前 close, 我们用 price 即可
                    change=float(fields[1] or 0) - float(fields[2] or 0),
                    change_pct=(
                        (float(fields[1] or 0) - float(fields[2] or 0))
                        / float(fields[2] or 1)
                        * 100
                        if float(fields[2])
                        else 0.0
                    ),
                    volume=float(fields[5] or 0) * 100 if fields[5] else 0,  # 手
                    amount=float(fields[9] or 0) if len(fields) > 9 else 0,
                    source="sina",
                    market=code.split(".")[1] if "." in code else "",
                )
                quotes[code] = q
            except (ValueError, IndexError):
                continue
    return quotes


# ---------------------------------------------------------------------------
# 腾讯 (兜底)
# ---------------------------------------------------------------------------
def fetch_tencent(codes: list[str]) -> dict[str, Quote]:
    """v_sh600519="1~贵州茅台~600519~1271.63~1285.13~1285.15~19283~..." """
    mapping = _sina_codes(codes)  # 同一种 sym
    sym_to_code = {sym: code for code, sym in mapping}
    quotes: dict[str, Quote] = {}
    if not mapping:
        return quotes

    syms = ",".join(sym for _, sym in mapping)
    url = TX_URL.format(codes=syms)
    try:
        req = urllib.request.Request(url, headers=HEADERS_TX)
        raw = urllib.request.urlopen(req, timeout=6).read().decode("gbk", "ignore")
    except (urllib.error.URLError, TimeoutError, Exception) as e:  # noqa: BLE001
        print(f"[tx] err {e}")
        return quotes

    for line in raw.split(";"):
        line = line.strip()
        if "=" not in line or "v_" not in line:
            continue
        try:
            sym = line.split('="', 1)[0].replace("v_", "")
            payload = line.split('="', 1)[1].rstrip('";\n')
        except IndexError:
            continue
        f = payload.split("~")
        if len(f) < 35:
            continue
        code = sym_to_code.get(sym, sym)
        try:
            price = float(f[3] or 0)
            prev = float(f[4] or 0)
            open_p = float(f[5] or 0)
            vol = float(f[6] or 0) * 100  # 手
            amount = float(f[37] or 0) * 10000  # 万元 → 元
            q = Quote(
                code=code,
                name=f[1],
                price=price,
                prev_close=prev,
                open=open_p,
                change=price - prev,
                change_pct=(price - prev) / prev * 100 if prev else 0,
                high=float(f[33] or 0),
                low=float(f[34] or 0),
                volume=vol,
                amount=amount,
                turnover_rate=float(f[38] or 0),
                pe_ttm=float(f[39] or 0),
                total_mv=float(f[45] or 0) * 1e8 if len(f) > 45 else 0,
                circ_mv=float(f[44] or 0) * 1e8 if len(f) > 44 else 0,
                source="tencent",
                market=code.split(".")[1] if "." in code else "",
            )
            quotes[code] = q
        except (ValueError, IndexError):
            continue
    return quotes


# ---------------------------------------------------------------------------
# 智能获取: 优先新浪, 不足时腾讯补
# ---------------------------------------------------------------------------
def fetch_quotes(codes: list[str]) -> dict[str, Quote]:
    """一次拿到的报价字典, 失败自动换源"""
    if not codes:
        return {}
    out = fetch_sina(codes)
    if not out or len(out) < len(codes) * 0.7:
        out = fetch_tencent(codes)
    return out


# ---------------------------------------------------------------------------
# 证券清单 (全市场, 走东财, 失败退到新浪大盘列表)
# ---------------------------------------------------------------------------
def fetch_stock_list() -> list[Quote]:
    """全市场 A 股清单 + 实时价 (火麒麟 '所有股票' 表格所需)"""
    # 东财 push2 一次性拿 5000 只, 失败就拉多次
    all_q: list[Quote] = []
    page_size = 100
    for page in range(1, 30):
        url = EM_BATCH_URL.format(pn=page, pz=page_size)
        try:
            req = urllib.request.Request(url, headers=HEADERS_EM)
            raw = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
            data = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            print(f"[em list] page {page} err {e}")
            break
        rows = data.get("data", {}).get("diff", []) or []
        if not rows:
            break
        for r in rows:
            try:
                raw_code = r.get("f12", "")
                if not raw_code or len(raw_code) != 6:
                    continue
                # f13 -> market(1 sh / 0 sz / ...)
                market_idx = r.get("f13", 1)
                mk = "SH" if market_idx == 1 else ("SZ" if market_idx == 0 else "BJ")
                code = f"{raw_code}.{mk}"
                price = float(r.get("f2", 0) or 0)
                prev = float(r.get("f4", 0) or 0)
                pct = float(r.get("f3", 0) or 0)
                q = Quote(
                    code=code,
                    name=r.get("f14", ""),
                    price=price,
                    prev_close=prev,
                    change_pct=pct,
                    change=price - prev,
                    high=float(r.get("f5", 0) or 0),
                    low=float(r.get("f6", 0) or 0),
                    volume=float(r.get("f8", 0) or 0),
                    amount=float(r.get("f9", 0) or 0),
                    turnover_rate=float(r.get("f10", 0) or 0),
                    pe_ttm=float(r.get("f20", 0) or 0),
                    total_mv=float(r.get("f23", 0) or 0),
                    market=mk,
                    source="eastmoney",
                )
                all_q.append(q)
            except (ValueError, TypeError):
                continue
        if len(rows) < page_size:
            break
        time.sleep(0.05)
    return all_q


if __name__ == "__main__":
    q = fetch_sina(["600519.SH", "000001.SZ"])
    for c, v in q.items():
        print(c, v.name, v.price, v.change_pct)