"""
價值投資選股 App - Leading Signals Engine (領先訊號引擎)
遵循技術規格書 V1.7 第 14 章：
- 14.1 領先訊號定位 (補足財報落後指標問題)
- 14.2 基礎版八大訊號判定 (L1 至 L8)
- 14.3 景氣循環股與金融股特殊處理
- 14.4 領先狀態彙整 (strengthening, weakening, neutral, insufficient)
- 14.5 輸出標準化燈號與高中生白話說明
"""

from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any

SignalLight = Literal["green", "yellow", "red", "gray"]
OverallLeadingStatus = Literal["strengthening", "neutral", "weakening", "insufficient"]

@dataclass(frozen=True)
class SingleSignalResult:
    signal_id: str           # "L1" ~ "L8"
    name_zh: str             # "月營收加速度", "合約負債", 等
    category: str            # "基本面領先" | "籌碼領先" | "技術與訊息"
    light: SignalLight
    value_display: str
    plain_explanation: str   # 高中生看得懂的白話說明


@dataclass(frozen=True)
class LeadingSummaryResult:
    ticker: str
    status: OverallLeadingStatus
    status_name_zh: str
    green_count: int
    yellow_count: int
    red_count: int
    gray_count: int
    signals: List[SingleSignalResult]
    explanation: str


def evaluate_l1_revenue_accel(
    monthly_yoys_12m: List[float],
    accel_diff_threshold: float = 0.05
) -> SingleSignalResult:
    """L1: 月營收加速度"""
    if len(monthly_yoys_12m) < 6:
        return SingleSignalResult(
            signal_id="L1",
            name_zh="月營收加速度",
            category="基本面領先",
            light="gray",
            value_display="資料不足",
            plain_explanation="歷史營收不足 6 個月，無法計算加速度"
        )

    # 近 3 個月與近 12 個月平均
    m3 = sum(monthly_yoys_12m[-3:]) / 3.0
    m12 = sum(monthly_yoys_12m) / len(monthly_yoys_12m)
    
    # 是否連續 3 個月上升
    y3, y2, y1 = monthly_yoys_12m[-1], monthly_yoys_12m[-2], monthly_yoys_12m[-3]
    is_consec_up = y3 > y2 > y1
    is_consec_down = y3 < y2 < y1

    diff = m3 - m12
    if diff >= accel_diff_threshold or is_consec_up:
        light: SignalLight = "green"
        exp = f"營收加速衝刺！近 3 個月年增率平均 {m3*100:+.1f}%，比近 12 個月平均多出 {diff*100:+.1f}%"
    elif diff <= -accel_diff_threshold or is_consec_down:
        light = "red"
        exp = f"營收動能減速！近 3 個月年增率平均 {m3*100:+.1f}%，明顯低於過去常態"
    else:
        light = "yellow"
        exp = f"營收維持平穩步伐，近 3 個月年增率 {m3*100:+.1f}%"

    return SingleSignalResult(
        signal_id="L1",
        name_zh="月營收加速度",
        category="基本面領先",
        light=light,
        value_display=f"近3月 {m3*100:+.1f}%",
        plain_explanation=exp
    )


def evaluate_l2_contract_liabilities(
    contract_liabilities_quarterly: List[float]
) -> SingleSignalResult:
    """L2: 合約負債（客戶預付款）"""
    if len(contract_liabilities_quarterly) < 3:
        return SingleSignalResult(
            signal_id="L2",
            name_zh="合約負債",
            category="基本面領先",
            light="gray",
            value_display="資料不足",
            plain_explanation="季報合約負債數據不足"
        )

    c = contract_liabilities_quarterly
    is_2q_up = c[-1] > c[-2] > c[-3]
    is_all_time_high = c[-1] == max(c)

    if is_2q_up and is_all_time_high:
        light: SignalLight = "green"
        exp = "客戶訂金大增且創新高！合約負債連續 2 季成長，代表未來營收有望認列"
    elif c[-1] < c[-2] < c[-3]:
        light = "red"
        exp = "客戶訂單與預收款連續 2 季顯著減少，後續訂單動能需警戒"
    else:
        light = "yellow"
        exp = f"合約負債維持正常波動水準 ({c[-1]:.1f} 億元)"

    return SingleSignalResult(
        signal_id="L2",
        name_zh="合約負債",
        category="基本面領先",
        light=light,
        value_display=f"{c[-1]:.1f} 億元",
        plain_explanation=exp
    )


def evaluate_l3_inventory_vs_revenue(
    inventory_yoy: float,
    revenue_yoy: float,
    is_cyclical: bool = False
) -> SingleSignalResult:
    """L3: 存貨與營收關係"""
    diff = inventory_yoy - revenue_yoy

    if inventory_yoy < revenue_yoy:
        light: SignalLight = "green"
        exp = "庫存去化良好！貨賣得比堆得快 (營收增幅高於存貨)"
    elif diff >= 0.15:  # 存貨增速超過營收 15 個百分點
        light = "red"
        exp = "注意庫存堆積！存貨增長速度大幅超過產品銷售營收"
    else:
        light = "yellow"
        exp = "存貨與營收增長步伐大致相當"

    return SingleSignalResult(
        signal_id="L3",
        name_zh="存貨健康度",
        category="基本面領先",
        light=light,
        value_display=f"存貨 {inventory_yoy*100:+.1f}% vs 營收 {revenue_yoy*100:+.1f}%",
        plain_explanation=exp
    )


def evaluate_l4_capex_growth(
    capex_quarterly_growth: float,
    revenue_growing: bool
) -> SingleSignalResult:
    """L4: 資本支出與擴產"""
    if capex_quarterly_growth >= 0.20 and revenue_growing:
        light: SignalLight = "green"
        exp = f"大舉擴產！資本支出季增達 {capex_quarterly_growth*100:+.1f}%，且營收同步走升"
    elif capex_quarterly_growth <= -0.20 and not revenue_growing:
        light = "red"
        exp = "投資緊縮且營收疲弱，公司擴張態度轉趨保守"
    else:
        light = "yellow"
        exp = f"資本支出正常投入 (季增 {capex_quarterly_growth*100:+.1f}%)"

    return SingleSignalResult(
        signal_id="L4",
        name_zh="擴產動能",
        category="基本面領先",
        light=light,
        value_display=f"季增 {capex_quarterly_growth*100:+.1f}%",
        plain_explanation=exp
    )


def evaluate_l5_insider_holding(
    insider_diff_pct: float
) -> SingleSignalResult:
    """L5: 內部人與大股東持股"""
    if insider_diff_pct > 0.5:
        light: SignalLight = "green"
        exp = f"最懂公司的人在加碼！內部董監持股增加 {insider_diff_pct:+.1f}%"
    elif insider_diff_pct < -0.5:
        light = "red"
        exp = f"內部董監持股減少 {insider_diff_pct:+.1f}%，需留意大股東動態"
    else:
        light = "yellow"
        exp = "董監內部人持股維持穩定"

    return SingleSignalResult(
        signal_id="L5",
        name_zh="內部人籌碼",
        category="籌碼領先",
        light=light,
        value_display=f"月變動 {insider_diff_pct:+.1f}%",
        plain_explanation=exp
    )


def evaluate_l6_institutional_funds(
    foreign_net_20d: float,
    trust_net_20d: float
) -> SingleSignalResult:
    """L6: 法人資金 (外資與投信近 20 日累計)"""
    if foreign_net_20d > 0 and trust_net_20d > 0:
        light: SignalLight = "green"
        exp = "土洋法人同步作多！外資與投信近 20 日皆站在大額買方"
    elif foreign_net_20d < 0 and trust_net_20d < 0:
        light = "red"
        exp = "法人資金同步撤出，外資與投信近期雙雙持續賣超"
    else:
        light = "yellow"
        exp = "法人動向分歧 (一方買進、一方賣出)，土洋對作中"

    return SingleSignalResult(
        signal_id="L6",
        name_zh="法人籌碼",
        category="籌碼領先",
        light=light,
        value_display=f"外資 {foreign_net_20d:+.0f} / 投信 {trust_net_20d:+.0f}",
        plain_explanation=exp
    )


def evaluate_l7_kd_strength(
    month_k: float,
    month_d: float,
    is_golden_cross: bool,
    is_death_cross: bool
) -> SingleSignalResult:
    """L7: 月 KD 與位階"""
    if is_golden_cross and month_k <= 35.0:
        light: SignalLight = "green"
        exp = f"長線轉折訊號出現！月 KD 在低檔 ({month_k:.1f}) 出現黃金交叉"
    elif is_death_cross and month_k >= 75.0:
        light = "red"
        exp = f"長線過熱警戒！月 KD 在高檔 ({month_k:.1f}) 出現死亡交叉"
    else:
        light = "yellow"
        exp = f"月 KD 數值為 K: {month_k:.1f} / D: {month_d:.1f}"

    return SingleSignalResult(
        signal_id="L7",
        name_zh="月度技術位階",
        category="技術與訊息",
        light=light,
        value_display=f"月KD {month_k:.0f}/{month_d:.0f}",
        plain_explanation=exp
    )


def evaluate_l8_material_keywords(
    recent_announcements: List[str]
) -> SingleSignalResult:
    """L8: 重大訊息關鍵字"""
    positive_keywords = ["擴廠", "上修", "大單", "獲利創高", "擴產", "增資"]
    negative_keywords = ["下修", "虧損", "裁員", "減產", "違約", "退票"]

    pos_hit = any(kw in text for kw in positive_keywords for text in recent_announcements)
    neg_hit = any(kw in text for kw in negative_keywords for text in recent_announcements)

    if pos_hit and not neg_hit:
        light: SignalLight = "green"
        exp = "近期公告出現擴廠、上修或大單等正向營運訊息"
    elif neg_hit:
        light = "red"
        exp = "注意！近期公告出現下修、虧損或減產等負面警示關鍵字"
    else:
        light = "yellow"
        exp = "近期無重大特定關鍵字公告"

    return SingleSignalResult(
        signal_id="L8",
        name_zh="重大訊息",
        category="技術與訊息",
        light=light,
        value_display="正向" if pos_hit else ("警示" if neg_hit else "持平"),
        plain_explanation=exp
    )


def summarize_leading_signals(
    ticker: str,
    signals: List[SingleSignalResult]
) -> LeadingSummaryResult:
    """
    依 14.4 彙整領先訊號狀態：
    - strengthening (轉強): 🟢 >= 3 且 🔴 = 0
    - weakening (轉弱): 🔴 >= 2
    - insufficient: ⚪ 過半 (>= 4)
    - neutral (中性): 其他
    """
    green_count = sum(1 for s in signals if s.light == "green")
    yellow_count = sum(1 for s in signals if s.light == "yellow")
    red_count = sum(1 for s in signals if s.light == "red")
    gray_count = sum(1 for s in signals if s.light == "gray")

    if gray_count >= 4:
        status: OverallLeadingStatus = "insufficient"
        status_zh = "資料不足"
        exp = "超過半數領先指標缺乏足夠歷史數據"
    elif green_count >= 3 and red_count == 0:
        status = "strengthening"
        status_zh = "訊號轉強"
        exp = f"具備多重領先轉強訊號 (🟢 {green_count} 項，無轉弱項)"
    elif red_count >= 2:
        status = "weakening"
        status_zh = "訊號轉弱"
        exp = f"出現基本面或籌碼疲弱訊號 (🔴 {red_count} 項)，宜謹慎觀察"
    else:
        status = "neutral"
        status_zh = "中性整理"
        exp = f"領先指標多空互見 (🟢 {green_count} / 🟡 {yellow_count} / 🔴 {red_count})"

    return LeadingSummaryResult(
        ticker=ticker,
        status=status,
        status_name_zh=status_zh,
        green_count=green_count,
        yellow_count=yellow_count,
        red_count=red_count,
        gray_count=gray_count,
        signals=signals,
        explanation=exp
    )
