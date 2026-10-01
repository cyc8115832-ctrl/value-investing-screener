"""
價值投資選股 App - 綜合好公司體質指數評分引擎 (company_score.py)
嚴格落實技術規格書 V1.7 第 18 章（綜合好公司指數）：
- 將好公司六大面向（營收、EPS、三率毛利、資本回報、現金流、擴產股利）權重化評分
- 滿分為 100 分，輸出五級評等 (AAA 卓越、AA 穩健、A 觀察、B 偏弱、C 退化)
- 產出六向度維度雷達分，利於視覺化呈現
"""

from typing import Dict, Any


def score_dimension(light: str, max_points: float) -> float:
    """單向度燈號給分 (綠燈滿分、黃/灰燈中位、紅燈 0 分)"""
    l = (light or "gray").lower()
    if l == "green":
        return max_points
    elif l in ["yellow", "gray"]:
        return round(max_points * 0.5, 1)
    elif l == "red":
        return 0.0
    return round(max_points * 0.5, 1)


def calculate_composite_company_score(
    revenue_light: str,
    eps_light: str,
    margin_light: str,
    efficiency_light: str,
    cashflow_light: str,
    growth_light: str,
    is_cyclical: bool = False,
    is_financial: bool = False
) -> Dict[str, Any]:
    """
    計算綜合好公司體質分數 (0 ~ 100 分)
    """
    # 權重分配
    # 營收 20, EPS 20, 三率 15, ROE 15, 現金流 15, 擴產股利 15
    pts_rev = score_dimension(revenue_light, 20.0)
    pts_eps = score_dimension(eps_light, 20.0)
    pts_margin = score_dimension(margin_light, 15.0)
    pts_eff = score_dimension(efficiency_light, 15.0)
    pts_cf = score_dimension(cashflow_light, 15.0)
    pts_growth = score_dimension(growth_light, 15.0)

    total_score = round(pts_rev + pts_eps + pts_margin + pts_eff + pts_cf + pts_growth, 1)

    # 等級評定
    if total_score >= 85.0:
        grade = "AAA"
        grade_desc = "卓越核心"
        color = "#00F59B"  # 翡翠綠
    elif total_score >= 70.0:
        grade = "AA"
        grade_desc = "穩健優良"
        color = "#38BDF8"  # 淺天藍
    elif total_score >= 55.0:
        grade = "A"
        grade_desc = "觀察持平"
        color = "#FBBF24"  # 琥珀金
    elif total_score >= 40.0:
        grade = "B"
        grade_desc = "偏弱警示"
        color = "#FB923C"  # 橘色
    else:
        grade = "C"
        grade_desc = "基本面退化"
        color = "#FF5252"  # 亮紅

    return {
        "total_score": total_score,
        "max_score": 100.0,
        "grade": grade,
        "grade_desc": grade_desc,
        "color": color,
        "summary": f"{grade} {grade_desc} ({total_score}分 / 100分)",
        "dimension_scores": {
            "revenue": {"name": "營收動能", "score": pts_rev, "max": 20.0, "light": revenue_light},
            "eps": {"name": "獲利成長", "score": pts_eps, "max": 20.0, "light": eps_light},
            "margin": {"name": "三率毛利", "score": pts_margin, "max": 15.0, "light": margin_light},
            "efficiency": {"name": "資本回報", "score": pts_eff, "max": 15.0, "light": efficiency_light},
            "cashflow": {"name": "自由現金流", "score": pts_cf, "max": 15.0, "light": cashflow_light},
            "growth": {"name": "擴產與股利", "score": pts_growth, "max": 15.0, "light": growth_light}
        }
    }
