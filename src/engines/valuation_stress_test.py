"""
價值投資選股 App - 多情境估值敏感度與黑天鵝壓力測試引擎 (valuation_stress_test.py)
嚴格落實價值投資原則：
- 規格書 5.4（長期情境 EPS 試算）
- 規格書 6.8 & 18（情境 EPS：樂觀、基準、悲觀三情境與敏感度價位帶）
- 規格書 19.5（模型風險：提供假設可調、計算可展開，包含極端市場下跌與黑天鵝防守壓力測試）
- 純函式實作 (Pure Function)，無外部依賴與副作用
"""

from typing import Dict, Any, Optional
import math


def calculate_valuation_stress_test(
    ticker: str,
    current_price: float,
    base_eps: float,
    book_value_per_share: float,
    pe_anchors: Dict[str, float],
    historical_min_pe: float = 10.0,
    historical_min_pb: float = 1.0,
    optimistic_growth_pct: float = 20.0,
    pessimistic_growth_pct: float = -20.0,
    is_cyclical: bool = False
) -> Dict[str, Any]:
    """
    純函式執行多情境估值敏感度與黑天鵝壓力測試。

    參數:
      ticker: 股票代號
      current_price: 最新現價 (NTD)
      base_eps: 基準預估 EPS 或實際 TTM EPS
      book_value_per_share: 每股淨值 (BVPS)
      pe_anchors: 河流圖六個本益比錨點 (a1 特價, a2 便宜, a3 合理下, a4 合理上, a5 昂貴, a6 瘋狂)
      historical_min_pe: 歷史極限最低本益比 (預設 10.0)
      historical_min_pb: 歷史極限最低股價淨值比 (預設 1.0)
      optimistic_growth_pct: 樂觀情境獲利成長率 (預設 +20.0%)
      pessimistic_growth_pct: 悲觀情境獲利衰退率 (預設 -20.0%)
      is_cyclical: 是否為景氣循環股
    """
    if current_price <= 0:
        return {
            "success": False,
            "error": "現價必須大於 0",
            "scenarios": {},
            "floor_test": {}
        }

    # 確保 base_eps 與 bvps 有效
    eff_eps = max(0.01, base_eps)
    eff_bvps = max(1.0, book_value_per_share)

    # 提取錨點倍數
    a1 = pe_anchors.get("a1", 12.0)
    a2 = pe_anchors.get("a2", 15.0)
    a3 = pe_anchors.get("a3", 18.0)
    a4 = pe_anchors.get("a4", 21.0)
    a5 = pe_anchors.get("a5", 24.0)

    # ---------------- 1. 三大情境敏感度試算 ----------------
    # 樂觀情境：營收獲利超預期成長，市場給予合理偏上倍數 (A4)
    opt_eps = eff_eps * (1.0 + optimistic_growth_pct / 100.0)
    opt_target_pe = a4
    opt_price = round(opt_eps * opt_target_pe, 1)
    opt_change_pct = round(((opt_price - current_price) / current_price * 100.0), 1)

    # 基準情境：維持目前預估軌跡，市場回歸合理中位倍數 (A3)
    base_target_pe = a3
    base_price = round(eff_eps * base_target_pe, 1)
    base_change_pct = round(((base_price - current_price) / current_price * 100.0), 1)

    # 悲觀情境：遭遇產業逆風或景氣趨緩，獲利衰退且估值壓縮至便宜線 (A2)
    pess_eps = max(0.01, eff_eps * (1.0 + pessimistic_growth_pct / 100.0))
    pess_target_pe = a2
    pess_price = round(pess_eps * pess_target_pe, 1)
    pess_change_pct = round(((pess_price - current_price) / current_price * 100.0), 1)

    # ---------------- 2. 黑天鵝防守底線壓力測試 (Floor Price Stress Test) ----------------
    # (1) 悲觀 EPS 乘歷史極限最低 PE
    pe_floor_price = round(pess_eps * max(6.0, min(historical_min_pe, a1)), 1)
    # (2) 淨值防守線 (每股淨值 × 歷史極限最低 PB)
    pb_floor_price = round(eff_bvps * max(0.5, historical_min_pb), 1)
    # (3) 清算價值有形淨值線 (保守以每股淨值 80% 作為極端硬資產底線)
    tangible_floor_price = round(eff_bvps * 0.8, 1)

    # 綜合黑天鵝極限防守底線：取有形淨值與歷史極限指標中具公信力之防守價
    # 若為景氣循環股則偏重淨值底線，一般股取 PE/PB 底線之較高支撐或有形淨值
    if is_cyclical:
        ultimate_floor = round(max(tangible_floor_price, min(pb_floor_price, current_price * 0.5)), 1)
    else:
        # 取 pe_floor 與 pb_floor 兩者之相對防守中位
        ultimate_floor = round(min(pe_floor_price, pb_floor_price, current_price), 1)
        ultimate_floor = max(tangible_floor_price * 0.7, ultimate_floor)

    # 確保極限底價不高於現價
    ultimate_floor = min(ultimate_floor, current_price)

    # 最大下行空間 (Downside Risk %)
    max_downside_pct = round(((ultimate_floor - current_price) / current_price * 100.0), 1)
    safety_cushion_pct = abs(max_downside_pct)

    # 安全緩衝評級
    if safety_cushion_pct <= 15.0:
        cushion_grade = "very_strong"  # 現價極度接近歷史底線，下行風險極低
        cushion_desc = "極高安全緩衝 (現價已非常貼近歷史極限防禦底線)"
    elif safety_cushion_pct <= 30.0:
        cushion_grade = "moderate"
        cushion_desc = "中度安全緩衝 (具備合理防守空間)"
    else:
        cushion_grade = "wide"
        cushion_desc = "下行緩衝較深 (若遇極端黑天鵝需留意波動修正)"

    # ---------------- 3. 風險報酬比 (Risk / Reward Ratio) ----------------
    # 潛在上行利益 (基準合理價相較現價)
    potential_gain = max(0.0, base_price - current_price)
    # 潛在下行風險 (現價距黑天鵝底線距離)
    potential_loss = max(1.0, current_price - ultimate_floor)

    rr_ratio = round(potential_gain / potential_loss, 2)
    is_favorable = rr_ratio >= 1.5

    return {
        "success": True,
        "ticker": ticker,
        "current_price": current_price,
        "base_metrics": {
            "base_eps": round(eff_eps, 2),
            "book_value_per_share": round(eff_bvps, 2),
            "is_cyclical": is_cyclical
        },
        "scenarios": {
            "optimistic": {
                "name": "樂觀情境 (獲利超預期)",
                "growth_pct": optimistic_growth_pct,
                "projected_eps": round(opt_eps, 2),
                "target_pe": opt_target_pe,
                "projected_price": opt_price,
                "change_pct": opt_change_pct,
                "scenario_desc": "營收超預期成長，本益比修復至合理上緣"
            },
            "base": {
                "name": "基準情境 (穩健中位)",
                "growth_pct": 0.0,
                "projected_eps": round(eff_eps, 2),
                "target_pe": base_target_pe,
                "projected_price": base_price,
                "change_pct": base_change_pct,
                "scenario_desc": "獲利如期實現，估值回歸長期合理中軸"
            },
            "pessimistic": {
                "name": "悲觀情境 (景氣逆風)",
                "growth_pct": pessimistic_growth_pct,
                "projected_eps": round(pess_eps, 2),
                "target_pe": pess_target_pe,
                "projected_price": pess_price,
                "change_pct": pess_change_pct,
                "scenario_desc": "獲利遭遇壓縮，市場估值回落至便宜線"
            }
        },
        "floor_test": {
            "pe_floor_price": pe_floor_price,
            "pb_floor_price": pb_floor_price,
            "tangible_floor_price": tangible_floor_price,
            "ultimate_floor_price": ultimate_floor,
            "max_downside_pct": max_downside_pct,
            "safety_cushion_pct": safety_cushion_pct,
            "cushion_grade": cushion_grade,
            "cushion_desc": cushion_desc
        },
        "risk_reward": {
            "potential_gain_ntd": round(potential_gain, 1),
            "potential_loss_ntd": round(potential_loss, 1),
            "risk_reward_ratio": rr_ratio,
            "is_favorable": is_favorable,
            "summary_tag": "高風報比 (優質進場點)" if is_favorable else "中性風報比"
        },
        "summary": {
            "message": (
                f"在悲觀衰退情境下股價推估約 NT$ {pess_price} 元 ({pess_change_pct:+.1f}%)；"
                f"遭遇黑天鵝市場崩盤時，極限防守底線為 NT$ {ultimate_floor} 元 (下行緩衝 {safety_cushion_pct:.1f}%)。"
                f" 目前風險報酬比為 {rr_ratio}:1，{'具備絕佳安全邊際' if is_favorable else '下行風險適中'}。"
            )
        }
    }
