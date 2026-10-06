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


# 產業屬性與差異化配置寄語庫 (依產業週期、景氣連動度與防禦屬性量身訂製)
INDUSTRY_PROFILES: Dict[str, Dict[str, str]] = {
    "半導體業": {
        "trait": "具高成長性與強科技動能，但景氣循環波動劇烈，受全球資本支出與消費性電子週期影響甚大",
        "action": "留意高波動風險，切忌在估值過熱或昂貴區追高，建議搭配高股息、民生內需或公用事業平衡組合波動。"
    },
    "金融保險業": {
        "trait": "獲利與配息相對穩健，具防禦性與股息保護傘，但受央行降息利差縮小及景氣衰退資產品質影響",
        "action": "可作為領息與抗跌防守核心，但須留意淨利差 (NIM) 走勢與投資部位評價波動，避免整體資金過度偏向單一金融牌照。"
    },
    "電腦及週邊": {
        "trait": "多受惠 AI 伺服器與硬體換機潮，但營運多屬組裝代工與品牌競爭，毛利率偏薄且資本支出高",
        "action": "配置應著重具備高合約負債動能與高毛利優勢者，並配置上游原料或非科技類股分散供應鏈瓶頸風險。"
    },
    "電子零組件": {
        "trait": "涵蓋被動元件、PCB、散熱等關鍵配件，營收彈性大，但容易受下游拉貨停滯造成庫存去化壓力",
        "action": "建議關注個別龍頭之營收 YoY 轉折與存貨週轉天數，適度分批佈局，防範單一科技次產業反轉回挫。"
    },
    "通信網路業": {
        "trait": "營收來自電信資費與基建，具天然寡占與極高現金流確定性，防禦性極強",
        "action": "適合作為熊市避風港與穩定股息來源，但資本成長動能相對溫和，可視為資產配置中的防禦穩定基石。"
    },
    "航運業": {
        "trait": "極度強烈的景氣循環股，運價 (SCFI/BDI) 與全球貿易盛衰高度連動，獲利爆發力與退潮速度皆極快",
        "action": "嚴格遵守河流圖特價區與低 P/B 買進紀律，切勿以景氣高峰時之超低 P/E 或高配息誤判價值，必須落實資金控管。"
    },
    "鋼鐵工業": {
        "trait": "重工業景氣循環基石，受大宗原物料報價 (鐵礦砂/煤) 與中國基建房市需求強烈牽動",
        "action": "宜在報價谷底、產能去化期逢低佈局，並搭配高成長或高毛利之輕資產好公司平衡資金週轉效率。"
    },
    "塑膠工業": {
        "trait": "原物料石化循環股，受原油油價震盪及全球石化產能擴張供需牽動顯著",
        "action": "注意產品利差 (Spread) 變化，建議僅於特價區低本淨比時配置，並分散至具穩定現金流的終端消費內需板塊。"
    },
    "貿易百貨業": {
        "trait": "以民間消費、民生剛需與通路零售為主，受宏觀通膨與可支配所得影響，但營收現金流極為穩定",
        "action": "防守價值顯著，可有效抗衡科技股下跌回檔，建議長期持有並將股息再投入以發揮複利滾雪球優勢。"
    },
    "其他業": {
        "trait": "包含各類多元利基龍頭（如製鞋代工、租賃控股），各具獨特商業模式與全球布局",
        "action": "應深入檢視個別企業之自由現金流與應收帳款品質，確保個別利基優勢不易被同業侵蝕。"
    }
}

DEFAULT_PROFILE = {
    "trait": "產業比重高於分散配置門檻，組合連動度可能過於集中",
    "action": "建議檢視產業週期連動性，適度分散資金至不同防禦面向或傳產配置，避免市場單一黑天鵝衝擊。"
}


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
            prof = INDUSTRY_PROFILES.get(ind, DEFAULT_PROFILE)
            alerts.append(
                f"⚠️【產業集中風險】「{ind}」共有 {count} 檔標的入選（佔比達 {pct}%），超過分散門檻（{threshold} 檔）。"
                f"【特質剖析】{prof['trait']}。💡【配置寄語】{prof['action']}"
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
