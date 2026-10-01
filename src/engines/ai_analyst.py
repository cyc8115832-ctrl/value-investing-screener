"""
價值投資選股 App - AI 價值研究員引擎 (ai_analyst.py)
依據技術規格書 V1.7 第 18 章（V3.0 規劃）與個股第 6 頁「AI 解讀」：
- 自動閱讀：月營收 YoY、季報三率、EPS 滾動、合約負債、河流圖五段位階、領先訊號、三大法人籌碼
- 產出三大結構化專業研究維度：
  1. 【為何進入研究區】：核心投資亮點、護城河與估值性價比
  2. 【營運拐點與相較上季顯著變化】：三率毛利走勢、在手訂單合約負債、法人資金動態
  3. 【潛在下行風險與檢驗清單】：景氣週期、存貨去化、高估值倍數修正風險
- 嚴格遵守金融法規（規格書第 19 章）：
  - 純客觀事實與邏輯推理，嚴禁買賣建議、不出現「必賺」「買進」指令
  - 詳實標註資料來源與依據（如最新月營收、近4季季報、5日法人買賣超）
  - 內建離線確定性專家合成器 (Deterministic Expert Synthesizer)，零外部依賴 100% 穩定產出
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date


def generate_ai_research_report(
    stock_info: Dict[str, Any],
    price_info: Dict[str, Any],
    good_company_info: Dict[str, Any],
    eps_info: Dict[str, Any],
    river_info: Dict[str, Any],
    leading_info: Optional[Dict[str, Any]] = None,
    chip_info: Optional[Dict[str, Any]] = None,
    cashflow_info: Optional[Dict[str, Any]] = None,
    extreme_flag_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    純函式合成 AI 價值研究員深度個股分析報告
    """
    ticker = stock_info.get("ticker", "2330")
    name = stock_info.get("company_name", "台積電")
    industry = stock_info.get("industry", "半導體業")
    is_cyclical = stock_info.get("is_cyclical", False)
    sector_type = stock_info.get("sector_type", "electronics")

    cur_price = price_info.get("current_price", 100.0)
    cur_zone = river_info.get("current_zone", "fair")
    zone_name = river_info.get("zone_name_zh", "合理區")
    metric_type = river_info.get("metric", "pe").upper()

    overall_good = good_company_info.get("overall", "good")
    lights = good_company_info.get("lights", {})
    reasons = good_company_info.get("reasons", [])
    comp_score = good_company_info.get("composite_score", {})

    est_eps = eps_info.get("estimated_eps_base", 5.0)
    actual_eps = eps_info.get("actual_eps", 4.5)
    rev_g = eps_info.get("cumulative_rev_yoy_g", 0.0) * 100.0

    # ---------------- 1. 核心投資亮點與為何進入研究區 ----------------
    highlights = []
    if cur_zone in ["special", "cheap"]:
        highlights.append(f"【估值具備安全邊際】現價 ${cur_price} 處於 {metric_type} 河流圖之「{zone_name}」，低於歷史合理評價中軸，具備防守緩衝。")
    elif cur_zone == "fair":
        highlights.append(f"【合理估值常態持有】現價 ${cur_price} 位於「{zone_name}」，反映當前基本面營運價值，無過度溢價追高風險。")
    else:
        highlights.append(f"【估值位階偏高】現價 ${cur_price} 處於「{zone_name}」，估值倍數相對飽滿，建議關注基本面是否具備超預期成長。")

    if rev_g >= 15.0:
        highlights.append(f"【營收動能強勁】累計月營收年增率達 +{rev_g:.1f}%，顯示下游產業終端需求維持擴張態勢。")
    elif rev_g > 0:
        highlights.append(f"【營收穩步溫和成長】累計月營收年增 +{rev_g:.1f}%，業務經營維持正向基調。")
    else:
        highlights.append(f"【營收處於整理打底期】累計月營收年增 {rev_g:.1f}%，需檢視是否正處於新舊產品交替期。")

    if lights.get("margin") == "green":
        highlights.append("【獲利品質提升】近 4 季毛利率與營業利益率展現抗通膨能力，反映技術領先或定價權優勢。")

    grade = "AA"
    if comp_score:
        if isinstance(comp_score, dict):
            grade = comp_score.get("grade", "AA")
            score_val = comp_score.get("total_score", 75.0)
        else:
            grade = "AA"
            score_val = comp_score
        highlights.append(f"【體質評等】綜合好公司體質指標獲得 {grade} 級（{score_val} 分），基本面整體營運韌性高。")

    # ---------------- 2. 營運拐點與相較上季顯著變化 ----------------
    inflection_points = []
    if leading_info:
        lead_status = leading_info.get("status", "neutral")
        if lead_status == "strengthening":
            inflection_points.append("【領先訊號浮現正向拐點】領先訊號模組呈現綠燈轉強狀態，月營收連續突破或合約負債增長，預示短期具催化題材。")
        else:
            inflection_points.append("【領先訊號持平整固】未出現顯著過熱或急劇反轉，營運節奏與產業大週期同頻。")

    if cashflow_info and cashflow_info.get("applicable"):
        fcf_label = cashflow_info.get("fcf_quality_label", "")
        cl_data = cashflow_info.get("contract_liabilities", {})
        if cl_data.get("has_data") and cl_data.get("qoq_growth_pct") is not None:
            qoq = cl_data["qoq_growth_pct"]
            inflection_points.append(f"【訂單儲備能見度】最新季度合約負債（客戶預收款）季增 {qoq:+.1f}%，提供後續季度的營收轉化確定性。")
        if fcf_label:
            inflection_points.append(f"【真實現金轉化】自由現金流狀況：{fcf_label}，帳面獲利具備現金流支撐。")

    if chip_info and chip_info.get("status") == "success":
        stance_tag = chip_info.get("stance", {}).get("tag", "")
        cum_5d = chip_info.get("cumulative_5d", {}).get("total", 0.0)
        if stance_tag:
            inflection_points.append(f"【籌碼資金態度】三大法人近 5 日合計買賣超 {cum_5d:+.0f} 張，動態標籤為「{stance_tag}」。")

    # ---------------- 3. 潛在下行風險與防守檢驗清單 ----------------
    risk_checklist = []
    if is_cyclical:
        risk_checklist.append("【景氣循環波動風險】本股屬於景氣循環特徵標的，高獲利期常伴隨產品報價高峰，需防範報價反轉與產能過剩風險。")

    if extreme_flag_info and extreme_flag_info.get("flagged"):
        risk_checklist.append(f"【估值極端警示】觸發極端旗標：{extreme_flag_info.get('message', '估值倍數處於歷史極高分位')}。")

    if lights.get("cashflow") in ["yellow", "red"]:
        risk_checklist.append("【資本支出吃緊】自由現金流偏低或為負，請持續追蹤公司資本支出與營業現金流匹配度。")

    if lights.get("eps") == "yellow":
        risk_checklist.append("【獲利成長放緩】近期 EPS 成長力道趨平，若後續季報未達市場共識，恐面臨本益比修正壓力。")

    # 補充通則型防守確認
    risk_checklist.append("【宏觀利率敏感度】留意國際無風險利率（美債殖利率）變動，若全球流動性收縮，高估值倍數族群修正波動較大。")

    # ---------------- 綜合結構報告封裝 ----------------
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return {
        "ticker": ticker,
        "company_name": name,
        "industry": industry,
        "generated_at": now_str,
        "compliance_disclaimer": "⚠️ 【研究宣告與資料揭露】本報告由系統依據公開財務報表、月營收公告與交易數據自動結構化生成，僅供個人價值投資研究參考，不構成任何形式之有價證券買賣建議或獲利保證。投資人應獨立判斷並自負投資風險。",
        "report_sections": {
            "core_investment_highlights": {
                "title": "📌 一、核心投資亮點與評價優勢",
                "items": highlights,
                "data_source": "證交所日收盤價、最新月營收公告、河流圖估值模型"
            },
            "operational_inflection_points": {
                "title": "📈 二、營運拐點與財報質性變化",
                "items": inflection_points,
                "data_source": "最新季報三率、合約負債科目、三大法人日買賣超彙整"
            },
            "downside_risks_and_moat_defense": {
                "title": "🛡️ 三、潛在下行風險與護城河防守檢驗",
                "items": risk_checklist,
                "data_source": "歷史本益比區間、自由現金流覆蓋率、景氣週期特徵標籤"
            }
        },
        "executive_summary": f"{name} ({ticker}) 最新處於 {zone_name}，營收累計年增 {rev_g:+.1f}%，好公司體質評為 {grade} 級。投資人宜重點關注後續三率維持能力與在手合約負債轉化進度。"
    }
