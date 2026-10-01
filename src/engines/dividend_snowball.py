"""
價值投資選股 App - 股息現金流複利滾雪球與長期被動收入試算引擎 (dividend_snowball.py)
嚴格落實價值投資原則：
- 規格書 5.5（定期定額與股息再投入）
- 規格書 6.8b（357 股利評價與長期持有）
- 規格書 16.4（心法：時間是好公司的朋友，複利滾雪球被動現金流）
- 純函式實作 (Pure Function)，無外部依賴與副作用
"""

from typing import Dict, Any, List, Optional
import math


def simulate_dividend_snowball(
    initial_capital: float = 1_000_000.0,
    annual_addition: float = 120_000.0,
    initial_dividend_yield_pct: float = 5.0,
    dividend_growth_rate_pct: float = 5.0,
    price_growth_rate_pct: float = 6.0,
    years: int = 15,
    reinvest_dividends: bool = True,
    inflation_rate_pct: float = 2.0
) -> Dict[str, Any]:
    """
    純函式模擬股息滾雪球複利成長軌跡與被動現金流。

    參數:
      initial_capital: 初始本金 (NTD)
      annual_addition: 每年額外定期定額投入資金 (NTD，例：每月 1 萬 = 每年 12 萬)
      initial_dividend_yield_pct: 初始股息殖利率 (%)，例 5.0 代表 5%
      dividend_growth_rate_pct: 預估年化股利成長率 (%)，例 5.0 代表 5%
      price_growth_rate_pct: 預估股價年化成長率 (%)，例 6.0 代表 6%
      years: 試算年數 (預設 15 年，範圍 3 ~ 40 年)
      reinvest_dividends: 是否將當年度領取的股息再投入買股 (DRIP)
      inflation_rate_pct: 預估年化通貨膨脹率 (%)，用於折算實質購買力
    """
    if initial_capital <= 0 and annual_addition <= 0:
        return {
            "success": False,
            "error": "初始本金與每年定額投入不能同時小於或等於 0",
            "yearly_trajectory": [],
            "summary": {}
        }

    # 參數邊界保護
    years = max(1, min(int(years), 50))
    init_yield = max(0.001, initial_dividend_yield_pct / 100.0)
    div_growth = max(-0.5, dividend_growth_rate_pct / 100.0)
    price_growth = max(-0.5, price_growth_rate_pct / 100.0)
    inflation = max(0.0, inflation_rate_pct / 100.0)

    # 基準假設：設定起始基準股價為 100 元，推算每股初始股利
    base_price = 100.0
    initial_dps = base_price * init_yield  # 每股配息

    # 第 0 期初始狀態
    initial_shares = initial_capital / base_price if base_price > 0 else 0.0

    yearly_trajectory: List[Dict[str, Any]] = []
    current_shares = initial_shares
    cum_invested_cash = initial_capital
    cum_dividends = 0.0

    # 里程碑追蹤
    payback_year: Optional[int] = None
    reached_100k_year: Optional[int] = None
    reached_500k_year: Optional[int] = None
    reached_1m_year: Optional[int] = None

    for yr in range(1, years + 1):
        # 當年度每股股利 (經股利成長率逐年複利)
        # Year 1 配息以 initial_dps 為基準，後續逐年乘 (1 + div_growth)
        current_dps = initial_dps * math.pow(1.0 + div_growth, yr - 1)

        # 當年度除息時股價 (經股價年化成長率逐年複利)
        current_price = base_price * math.pow(1.0 + price_growth, yr - 1)

        # 1. 每年初追加之定期定額所購得之股數
        dca_shares = annual_addition / current_price if current_price > 0 else 0.0
        cum_invested_cash += annual_addition

        shares_before_dividend = current_shares + dca_shares

        # 2. 當年度領取現金股利總額
        annual_div = shares_before_dividend * current_dps
        cum_dividends += annual_div

        # 3. 股息再投入 (DRIP)
        reinvested_shares = 0.0
        if reinvest_dividends and current_price > 0:
            reinvested_shares = annual_div / current_price

        end_shares = shares_before_dividend + reinvested_shares
        portfolio_market_val = end_shares * current_price

        # 4. 成本殖利率 (Yield on Cost) = 當年股利 / 累計自掏腰包投入本金
        yoc_pct = (annual_div / cum_invested_cash * 100.0) if cum_invested_cash > 0 else 0.0

        # 5. 通膨折現後之實質購買力
        purchasing_power_div = annual_div / math.pow(1.0 + inflation, yr)

        # 檢查里程碑
        if payback_year is None and cum_dividends >= cum_invested_cash:
            payback_year = yr
        if reached_100k_year is None and annual_div >= 100_000:
            reached_100k_year = yr
        if reached_500k_year is None and annual_div >= 500_000:
            reached_500k_year = yr
        if reached_1m_year is None and annual_div >= 1_000_000:
            reached_1m_year = yr

        yearly_trajectory.append({
            "year": yr,
            "start_shares": round(current_shares, 1),
            "dca_shares": round(dca_shares, 1),
            "reinvested_shares": round(reinvested_shares, 1),
            "end_shares": round(end_shares, 1),
            "share_price": round(current_price, 2),
            "dividend_per_share": round(current_dps, 2),
            "annual_dividend": round(annual_div, 0),
            "cumulative_dividends": round(cum_dividends, 0),
            "total_invested_capital": round(cum_invested_cash, 0),
            "portfolio_market_value": round(portfolio_market_val, 0),
            "yield_on_cost_pct": round(yoc_pct, 2),
            "real_dividend_purchasing_power": round(purchasing_power_div, 0)
        })

        # 滾入下一年
        current_shares = end_shares

    # 6. 計算對照組：若「未再投入股息（Reinvestment = False）」的最終資產與被動現金流
    no_drip_shares = initial_shares
    no_drip_cum_div = 0.0
    no_drip_invested = initial_capital

    for yr in range(1, years + 1):
        c_price = base_price * math.pow(1.0 + price_growth, yr - 1)
        c_dps = initial_dps * math.pow(1.0 + div_growth, yr - 1)
        d_shares = annual_addition / c_price if c_price > 0 else 0.0
        no_drip_invested += annual_addition
        s_total = no_drip_shares + d_shares
        no_drip_cum_div += (s_total * c_dps)
        no_drip_shares = s_total

    final_price = base_price * math.pow(1.0 + price_growth, years - 1)
    no_drip_market_val = no_drip_shares * final_price
    # 總財富 (市值 + 拿在手上的累積現金股利)
    no_drip_total_wealth = no_drip_market_val + no_drip_cum_div

    final_record = yearly_trajectory[-1]
    drip_final_wealth = final_record["portfolio_market_value"] if reinvest_dividends else (final_record["portfolio_market_value"] + final_record["cumulative_dividends"])
    wealth_diff_ratio = (drip_final_wealth / no_drip_total_wealth) if no_drip_total_wealth > 0 else 1.0

    return {
        "success": True,
        "input_parameters": {
            "initial_capital": initial_capital,
            "annual_addition": annual_addition,
            "initial_dividend_yield_pct": initial_dividend_yield_pct,
            "dividend_growth_rate_pct": dividend_growth_rate_pct,
            "price_growth_rate_pct": price_growth_rate_pct,
            "years": years,
            "reinvest_dividends": reinvest_dividends,
            "inflation_rate_pct": inflation_rate_pct
        },
        "final_metrics": {
            "total_invested_capital": final_record["total_invested_capital"],
            "final_portfolio_value": final_record["portfolio_market_value"],
            "final_annual_dividend": final_record["annual_dividend"],
            "cumulative_dividends_received": final_record["cumulative_dividends"],
            "final_yield_on_cost_pct": final_record["yield_on_cost_pct"],
            "final_shares_count": final_record["end_shares"],
            "capital_gain_return_pct": round(((final_record["portfolio_market_value"] - final_record["total_invested_capital"]) / final_record["total_invested_capital"] * 100.0), 1) if final_record["total_invested_capital"] > 0 else 0.0
        },
        "milestones": {
            "payback_year": payback_year,
            "reached_100k_year": reached_100k_year,
            "reached_500k_year": reached_500k_year,
            "reached_1m_year": reached_1m_year
        },
        "comparison_vs_no_drip": {
            "drip_final_total_wealth": round(drip_final_wealth, 0),
            "no_drip_final_total_wealth": round(no_drip_total_wealth, 0),
            "wealth_difference_amount": round(drip_final_wealth - no_drip_total_wealth, 0),
            "wealth_multiplier": round(wealth_diff_ratio, 2)
        },
        "yearly_trajectory": yearly_trajectory,
        "summary": {
            "message": (
                f"在持續投入與好公司股息成長下，第 {years} 年預估年領股息 NT$ {final_record['annual_dividend']:,.0f} 元，"
                f"持有成本殖利率（YoC）大幅躍升至 {final_record['yield_on_cost_pct']}%！"
                + (f" 累積領取股利於第 {payback_year} 年超越本金全數回本！" if payback_year else "")
            )
        }
    }
