"""
價值投資選股 App - 三大法人籌碼流與股權集中度分析引擎 (chip_analysis.py)
嚴格落實技術規格書 V1.7 第 9、18 章：
- 三大法人（外資、投信、自營商）日買賣超與 5日 / 20日累計動向
- 法人資金態度判定（積極佈局、外資偏多、中性觀望、調節賣超）
- 大戶持股比例（400張/1000張）變化趨勢（籌碼集中 vs 分散）
- 董監事持股比率健康度檢驗
"""

from typing import Dict, List, Any, Optional
from datetime import date, datetime


def analyze_stock_chip_data(chip_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    純函式分析個股籌碼數據序列

    :param chip_records: 依日期遞增排序之籌碼記錄清單，每項包含 date, foreign_net, trust_net, dealer_net, insider_holding_pct, big_holder_pct
    """
    if not chip_records:
        return {
            "status": "insufficient_data",
            "message": "無籌碼資料",
            "summary_tag": "無籌碼資料",
            "latest": None
        }

    # 確保按日期排序
    sorted_recs = sorted(chip_records, key=lambda x: str(x.get("date", "")))
    latest = sorted_recs[-1]

    # 計算最近 5 日與 20 日累計
    recs_5d = sorted_recs[-5:] if len(sorted_recs) >= 5 else sorted_recs
    recs_20d = sorted_recs[-20:] if len(sorted_recs) >= 20 else sorted_recs

    foreign_5d = round(sum(float(r.get("foreign_net", 0.0) or 0.0) for r in recs_5d), 1)
    trust_5d = round(sum(float(r.get("trust_net", 0.0) or 0.0) for r in recs_5d), 1)
    dealer_5d = round(sum(float(r.get("dealer_net", 0.0) or 0.0) for r in recs_5d), 1)
    total_5d = round(foreign_5d + trust_5d + dealer_5d, 1)

    foreign_20d = round(sum(float(r.get("foreign_net", 0.0) or 0.0) for r in recs_20d), 1)
    trust_20d = round(sum(float(r.get("trust_net", 0.0) or 0.0) for r in recs_20d), 1)
    dealer_20d = round(sum(float(r.get("dealer_net", 0.0) or 0.0) for r in recs_20d), 1)
    total_20d = round(foreign_20d + trust_20d + dealer_20d, 1)

    # 法人動向態度標籤
    if total_5d > 500 and trust_5d > 0:
        stance_tag = "🟢 法人積極加碼 (投信外資合買)"
        stance_type = "positive"
    elif total_5d > 0:
        stance_tag = "🩵 法人偏多買超"
        stance_type = "mild_positive"
    elif total_5d < -500:
        stance_tag = "🟠 法人調節賣超"
        stance_type = "negative"
    else:
        stance_tag = "🟡 法人中性觀望"
        stance_type = "neutral"

    # 大戶持股趨勢分析 (近 20 日或更長)
    cur_big_holder = float(latest.get("big_holder_pct", 0.0) or 0.0)
    old_big_holder = float(recs_20d[0].get("big_holder_pct", cur_big_holder) or cur_big_holder)
    big_holder_diff = round(cur_big_holder - old_big_holder, 2)

    if big_holder_diff >= 0.5:
        concentration_desc = f"大戶籌碼持續集中 (近期增加 {big_holder_diff:+.2f}%)"
        concentration_status = "concentrating"
    elif big_holder_diff <= -0.5:
        concentration_desc = f"大戶籌碼稍見分散 (近期減少 {big_holder_diff:+.2f}%)"
        concentration_status = "distributing"
    else:
        concentration_desc = "大戶持股維持穩定"
        concentration_status = "stable"

    # 董監持股分析
    insider_pct = float(latest.get("insider_holding_pct", 0.0) or 0.0)
    if insider_pct < 10.0 and insider_pct > 0:
        insider_status = "董監持股偏低 (<10%)"
        insider_safe = False
    elif insider_pct >= 20.0:
        insider_status = f"董監持股高度集中 ({insider_pct:.1f}%)"
        insider_safe = True
    else:
        insider_status = f"董監持股穩健 ({insider_pct:.1f}%)"
        insider_safe = True

    return {
        "status": "success",
        "latest_date": str(latest.get("date", "")),
        "stance": {
            "tag": stance_tag,
            "type": stance_type
        },
        "latest_daily": {
            "foreign_net": round(float(latest.get("foreign_net", 0.0) or 0.0), 1),
            "trust_net": round(float(latest.get("trust_net", 0.0) or 0.0), 1),
            "dealer_net": round(float(latest.get("dealer_net", 0.0) or 0.0), 1),
            "total_net": round(float(latest.get("foreign_net", 0.0) or 0.0) + float(latest.get("trust_net", 0.0) or 0.0) + float(latest.get("dealer_net", 0.0) or 0.0), 1)
        },
        "cumulative_5d": {
            "foreign": foreign_5d,
            "trust": trust_5d,
            "dealer": dealer_5d,
            "total": total_5d
        },
        "cumulative_20d": {
            "foreign": foreign_20d,
            "trust": trust_20d,
            "dealer": dealer_20d,
            "total": total_20d
        },
        "concentration": {
            "current_big_holder_pct": cur_big_holder,
            "change_pct": big_holder_diff,
            "status": concentration_status,
            "description": concentration_desc
        },
        "insider": {
            "insider_holding_pct": insider_pct,
            "status": insider_status,
            "is_safe": insider_safe
        }
    }
