"""火麒麟 · 价值投资综合评估系统 — 一键打包脚本
================================================

依赖: pip install pywebview pyinstaller finshare baostock pandas requests

执行:
    python build.py

产物: dist/火麒麟.exe (~30 MB)
"""

import os
import shutil
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, **kwargs):
    print(f"\n>>> {' '.join(cmd) if isinstance(cmd, list) else cmd}\n")
    return subprocess.run(cmd, **kwargs)


def main():
    os.chdir(HERE)

    # 1) 清理
    for d in ("build", "dist"):
        if os.path.exists(d):
            shutil.rmtree(d)
    for f in os.listdir("."):
        if f.endswith(".spec"):
            os.remove(f)

    # 2) 检查依赖
    print("=" * 60)
    print("检查依赖 ...")
    for pkg in ("finshare", "baostock", "pywebview", "PyInstaller"):
        mod = "webview" if pkg == "pywebview" else pkg
        try:
            __import__(mod)
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ✗ 缺少 {pkg}, 请先 pip install {pkg}")
            sys.exit(1)

    # 3) PyInstaller
    # 注意: --collect-all finshare 把 finshare 的数据文件全打包
    #       --add-data 把前端 HTML 打包进 assets/
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "火麒麟",
        "--collect-all", "finshare",
        "--add-data", f"assets{os.pathsep}assets",
        "--hidden-import", "bottle",
        "--hidden-import", "webview",
        "--hidden-import", "baostock",
        "run.py",
    ]
    print("\n" + "=" * 60)
    print("开始打包 ...")
    print("=" * 60)
    r = run(cmd)
    if r.returncode != 0:
        print("打包失败!")
        sys.exit(1)

    # 4) 提示
    out = os.path.join(HERE, "dist", "火麒麟.exe")
    if os.path.exists(out):
        size_mb = os.path.getsize(out) / 1024 / 1024
        print(f"\n✅ 打包成功: {out}  ({size_mb:.1f} MB)")
        print("双击 dist/火麒麟.exe 即可运行")
    else:
        print("⚠️  打包完成但未找到 dist/火麒麟.exe, 请检查上方日志")


if __name__ == "__main__":
    main()