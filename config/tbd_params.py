"""
價值投資選股 App - TBD 門檻與權重參數設定檔 (V1.7)
所有技術規格書中標記 [TBD] 的參數均收錄於此，做成可配置化參數，並附帶暫定預設值。
"""

from pydantic import BaseModel, Field
from typing import List, Tuple

class TBDParameters(BaseModel):
    # D-1 價格區邊界判定版本
    zone_rule_version: str = Field(default="v1.5_line", description="價位區邊界判定規則 (v1.5_line 採線判定)")

    # D-2 好公司六面向門檻
    revenue_cagr_years: int = Field(default=3, description="營收 CAGR 計算年數")
    revenue_positive_quarters_needed: int = Field(default=3, description="近4季營收YoY至少需幾季為正")
    margin_decline_consecutive_quarters: int = Field(default=2, description="三率連續幾季下滑視為黃燈")
    roe_good_threshold: float = Field(default=10.0, description="資本效率 ROE 良好標準 (%)")
    roic_good_threshold: float = Field(default=8.0, description="資本效率 ROIC 良好標準 (%)")
    dividend_payout_max_safe: float = Field(default=100.0, description="股利配發率安全上限 (%)")
    dividend_consecutive_years: int = Field(default=3, description="連續配息年數門檻")
    capex_growth_threshold_pct: float = Field(default=20.0, description="資本支出大幅擴產季增門檻 (%)")
    non_operating_income_warn_ratio: float = Field(default=0.30, description="單季業外收益佔淨利警示比例 (30%)")

    # D-3 離群值與歷史區間
    outlier_method: str = Field(default="iqr", description="離群值剔除方法 (iqr: 1.5x IQR)")
    valuation_history_years: int = Field(default=5, description="河流圖歷史資料區間 (3或5年)")

    # D-4 金融股替代指標門檻
    financial_roe_threshold: float = Field(default=8.0, description="金融股 ROE 良好門檻 (%)")

    # D-5 景氣循環股產業清單
    cyclical_industries: List[str] = Field(
        default=["記憶體", "DRAM", "面板", "航運", "鋼鐵", "塑化", "被動元件", "水泥", "造紙"],
        description="預設景氣循環股產業名稱"
    )

    # D-10 提前反映警示閾值
    early_reflection_tolerance_pct: float = Field(default=0.0, description="現價超過隔年合理價之警示閾值")

    # D-11 自選股上限
    custom_stock_limit: int = Field(default=50, description="每位使用者自選股上限檔數")

    # D-12 標的納入設定
    include_preferred_stocks: bool = Field(default=False, description="是否納入特別股 (V1預設排除)")
    include_dr: bool = Field(default=False, description="是否納入存託憑證 (V1預設排除)")

    # D-13 雷達首頁預設股池範圍
    radar_default_scope: str = Field(default="etf", description="雷達預設股池範圍 (all | etf | custom)")

    # D-14 產業集中度提醒門檻
    industry_concentration_limit: int = Field(default=5, description="同產業入選超過幾檔時提醒分散風險")

    # D-16 每日精選流動性門檻
    min_daily_volume_ntd: float = Field(default=10_000_000.0, description="日均成交金額門檻 (NT$ 10,000,000)")

    # D-17 領先訊號門檻
    l1_revenue_accel_diff_pct: float = Field(default=5.0, description="L1: 近3月平均年增高於近12月之百分點差距")
    l4_capex_growth_pct: float = Field(default=20.0, description="L4: 資本支出季增成長率門檻 (%)")

    # D-22 字級預設
    default_font_level: str = Field(default="large", description="預設字級 (standard, large, xlarge, xxlarge)")

    # D-23 357 股利法比率 (便宜, 合理, 昂貴)
    dividend_357_yields: Tuple[float, float, float] = Field(
        default=(0.07, 0.05, 0.03),
        description="357股利法殖利率基準 (7%便宜, 5%合理, 3%昂貴)"
    )

    # D-24 PEG 保守估值門檻
    peg_targets: Tuple[float, float, float] = Field(
        default=(0.75, 1.0, 1.5),
        description="PEG 目標倍數 (便宜 0.75, 合理 1.0, 昂貴 1.5)"
    )
    peg_max_growth_rate: float = Field(default=25.0, description="PEG 成長率上限 (25%)")

    # D-25 美國10年期公債殖利率宏觀水位
    macro_us10y_alert: float = Field(default=5.0, description="美債殖利率警示門檻 (%)")
    macro_us10y_approach: float = Field(default=4.5, description="美債殖利率接近提示門檻 (%)")

    # D-26 估值極端旗標門檻
    extreme_pe_threshold: float = Field(default=100.0, description="極端本益比警示門檻 (倍)")
    extreme_pe_peer_multiple: float = Field(default=3.0, description="高於同族群中位數幾倍觸發警示")

    # D-27 交易成本預設值
    brokerage_fee_rate: float = Field(default=0.001425, description="券商公定手續費率 (0.1425%)")
    stock_tax_rate: float = Field(default=0.003, description="證券交易稅率 (0.3%)")
    etf_tax_rate: float = Field(default=0.001, description="ETF 證券交易稅率 (0.1%)")

# 全域預設單例
TBD_CONFIG = TBDParameters()
