"""火麒麟 · 价值投资综合评估系统 — 主入口
==========================================

打包成单 exe:
    pip install pywebview pyinstaller
    pyinstaller --noconfirm --onefile --windowed \
        --name "火麒麟" \
        --collect-all finshare \
        --add-data "assets;assets" \
        run.py

开发模式:
    python run.py
"""

from __future__ import annotations

import os
import sys
import tempfile


def _fix_stdio_for_windowed():
    """PyInstaller --windowed 下 sys.stderr/sys.stdout 是 None, 会导致 loguru 等
    库在第一次 add(sink=sys.stderr) 时崩溃 (TypeError: Cannot log to NoneType).
    这里把 stdio 重定向到临时文件, 让一切正常. 无论源码运行还是打包都安全.
    """
    if sys.stderr is not None and sys.stdout is not None:
        return
    log_dir = os.path.join(tempfile.gettempdir(), "huoqilin")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "huoqilin.log")
    log_fh = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log_fh
    if sys.stderr is None:
        sys.stderr = log_fh
    os.environ.setdefault("NO_COLOR", "1")


def main():
    # 0) PyInstaller --windowed 兼容
    _fix_stdio_for_windowed()

    # 1) 启动后端 API
    from firekylin.api import start as start_api
    host, port = start_api()
    url = f"http://{host}:{port}/"
    print(f"[火麒麟] API ready: {url}")

    # 2) 启动 WebView 窗口
    import webview
    window_kwargs = dict(
        title="火麒麟 · 价值投资综合评估系统",
        url=url,
        width=1280,
        height=820,
        min_size=(960, 640),
        resizable=True,
        text_select=True,
        background_color="#0d1117",
    )

    window = webview.create_window(**window_kwargs)

    # 3) 启动
    try:
        webview.start(debug=False)
    except Exception as e:  # noqa: BLE001
        print(f"[火麒麟] webview 启动失败: {e}")
        # 退化: 直接打开浏览器
        import webbrowser
        webbrowser.open(url)
        print(f"[火麒麟] 已在浏览器打开: {url}")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()