"""
價值投資選股 App - 交易成本與損益兩平試算引擎 (trade_cost.py)
嚴格落實技術規格書 V1.7 第 12、18 章：
- 台股經紀商手續費（公定 0.1425%、支援券商折扣，例如 6折、2.8折）
- 最低手續費規則（零股 1 元、整張 20 元）
- 證券交易稅（一般股票 0.3%、ETF 0.1%）
- 符合台灣證券交易所最新之「檔位升降單位 (Tick Size)」計算損益兩平點 (Breakeven Price)
- 提供目標賣出價損益試算與總規費成本佔比分析
"""

import math
from typing import Dict, Any, Optional


def get_taiwan_tick_size(price: float) -> float:
    """
    依台灣證券交易所規定之六級股價升降單位 (Tick Size)：
    - 未滿 10 元：0.01 元
    - 10 元至未滿 50 元：0.05 元
    - 50 元至未滿 100 元：0.10 元
    - 100 元至未滿 500 元：0.50 元
    - 500 元至未滿 1,000 元：1.00 元
    - 1,000 元以上：5.00 元
    """
    if price < 10.0:
        return 0.01
    elif price < 50.0:
        return 0.05
    elif price < 100.0:
        return 0.10
    elif price < 500.0:
        return 0.50
    elif price < 1000.0:
        return 1.00
    else:
        return 5.00


def round_up_to_tick(price: float) -> float:
    """將價格無條件進位至下一個合法跳動檔位 (Tick)"""
    tick = get_taiwan_tick_size(price)
    # 浮點數精度保護
    units = math.ceil(round(price / tick, 4))
    return round(units * tick, 2)


def calculate_trade_cost(
    buy_price: float,
    shares: int = 1000,
    target_sell_price: Optional[float] = None,
    fee_rate: float = 0.001425,
    fee_discount: float = 1.0,
    min_fee: float = 1.0,
    is_etf: bool = False,
    is_day_trade: bool = False
) -> Dict[str, Any]:
    """
    純函式計算交易規費與損益兩平

    :param buy_price: 買進每股價格
    :param shares: 買進股數 (例如 1000 股 = 1 張)
    :param target_sell_price: 預期賣出每股價格 (可選)
    :param fee_rate: 經紀商公定手續費率 (預設 0.001425)
    :param fee_discount: 券商手續費折扣 (預設 1.0 不打折，如 0.6 代表 6 折)
    :param min_fee: 單筆最低手續費 (零股預設 1 元，整張預設 20 元)
    :param is_etf: 是否為 ETF (影響證交稅：ETF 0.1%，股票 0.3%)
    :param is_day_trade: 是否為現股當沖 (證交稅減半)
    """
    if buy_price <= 0 or shares <= 0:
        return {"status": "error", "message": "買進價格與股數必須大於 0"}

    # 1. 決定證交稅率
    if is_day_trade:
        tax_rate = 0.0015
    elif is_etf:
        tax_rate = 0.001
    else:
        tax_rate = 0.003

    # 2. 買進成本計算
    buy_trade_val = buy_price * shares
    buy_fee_raw = buy_trade_val * fee_rate * fee_discount
    buy_fee = max(int(min_fee), math.floor(buy_fee_raw))
    total_buy_cost = buy_trade_val + buy_fee

    # 3. 損益兩平價位 (Breakeven Price) 計算
    # 賣出實收 = P_sell * shares - max(min_fee, floor(P_sell * shares * fee_rate * fee_discount)) - floor(P_sell * shares * tax_rate)
    # 我們從理論價開始，透過逐檔跳動找到剛好 net_profit >= 0 的最小合法價格檔位
    eff_rate = fee_rate * fee_discount + tax_rate
    approx_breakeven = (total_buy_cost + min_fee) / (shares * (1.0 - eff_rate)) if (1.0 - eff_rate) > 0 else buy_price

    candidate_price = round_up_to_tick(approx_breakeven)

    # 迭代驗證與微調檔位確保精準兩平
    for _ in range(10):
        c_val = candidate_price * shares
        c_fee = max(int(min_fee), math.floor(c_val * fee_rate * fee_discount))
        c_tax = math.floor(c_val * tax_rate)
        c_proceeds = c_val - c_fee - c_tax
        if c_proceeds >= total_buy_cost:
            # 檢查前一檔是否也已保本
            prev_tick = get_taiwan_tick_size(candidate_price - 0.001)
            prev_cand = round(candidate_price - prev_tick, 2)
            if prev_cand >= buy_price:
                p_val = prev_cand * shares
                p_fee = max(int(min_fee), math.floor(p_val * fee_rate * fee_discount))
                p_tax = math.floor(p_val * tax_rate)
                if (p_val - p_fee - p_tax) >= total_buy_cost:
                    candidate_price = prev_cand
                    continue
            break
        else:
            tick = get_taiwan_tick_size(candidate_price)
            candidate_price = round(candidate_price + tick, 2)

    breakeven_price = candidate_price
    breakeven_diff = round(breakeven_price - buy_price, 2)
    breakeven_gain_pct = round((breakeven_price - buy_price) / buy_price * 100.0, 2)

    # 4. 若有輸入目標賣出價，計算情境獲利
    simulation = None
    if target_sell_price is not None and target_sell_price > 0:
        sell_val = target_sell_price * shares
        sell_fee = max(int(min_fee), math.floor(sell_val * fee_rate * fee_discount))
        sell_tax = math.floor(sell_val * tax_rate)
        net_sell_proceeds = sell_val - sell_fee - sell_tax

        net_profit = net_sell_proceeds - total_buy_cost
        net_return_pct = round((net_profit / total_buy_cost) * 100.0, 2)
        total_costs = buy_fee + sell_fee + sell_tax
        cost_ratio_pct = round((total_costs / total_buy_cost) * 100.0, 3)

        simulation = {
            "target_sell_price": round(target_sell_price, 2),
            "sell_trade_value": round(sell_val),
            "sell_fee": sell_fee,
            "securities_tax": sell_tax,
            "net_sell_proceeds": round(net_sell_proceeds),
            "total_transaction_costs": total_costs,
            "costs_ratio_pct": cost_ratio_pct,
            "net_profit": round(net_profit),
            "net_return_pct": net_return_pct
        }

    return {
        "status": "success",
        "inputs": {
            "buy_price": round(buy_price, 2),
            "shares": shares,
            "fee_discount": fee_discount,
            "min_fee": min_fee,
            "is_etf": is_etf,
            "tax_rate_pct": round(tax_rate * 100, 2)
        },
        "buy_summary": {
            "trade_value": round(buy_trade_val),
            "buy_fee": buy_fee,
            "total_cost": round(total_buy_cost)
        },
        "breakeven": {
            "breakeven_price": breakeven_price,
            "price_diff": breakeven_diff,
            "required_gain_pct": breakeven_gain_pct,
            "tick_size": get_taiwan_tick_size(breakeven_price),
            "description": f"買進 {buy_price} 元，需上漲 {breakeven_gain_pct:+.2f}% 至 {breakeven_price} 元即可損益兩平。"
        },
        "simulation": simulation
    }
