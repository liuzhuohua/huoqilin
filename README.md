# 🔥 火麒麟 · 价值投资综合评估系统

> 基于 **Benjamin Graham + Warren Buffett** 经典价值投资公式的中文 A 股分析工具.
> 100 分制财务健康评分 · MOS 安全边际 · 红绿灯信号 · 完全本地运行.
> 数据来自公开免费源, 无需付费账号, 无需联网登录.

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Data](https://img.shields.io/badge/data-100%25%20public%20free-brightgreen.svg)]()

---

## ✨ 这是什么

火麒麟是一个**单 exe 的桌面应用**, 双击即用. 它把 Tykr.com 的核心算法(100 分制评分 + MOS 安全边际)原样移植到 A 股市场, 数据 100% 走公开免费源(东方财富 / 腾讯 / 新浪 / BaoStock).

**它适合**:
- 想用价值投资思路筛 A 股的散户
- 自学 Warren Buffett / Benjamin Graham 投资框架
- 不想为付费研报工具付费的个人投资者

**它不适合**:
- 短线交易者 — 它是给长期持有者设计的
- 美股 / 港股用户 — 当前版本只覆盖 A 股(沪深北)

---

## 🚀 快速上手

### 方式 1: 下载预编译 exe (推荐)

到 [Releases](https://github.com/liuzhuohua/huoqilin/releases) 下载 `火麒麟.exe`, 双击即用.

> 需要 Windows 10/11 + 已装 Edge WebView2 (Win11 默认带, Win10 大多也带).

### 方式 2: 源码运行

```bash
git clone https://github.com/liuzhuohua/huoqilin.git
cd huoqilin
pip install -r requirements.txt
python run.py
```

### 方式 3: 自己打包成单 exe

```bash
pip install -r requirements.txt
python build.py
# 产物: dist/火麒麟.exe (约 108 MB)
```

---

## 📖 核心功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 🟢🟡🔴 红绿灯信号 | 一眼看出买入 / 观望 / 卖出 | ✅ |
| 💯 100 分制评分 | ROIC / 销售 / 权益 / EPS / FCF / 资产 / 净利 / 负债 8 维度 | ✅ |
| 📐 MOS 安全边际 | Benjamin Graham 简化公式 | ✅ |
| 🔍 智能筛选 | 按评分 / MOS / 市场过滤 7200+ 只 A 股 | ✅ |
| ⭐ 自选股 | 本地持久化, 跟踪评分变化 | ✅ |
| 💼 投资组合 | 持仓 / 加权平均成本 / 盈亏 | ✅ |
| 📚 投资课堂 | 中文算法解释 | ✅ |

### 红绿灯怎么判定?

| 信号 | 条件 | 含义 |
|------|------|------|
| 🟢 **低估买入** | 评分 ≥ 50 **且** MOS ≥ 50% | 财务健康且价格低估 |
| 🟡 **观望** | 评分 ≥ 50 **或** MOS ≥ 50% | 只有一项达标 |
| 🔴 **高估卖出** | 都不满足 | 财务不健康且价格高估 |

---

## 🧮 评分公式 (基于经典价值投资理论)

**总分 100 分**, 由 8 项组成:

| 维度 | 满分 | 评分细则 |
|------|------|----------|
| **ROIC** (投入资本回报率) | 30 | 近 4 年各 5 分 (ROIC ≥ 10%) + 趋势 5 分 |
| **Sales 增长** (TTM) | 16 | 近 1y / 2y / 3y 增长各 4 分 (≥ 10%) + 趋势 4 分 |
| **Equity 增长** (TTM) | 16 | 近 1y / 2y / 3y 增长各 4 分 (≥ 10%) + 趋势 4 分 |
| **EPS 增长** (TTM) | 16 | 近 1y / 2y / 3y 增长各 4 分 (≥ 10%) + 趋势 4 分 |
| **FCF 增长** | 8 | 近 4 年增长各 2 分 |
| **Total Assets 增长** | 8 | 近 4 年增长各 2 分 |
| **Net Income 增长** | 3 | 近 3 年增长各 1 分 |
| **Total Liabilities 下降** | 3 | 近 3 年下降各 1 分 |

**合理价 (Fair Value)**: `EPS × (8.5 + 2 × 年化EPS增长率)` — Benjamin Graham 经典公式
**MOS**: `100% − (股价 / 合理价)`

---

## 📚 数据源 (全部公开免费)

| 数据 | 来源 | 用途 |
|------|------|------|
| A 股实时价 | 腾讯 qt.gtimg.cn / 新浪 hq.sinajs.cn | 行情 / 涨跌 / 成交量 |
| 财务三表 | 东方财富 (经 [finshare](https://github.com/finvfamily/finshare)) | 利润表 / 资产负债表 / 现金流量表 |
| 财务指标 | 东方财富 (经 finshare) | EPS / ROE / 资产负债率 |
| 全市场清单 | [BaoStock](http://baostock.com/) | 7200+ 股票 / ETF / 基金 |
| 行业分类 | BaoStock | 申万行业 |

**注意**: 东方财富 push2 接口偶发限流. 火麒麟有自动重试 + 冷却 + 缓存机制(评分 1 小时缓存), 不会因瞬时风控崩溃.

---

## 📁 项目结构

```
huoqilin/
├── run.py                    # PyWebView 主入口
├── build.py                  # PyInstaller 打包脚本
├── requirements.txt
├── README.md
├── LICENSE                   # MIT
├── .gitignore
├── .gitattributes
├── .github/
│   └── workflows/
│       └── ci.yml            # GitHub Actions CI (lint + import smoke)
├── firekylin/                # 核心 Python 包
│   ├── __init__.py
│   ├── api.py                # Bottle HTTP API + 静态文件服务
│   ├── data/
│   │   ├── realtime.py       # 腾讯 / 新浪实时报价
│   │   └── securities.py     # BaoStock 证券清单
│   └── score/
│       └── scorer.py         # 100 分制评分 + MOS + 红绿灯
├── assets/
│   ├── index.html            # 火麒麟前端 (单页应用)
│   └── watchlist.json        # 自选股 (运行时生成)
├── scripts/
│   └── _device_login.py      # GitHub device-flow helper (开发用)
└── dist/火麒麟.exe           # 打包产物 (本地构建, 不入库)
```

---

## 🛠️ 开发

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式启动
python run.py

# 评分算法单独测试
python -m firekylin.score.scorer
```

### 依赖说明

| 包 | 用途 |
|----|------|
| `finshare` | 金融数据 (核心, 聚合东财 / 腾讯 / 新浪 / BaoStock) |
| `baostock` | 全 A 股证券清单 (兜底源) |
| `pandas` | 数据处理 |
| `bottle` | 内置 HTTP server (pywebview 自带) |
| `pywebview` | Edge WebView2 桌面壳 |
| `pyinstaller` | 单 exe 打包 (可选) |

---

## ⚠️ 免责声明

本系统仅作为投资分析工具, 所有数据按公开公式计算. **不构成任何投资建议**.
投资有风险, 入市需谨慎. 请独立判断, 盈亏自负.

---

## 🙏 致谢

- **算法灵感**: Benjamin Graham《聪明的投资者》+ Warren Buffett 投资哲学
- **数据源**:
  - [finshare](https://github.com/finvfamily/finshare) — 综合金融数据
  - [BaoStock](http://baostock.com/) — A 股证券清单
  - 东方财富 / 腾讯财经 / 新浪财经 — 公开 HTTP 接口
- **桌面壳**: [pywebview](https://pywebview.flowrl.com/) — Edge WebView2 包装

---

## 📄 许可证

[MIT](LICENSE) © 2026 liuzhuohua