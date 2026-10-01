"""
價值投資選股 App - 股價漲跌拆解與估值極端旗標引擎 (decomposition.py)
嚴格落實技術規格書 V1.7 第 6.9 節：
- 漲跌拆解公式：ln(P1/P0) = ln(EPS1/EPS0) + ln(PE1/PE0)
- 拆解為「獲利貢獻 (EPS)」與「本益比評價擴張/收縮 (PE)」之百分比佔比
- EPS ≤ 0 時依規格不顯示拆解
- 估值極端旗標 (D-26)：
  1. 本益比 > 100 倍，或 > 同族群中位數的 3 倍。
  2. EPS ≤ 0，且股價位於近 52 週區間之上 20%。
- 適用範圍：排除景氣循環股與金融股
- 僅顯示「獲利尚未支撐股價」警示條，不改變價位區判定
"""

import math
from typing import Dict, Any, Optional, List


def calculate_price_decomposition(
    p0: float,
    p1: float,
    eps0: float,
    eps1: float,
    period_name: str = "1年"
) -> Dict[str, Any]:
    """
    純函式計算股價變動拆解
    ln(P1/P0) = ln(EPS1/EPS0) + ln(PE1/PE0)
    """
    # 規格書 6.9: EPS ≤ 0 時不顯示拆解
    if eps0 <= 0 or eps1 <= 0 or p0 <= 0 or p1 <= 0:
        return {
            "applicable": False,
            "period": period_name,
            "reason": "期初或期末 EPS ≤ 0 或股價異常，依規格不顯示獲利拆解",
            "p0": p0,
            "p1": p1,
            "eps0": eps0,
            "eps1": eps1
        }

    pe0 = p0 / eps0
    pe1 = p1 / eps1

    ln_p = math.log(p1 / p0)
    ln_eps = math.log(eps1 / eps0)
    ln_pe = math.log(pe1 / pe0)

    p_change_pct = round((p1 - p0) / p0 * 100.0, 2)
    eps_change_pct = round((eps1 - eps0) / eps0 * 100.0, 2)
    pe_change_pct = round((pe1 - pe0) / pe0 * 100.0, 2)

    # 貢獻百分比計算
    if abs(ln_p) < 1e-4:
        eps_contrib_pct = 50.0
        pe_contrib_pct = 50.0
        driver_desc = "本期股價基本持平"
    else:
        eps_contrib_pct = round((ln_eps / ln_p) * 100.0, 1)
        pe_contrib_pct = round((ln_pe / ln_p) * 100.0, 1)

        # 語意化解讀
        if p1 > p0:
            if eps_contrib_pct >= 50:
                driver_desc = f"股價上漲主要由公司基本面獲利成長驅動 (獲利貢獻 {eps_contrib_pct}%)"
            else:
                driver_desc = f"股價上漲主要由市場估值倍數擴張驅動 (倍數擴張貢獻 {pe_contrib_pct}%)"
        else:
            if eps_contrib_pct >= 50:
                driver_desc = f"股價下跌主要受公司基本面獲利衰退影響 (衰退影響 {eps_contrib_pct}%)"
            else:
                driver_desc = f"股價下跌主要受市場估值倍數收縮修正影響 (倍數收縮影響 {pe_contrib_pct}%)"

    return {
        "applicable": True,
        "period": period_name,
        "p0": round(p0, 2),
        "p1": round(p1, 2),
        "price_change_pct": p_change_pct,
        "eps0": round(eps0, 2),
        "eps1": round(eps1, 2),
        "eps_change_pct": eps_change_pct,
        "pe0": round(pe0, 2),
        "pe1": round(pe1, 2),
        "pe_change_pct": pe_change_pct,
        "ln_price_diff": round(ln_p, 4),
        "ln_eps_diff": round(ln_eps, 4),
        "ln_pe_diff": round(ln_pe, 4),
        "eps_contribution_pct": eps_contrib_pct,
        "pe_contribution_pct": pe_contrib_pct,
        "driver_summary": driver_desc
    }


def evaluate_valuation_extreme_flag(
    current_price: float,
    current_pe: Optional[float],
    current_eps: Optional[float],
    week52_high: float,
    week52_low: float,
    industry_median_pe: Optional[float] = None,
    is_cyclical: bool = False,
    sector_type: str = "general"
) -> Dict[str, Any]:
    """
    評估估值極端旗標 (規格書 6.9 & D-26)
    符合下列任一條件，顯示「獲利尚未支撐股價」警示條：
    1. 本益比 > 100 倍，或 > 同族群中位數的 3 倍。
    2. EPS ≤ 0，且股價位於近 52 週區間的上 20%。
    適用範圍：排除循環股與金融股
    """
    # 排除景氣循環股與金融股
    if is_cyclical or sector_type in ["cyclical", "financial"]:
        return {
            "flagged": False,
            "excluded": True,
            "reason": "循環股或金融股排除估值極端旗標判定",
            "message": None
        }

    reasons = []

    # 條件 1: 本益比極端偏高
    if current_pe is not None and current_pe > 0:
        if current_pe > 100.0:
            reasons.append(f"目前本益比 {current_pe:.1f} 倍 (> 100倍)")
        elif industry_median_pe is not None and industry_median_pe > 0 and current_pe > (3.0 * industry_median_pe):
            reasons.append(f"目前本益比 {current_pe:.1f} 倍 (> 同業中位數 {industry_median_pe:.1f} 倍之 3 倍)")

    # 條件 2: 虧損但股價處於高檔 (近 52 週上 20%)
    if current_eps is not None and current_eps <= 0:
        range_52 = week52_high - week52_low
        if range_52 > 0:
            pct_position = (current_price - week52_low) / range_52
            if pct_position >= 0.80:
                reasons.append(f"EPS 虧損 ({current_eps:.2f}元) 但股價處於 52 週前 20% 高檔區間")

    flagged = len(reasons) > 0

    return {
        "flagged": flagged,
        "excluded": False,
        "badge": "⚠️ 獲利尚未支撐股價" if flagged else None,
        "message": "；".join(reasons) if flagged else None,
        "notice": "※ 僅作為風險提示警示條，不改變河流圖價位區判定。可改用 P/S 進行同族群橫向比較。" if flagged else None
    }
