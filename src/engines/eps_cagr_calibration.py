"""
價值投資選股 App - EPS 長期複合成長率 (CAGR) 與歷史預估偏差校準引擎
遵循技術規格書 V1.7 第 5 章 (§5.4 長期情境 EPS) 與第 6 章 (§6.8c 歷史複合成長率校準):

核心功能：
1. calculate_eps_cagr: 計算歷史 3 年與 5 年 EPS 複合成長率 (CAGR)，對 EPS <= 0 與極端波動進行防呆鉗制。
2. evaluate_forecast_calibration: 滾動比對歷史預估 EPS 與實際公告 EPS 之偏差，計算 MAPE (平均絕對百分比誤差)、信心指數 (Confidence Score) 與可信度評等。
3. project_multi_year_eps_scenarios: 結合複合成長率與本益比估值錨點，推估未來 3 年與 5 年在保守/基準/樂觀情境下之目標 EPS 與潛在目標價位。

本模組為純函式 (Pure Functions)，無外部副作用，易於單元測試。
"""

import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class EPSCagrResult:
    cagr_3y: Optional[float]           # 3 年 EPS 複合成長率 (如 0.15 代表 15.0%)
    cagr_5y: Optional[float]           # 5 年 EPS 複合成長率
    effective_growth_rate: float      # 用於估值之有效保守成長率 (百分點如 15.0，上限 25.0%，負成長鉗制為 0%)
    is_growth_steady: bool             # 是否為連續正成長
    growth_quality_desc: str           # 成長品質說明 (如 "強勁穩健成長", "溫和成長", "獲利波動大", "虧損修復中")
    historical_points: List[Dict[str, Any]] # 歷年 EPS 明細


@dataclass(frozen=True)
class ForecastCalibrationItem:
    year: int                          # 預估年度 (如 2024)
    estimated_eps: float               # 當時預估 EPS
    actual_eps: float                  # 實際公佈 EPS
    error_amount: float                # 偏差金額 (estimated - actual)
    error_pct: float                   # 偏差百分比 ((estimated - actual) / actual * 100)
    abs_error_pct: float               # 絕對偏差百分比


@dataclass(frozen=True)
class ForecastCalibrationSummary:
    has_sufficient_history: bool       # 是否有足夠比對紀錄 (>= 2 年)
    comparison_count: int              # 比對樣本數
    mape: float                        # 平均絕對百分比誤差 (%)
    confidence_score: float            # 可信度評分 (0 ~ 100)
    confidence_grade: str              # "high" (高可信) | "moderate" (中等可信) | "volatile" (預估波動大)
    confidence_grade_zh: str           # 中文評級
    bias_direction: str                # "overestimate" (傾向偏高) | "underestimate" (傾向保守) | "balanced" (精準對齊)
    bias_desc: str                     # 偏差特徵白話描述
    calibration_details: List[Dict[str, Any]] # 各年度比對明細


@dataclass(frozen=True)
class MultiYearProjectionScenario:
    scenario_type: str                 # "conservative" | "base" | "optimistic"
    scenario_name_zh: str              # "保守情境" | "基準情境" | "樂觀情境"
    growth_rate_used_pct: float        # 採用之年增長率 (%)
    projected_eps_3y: float            # 未來第 3 年推估 EPS
    projected_price_3y: float          # 未來第 3 年目標價 (EPS * target_pe)
    projected_eps_5y: float            # 未來第 5 年推估 EPS
    projected_price_5y: float          # 未來第 5 年目標價
    upside_pct_3y: float               # 距現價 3 年潛在空間 (%)
    upside_pct_5y: float               # 距現價 5 年潛在空間 (%)


@dataclass(frozen=True)
class EPSMultiYearProjectionResult:
    current_price: float
    current_eps: float
    target_pe: float
    scenarios: List[MultiYearProjectionScenario]


def calculate_eps_cagr(
    yearly_eps_records: List[Dict[str, Any]],
    max_growth_cap: float = 0.25
) -> EPSCagrResult:
    """
    計算歷史 3 年與 5 年 EPS 複合成長率 (CAGR)。
    yearly_eps_records 格式: [{"year": 2021, "eps": 10.5}, {"year": 2022, "eps": 12.0}, ...]
    按照年份由舊到新排序。
    公式: CAGR = (EPS_end / EPS_start) ** (1 / n) - 1
    防呆與保守規則:
    - 若 EPS_start <= 0 或 EPS_end <= 0，CAGR 視為不可算 (None)，標記為虧損或轉虧為盈。
    - effective_growth_rate: 取 3 年 CAGR (若無則取 5 年)，轉換為百分點，並依規格書 6.8c 設上限 (預設 25%)，且下限為 0%。
    """
    sorted_records = sorted(
        [r for r in yearly_eps_records if "year" in r and "eps" in r and r["eps"] is not None],
        key=lambda x: x["year"]
    )

    n_years = len(sorted_records)
    if n_years < 2:
        return EPSCagrResult(
            cagr_3y=None,
            cagr_5y=None,
            effective_growth_rate=0.0,
            is_growth_steady=False,
            growth_quality_desc="歷史年度 EPS 資料不足（需至少 2 年）",
            historical_points=sorted_records
        )

    # 檢查是否連續正成長
    eps_values = [r["eps"] for r in sorted_records]
    is_growth_steady = all(
        eps_values[i] > eps_values[i - 1] and eps_values[i - 1] > 0
        for i in range(1, len(eps_values))
    )

    def _calc_cagr(end_idx: int, span: int) -> Optional[float]:
        start_idx = end_idx - span
        if start_idx < 0:
            return None
        start_eps = sorted_records[start_idx]["eps"]
        end_eps = sorted_records[end_idx]["eps"]
        if start_eps <= 0 or end_eps <= 0:
            return None
        try:
            return math.pow(end_eps / start_eps, 1.0 / span) - 1.0
        except (ValueError, ZeroDivisionError):
            return None

    last_idx = n_years - 1
    cagr_3y = _calc_cagr(last_idx, 3)
    cagr_5y = _calc_cagr(last_idx, 5)

    # 決定有效成長率 (百分點計)
    primary_cagr = cagr_3y if cagr_3y is not None else cagr_5y
    if primary_cagr is not None and primary_cagr > 0:
        raw_pct = primary_cagr * 100.0
        effective_pct = min(raw_pct, max_growth_cap * 100.0)
    else:
        effective_pct = 0.0

    # 評估品質說明
    if any(e <= 0 for e in eps_values):
        growth_quality_desc = "歷史年度曾有虧損，成長率受非經常波動干擾"
    elif cagr_3y is not None and cagr_3y >= 0.15 and is_growth_steady:
        growth_quality_desc = f"強勁穩健成長（3年複合成長 {cagr_3y*100:.1f}%，年年成長）"
    elif cagr_3y is not None and cagr_3y >= 0.08:
        growth_quality_desc = f"溫和穩健成長（3年複合成長 {cagr_3y*100:.1f}%）"
    elif cagr_3y is not None and cagr_3y >= 0.0:
        growth_quality_desc = f"獲利持平盤整（3年複合成長 {cagr_3y*100:.1f}%）"
    elif cagr_3y is not None and cagr_3y < 0.0:
        growth_quality_desc = f"獲利呈現衰退（3年複合成長 {cagr_3y*100:.1f}%，宜保守謹慎）"
    elif cagr_5y is not None and cagr_5y > 0:
        growth_quality_desc = f"長期 5 年複合成長 {cagr_5y*100:.1f}%"
    else:
        growth_quality_desc = "成長軌跡波動較大或處於產業景氣調整期"

    return EPSCagrResult(
        cagr_3y=round(cagr_3y, 4) if cagr_3y is not None else None,
        cagr_5y=round(cagr_5y, 4) if cagr_5y is not None else None,
        effective_growth_rate=round(effective_pct, 2),
        is_growth_steady=is_growth_steady,
        growth_quality_desc=growth_quality_desc,
        historical_points=sorted_records
    )


def evaluate_forecast_calibration(
    forecast_vs_actual: List[Dict[str, Any]]
) -> ForecastCalibrationSummary:
    """
    比對歷史預估 EPS 與實際公佈 EPS 之偏差與可信度校準。
    forecast_vs_actual 格式:
    [{"year": 2023, "estimated_eps": 32.5, "actual_eps": 31.8}, ...]
    公式:
    error_pct = (estimated - actual) / actual * 100
    MAPE = 平均(|error_pct|)
    confidence_score = max(0, min(100, 100 - MAPE))
    等級劃分:
    - MAPE <= 10%: high (高可信度，預估偏差小)
    - 10% < MAPE <= 20%: moderate (中等可信度，具常態預測參考性)
    - MAPE > 20%: volatile (偏差波動大，需提高安全邊際)
    """
    valid_items: List[ForecastCalibrationItem] = []
    over_count = 0
    under_count = 0

    for item in sorted(forecast_vs_actual, key=lambda x: x.get("year", 0)):
        y = item.get("year")
        est = item.get("estimated_eps")
        act = item.get("actual_eps")

        if y is None or est is None or act is None:
            continue
        if act <= 0 or est <= 0:
            continue

        err = est - act
        err_pct = (err / act) * 100.0
        abs_err_pct = abs(err_pct)

        if err > 0:
            over_count += 1
        elif err < 0:
            under_count += 1

        valid_items.append(ForecastCalibrationItem(
            year=int(y),
            estimated_eps=round(float(est), 2),
            actual_eps=round(float(act), 2),
            error_amount=round(float(err), 2),
            error_pct=round(float(err_pct), 2),
            abs_error_pct=round(float(abs_err_pct), 2)
        ))

    n = len(valid_items)
    if n < 1:
        return ForecastCalibrationSummary(
            has_sufficient_history=False,
            comparison_count=0,
            mape=0.0,
            confidence_score=70.0,
            confidence_grade="moderate",
            confidence_grade_zh="尚無足夠比對歷史",
            bias_direction="balanced",
            bias_desc="本標的尚無足夠之歷史年度「預估 vs 實際」比對數據。",
            calibration_details=[]
        )

    mape = sum(i.abs_error_pct for i in valid_items) / float(n)
    confidence_score = max(0.0, min(100.0, 100.0 - mape))

    # 偏差傾向
    if over_count > under_count and (over_count / n) >= 0.6:
        bias_direction = "overestimate"
        bias_desc = f"歷史預估模型傾向偏樂觀（高於實際），建議實務上扣減 5%~10% 作為安全邊際"
    elif under_count > over_count and (under_count / n) >= 0.6:
        bias_direction = "underestimate"
        bias_desc = f"歷史預估模型傾向保守（低於實際），實際公佈獲利常優於預期"
    else:
        bias_direction = "balanced"
        bias_desc = f"歷史預估與實際獲利貼合良好，無顯著單向系統性偏差"

    if mape <= 10.0:
        c_grade = "high"
        c_grade_zh = "高可信度（偏差 ≤ 10%）"
    elif mape <= 20.0:
        c_grade = "moderate"
        c_grade_zh = "中等可信度（偏差 10%~20%）"
    else:
        c_grade = "volatile"
        c_grade_zh = "波動較大（偏差 > 20%）"

    return ForecastCalibrationSummary(
        has_sufficient_history=(n >= 2),
        comparison_count=n,
        mape=round(mape, 2),
        confidence_score=round(confidence_score, 1),
        confidence_grade=c_grade,
        confidence_grade_zh=c_grade_zh,
        bias_direction=bias_direction,
        bias_desc=bias_desc,
        calibration_details=[asdict(i) for i in valid_items]
    )


def project_multi_year_eps_scenarios(
    current_price: float,
    current_eps: float,
    cagr_base_pct: float,
    target_pe: float = 18.0
) -> EPSMultiYearProjectionResult:
    """
    依據規格書 5.4 試算未來 3 年與 5 年在三大情境下之 EPS 與目標價位：
    - 保守情境 (Conservative): 成長率 = cagr_base_pct * 0.7 (或 cagr - 5%)，保守估值
    - 基準情境 (Base): 成長率 = cagr_base_pct，以有效成長率複合推估
    - 樂觀情境 (Optimistic): 成長率 = cagr_base_pct * 1.3 (或 cagr + 5%)，產業景氣向上
    """
    if current_eps <= 0 or current_price <= 0:
        # 虧損時防呆回傳中性結構
        scenarios = [
            MultiYearProjectionScenario(
                scenario_type=s_type,
                scenario_name_zh=s_zh,
                growth_rate_used_pct=0.0,
                projected_eps_3y=0.0,
                projected_price_3y=0.0,
                projected_eps_5y=0.0,
                projected_price_5y=0.0,
                upside_pct_3y=0.0,
                upside_pct_5y=0.0
            )
            for s_type, s_zh in [("conservative", "保守情境"), ("base", "基準情境"), ("optimistic", "樂觀情境")]
        ]
        return EPSMultiYearProjectionResult(
            current_price=current_price,
            current_eps=current_eps,
            target_pe=target_pe,
            scenarios=scenarios
        )

    # 基準年增率（百分比）
    g_base = max(0.0, min(30.0, cagr_base_pct))
    g_cons = max(0.0, g_base * 0.65)
    g_opt = min(40.0, g_base * 1.35 if g_base > 0 else 5.0)

    configs = [
        ("conservative", "保守情境", g_cons),
        ("base", "基準情境", g_base),
        ("optimistic", "樂觀情境", g_opt),
    ]

    scenarios = []
    for s_type, s_zh, g in configs:
        rate = g / 100.0
        eps_3y = current_eps * math.pow(1.0 + rate, 3)
        price_3y = eps_3y * target_pe
        upside_3y = ((price_3y - current_price) / current_price) * 100.0

        eps_5y = current_eps * math.pow(1.0 + rate, 5)
        price_5y = eps_5y * target_pe
        upside_5y = ((price_5y - current_price) / current_price) * 100.0

        scenarios.append(MultiYearProjectionScenario(
            scenario_type=s_type,
            scenario_name_zh=s_zh,
            growth_rate_used_pct=round(g, 2),
            projected_eps_3y=round(eps_3y, 2),
            projected_price_3y=round(price_3y, 1),
            projected_eps_5y=round(eps_5y, 2),
            projected_price_5y=round(price_5y, 1),
            upside_pct_3y=round(upside_3y, 1),
            upside_pct_5y=round(upside_5y, 1)
        ))

    return EPSMultiYearProjectionResult(
        current_price=round(current_price, 2),
        current_eps=round(current_eps, 2),
        target_pe=round(target_pe, 1),
        scenarios=scenarios
    )
