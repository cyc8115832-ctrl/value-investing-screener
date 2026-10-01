"""
價值投資選股 App - 葛林布雷神奇公式引擎 (magic_formula.py)
依據技術規格書 V1.7 第 18 章（V2.0 擴充）：
- 資本報酬率 (ROC, Return on Capital) = EBIT / 淨投資資本
  = 營業利益 / (流動資產 - 流動負債 + 不動產廠房及設備)
- 盈餘殖利率 (EY, Earnings Yield) = EBIT / 企業價值 (EV)
  = 營業利益 / (市值 + 計息負債 - 現金及約當現金)
- 結合雙指標排名加總，選出「高品質（高 ROC）」且「好價格（高 EY）」之標的
- 金融股因資產結構特殊，給予自適應說明或排除標記
"""

from typing import Dict, Any, Optional


def calculate_magic_formula_metrics(
    operating_income: float,          # 營業利益 (EBIT)
    market_cap: float,                # 市值 (股價 * 股數)
    total_assets: float = 0.0,        # 總資產
    current_assets: float = 0.0,      # 流動資產
    current_liabilities: float = 0.0, # 流動負債
    net_ppe: float = 0.0,             # 不動產、廠房及設備淨額
    total_debt: float = 0.0,          # 總負債 / 計息負債
    cash_and_equivalents: float = 0.0,# 現金及約當現金
    is_financial: bool = False,       # 是否為金融股
    is_cyclical: bool = False         # 是否為循環股
) -> Dict[str, Any]:
    """
    計算單一個股之神奇公式指標 (ROC 與 EY)
    """
    if is_financial:
        return {
            "applicable": False,
            "roc": None,
            "ey": None,
            "roc_pct": None,
            "ey_pct": None,
            "magic_rank_score": None,
            "magic_score": 0.0,
            "quality_tag": "金融股不適用",
            "tier": "excluded",
            "is_cyclical": is_cyclical,
            "explanation": "金融業因資本結構特殊，不適用神奇公式 ROC 與 EY 計算。",
            "reason": "金融股主要獲利資產為放款與投資，負債主要為存款，不適用標準營業利益與資本報酬率公式。"
        }

    # 1. 計算淨投資資本 (Invested Capital)
    # 簡化標準：(流動資產 - 流動負債) + 不動產廠房設備；若缺乏明細，退化使用總資產 * 0.6
    net_working_capital = current_assets - current_liabilities if (current_assets > 0 or current_liabilities > 0) else 0.0
    invested_capital = net_working_capital + net_ppe
    if invested_capital <= 0:
        if total_assets > 0:
            invested_capital = total_assets * 0.6
        else:
            invested_capital = None

    # 2. 資本報酬率 ROC = EBIT / Invested Capital
    if invested_capital and invested_capital > 0:
        roc = operating_income / invested_capital
        roc_pct = round(roc * 100.0, 2)
    else:
        roc = None
        roc_pct = None

    # 3. 計算企業價值 EV = 市值 + 總負債 - 現金
    ev = market_cap + total_debt - cash_and_equivalents
    if ev <= 0:
        ev = max(1.0, market_cap)

    # 4. 盈餘殖利率 EY = EBIT / EV
    ey = operating_income / ev if ev > 0 else 0.0
    ey_pct = round(ey * 100.0, 2)

    # 5. 評等與評價標籤
    # ROC > 20% 為卓越資本回報，EY > 8% 為極具吸引力估值
    if roc_pct is not None and roc_pct >= 20.0 and ey_pct >= 7.0:
        quality_tag = "🌟 神奇公式雙優 (高報酬低估值)"
        tier = "top"
    elif roc_pct is not None and roc_pct >= 15.0 and ey_pct >= 5.0:
        quality_tag = "🟢 優質穩健價值股"
        tier = "good"
    elif roc_pct is not None and roc_pct < 8.0 and ey_pct < 4.0:
        quality_tag = "🟠 資本回報與殖利率偏低"
        tier = "weak"
    elif ey_pct < 3.0:
        quality_tag = "⚠️ 估值偏高 (盈餘殖利率低)"
        tier = "expensive"
    else:
        quality_tag = "🟡 資本回報中性"
        tier = "neutral"

    # 合成綜合分數 (0 ~ 100 分)：ROC 權重 50%、EY 權重 50% (正規化映射)
    # ROC 0~35% 映射 0~50 分；EY 0~12% 映射 0~50 分
    roc_score = min(50.0, max(0.0, (roc_pct / 30.0) * 50.0)) if roc_pct is not None else 0.0
    ey_score = min(50.0, max(0.0, (ey_pct / 10.0) * 50.0))
    total_magic_score = round(roc_score + ey_score, 1)

    roc_desc = f"{roc_pct}%" if roc_pct is not None else "無法計算(淨投資資本不足)"

    return {
        "applicable": True,
        "operating_income_ebit": round(operating_income, 1),
        "invested_capital": round(invested_capital, 1) if invested_capital is not None else None,
        "enterprise_value_ev": round(ev, 1),
        "roc": round(roc, 4) if roc is not None else None,
        "roc_pct": roc_pct,
        "ey": round(ey, 4),
        "ey_pct": ey_pct,
        "magic_score": total_magic_score,
        "quality_tag": quality_tag,
        "tier": tier,
        "is_cyclical": is_cyclical,
        "explanation": f"資本報酬率 (ROC) 為 {roc_desc}，盈餘殖利率 (EY) 為 {ey_pct}%。綜合神奇評分 {total_magic_score} 分。"
    }
