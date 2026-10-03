"""
價值投資選股 App - 宏觀市場水位與美債殖利率聯動引擎
遵循技術規格書 V1.7 第 10 章與第 14.6 節規範：

核心概念：
1. 無風險利率升高時，資產折現率提升，市場願意給予股票之本益比 (P/E) 倍數可能承壓下修；
   即使企業獲利持續成長，若市場整體估值水位壓縮，股價仍可能面臨估值重定價 (Re-rating / De-rating)。
2. 本引擎計算：
   - 股權風險溢酬 (ERP, Equity Risk Premium) = 台股/標的預期盈餘殖利率 (1/PE) - 美債無風險利率
   - 估值折現敏感度矩陣：模擬無風險利率自 3.5% 升至 5.5% 時，本益比倍數與價格區間之理論折現影響
   - 宏觀水位警戒層級判定：
     * normal: < 4.5% (利率正常平穩)
     * warning_4_5: 4.5% ~ 5.0% (接近警戒水位，高本益比標的留意倍數壓縮)
     * alert_5_0: >= 5.0% (高利率警戒，市場整體估值承受重定價壓力)
3. 嚴格遵循規格書約束：本模組為純風險提示與敏感度試算，不作為買賣訊號，亦不改變好公司六面向判定。

本模組為純函式 (Pure Functions)，無外部副作用，易於單元測試。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class MacroSensitivityPoint:
    simulated_yield_pct: float       # 模擬美債殖利率 (如 4.0%, 4.5%, 5.0%)
    discount_factor: float           # 相對基準倍數之折現因子 (例如 0.92 代表折現 8%)
    adjusted_target_pe: float        # 動態折現後之目標 PE 倍數
    adjusted_price: float            # 動態折現後之理論合理價
    change_pct: float                # 距基準合理價之理論變動幅幅 (%)


@dataclass(frozen=True)
class MacroStockSensitivityResult:
    ticker: str
    current_price: float
    current_pe: Optional[float]
    earning_yield_pct: Optional[float] # 盈餘殖利率 (E/P * 100%)
    current_us_10y_yield: float        # 當前 10 年期美債殖利率 (%)
    equity_risk_premium_pct: Optional[float] # 股權風險溢酬 ERP (%)
    erp_assessment_zh: str             # ERP 評價結論
    base_target_pe: float              # 基準合理 PE
    base_fair_price: float             # 基準合理價
    macro_status_level: str            # normal | warning | alert
    macro_status_zh: str               # 中文狀態
    macro_guidance_text: str           # 宏觀聯動白話指導
    sensitivity_table: List[Dict[str, Any]] # 多利率情境敏感度表格


@dataclass(frozen=True)
class MacroMarketOverviewResult:
    calc_date: str
    current_us_10y_yield: float
    historical_1y_high: float
    historical_1y_low: float
    historical_1y_avg: float
    warning_flag: str                  # normal | warning_4_5 | alert_5_0
    warning_level: str                 # normal | warning | alert
    warning_title: str
    warning_message: str
    impact_summary_zh: str
    high_pe_risk_hint: str
    historical_points: List[Dict[str, Any]]


def evaluate_macro_status(yield_val: float) -> Dict[str, str]:
    """
    依規格書 14.6 判定利率警示旗標與指引文字
    """
    if yield_val >= 5.0:
        return {
            "flag": "alert_5_0",
            "level": "alert",
            "title": "高利率警戒（美債殖利率 ≥ 5.0%）",
            "message": "無風險利率攀升至 5.0% 以上，資金成本顯著提高。市場對高估值（高 PE）成長股之倍數容忍度將明顯收縮，評價面臨下修重定價壓力。",
            "guidance": "高估值標的宜保守應對，留意防守底線與安全邊際；優先聚焦自由現金流充沛、高殖利率之實質獲利公司。"
        }
    elif yield_val >= 4.5:
        return {
            "flag": "warning_4_5",
            "level": "warning",
            "title": "利率接近警戒（美債殖利率 ≥ 4.5%）",
            "message": "美債殖利率已接近 5.0% 關鍵警戒線，無風險資產吸引力上升，高倍數估值標的應留意成長放緩時之本益比壓縮效應。",
            "guidance": "利率接近高檔區間，建議避免追價昂貴或瘋狂區標的，維持一定比例之戰略現金儲備。"
        }
    else:
        return {
            "flag": "normal",
            "level": "normal",
            "title": "利率平穩區間（美債殖利率 < 4.5%）",
            "message": "美債無風險利率處於相對平穩水位，對股票市場估值倍數未形成顯著系統性壓抑。",
            "guidance": "宏觀利率環境中性，回歸個別公司之獲利成長質量與河流圖五段位階挑選優質標的。"
        }


def calculate_macro_stock_sensitivity(
    ticker: str,
    current_price: float,
    current_eps: float,
    base_target_pe: float,
    current_us_10y_yield: float,
    historical_rates: Optional[List[float]] = None
) -> MacroStockSensitivityResult:
    """
    計算單一個股之美債殖利率敏感度、盈餘殖利率、股權風險溢酬 (ERP) 與動態折現表。
    """
    # 1. 盈餘殖利率與 ERP
    if current_eps > 0 and current_price > 0:
        cur_pe = round(current_price / current_eps, 2)
        earning_yield = round((current_eps / current_price) * 100.0, 2)
        erp = round(earning_yield - current_us_10y_yield, 2)
    else:
        cur_pe = None
        earning_yield = None
        erp = None

    if erp is not None:
        if erp >= 3.0:
            erp_desc = f"ERP 高達 +{erp}%，股票相對於美債具有極佳吸引力與風險補償"
        elif erp >= 1.0:
            erp_desc = f"ERP 為 +{erp}%，股票相對於無風險利率具備合理收益緩衝"
        elif erp >= 0.0:
            erp_desc = f"ERP 僅 +{erp}%，股票風險溢酬偏薄，評價吸引力有限"
        else:
            erp_desc = f"ERP 為負值 ({erp}%)，盈餘殖利率低於美債無風險利率，估值偏貴"
    else:
        erp_desc = "虧損或無獲利標的，無法計算盈餘殖利率與 ERP"

    # 基準合理價
    base_fair_price = round(current_eps * base_target_pe, 1) if current_eps > 0 else current_price

    # 2. 利率敏感度試算矩陣 (模擬利率：3.5%, 4.0%, 4.5%, 5.0%, 5.5%)
    # 折現假定：以 4.0% 為中樞，利率每上升 0.5%，本益比估值折現約 -4.5% ~ -5.0%
    base_benchmark_rate = 4.0
    simulated_rates = [3.5, 4.0, 4.5, 5.0, 5.5]
    table_points: List[Dict[str, Any]] = []

    for r in simulated_rates:
        rate_diff = r - base_benchmark_rate
        # 每高出 1% 折現約 9%
        discount_factor = max(0.65, min(1.35, 1.0 - (rate_diff * 0.09)))
        adj_pe = round(base_target_pe * discount_factor, 1)
        adj_price = round(current_eps * adj_pe, 1) if current_eps > 0 else 0.0
        change_pct = round(((adj_price - base_fair_price) / base_fair_price * 100.0), 1) if base_fair_price > 0 else 0.0

        table_points.append(asdict(MacroSensitivityPoint(
            simulated_yield_pct=r,
            discount_factor=round(discount_factor, 3),
            adjusted_target_pe=adj_pe,
            adjusted_price=adj_price,
            change_pct=change_pct
        )))

    macro_status = evaluate_macro_status(current_us_10y_yield)

    return MacroStockSensitivityResult(
        ticker=ticker,
        current_price=round(current_price, 2),
        current_pe=cur_pe,
        earning_yield_pct=earning_yield,
        current_us_10y_yield=round(current_us_10y_yield, 2),
        equity_risk_premium_pct=erp,
        erp_assessment_zh=erp_desc,
        base_target_pe=round(base_target_pe, 1),
        base_fair_price=base_fair_price,
        macro_status_level=macro_status["level"],
        macro_status_zh=macro_status["title"],
        macro_guidance_text=macro_status["guidance"],
        sensitivity_table=table_points
    )


def generate_macro_market_overview(
    historical_daily_records: List[Dict[str, Any]],
    current_yield: Optional[float] = None
) -> MacroMarketOverviewResult:
    """
    彙整過去 1 年美債殖利率趨勢、極值統計與全市場宏觀水位儀表板數據。
    historical_daily_records 格式: [{"date": "2026-09-01", "us_10y_yield": 4.28}, ...]
    """
    clean_points = [
        p for p in historical_daily_records
        if "us_10y_yield" in p and p["us_10y_yield"] is not None and p["us_10y_yield"] > 0
    ]

    clean_points = sorted(clean_points, key=lambda x: x.get("date", ""))

    rates = [p["us_10y_yield"] for p in clean_points]

    if current_yield is not None:
        latest_val = current_yield
    elif rates:
        latest_val = rates[-1]
    else:
        latest_val = 4.35

    h_high = round(max(rates), 2) if rates else round(latest_val * 1.1, 2)
    h_low = round(min(rates), 2) if rates else round(latest_val * 0.9, 2)
    h_avg = round(sum(rates) / len(rates), 2) if rates else latest_val

    status_info = evaluate_macro_status(latest_val)

    impact_summary = (
        f"當前美債 10 年期殖利率為 {latest_val:.2f}%（近1年區間：{h_low:.2f}% ~ {h_high:.2f}%，平均：{h_avg:.2f}%）。"
        f"{status_info['message']}"
    )

    high_pe_hint = (
        "若殖利率向上突破 4.5%~5.0%，歷史經驗顯示市場對 PE > 25 倍之高估值科技/成長股往往會啟動估值壓縮；"
        "建議加重檢視標的之自由現金流覆蓋率 (FCF) 與本益成長比 (PEG)，或拉大安全邊際。"
    )

    calc_date = clean_points[-1]["date"] if clean_points else "今日"

    return MacroMarketOverviewResult(
        calc_date=calc_date,
        current_us_10y_yield=round(latest_val, 2),
        historical_1y_high=h_high,
        historical_1y_low=h_low,
        historical_1y_avg=h_avg,
        warning_flag=status_info["flag"],
        warning_level=status_info["level"],
        warning_title=status_info["title"],
        warning_message=status_info["message"],
        impact_summary_zh=impact_summary,
        high_pe_risk_hint=high_pe_hint,
        historical_points=clean_points[-60:] if len(clean_points) > 60 else clean_points
    )
