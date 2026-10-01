"""
價值投資選股 App - 產業集中度分析與風控警示模組 (industry_concentration.py)
遵循技術規格書 V1.7 第 13.10 節、第 15 章與待決事項 D-14：
- 00881、00891 偏科技半導體，台積電權重高，成分股池容易同質化
- 同產業入選超過門檻 (預設 3 檔，可設定 [TBD]) 時觸發產業集中度提醒
- 計算產業分佈百分比與分散度指數 (HHI / Diversification Score)
- 提供高中生與長輩易懂的風控白話文案
"""

from typing import List, Dict, Any, Optional
from collections import Counter


def analyze_industry_concentration(
    stocks: List[Dict[str, Any]],
    threshold: int = 3
) -> Dict[str, Any]:
    """
    純函式分析股票清單之產業集中度與分散度風險

    Args:
        stocks: 股票字典列表，每個字典至少包含 'ticker', 'company_name', 'industry'
        threshold: 同產業觸發集中度警示之門檻檔數 (規格書 D-14，預設 3 檔)

    Returns:
        包含產業分佈、集中度警示與分散度評分的結構化報告
    """
    if not stocks:
        return {
            "total_stocks": 0,
            "unique_industries_count": 0,
            "has_concentration_risk": False,
            "is_concentrated": False,
            "alerts": [],
            "top_industries": [],
            "industry_breakdown": [],
            "hhi": 0.0,
            "diversification_score": 100.0,
            "diversification_level": "good",
            "level": "low",
            "level_label": "🟢 產業配置分散",
            "summary": "清單中暫無標的"
        }

    total_count = len(stocks)
    ind_counts = Counter(s.get("industry") or "未分類" for s in stocks)

    # 排序產業（檔數降序）
    sorted_inds = ind_counts.most_common()

    top_industries = []
    over_threshold_inds = []

    # 計算 HHI (Herfindahl-Hirschman Index)，衡量集中度 (0 ~ 10,000)
    hhi = 0.0

    for ind, count in sorted_inds:
        pct = round(count / total_count * 100.0, 1)
        is_concentrated = count >= threshold
        top_industries.append({
            "industry": ind,
            "count": count,
            "pct": pct,
            "is_concentrated": is_concentrated
        })

        if is_concentrated:
            over_threshold_inds.append((ind, count, pct))

        share_ratio = (count / total_count) * 100.0
        hhi += share_ratio ** 2

    # 分散度評分：HHI 越低越分散。轉化為 0 ~ 100 分
    # HHI < 1500 為高度分散 (90~100分)，1500~2500 為適度集中 (70~89分)，> 2500 為高度集中 (< 70分)
    if hhi <= 1500:
        div_score = round(max(85.0, 100.0 - (hhi / 1500.0) * 15.0), 1)
        div_level = "good"
    elif hhi <= 2500:
        div_score = round(70.0 + (2500.0 - hhi) / 1000.0 * 15.0, 1)
        div_level = "moderate"
    else:
        div_score = round(max(30.0, 70.0 - (hhi - 2500.0) / 7500.0 * 40.0), 1)
        div_level = "concentrated"

    alerts = []
    has_risk = len(over_threshold_inds) > 0

    if has_risk:
        for ind, count, pct in over_threshold_inds:
            alerts.append(
                f"⚠️【產業集中風險】「{ind}」共有 {count} 檔標的入選（佔比達 {pct}%），"
                f"超過分散門檻（{threshold} 檔）。配置時請留意產業過度集中風險，建議適度分散至傳產或金融防禦配置。"
            )
    else:
        alerts.append("🟢【產業配置分散】入選標的產業分布均勻，無單一產業過度集中問題。")

    summary_text = f"總計 {total_count} 檔標的分佈於 {len(sorted_inds)} 個產業。"
    if has_risk:
        top_name = over_threshold_inds[0][0]
        top_pct = over_threshold_inds[0][2]
        summary_text += f" 最大權重為「{top_name}」（{top_pct}%），請注意資金配置均衡。"
    else:
        summary_text += " 各產業配置比例適中，防禦性良好。"

    level = "low" if div_level == "good" else ("moderate" if div_level == "moderate" else "high")
    level_label = "🟢 產業配置分散" if level == "low" else ("🟡 產業輕度集中" if level == "moderate" else "🔴 產業高度集中")

    return {
        "total_stocks": total_count,
        "unique_industries_count": len(sorted_inds),
        "has_concentration_risk": has_risk,
        "is_concentrated": has_risk,
        "threshold": threshold,
        "alerts": alerts,
        "top_industries": top_industries,
        "industry_breakdown": top_industries,
        "hhi": round(hhi, 1),
        "diversification_score": div_score,
        "diversification_level": div_level,
        "level": level,
        "level_label": level_label,
        "summary": summary_text
    }
