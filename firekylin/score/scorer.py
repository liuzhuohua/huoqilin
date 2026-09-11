"""火麒麟评分 + 红绿灯 + MOS
============================

基于 Benjamin Graham + Warren Buffett 经典价值投资公式实现.
8 维度评分, 红绿灯判定, 安全边际, 完全本地运行.

Total Score = 100 分
  ROIC                       30  (近 1~4 年各 5 分 + 当年 vs 4 年趋势 5 分)
  Equity Growth              16  (近 1/2/3 年 TTM 增长各 4 分 + 趋势 4 分)
  EPS Growth                 16  (近 1/2/3 年 TTM 增长各 4 分 + 趋势 4 分)
  Sales Growth               16  (近 1/2/3 年 TTM 增长各 4 分 + 趋势 4 分)
  Free Cash Flow Growth       8
  Total Assets Growth         8
  Net Income Growth           3
  Total Liabilities Decrease  3

红绿灯判定:
  Score >= 50  且  MOS >= 50%   低估买入 (绿)
  Score >= 50  或  MOS >= 50%   观望 (灰)
  否则                            高估卖出 (红)

数据全部来自 finshare (东财公开接口, 完全免费).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional

import finshare as fs
import pandas as pd


# ---------------------------------------------------------------------------
# 数据整理
# ---------------------------------------------------------------------------
def _annual_rows(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """finshare 返回的 report_date 形如 20231231 / 20240630, 只取 12-31 年度行"""
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    df["report_date"] = df["report_date"].astype(str)
    df = df[df["report_date"].str.endswith("1231")]
    df["year"] = df["report_date"].str[:4].astype(int)
    df = df.sort_values("year", ascending=False).drop_duplicates("year")
    return df.reset_index(drop=True)


def _to_float(x) -> float:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return 0.0
        return float(x)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# 工具: 用 TTM (近 4 季度) 求增长率
# ---------------------------------------------------------------------------
def _quarter_rows(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """finshare 返回的混合季度/年度, 我们取所有季度行"""
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    df["report_date"] = df["report_date"].astype(str)
    df = df.sort_values("report_date", ascending=False).reset_index(drop=True)
    return df


def _ttm_sum(df: pd.DataFrame, col: str, n_quarters: int = 4) -> Optional[float]:
    """取最近 n 季度的合计 (TTM)"""
    if df is None or col not in df.columns or len(df) < n_quarters:
        return None
    vals = pd.to_numeric(df[col].head(n_quarters), errors="coerce").fillna(0)
    return float(vals.sum())


# ---------------------------------------------------------------------------
# 评分结果
# ---------------------------------------------------------------------------
@dataclass
class HuoqilinResult:
    code: str
    name: str
    score: int = 0
    max_score: int = 100
    mos: float = 0.0
    summary: str = "高估"
    fair_value: float = 0.0
    share_price: float = 0.0
    breakdown: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 单项得分函数 (按经典价值投资权重, 8 维度)
# ---------------------------------------------------------------------------
def _roic_score(roics: list[float]) -> int:
    """ROIC 30 分: 近 4 年各 5 分 + 趋势 5 分"""
    if len(roics) < 5:
        return 0
    pts = 0
    for r in roics[:4]:
        if r >= 0.10:
            pts += 5
    if roics[0] > roics[4]:
        pts += 5
    return min(pts, 30)


def _ttm_growth_score(t_now: Optional[float], t_1y: Optional[float], t_2y: Optional[float], t_3y: Optional[float]) -> int:
    """Sales/Equity/EPS 的 TTM 增长率 16 分: 3 个时点各 4 分 + 趋势 4 分"""
    pts = 0
    if t_now is None or t_1y is None or t_2y is None or t_3y is None:
        return 0
    if t_1y == 0 or t_2y == 0 or t_3y == 0:
        return 0
    g1 = (t_now / t_1y) ** (1 / 1) - 1
    g2 = (t_now / t_2y) ** (1 / 2) - 1
    g3 = (t_now / t_3y) ** (1 / 3) - 1
    if g1 >= 0.10:
        pts += 4
    if g2 >= 0.10:
        pts += 4
    if g3 >= 0.10:
        pts += 4
    g4 = (t_now / t_3y) ** (1 / 4) - 1
    if g1 > g4:
        pts += 4
    return min(pts, 16)


def _simple_growth_score(values: list[float], years: int = 4, weight: int = 4) -> int:
    """FCF / Total Assets 增长各 8 分: 4 个时点各 weight 分"""
    if len(values) < years + 1:
        return 0
    pts = 0
    for i in range(1, years + 1):
        if i >= len(values):
            break
        if values[i - 1] > values[i]:
            pts += weight
    return min(pts, years * weight)


def _simple_decrease_score(values: list[float], years: int = 4, weight: int = 1) -> int:
    """Net Income / Total Liabilities 3 分"""
    if len(values) < years + 1:
        return 0
    pts = 0
    for i in range(1, years + 1):
        if i >= len(values):
            break
        if values[i - 1] < values[i]:
            pts += weight
    return min(pts, years * weight)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def calculate(code: str, name: str, share_price: float) -> HuoqilinResult:
    """火麒麟评分 (8 维度财务健康 + MOS 安全边际)"""
    res = HuoqilinResult(code=code, name=name, share_price=share_price)

    try:
        income_y = _annual_rows(fs.get_income(code))
        balance_y = _annual_rows(fs.get_balance(code))
        cashflow_y = _annual_rows(fs.get_cashflow(code))
        indicator_y = _annual_rows(fs.get_financial_indicator(code))

        # 季度版 (用于 TTM)
        income_q = _quarter_rows(fs.get_income(code))
        balance_q = _quarter_rows(fs.get_balance(code))
        cashflow_q = _quarter_rows(fs.get_cashflow(code))
        indicator_q = _quarter_rows(fs.get_financial_indicator(code))

        if income_y is None or len(income_y) < 5:
            res.error = "财务数据不足 (无法取到 5 年年度数据)"
            return res

        revenue_y = [_to_float(v) for v in income_y["revenue"].head(5).tolist()]
        netincome_y = [_to_float(v) for v in income_y["net_profit"].head(5).tolist()]
        assets_y = [_to_float(v) for v in balance_y["total_assets"].head(5).tolist()] if "total_assets" in balance_y.columns else [0] * 5
        liab_y = [_to_float(v) for v in balance_y["total_liab"].head(5).tolist()] if "total_liab" in balance_y.columns else [0] * 5
        equity_y = [a - l for a, l in zip(assets_y, liab_y)]
        fcf_y = [_to_float(v) for v in cashflow_y["operate_cashflow"].head(5).tolist()] if "operate_cashflow" in cashflow_y.columns else [0] * 5
        eps_y = [_to_float(v) for v in indicator_y["eps"].head(5).tolist()]

        # ROIC (经典: EBITA / (debt+equity); 火麒麟版: net_profit / (debt+equity) 简化)
        roic_y = []
        for i in range(5):
            denom = liab_y[i] + equity_y[i]
            roic_y.append(netincome_y[i] / denom if denom > 0 else 0.0)

        # TTM 序列 (至少 16 个季度)
        rev_ttm_now = _ttm_sum(income_q, "revenue", 4)
        rev_ttm_1y = _ttm_sum(income_q, "revenue", 8) - (rev_ttm_now or 0) if rev_ttm_now else None
        rev_ttm_2y = _ttm_sum(income_q, "revenue", 12) - ((rev_ttm_now or 0) + (rev_ttm_1y or 0)) if rev_ttm_now else None
        rev_ttm_3y = _ttm_sum(income_q, "revenue", 16) - ((rev_ttm_now or 0) + (rev_ttm_1y or 0) + (rev_ttm_2y or 0)) if rev_ttm_now else None

        equity_ttm_now = _ttm_sum(balance_q, "total_equity", 4) if "total_equity" in balance_q.columns else None
        if equity_ttm_now is None and "total_assets" in balance_q.columns:
            a = _ttm_sum(balance_q, "total_assets", 4)
            l = _ttm_sum(balance_q, "total_liab", 4)
            equity_ttm_now = (a or 0) - (l or 0)
        equity_ttm_1y = _ttm_sum(balance_q, "total_assets", 8) - _ttm_sum(balance_q, "total_liab", 8)
        equity_ttm_2y = _ttm_sum(balance_q, "total_assets", 12) - _ttm_sum(balance_q, "total_liab", 12)
        equity_ttm_3y = _ttm_sum(balance_q, "total_assets", 16) - _ttm_sum(balance_q, "total_liab", 16)

        eps_ttm_now = _ttm_sum(indicator_q, "eps", 4)
        eps_ttm_1y = _ttm_sum(indicator_q, "eps", 8) - (eps_ttm_now or 0) if eps_ttm_now else None
        eps_ttm_2y = _ttm_sum(indicator_q, "eps", 12) - ((eps_ttm_now or 0) + (eps_ttm_1y or 0)) if eps_ttm_now else None
        eps_ttm_3y = _ttm_sum(indicator_q, "eps", 16) - ((eps_ttm_now or 0) + (eps_ttm_1y or 0) + (eps_ttm_2y or 0)) if eps_ttm_now else None

        breakdown = {}
        breakdown["ROIC(30)"] = _roic_score(roic_y)
        breakdown["Sales增长(16)"] = _ttm_growth_score(rev_ttm_now, rev_ttm_1y, rev_ttm_2y, rev_ttm_3y)
        breakdown["Equity增长(16)"] = _ttm_growth_score(equity_ttm_now, equity_ttm_1y, equity_ttm_2y, equity_ttm_3y)
        breakdown["EPS增长(16)"] = _ttm_growth_score(eps_ttm_now, eps_ttm_1y, eps_ttm_2y, eps_ttm_3y)
        breakdown["FCF增长(8)"] = _simple_growth_score(fcf_y, years=4, weight=2)
        breakdown["资产增长(8)"] = _simple_growth_score(assets_y, years=4, weight=2)
        breakdown["净利增长(3)"] = _simple_decrease_score(netincome_y, years=3, weight=1)
        breakdown["负债下降(3)"] = _simple_decrease_score(liab_y, years=3, weight=1)

        total = sum(breakdown.values())
        res.score = total
        res.breakdown = breakdown

        # Fair Value (Benjamin Graham 简化): FV = EPS_TTM × (8.5 + 2 × growth)
        cur_eps = eps_y[0]
        if len(eps_y) >= 5 and eps_y[4] > 0 and eps_y[0] > 0:
            g = (eps_y[0] / eps_y[4]) ** (1 / 4) - 1
        elif len(eps_y) >= 2 and eps_y[1] > 0 and eps_y[0] > 0:
            g = (eps_y[0] / eps_y[1]) - 1
        else:
            g = 0
        if cur_eps > 0 and g > 0:
            mult = max(8.5, 8.5 + 2 * g * 100)
            res.fair_value = cur_eps * mult

        if res.fair_value > 0 and share_price > 0:
            res.mos = max(0.0, (1 - share_price / res.fair_value) * 100)

        # 红绿灯
        if res.score >= 50 and res.mos >= 50:
            res.summary = "低估买入"
        elif res.score >= 50 or res.mos >= 50:
            res.summary = "观望"
        else:
            res.summary = "高估卖出"

    except Exception as e:  # noqa: BLE001
        res.error = f"评分失败: {e}"

    return res


if __name__ == "__main__":
    for code, name, price in [
        ("600519.SH", "贵州茅台", 1285.15),
        ("000001.SZ", "平安银行", 11.82),
        ("300750.SZ", "宁德时代", 333.06),
    ]:
        r = calculate(code, name, price)
        print(f"\n=== {code} {name} ({price}) ===")
        print(f"Score: {r.score}/100  MOS: {r.mos:.1f}%  Summary: {r.summary}")
        print(f"Fair Value: {r.fair_value:.2f}")
        print(f"Breakdown: {r.breakdown}")
        if r.error:
            print(f"Err: {r.error}")