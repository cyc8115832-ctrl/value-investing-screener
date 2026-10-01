"""
價值投資選股 App - Valuation River Engine (河流圖五段價位估值引擎)
遵循技術規格書 V1.7 第 6 章：
- 6.1 五段價位演算法
- 6.2 驗收測試案例 (台積電範例)
- 6.2b 價位區歸屬測試案例
- 6.3 區間歸屬 (線判定：特價 <= A1, 便宜 A1-A2, 合理 A2-A5, 昂貴 A5-A6, 瘋狂 >= A6)
- 6.8b 357 股利法 (V2)
- 6.8c PEG 保守估值 (V2)
本模組為純函式 (Pure Functions)，無外部副作用，易於單元測試。
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Literal
import math

ZoneType = Literal["special", "cheap", "fair", "expensive", "crazy"]
SubZoneType = Literal["special", "cheap", "fair_low", "fair_core", "fair_high", "expensive", "crazy"]

@dataclass(frozen=True)
class RiverAnchors:
    vmin: float
    vmax: float
    delta: float
    a1: float  # 特價錨 (Vmin)
    a2: float  # 便宜錨 (Vmin + 1Δ)
    a3: float  # 合理下緣 (Vmin + 2Δ)
    a4: float  # 合理上緣 (Vmin + 3Δ)
    a5: float  # 昂貴錨 (Vmin + 4Δ)
    a6: float  # 瘋狂錨 (Vmax)

@dataclass(frozen=True)
class RiverPrices:
    base: float
    p1: float  # 特價線
    p2: float  # 便宜線
    p3: float  # 合理下緣線
    p4: float  # 合理上緣線
    p5: float  # 昂貴線
    p6: float  # 瘋狂線

@dataclass(frozen=True)
class ZoneClassification:
    current_price: float
    zone: ZoneType
    zone_name_zh: str
    sub_zone: SubZoneType
    sub_zone_desc: str
    is_buy_research_zone: bool  # P <= P2 (特價 + 便宜)
    is_warning_zone: bool       # P >= P5 (昂貴 + 瘋狂)
    color_hex: str

@dataclass(frozen=True)
class PEGValuationResult:
    is_applicable: bool
    reason: str
    eps_ttm: float
    growth_rate_input: float
    effective_growth_rate: float
    p_cheap: float      # 0.75 * G * EPS
    p_fair: float       # 1.00 * G * EPS
    p_expensive: float  # 1.50 * G * EPS

@dataclass(frozen=True)
class Dividend357Result:
    is_applicable: bool
    reason: str
    dividend_base_d: float
    p_cheap: float      # D / 0.07
    p_fair: float       # D / 0.05
    p_expensive: float  # D / 0.03


def filter_outliers_iqr(series: List[float]) -> List[float]:
    """
    依 6.1 / D-3 排除離群值 (1.5x IQR)
    """
    clean_series = [x for x in series if x is not None and not math.isnan(x) and x > 0]
    if len(clean_series) < 4:
        return clean_series

    sorted_s = sorted(clean_series)
    n = len(sorted_s)
    
    # 計算 Q1 與 Q3 (線性插值)
    def percentile(p: float) -> float:
        pos = p * (n - 1)
        base = int(pos)
        rest = pos - base
        if base + 1 < n:
            return sorted_s[base] + rest * (sorted_s[base + 1] - sorted_s[base])
        return sorted_s[base]

    q1 = percentile(0.25)
    q3 = percentile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    filtered = [x for x in sorted_s if lower_bound <= x <= upper_bound]
    return filtered if filtered else sorted_s


def calculate_anchors(vmin: float, vmax: float) -> RiverAnchors:
    """
    依 6.1 計算六個倍數錨點與 Δ
    Δ = (Vmax - Vmin) / 5
    A1 = Vmin
    A2 = Vmin + 1Δ
    A3 = Vmin + 2Δ
    A4 = Vmin + 3Δ
    A5 = Vmin + 4Δ
    A6 = Vmax
    """
    if vmax < vmin:
        raise ValueError(f"vmax ({vmax}) 不能小於 vmin ({vmin})")
    
    delta = (vmax - vmin) / 5.0
    a1 = vmin
    a2 = vmin + 1.0 * delta
    a3 = vmin + 2.0 * delta
    a4 = vmin + 3.0 * delta
    a5 = vmin + 4.0 * delta
    a6 = vmax
    
    return RiverAnchors(
        vmin=vmin,
        vmax=vmax,
        delta=delta,
        a1=a1,
        a2=a2,
        a3=a3,
        a4=a4,
        a5=a5,
        a6=a6
    )


def calculate_river_prices(anchors: RiverAnchors, base: float) -> RiverPrices:
    """
    價格錨點 = 錨點倍數 × 基準 (預估 EPS、近 4 季 EPS、每股淨值或每股營收)
    """
    if base <= 0:
        raise ValueError(f"估值基準 base 必須為正數，目前為 {base}")

    return RiverPrices(
        base=base,
        p1=anchors.a1 * base,
        p2=anchors.a2 * base,
        p3=anchors.a3 * base,
        p4=anchors.a4 * base,
        p5=anchors.a5 * base,
        p6=anchors.a6 * base,
    )


def classify_price_zone(
    current_price: float,
    prices: RiverPrices,
    zone_rule_version: str = "v1.5_line"
) -> ZoneClassification:
    """
    依 6.3「線」判定規則分類五段價位區 (D-1 定案):
    - 🔵 特價: P <= P1
    - 🩵 便宜: P1 < P <= P2
    - 🟢 合理: P2 < P < P5
        * P <= P3: 合理偏低
        * P3 < P < P4: 核心合理帶
        * P >= P4: 合理偏高
    - 🟠 昂貴: P5 <= P < P6
    - 🔴 瘋狂 (紫色標示): P >= P6
    """
    p = current_price
    p1 = prices.p1
    p2 = prices.p2
    p3 = prices.p3
    p4 = prices.p4
    p5 = prices.p5
    p6 = prices.p6

    # 浮點數精度微調容差
    tol = 1e-6

    if p <= p1 + tol:
        zone: ZoneType = "special"
        zone_name = "特價"
        sub_zone: SubZoneType = "special"
        sub_desc = "特價區 (低於特價線)"
        color = "#2563EB"
    elif p <= p2 + tol:
        zone = "cheap"
        zone_name = "便宜"
        sub_zone = "cheap"
        sub_desc = "便宜區 (特價線至便宜線)"
        color = "#38BDF8"
    elif p < p5 - tol:
        zone = "fair"
        zone_name = "合理"
        color = "#10B981"
        if p <= p3 + tol:
            sub_zone = "fair_low"
            sub_desc = "合理偏低"
        elif p >= p4 - tol:
            sub_zone = "fair_high"
            sub_desc = "合理偏高"
        else:
            sub_zone = "fair_core"
            sub_desc = "核心合理帶"
    elif p < p6 - tol:
        zone = "expensive"
        zone_name = "昂貴"
        sub_zone = "expensive"
        sub_desc = "昂貴區 (昂貴線至瘋狂線)"
        color = "#F59E0B"
    else:
        zone = "crazy"
        zone_name = "瘋狂"
        sub_zone = "crazy"
        sub_desc = "瘋狂區 (高於瘋狂線，紫色標示)"
        color = "#A855F7"

    is_buy = p <= p2 + tol
    is_warn = p >= p5 - tol

    return ZoneClassification(
        current_price=p,
        zone=zone,
        zone_name_zh=zone_name,
        sub_zone=sub_zone,
        sub_zone_desc=sub_desc,
        is_buy_research_zone=is_buy,
        is_warning_zone=is_warn,
        color_hex=color
    )


def calculate_peg_valuation(
    eps_ttm: float,
    growth_rate_forecast: float,
    growth_rate_cagr_3y: float,
    is_cyclical: bool = False,
    is_financial: bool = False,
    confidence_flag: str = "normal",
    max_growth_rate: float = 25.0
) -> PEGValuationResult:
    """
    依 6.8c 保守估值定案：
    - 價格 = 目標 PEG × 成長率 G × EPS (G 以百分點計，如 20% -> 20)
    - 成長率 G = min(預估成長率, 3年CAGR)，上限 25%
    - 便宜 0.75, 合理 1.0, 昂貴 1.5
    """
    if eps_ttm <= 0:
        return PEGValuationResult(
            is_applicable=False,
            reason="EPS TTM 小於等於 0，不適用 PEG 估值",
            eps_ttm=eps_ttm,
            growth_rate_input=0.0,
            effective_growth_rate=0.0,
            p_cheap=0.0, p_fair=0.0, p_expensive=0.0
        )
    if is_cyclical or is_financial:
        return PEGValuationResult(
            is_applicable=False,
            reason="景氣循環股或金融股不適用 PEG 估值",
            eps_ttm=eps_ttm,
            growth_rate_input=0.0,
            effective_growth_rate=0.0,
            p_cheap=0.0, p_fair=0.0, p_expensive=0.0
        )
    if confidence_flag != "normal":
        return PEGValuationResult(
            is_applicable=False,
            reason=f"可信度旗標為 {confidence_flag}，不適用 PEG 估值",
            eps_ttm=eps_ttm,
            growth_rate_input=0.0,
            effective_growth_rate=0.0,
            p_cheap=0.0, p_fair=0.0, p_expensive=0.0
        )

    g_raw = min(growth_rate_forecast, growth_rate_cagr_3y)
    if g_raw <= 0:
        return PEGValuationResult(
            is_applicable=False,
            reason="成長率 G 小於等於 0，不適用 PEG 估值",
            eps_ttm=eps_ttm,
            growth_rate_input=g_raw,
            effective_growth_rate=0.0,
            p_cheap=0.0, p_fair=0.0, p_expensive=0.0
        )

    # 上限 25%
    effective_g = min(g_raw, max_growth_rate)

    p_cheap = 0.75 * effective_g * eps_ttm
    p_fair = 1.00 * effective_g * eps_ttm
    p_expensive = 1.50 * effective_g * eps_ttm

    return PEGValuationResult(
        is_applicable=True,
        reason="符合條件，採保守 PEG 估值 (G設上限25%)",
        eps_ttm=eps_ttm,
        growth_rate_input=g_raw,
        effective_growth_rate=effective_g,
        p_cheap=p_cheap,
        p_fair=p_fair,
        p_expensive=p_expensive
    )


def calculate_dividend_357(
    avg_5y_dividend: float,
    estimated_eps: float,
    avg_3y_payout_ratio: float,
    consecutive_years: int = 5,
    min_years_threshold: int = 3,
    is_cyclical: bool = False
) -> Dividend357Result:
    """
    依 6.8b / D-23 定案：
    - 比率：7% (便宜)、5% (合理)、3% (昂貴)
    - 股利基準 D = min(近 5 年平均現金股利, 預估 EPS × 近 3 年平均配息率)
    - 便宜價 = D / 0.07; 合理價 = D / 0.05; 昂貴價 = D / 0.03
    """
    if is_cyclical:
        return Dividend357Result(
            is_applicable=False,
            reason="景氣循環股配息不穩，不適用 357 股利法",
            dividend_base_d=0.0,
            p_cheap=0.0, p_fair=0.0, p_expensive=0.0
        )
    if consecutive_years < min_years_threshold:
        return Dividend357Result(
            is_applicable=False,
            reason=f"連續配息未滿 {min_years_threshold} 年，不適用 357 股利法",
            dividend_base_d=0.0,
            p_cheap=0.0, p_fair=0.0, p_expensive=0.0
        )

    d1 = avg_5y_dividend
    d2 = estimated_eps * avg_3y_payout_ratio
    d_base = min(d1, d2)

    if d_base <= 0:
        return Dividend357Result(
            is_applicable=False,
            reason="計算出的股利基準 D 小於等於 0",
            dividend_base_d=0.0,
            p_cheap=0.0, p_fair=0.0, p_expensive=0.0
        )

    p_cheap = d_base / 0.07
    p_fair = d_base / 0.05
    p_expensive = d_base / 0.03

    return Dividend357Result(
        is_applicable=True,
        reason="採 357 股利法 (7%便宜 / 5%合理 / 3%昂貴，基準取較低者)",
        dividend_base_d=d_base,
        p_cheap=p_cheap,
        p_fair=p_fair,
        p_expensive=p_expensive
    )
