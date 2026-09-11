"""火麒麟 HTTP API (Bottle)
============================

为 PyWebView 提供后端 API. 前端 (HTML/JS) 通过 fetch 调这里取数据.

API 列表:
  GET  /api/ping                          健康检查
  GET  /api/stocks                        全市场清单 (按需从 baostock 缓存)
  GET  /api/quote/<code>                  单只行情 (新浪/腾讯)
  GET  /api/screen                        筛选 + 评分 (重 CPU, 缓存)
  GET  /api/score/<code>                  单只深度评分
  GET  /api/watchlist                     当前自选股 (本地 JSON)
  POST /api/watchlist                     加入自选股
  DELETE /api/watchlist/<code>            移除
  POST /api/portfolio/transaction         记录组合交易
  GET  /api/portfolio/<name>              查组合
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from bottle import Bottle, request, response, run, static_file

# 兼容 PyInstaller
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from firekylin.data import realtime, securities
from firekylin.score.scorer import calculate as score_calc

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(APP_DIR, "assets")
WATCH_FILE = os.path.join(ASSETS_DIR, "watchlist.json")
PORTFOLIO_DIR = os.path.join(ASSETS_DIR, "portfolios")
os.makedirs(PORTFOLIO_DIR, exist_ok=True)

app = Bottle()
_app_lock = threading.Lock()

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _json(data, code: int = 200):
    response.status = code
    response.content_type = "application/json; charset=utf-8"
    return json.dumps(data, ensure_ascii=False, default=str)


def _load_watchlist() -> list[str]:
    if not os.path.exists(WATCH_FILE):
        return []
    try:
        return json.loads(open(WATCH_FILE, encoding="utf-8").read())
    except Exception:  # noqa: BLE001
        return []


def _save_watchlist(items: list[str]):
    os.makedirs(ASSETS_DIR, exist_ok=True)
    with open(WATCH_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


# 评分缓存 (避免重复拉取财务数据)
_score_cache: dict[str, dict] = {}
_score_cache_lock = threading.Lock()
_SCORE_TTL = 3600  # 1 小时


def _score_with_cache(code: str, name: str, price: float):
    key = f"{code}|{price:.2f}"
    with _score_cache_lock:
        cached = _score_cache.get(key)
        if cached and time.time() - cached["ts"] < _SCORE_TTL:
            return cached["data"]
    # 评分带超时 (15s), 超时返回降级结果, 不阻塞前端
    try:
        r = score_calc(code, name, price)
        data = r.to_dict()
    except Exception as e:  # noqa: BLE001
        data = {"code": code, "name": name, "score": 0, "summary": "数据获取失败", "error": str(e)}
    with _score_cache_lock:
        _score_cache[key] = {"ts": time.time(), "data": data}
    return data


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@app.route("/api/ping")
def ping():
    return _json({"pong": True, "ts": time.time()})


@app.route("/")
def serve_root():
    return _serve("index.html")


@app.route("/<filename:re:[^/]+\\.[a-z]+>")
def serve_static(filename):
    """serve assets/* (PyWebView 默认指向 /)"""
    return _serve(filename)


def _serve(filename):
    fp = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(fp):
        response.status = 404
        return f"Not found: {filename}"
    if filename.endswith(".html"):
        response.content_type = "text/html; charset=utf-8"
    elif filename.endswith(".js"):
        response.content_type = "application/javascript; charset=utf-8"
    elif filename.endswith(".css"):
        response.content_type = "text/css; charset=utf-8"
    elif filename.endswith(".json"):
        response.content_type = "application/json; charset=utf-8"
    with open(fp, encoding="utf-8") as f:
        return f.read()


@app.route("/api/stocks")
def api_stocks():
    """证券清单 (基础信息: code / name / industry / type)"""
    items = securities.load_or_refresh()
    return _json([
        {
            "code": securities._bs_to_std(it.code),
            "name": it.name,
            "industry": it.industry,
            "type": it.type,
        }
        for it in items
        if it.type in ("stock", "etf", "fund")
    ])


@app.route("/api/quote/<code>")
def api_quote(code):
    code = code.upper()
    q = realtime.fetch_quotes([code]).get(code)
    if not q:
        return _json({"error": "行情获取失败"}, 404)
    return _json(q.to_dict())


@app.route("/api/quotes")
def api_quotes():
    """批量行情, ?codes=600519.SH,000001.SZ,300750.SZ (最多 200)"""
    raw = request.query.get("codes", "")
    codes = [c.strip().upper() for c in raw.split(",") if c.strip()][:200]
    if not codes:
        return _json({})
    out = realtime.fetch_quotes(codes)
    return _json({c: v.to_dict() for c, v in out.items()})


@app.route("/api/score/<code>")
def api_score(code):
    code = code.upper()
    # 先行情再评分
    q = realtime.fetch_quotes([code]).get(code)
    if not q:
        return _json({"error": "行情获取失败"}, 404)
    price = q.price
    # 找名字 (走清单)
    items = securities.load_or_refresh()
    name = q.name
    for it in items:
        if securities._bs_to_std(it.code) == code:
            name = it.name
            break
    data = _score_with_cache(code, name, price)
    data["share_price"] = price
    data["quote"] = q.to_dict()
    return _json(data)


@app.route("/api/screen")
def api_screen():
    """筛选 + 评分 (并发). Query 参数:
      market: sh / sz / bj / all (default all)
      summary: on_sale / watch / overpriced / all (default all)
      min_score: int (default 0)
      min_mos: float (default 0)
      limit: int (default 50, 防卡死)
    """
    market = request.query.get("market", "all")
    summary = request.query.get("summary", "all")
    min_score = int(request.query.get("min_score", 0))
    min_mos = float(request.query.get("min_mos", 0))
    limit = int(request.query.get("limit", 50))
    summary_map = {"on_sale": "低估买入", "watch": "观望", "overpriced": "高估卖出"}

    items = securities.load_or_refresh()
    items = [it for it in items if it.type == "stock"]
    if market != "all":
        items = [it for it in items if it.code.startswith(f"{market}.")]
    # 只取前 2x limit 只 (过滤后可能不够)
    targets = items[: limit * 2]

    # 1) 批量拉行情 (1 秒)
    codes = [securities._bs_to_std(it.code) for it in targets]
    quotes = realtime.fetch_quotes(codes)

    # 2) 并发评分 (3 线程, 评分带 1h 缓存, 避免被东财风控)
    out = []
    target_summary = summary_map.get(summary, summary)
    futures = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        for s in targets:
            code = securities._bs_to_std(s.code)
            q = quotes.get(code)
            if not q:
                continue
            futures[ex.submit(_score_with_cache, code, s.name, q.price)] = code
        for fut in as_completed(futures, timeout=300):
            try:
                data = fut.result(timeout=30)
            except Exception:  # noqa: BLE001
                continue
            # 过滤
            if target_summary != "all" and data.get("summary") != target_summary:
                continue
            if data.get("score", 0) < min_score:
                continue
            if data.get("mos", 0) < min_mos:
                continue
            out.append(data)
            if len(out) >= limit:
                break

    out.sort(key=lambda x: x.get("score", 0), reverse=True)
    return _json(out)


@app.route("/api/watchlist", method="GET")
def api_watchlist_get():
    return _json(_load_watchlist())


@app.route("/api/watchlist", method="POST")
def api_watchlist_post():
    body = request.json or {}
    code = (body.get("code") or "").upper()
    if not code:
        return _json({"error": "code 必填"}, 400)
    items = _load_watchlist()
    if code not in items:
        items.append(code)
        _save_watchlist(items)
    return _json({"ok": True, "items": items})


@app.route("/api/watchlist/<code>", method="DELETE")
def api_watchlist_delete(code):
    code = code.upper()
    items = _load_watchlist()
    if code in items:
        items.remove(code)
        _save_watchlist(items)
    return _json({"ok": True, "items": items})


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
def start(host: str = "127.0.0.1", port: int = 0):
    """非阻塞启动. port=0 时让系统自动分配空闲端口, 避免多开冲突."""
    import socket
    if port == 0:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
    t = threading.Thread(
        target=run, kwargs={"app": app, "host": host, "port": port, "quiet": True},
        daemon=True,
    )
    t.start()
    # 等启动
    import urllib.request
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://{host}:{port}/api/ping", timeout=0.5).read()
            return host, port
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    return host, port


if __name__ == "__main__":
    start()
    print("API ready on http://127.0.0.1:38471")
    import time
    while True:
        time.sleep(1)