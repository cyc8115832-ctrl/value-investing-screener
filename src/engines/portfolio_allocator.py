"""
價值投資選股 App - 資產配置與資金部位管理引擎 (portfolio_allocator.py)
嚴格落實價值投資原則：
- 永不借錢、保留戰略現金儲備 (預設 20%)
- 單一標的上限風控 (預設 15%~20%)，防止單押風險
- 依河流圖位階與安全邊際動態加權 (特價區權重大於便宜區，合理/昂貴區不予新配置)
- 支援台股整張 (1,000 股) 與零股試算
- 純函式實作 (Pure Function)，無外部依賴與副作用
"""

from typing import List, Dict, Any, Optional
import math


def calculate_portfolio_allocation(
    total_capital: float,
    candidates: List[Dict[str, Any]],
    cash_reserve_pct: float = 20.0,
    max_single_stock_pct: float = 20.0,
    allow_odd_lots: bool = False
) -> Dict[str, Any]:
    """
    根據總投資資金與候選標的，純函式計算科學化資金配置。
    
    參數:
      total_capital: 總閒錢資金 (NTD)
      candidates: 候選股票清單，每項需包含:
                  - ticker (str)
                  - company_name (str)
                  - current_price (float)
                  - zone (str: 'special', 'cheap', 'fair', 'expensive', 'crazy')
                  - margin_pct (float: 安全邊際 %)
                  - is_good (bool: 是否為好公司)
      cash_reserve_pct: 戰略現金儲備比例 (預設 20.0%)
      max_single_stock_pct: 單一股票配置上限比例 (預設 20.0%)
      allow_odd_lots: 是否支援零股 (False 則以 1,000 股整張向下取整)
    """
    if total_capital <= 0:
        return {
            "success": False,
            "error": "總投資資金必須大於 0",
            "allocations": [],
            "summary": {}
        }

    # 1. 預留戰略現金
    reserve_cash = total_capital * (cash_reserve_pct / 100.0)
    investable_capital = total_capital - reserve_cash

    # 2. 篩選與加權評分
    eligible_items = []
    total_weight = 0.0

    for c in candidates:
        price = c.get("current_price", 0.0)
        zone = c.get("zone", "fair")
        is_good = c.get("is_good", True)
        margin = max(0.0, c.get("margin_pct", 0.0))

        # 僅針對 好公司 且 處於 特價 或 便宜 區的標的給予配置權重
        if not is_good or zone not in ["special", "cheap"] or price <= 0:
            continue

        # 特價區基礎權重 2.0，便宜區 1.0
        base_w = 2.0 if zone == "special" else 1.0
        # 加上安全邊際加成 (安全邊際每多 10% 增加 0.1 權重)
        weight = base_w * (1.0 + margin / 100.0)

        eligible_items.append({
            "ticker": c.get("ticker", ""),
            "company_name": c.get("company_name", ""),
            "current_price": price,
            "zone": zone,
            "margin_pct": margin,
            "weight": weight
        })
        total_weight += weight

    if not eligible_items or total_weight <= 0:
        return {
            "success": True,
            "total_capital": total_capital,
            "investable_budget": investable_capital,
            "total_allocated": 0.0,
            "allocated_pct": 0.0,
            "remaining_cash": total_capital,
            "actual_cash_pct": 100.0,
            "cash_reserve": total_capital,
            "cash_reserve_pct": 100.0,
            "cash_reserve_target_pct": cash_reserve_pct,
            "max_single_stock_pct": max_single_stock_pct,
            "allow_odd_lots": allow_odd_lots,
            "allocations_count": 0,
            "allocations": [],
            "summary": {
                "message": "目前候選名單中無符合『好公司＋特價/便宜區』之配置標的，建議 100% 保留現金耐心等待好價格。"
            }
        }

    # 3. 初步資金權重分配與單一上限風控
    max_single_cap = total_capital * (max_single_stock_pct / 100.0)
    allocations = []
    actual_spent = 0.0

    for item in eligible_items:
        # 初步依權重分配的理論資金
        raw_cap = investable_capital * (item["weight"] / total_weight)
        # 單一標的上限風控封頂
        capped_cap = min(raw_cap, max_single_cap)

        price = item["current_price"]
        lot_size = 1 if allow_odd_lots else 1000

        # 計算建議股數 (向下取整至最小交易單位)
        max_shares = int(capped_cap // price)
        suggested_shares = (max_shares // lot_size) * lot_size

        allocated_amount = suggested_shares * price
        suggested_lots = suggested_shares / 1000.0

        actual_spent += allocated_amount

        allocations.append({
            "ticker": item["ticker"],
            "company_name": item["company_name"],
            "current_price": price,
            "zone": item["zone"],
            "zone_name_zh": "特價區" if item["zone"] == "special" else "便宜區",
            "margin_pct": item["margin_pct"],
            "suggested_shares": suggested_shares,
            "suggested_lots": suggested_lots,
            "allocated_amount": round(allocated_amount, 1),
            "allocation_pct": round((allocated_amount / total_capital) * 100.0, 1),
            "cap_limited": (raw_cap > max_single_cap)
        })

    # 4. 總結統計
    remaining_cash = round(total_capital - actual_spent, 1)
    actual_cash_pct = round((remaining_cash / total_capital) * 100.0, 1)

    return {
        "success": True,
        "total_capital": total_capital,
        "investable_budget": investable_capital,
        "total_allocated": round(actual_spent, 1),
        "allocated_pct": round((actual_spent / total_capital) * 100.0, 1),
        "remaining_cash": remaining_cash,
        "actual_cash_pct": actual_cash_pct,
        "cash_reserve_target_pct": cash_reserve_pct,
        "max_single_stock_pct": max_single_stock_pct,
        "allow_odd_lots": allow_odd_lots,
        "allocations_count": len(allocations),
        "allocations": allocations,
        "summary": {
            "message": f"成功為 {len(allocations)} 檔便宜好公司規劃資金部位，預計投入 NT$ {actual_spent:,.0f} 元 (佔比 {actual_spent/total_capital*100:.1f}%)，保留現金 NT$ {remaining_cash:,.0f} 元 (佔比 {actual_cash_pct}%)。"
        }
    }
