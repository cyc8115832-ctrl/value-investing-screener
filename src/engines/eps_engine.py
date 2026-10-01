"""
價值投資選股 App - EPS Engine (滾動預估 EPS 與防呆引擎)
遵循技術規格書 V1.7 第 5 章：
- 5.1 六步驟模型 (一般成長股) 與中間過程保存
- 5.2 景氣循環股防呆 (隱藏預估 EPS，改推 P/B)
- 5.3 可信度旗標 (normal, cyclical, one_off, short_history, loss)
- 5.4 長期情境 EPS 試算 (V2)
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import math

ConfidenceFlag = str  # "normal" | "cyclical" | "one_off" | "short_history" | "loss"

@dataclass(frozen=True)
class EPSForecastDetails:
    cumulative_rev_yoy_g: float      # g: 今年累計營收 YoY (如 0.15 代表 15%)
    prior_full_year_revenue: float   # Rev_prior: 前一年全年營收
    estimated_revenue: float         # Rev_est = Rev_prior * (1 + g)
    margin_ttm: float                # Margin: 近4季淨利總和 / 近4季營收總和
    estimated_net_income: float      # NI_est = Rev_est * Margin
    shares_outstanding: float        # 最新流通在外股數
    estimated_eps_base: float        # EPS_est = NI_est / shares
    estimated_eps_conservative: float# 保守情境 EPS
    estimated_eps_optimistic: float  # 樂觀情境 EPS
    normalized_eps: Optional[float]  # 扣除一次性業外後之正常化 EPS (若有)

@dataclass(frozen=True)
class EPSCalculationResult:
    ticker: str
    period: str                      # 如 "2026-Q3"
    actual_eps_ttm: Optional[float]  # 近 4 季實際 EPS 加總
    latest_quarter_eps: Optional[float]
    estimated_eps: Optional[float]   # 基準預估 EPS (若為循環股或上市未滿四季則為 None)
    estimate_year: int
    estimate_method: str             # "six_step_growth" | "cyclical_hidden" | "insufficient_history"
    confidence_flag: ConfidenceFlag
    warning_message: Optional[str]
    calc_details: Optional[EPSForecastDetails]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def calculate_six_step_eps(
    ticker: str,
    estimate_year: int,
    cumulative_rev_yoy_g: float,
    prior_full_year_revenue: float,
    ttm_revenues: List[float],
    ttm_net_incomes: List[float],
    ttm_non_operating_incomes: Optional[List[float]],
    shares_outstanding: float,
    is_cyclical: bool = False,
    is_financial: bool = False,
    quarters_count: int = 4
) -> EPSCalculationResult:
    """
    純函式執行 EPS 六步驟滾動預估模型與防呆檢查
    """
    # 1. 檢查歷史長度 (4.4 / 5.3: 上市未滿四季)
    if quarters_count < 4 or len(ttm_revenues) < 4 or len(ttm_net_incomes) < 4:
        return EPSCalculationResult(
            ticker=ticker,
            period=f"{estimate_year}",
            actual_eps_ttm=None,
            latest_quarter_eps=ttm_net_incomes[-1] / shares_outstanding if (ttm_net_incomes and shares_outstanding > 0) else None,
            estimated_eps=None,
            estimate_year=estimate_year,
            estimate_method="insufficient_history",
            confidence_flag="short_history",
            warning_message="上市未滿四季，歷史不足以年化預估 EPS",
            calc_details=None
        )

    # 2. 計算實際近 4 季 TTM 淨利與營收
    total_rev_ttm = sum(ttm_revenues[-4:])
    total_ni_ttm = sum(ttm_net_incomes[-4:])
    actual_eps_ttm = total_ni_ttm / shares_outstanding if shares_outstanding > 0 else 0.0
    latest_quarter_eps = ttm_net_incomes[-1] / shares_outstanding if shares_outstanding > 0 else 0.0

    # 3. 虧損檢查
    if actual_eps_ttm <= 0:
        loss_flag: ConfidenceFlag = "loss"
    else:
        loss_flag = "normal"

    # 4. 景氣循環股防呆 (5.2: 停用預估 EPS，改推 P/B)
    if is_cyclical:
        return EPSCalculationResult(
            ticker=ticker,
            period=f"{estimate_year}",
            actual_eps_ttm=actual_eps_ttm,
            latest_quarter_eps=latest_quarter_eps,
            estimated_eps=None,
            estimate_year=estimate_year,
            estimate_method="cyclical_hidden",
            confidence_flag="cyclical",
            warning_message="景氣循環股獲利波動劇烈，預估 EPS 已隱藏，建議改用 P/B 河流圖搭配存貨與應收帳款指標",
            calc_details=None
        )

    # 5. 六步驟預估模型計算
    # 步驟 1: g = 累計營收 YoY
    g = cumulative_rev_yoy_g
    # 步驟 2 & 3: Rev_est = Rev_prior * (1 + g)
    rev_est = prior_full_year_revenue * (1.0 + g)
    # 步驟 4: Margin = 近4季淨利 / 近4季營收
    margin = total_ni_ttm / total_rev_ttm if total_rev_ttm > 0 else 0.0
    # 步驟 5: NI_est = Rev_est * Margin
    ni_est = rev_est * margin
    # 步驟 6: EPS_est = NI_est / shares
    eps_est_base = ni_est / shares_outstanding if shares_outstanding > 0 else 0.0

    # 情境分析 (5.1 / 13.4: 保守 -5% g & -1% margin, 樂觀 +5% g & +1% margin)
    g_cons = g - 0.05
    margin_cons = max(0.0, margin - 0.01)
    eps_cons = (prior_full_year_revenue * (1.0 + g_cons) * margin_cons) / shares_outstanding if shares_outstanding > 0 else 0.0

    g_opt = g + 0.05
    margin_opt = margin + 0.01
    eps_opt = (prior_full_year_revenue * (1.0 + g_opt) * margin_opt) / shares_outstanding if shares_outstanding > 0 else 0.0

    # 6. 單季業外收益防呆 (4.4 / 5.3: 業外收益佔淨利 > 30%)
    confidence_flag = loss_flag
    warn_msg = None
    normalized_eps = None

    if ttm_non_operating_incomes and len(ttm_non_operating_incomes) >= 4:
        latest_quarter_ni = ttm_net_incomes[-1]
        latest_quarter_non_op = ttm_non_operating_incomes[-1]
        
        # 檢查任一季或最新季業外 > 30% 淨利
        if latest_quarter_ni > 0 and (latest_quarter_non_op / latest_quarter_ni) > 0.30:
            confidence_flag = "one_off"
            warn_msg = f"⚠️ 最新季業外收益達 {latest_quarter_non_op / latest_quarter_ni * 100:.1f}%，超過淨利 30%，EPS 可能受一次性業外影響"
            
            # 計算扣除業外後的正常化淨利率與 EPS
            operating_ni_ttm = total_ni_ttm - sum(ttm_non_operating_incomes[-4:])
            norm_margin = operating_ni_ttm / total_rev_ttm if total_rev_ttm > 0 else 0.0
            norm_ni_est = rev_est * norm_margin
            normalized_eps = norm_ni_est / shares_outstanding if shares_outstanding > 0 else 0.0

    calc_details = EPSForecastDetails(
        cumulative_rev_yoy_g=g,
        prior_full_year_revenue=prior_full_year_revenue,
        estimated_revenue=rev_est,
        margin_ttm=margin,
        estimated_net_income=ni_est,
        shares_outstanding=shares_outstanding,
        estimated_eps_base=eps_est_base,
        estimated_eps_conservative=eps_cons,
        estimated_eps_optimistic=eps_opt,
        normalized_eps=normalized_eps
    )

    return EPSCalculationResult(
        ticker=ticker,
        period=f"{estimate_year}",
        actual_eps_ttm=actual_eps_ttm,
        latest_quarter_eps=latest_quarter_eps,
        estimated_eps=eps_est_base,
        estimate_year=estimate_year,
        estimate_method="six_step_growth",
        confidence_flag=confidence_flag,
        warning_message=warn_msg,
        calc_details=calc_details
    )


def calculate_long_term_scenario_eps(
    start_revenue: float,
    cagr: float,
    years: int,
    net_margin: float,
    shares_outstanding: float,
    target_pe: float
) -> Dict[str, float]:
    """
    規格書 5.4 長期情境 EPS 試算 (V2)
    輸入：起始營收、CAGR、年數、淨利率、股數、目標本益比
    範例：2.89 兆、CAGR 24%、5 年、淨利率 40%、股數 259.3 億股 -> EPS 約 130，乘 20 倍約 2,600
    """
    future_revenue = start_revenue * math.pow(1.0 + cagr, years)
    future_net_income = future_revenue * net_margin
    future_eps = future_net_income / shares_outstanding if shares_outstanding > 0 else 0.0
    future_target_price = future_eps * target_pe

    return {
        "future_revenue": future_revenue,
        "future_net_income": future_net_income,
        "future_eps": future_eps,
        "target_pe": target_pe,
        "target_price": future_target_price
    }
