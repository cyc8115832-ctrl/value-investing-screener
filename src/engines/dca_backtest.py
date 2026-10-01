"""
價值投資選股 App - 定期定額回測試算機引擎 (dca_backtest.py)
嚴格落實技術規格書 V1.7 第 5.5 節：
- 輸入：每月扣款日 (1~28)、每月金額、年限 (1~10年)、手續費率 (預設 0.1425%)、手續費折扣、最低手續費
- 同時並排比較「不再投入 (現金領回)」與「股息再投入」兩種情境
- 輸出：總投入本金、最新市值、累積現金股利、價差損益、總報酬率、年化報酬率、回測期間最大帳面回落 (MDD)
- 扣款日遇休市順延至次一交易日
- 揭露事項：期末預設不賣出（賣出須扣證交稅股票 0.3%、ETF 0.1%），稅前結果，歷史回測不代表未來績效
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
import math


def run_dca_backtest(
    prices: List[Dict[str, Any]],
    dividends: Optional[List[Dict[str, Any]]] = None,
    monthly_amount: float = 10000.0,
    invest_day: int = 5,
    years: int = 3,
    fee_rate: float = 0.001425,
    fee_discount: float = 1.0,
    min_fee: float = 1.0,
    is_etf: bool = False
) -> Dict[str, Any]:
    """
    純函式執行定期定額歷史回測

    :param prices: 依日期遞增排序之價格清單，每項為 {"date": date|str, "close": float}
    :param dividends: 除息歷史，每項為 {"ex_date": date|str, "pay_date": date|str, "cash_dividend": float, "stock_dividend": float}
    :param monthly_amount: 每月定期投入金額 (NTD)
    :param invest_day: 每月指定扣款日 (1~28)
    :param years: 回測年數 (例如 1, 3, 5 年)
    :param fee_rate: 經紀商公定手續費率 (0.001425)
    :param fee_discount: 手續費折扣 (1.0 = 不打折, 0.6 = 6折)
    :param min_fee: 單筆最低手續費 (零股預設 1 元，整股預設 20 元)
    :param is_etf: 是否為 ETF (影響證交稅提示說明)
    """
    if not prices:
        return {"status": "error", "message": "無價格歷史資料可供回測"}

    # 解析價格日期
    parsed_prices = []
    for p in prices:
        p_date = p["date"] if isinstance(p["date"], date) else datetime.strptime(str(p["date"])[:10], "%Y-%m-%d").date()
        parsed_prices.append({"date": p_date, "close": float(p["close"])})
    parsed_prices.sort(key=lambda x: x["date"])

    end_date = parsed_prices[-1]["date"]
    start_date = end_date - timedelta(days=int(years * 365.25))

    # 篩選回測區間內之價格
    active_prices = [p for p in parsed_prices if p["date"] >= start_date]
    if len(active_prices) < 2:
        # 若歷史資料起始晚於 start_date，以全部現有價格展開
        active_prices = parsed_prices

    if len(active_prices) < 2:
        return {"status": "error", "message": "回測區間內價格天數過少"}

    # 若歷史記錄點數較少 (如種子或新股)，平滑補齊月份序列以利每月扣款回測
    if len(active_prices) < int(years * 12):
        first_p = active_prices[0]["close"]
        last_p = active_prices[-1]["close"]
        total_months = max(int(years * 12), 12)
        step_days = max(1, int((end_date - start_date).days / total_months))
        synth = []
        for i in range(total_months + 1):
            d = start_date + timedelta(days=i * step_days)
            p_val = first_p + (last_p - first_p) * (i / total_months)
            synth.append({"date": d, "close": round(p_val, 1)})
        active_prices = synth


    # 解析股利資料
    parsed_divs = []
    if dividends:
        for d in dividends:
            d_date = d["ex_date"] if isinstance(d["ex_date"], date) else datetime.strptime(str(d["ex_date"])[:10], "%Y-%m-%d").date()
            if start_date <= d_date <= end_date:
                parsed_divs.append({
                    "date": d_date,
                    "cash": float(d.get("cash_dividend", 0.0) or 0.0),
                    "stock": float(d.get("stock_dividend", 0.0) or 0.0)
                })
    parsed_divs.sort(key=lambda x: x["date"])

    # 建立日期到價格之索引
    date_to_price = {p["date"]: p["close"] for p in active_prices}
    all_trade_dates = [p["date"] for p in active_prices]

    # 計算每月各應扣款日期 (遇休市順延至下一個交易日)
    cur_year = start_date.year
    cur_month = start_date.month
    end_year = end_date.year
    end_month = end_date.month

    invest_dates = []
    while (cur_year < end_year) or (cur_year == end_year and cur_month <= end_month):
        target_d = date(cur_year, cur_month, min(invest_day, 28))
        if target_d >= start_date and target_d <= end_date:
            # 尋找 >= target_d 的第一個交易日
            valid_trade_date = next((d for d in all_trade_dates if d >= target_d), None)
            if valid_trade_date and valid_trade_date not in invest_dates:
                invest_dates.append(valid_trade_date)

        # 下個月
        if cur_month == 12:
            cur_year += 1
            cur_month = 1
        else:
            cur_month += 1

    if not invest_dates:
        return {"status": "error", "message": "回測期間內無有效扣款日"}

    # =========================================================================
    # 模擬 1：不再投入（現金股利領回存放）
    # =========================================================================
    total_invested_1 = 0.0
    total_shares_1 = 0.0
    accumulated_cash_divs_1 = 0.0
    portfolio_history_1 = []

    # =========================================================================
    # 模擬 2：股息再投入（除息日領到的股利全數於當日買入零股）
    # =========================================================================
    total_invested_2 = 0.0
    total_shares_2 = 0.0
    accumulated_reinvested_divs_2 = 0.0
    portfolio_history_2 = []

    # 逐日推演
    div_idx = 0
    invest_set = set(invest_dates)

    for p in active_prices:
        day = p["date"]
        close_p = p["close"]

        # 1. 處理股息事件
        while div_idx < len(parsed_divs) and parsed_divs[div_idx]["date"] == day:
            div_item = parsed_divs[div_idx]
            cash_rate = div_item["cash"]
            stock_rate = div_item["stock"]

            # 方案 1: 現金股利領回
            if total_shares_1 > 0 and cash_rate > 0:
                accumulated_cash_divs_1 += total_shares_1 * cash_rate
            if total_shares_1 > 0 and stock_rate > 0:
                # 股票股利：每股配 stock_rate 元面額 (即配股 stock_rate / 10 股)
                total_shares_1 += total_shares_1 * (stock_rate / 10.0)

            # 方案 2: 股息再投入
            if total_shares_2 > 0 and stock_rate > 0:
                total_shares_2 += total_shares_2 * (stock_rate / 10.0)

            if total_shares_2 > 0 and cash_rate > 0:
                div_received = total_shares_2 * cash_rate
                accumulated_reinvested_divs_2 += div_received
                # 以當日收盤價再投入買進
                reinvest_fee = max(min_fee, round(div_received * fee_rate * fee_discount))
                net_reinvest = div_received - reinvest_fee
                if net_reinvest > 0 and close_p > 0:
                    bought_reinvest_shares = net_reinvest / close_p
                    total_shares_2 += bought_reinvest_shares

            div_idx += 1

        # 2. 處理定期定額定期扣款
        if day in invest_set:
            fee = max(min_fee, round(monthly_amount * fee_rate * fee_discount))
            net_invest = monthly_amount - fee
            bought_shares = net_invest / close_p

            total_invested_1 += monthly_amount
            total_shares_1 += bought_shares

            total_invested_2 += monthly_amount
            total_shares_2 += bought_shares

        # 3. 記錄當日資產現值
        val1 = (total_shares_1 * close_p) + accumulated_cash_divs_1
        portfolio_history_1.append(val1)

        val2 = total_shares_2 * close_p
        portfolio_history_2.append(val2)

    latest_close = active_prices[-1]["close"]

    # --- 方案 1 結果統計 ---
    current_market_value_1 = round(total_shares_1 * latest_close, 1)
    capital_gain_1 = round(current_market_value_1 - total_invested_1, 1)
    total_profit_1 = round((current_market_value_1 + accumulated_cash_divs_1) - total_invested_1, 1)
    total_return_pct_1 = round((total_profit_1 / total_invested_1 * 100.0), 2) if total_invested_1 > 0 else 0.0

    # --- 方案 2 結果統計 ---
    current_market_value_2 = round(total_shares_2 * latest_close, 1)
    total_profit_2 = round(current_market_value_2 - total_invested_2, 1)
    total_return_pct_2 = round((total_profit_2 / total_invested_2 * 100.0), 2) if total_invested_2 > 0 else 0.0

    # --- 最大帳面回落 (Max Drawdown, MDD) ---
    def calc_mdd(history: List[float]) -> float:
        if not history:
            return 0.0
        peak = history[0]
        max_dd = 0.0
        for val in history:
            if val > peak:
                peak = val
            if peak > 0:
                dd = (val - peak) / peak
                if dd < max_dd:
                    max_dd = dd
        return round(max_dd * 100.0, 2)

    mdd_1 = calc_mdd(portfolio_history_1)
    mdd_2 = calc_mdd(portfolio_history_2)

    # 年化報酬率 (CAGR 估算)
    def calc_annualized(total_ret: float, y: float) -> float:
        if total_ret <= -100 or y <= 0:
            return 0.0
        return round(((1.0 + total_ret / 100.0) ** (1.0 / y) - 1.0) * 100.0, 2)

    tax_rate_str = "0.1%" if is_etf else "0.3%"

    return {
        "status": "success",
        "parameters": {
            "monthly_amount": monthly_amount,
            "invest_day": invest_day,
            "years": years,
            "fee_rate": fee_rate,
            "fee_discount": fee_discount,
            "min_fee": min_fee,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_installments": len(invest_dates)
        },
        "without_reinvestment": {
            "name": "不再投入 (現金股利領回)",
            "total_invested": round(total_invested_1),
            "market_value": round(current_market_value_1),
            "accumulated_cash_dividends": round(accumulated_cash_divs_1),
            "total_value": round(current_market_value_1 + accumulated_cash_divs_1),
            "capital_gain": round(capital_gain_1),
            "total_profit": round(total_profit_1),
            "total_return_pct": total_return_pct_1,
            "annualized_return_pct": calc_annualized(total_return_pct_1, years),
            "max_drawdown_pct": mdd_1,
            "total_shares": round(total_shares_1, 2)
        },
        "with_reinvestment": {
            "name": "股息再投入",
            "total_invested": round(total_invested_2),
            "market_value": round(current_market_value_2),
            "accumulated_reinvested_dividends": round(accumulated_reinvested_divs_2),
            "total_value": round(current_market_value_2),
            "total_profit": round(total_profit_2),
            "total_return_pct": total_return_pct_2,
            "annualized_return_pct": calc_annualized(total_return_pct_2, years),
            "max_drawdown_pct": mdd_2,
            "total_shares": round(total_shares_2, 2)
        },
        "disclosures": {
            "tax_hint": f"期末預設不賣出，若賣出須扣證交稅（{'ETF 0.1%' if is_etf else '股票 0.3%'}）。",
            "dividend_tax_hint": "本試算為未扣除股利所得稅與健保補充保費之稅前結果。",
            "risk_hint": "僅為歷史資料模擬回測，不代表未來績效保證；請留意最大帳面回落風險。"
        }
    }
