"""
價值投資選股 App - Good Company Engine (好公司檢驗引擎)
遵循技術規格書 V1.7 第 4 章：
- 4.1 核心定義 (獲利越來越好，避免價值陷阱)
- 4.2 六個面向判定燈號 (🟢 / 🟡 / 🔴 / ⚪)
- 4.3 整體好公司三態判定 (good / watch / degraded / insufficient)
- 4.4 金融股與特殊情況處理
- 4.5 可解釋性面板與入選徽章生成 (純規則模板，零 LLM)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal

LightColor = Literal["green", "yellow", "red", "gray"]
OverallStatus = Literal["good", "watch", "degraded", "insufficient"]

@dataclass(frozen=True)
class DimensionResult:
    name_zh: str
    light: LightColor
    value_display: str
    explanation: str

@dataclass(frozen=True)
class GoodCompanyResult:
    ticker: str
    overall: OverallStatus
    overall_name_zh: str
    revenue_light: LightColor
    eps_light: LightColor
    margin_light: LightColor
    efficiency_light: LightColor
    cashflow_light: LightColor
    growth_or_dividend_light: LightColor
    dimensions: List[DimensionResult]
    reasons: List[str]            # 可解釋正面原因 (✓)
    warnings: List[str]           # 可解釋警戒提醒 (⚠)
    badges: List[str]             # 入選徽章代碼 (good, cheap, capex, contract, rev_up, eps_up)


def evaluate_revenue_dimension(
    cumulative_yoy: float,
    recent_4q_yoys: List[float],
    cagr_3y: Optional[float] = None
) -> DimensionResult:
    """面向 1：營收檢驗"""
    pos_quarters = sum(1 for y in recent_4q_yoys if y > 0)
    
    if cumulative_yoy > 0 and pos_quarters >= 3:
        light: LightColor = "green"
        exp = f"累計營收 YoY 成長 {cumulative_yoy*100:.1f}%，近 4 季中有 {pos_quarters} 季正成長"
    elif cumulative_yoy > -0.05 and pos_quarters >= 2:
        light = "yellow"
        exp = f"營收成長動能趨緩，累計 YoY {cumulative_yoy*100:.1f}%"
    else:
        light = "red"
        exp = f"營收衰退，累計 YoY {cumulative_yoy*100:.1f}%，近 4 季僅 {pos_quarters} 季正成長"

    val_str = f"累計 YoY {cumulative_yoy*100:+.1f}%"
    return DimensionResult(name_zh="營收動能", light=light, value_display=val_str, explanation=exp)


def evaluate_eps_dimension(
    annual_eps_3y: List[float],       # 近 3 年年 EPS (由舊到新)
    estimated_eps_current: Optional[float],
    estimated_eps_next: Optional[float] = None
) -> DimensionResult:
    """面向 2：獲利 (EPS) 檢驗"""
    if len(annual_eps_3y) < 3:
        return DimensionResult(
            name_zh="獲利成長",
            light="gray",
            value_display="資料不足",
            explanation="上市歷史未滿 3 年，無法評估長年獲利趨勢"
        )

    e1, e2, e3 = annual_eps_3y[-3], annual_eps_3y[-2], annual_eps_3y[-1]
    is_3y_growing = (e3 > e2) and (e2 > e1)
    
    # 預估是否成長
    forecast_growing = (estimated_eps_current is not None) and (estimated_eps_current >= e3)

    if is_3y_growing and forecast_growing:
        light: LightColor = "green"
        exp = f"近 3 年 EPS 逐年增長 ({e1:.2f} → {e2:.2f} → {e3:.2f})，且預估持續成長"
    elif (e3 >= e2 or forecast_growing) and e3 > 0:
        light = "yellow"
        exp = f"獲利維持正向但有波動 ({e1:.2f} → {e2:.2f} → {e3:.2f})"
    else:
        light = "red"
        exp = f"獲利連續衰退或由盈轉虧 ({e1:.2f} → {e2:.2f} → {e3:.2f})"

    val_str = f"近3年: {e3:.2f} 元"
    return DimensionResult(name_zh="獲利成長", light=light, value_display=val_str, explanation=exp)


def evaluate_margins_dimension(
    gross_margins: List[float],
    operating_margins: List[float],
    net_margins: List[float],
    is_financial: bool = False
) -> DimensionResult:
    """面向 3：三率檢驗 (毛利率、營益率、淨利率近 4 季趨勢)"""
    if is_financial:
        return DimensionResult(
            name_zh="三率趨勢",
            light="gray",
            value_display="金融股不適用",
            explanation="金融業無毛利率概念，改以淨值與 ROE 衡量"
        )

    if len(gross_margins) < 4:
        return DimensionResult(
            name_zh="三率趨勢",
            light="gray",
            value_display="資料不足",
            explanation="季報數據未滿 4 季"
        )

    # 檢查毛利率連續下滑
    gm = gross_margins[-4:]
    om = operating_margins[-4:]
    nm = net_margins[-4:]

    gm_declining = gm[3] < gm[2] < gm[1]
    om_declining = om[3] < om[2] < om[1]
    nm_declining = nm[3] < nm[2] < nm[1]

    decline_count = sum([gm_declining, om_declining, nm_declining])

    if decline_count >= 2:
        light: LightColor = "red"
        exp = "三率中多項指標呈現連續 2 季以上顯著下滑，利潤率受侵蝕"
    elif decline_count == 1:
        light = "yellow"
        exp = "部分利潤率指標出現連續下滑趨勢，需密切關注"
    else:
        light = "green"
        exp = f"三率走勢穩健 (最新毛利率 {gm[-1]*100:.1f}%，營益率 {om[-1]*100:.1f}%)"

    val_str = f"毛利 {gm[-1]*100:.1f}% / 營益 {om[-1]*100:.1f}%"
    return DimensionResult(name_zh="三率趨勢", light=light, value_display=val_str, explanation=exp)


def evaluate_efficiency_dimension(
    roe: float,
    roic: Optional[float] = None,
    is_financial: bool = False
) -> DimensionResult:
    """面向 4：資本效率 (ROE / ROIC)"""
    threshold = 8.0 if is_financial else 10.0

    if roe >= threshold:
        light: LightColor = "green"
        exp = f"ROE 達 {roe:.1f}%，優於標準 ({threshold}%)，資本回報率優秀"
    elif roe >= 5.0:
        light = "yellow"
        exp = f"ROE 為 {roe:.1f}%，維持在合理水準"
    else:
        light = "red"
        exp = f"ROE 僅 {roe:.1f}%，低於 5.0%，資本使用效率低落"

    val_str = f"ROE {roe:.1f}%"
    return DimensionResult(name_zh="資本效率", light=light, value_display=val_str, explanation=exp)


def evaluate_cashflow_dimension(
    operating_cf_4q: List[float],
    free_cf_4q: List[float]
) -> DimensionResult:
    """面向 5：現金流檢驗 (營業現金流 OCF 與 自由現金流 FCF)"""
    if len(operating_cf_4q) < 4 or len(free_cf_4q) < 4:
        return DimensionResult(
            name_zh="現金流量",
            light="gray",
            value_display="資料不足",
            explanation="現金流數據未滿 4 季"
        )

    sum_ocf = sum(operating_cf_4q[-4:])
    sum_fcf = sum(free_cf_4q[-4:])

    if sum_ocf > 0 and sum_fcf > 0:
        light: LightColor = "green"
        exp = "近 4 季營業現金流與自由現金流皆充沛為正，獲利含金量高"
    elif sum_ocf > 0 and sum_fcf <= 0:
        light = "yellow"
        exp = "營業現金流為正，但因資本支出投入使自由現金流暫時為負"
    else:
        light = "red"
        exp = "營業現金流為負，獲利未能有效轉化為真金白銀，需嚴防資金鏈"

    val_str = f"OCF > 0" if sum_ocf > 0 else "OCF < 0"
    return DimensionResult(name_zh="現金流量", light=light, value_display=val_str, explanation=exp)


def evaluate_growth_or_dividend_dimension(
    capex_growth_pct: Optional[float] = None,
    revenue_growth_sync: bool = True,
    payout_ratio: Optional[float] = None,
    fcf_covers_dividend: bool = True
) -> DimensionResult:
    """面向 6：未來成長 (擴產) 或 股利安全"""
    # 若有顯著資本支出擴產資料
    if capex_growth_pct is not None and capex_growth_pct >= 20.0:
        if revenue_growth_sync:
            return DimensionResult(
                name_zh="擴產動能",
                light="green",
                value_display=f"擴產季增 +{capex_growth_pct:.1f}%",
                explanation="資本支出大幅季增超過 20% 且營收維持同步增長，具擴產動能"
            )
        else:
            return DimensionResult(
                name_zh="擴產動能",
                light="yellow",
                value_display=f"擴產 +{capex_growth_pct:.1f}% (待觀察)",
                explanation="資本支出擴張，但營收成長尚未同步跟上，持續追蹤效益"
            )

    # 檢查股利安全 (高股息防呆)
    if payout_ratio is not None:
        if payout_ratio > 100.0 or not fcf_covers_dividend:
            return DimensionResult(
                name_zh="股利安全",
                light="red",
                value_display=f"配發率 {payout_ratio:.0f}%",
                explanation="配息率超過 100% 或自由現金流無法覆蓋股利，存在高股息陷阱風險"
            )
        else:
            return DimensionResult(
                name_zh="股利安全",
                light="green",
                value_display=f"配發率 {payout_ratio:.0f}%",
                explanation="股利配發率健康且現金流足以支應配息"
            )

    return DimensionResult(
        name_zh="成長展望",
        light="green",
        value_display="穩定持平",
        explanation="資本支出與股利政策維持穩健態勢"
    )


def evaluate_good_company(
    ticker: str,
    dim_revenue: DimensionResult,
    dim_eps: DimensionResult,
    dim_margin: DimensionResult,
    dim_efficiency: DimensionResult,
    dim_cashflow: DimensionResult,
    dim_growth_div: DimensionResult,
    previously_good: bool = True,
    is_in_buy_zone: bool = False
) -> GoodCompanyResult:
    """
    依 4.3 進行整體好公司三態判定：
    - good (好公司): 面向 1、2 皆須 🟢，且其餘面向不得有 🔴
    - watch (持續觀察): 未符合 good，但非 degraded
    - degraded (基本面退化): 原本為好公司，但出現面向 1 或 2 為 🔴，或有 2 個以上面向 🔴
    - insufficient (資料不足): 關鍵面向為 gray
    """
    dims = [dim_revenue, dim_eps, dim_margin, dim_efficiency, dim_cashflow, dim_growth_div]
    red_count = sum(1 for d in dims if d.light == "red")
    gray_count = sum(1 for d in dims if d.light == "gray")

    reasons: List[str] = []
    warnings: List[str] = []
    badges: List[str] = []

    # 收集正面理由與警戒
    if dim_revenue.light == "green":
        reasons.append("✓ 營收 YoY 上升")
        badges.append("rev_up")
    elif dim_revenue.light == "red":
        warnings.append("⚠ 營收累計持續衰退")

    if dim_eps.light == "green":
        reasons.append("✓ EPS 連續成長")
        badges.append("eps_up")
    elif dim_eps.light == "red":
        warnings.append("⚠ EPS 獲利衰退")

    if dim_margin.light == "green":
        reasons.append("✓ 毛利率與利潤率改善")
    elif dim_margin.light == "red":
        warnings.append("⚠ 三率多項連續下滑")

    if dim_efficiency.light == "green":
        reasons.append("✓ ROE 資本效率維持優良")
    elif dim_efficiency.light == "red":
        warnings.append("⚠ 資本效率 ROE 偏低")

    if dim_cashflow.light == "green":
        reasons.append("✓ 自由現金流充沛")
    elif dim_cashflow.light == "red":
        warnings.append("⚠ 營業現金流轉負")

    if dim_growth_div.name_zh == "擴產動能" and dim_growth_div.light == "green":
        badges.append("capex")
        reasons.append("✓ 資本支出大擴產")
    elif dim_growth_div.light == "red":
        warnings.append("⚠ 配息率過高或現金流不足覆蓋")

    # 4.3 三態判定邏輯
    if gray_count >= 3 or dim_revenue.light == "gray" or dim_eps.light == "gray" or dim_cashflow.light == "gray":
        overall: OverallStatus = "insufficient"
        overall_zh = "資料不足"
    elif dim_revenue.light == "green" and dim_eps.light == "green" and red_count == 0:
        overall = "good"
        overall_zh = "好公司"
        badges.insert(0, "good")
    elif previously_good and (dim_revenue.light == "red" or dim_eps.light == "red" or red_count >= 2):
        overall = "degraded"
        overall_zh = "基本面退化"
    else:
        overall = "watch"
        overall_zh = "持續觀察"

    if is_in_buy_zone:
        badges.append("cheap")
        reasons.append("✓ 現價進入便宜/特價研究區")

    # 確保徽章代碼去重
    unique_badges = list(dict.fromkeys(badges))

    return GoodCompanyResult(
        ticker=ticker,
        overall=overall,
        overall_name_zh=overall_zh,
        revenue_light=dim_revenue.light,
        eps_light=dim_eps.light,
        margin_light=dim_margin.light,
        efficiency_light=dim_efficiency.light,
        cashflow_light=dim_cashflow.light,
        growth_or_dividend_light=dim_growth_div.light,
        dimensions=dims,
        reasons=reasons,
        warnings=warnings,
        badges=unique_badges
    )
