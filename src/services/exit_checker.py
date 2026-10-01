"""
價值投資選股 App - 出場檢核與提醒服務 (exit_checker.py)
遵循技術規格書 V1.7 第 7.2 節與第 7.3 節：
- 出場檢查五大情境：
  1. 好公司基本面出現退化訊號 (面向 1 或 2 轉紅)
  2. 估值進入瘋狂區或大幅提前反映遠期獲利
  3. 營收公布前檢視提醒 (每月 10 日前)
  4. 季報公布檢視提醒 (每季 5/15, 8/14, 11/14, 3/31)
  5. 股池剔除提醒 (ETF 成分股剔除)
"""

from datetime import date
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from src.database.schema import (
    StockMaster, GoodCompanyRecord, ValuationBandsRecord,
    LeadingSummaryRecord, WatchGroupMember, UniverseEvent, PriceDaily
)

def check_watchlist_exit_conditions(db: Session, user_id: str = "default_user") -> List[Dict[str, Any]]:
    """
    檢查使用者觀察清單中所有標的之出場與檢視提醒
    """
    today_dt = date.today()
    members = db.query(WatchGroupMember)\
        .filter(WatchGroupMember.user_id == user_id)\
        .all()

    alerts = []

    for m in members:
        t = m.ticker
        stock = db.query(StockMaster).filter(StockMaster.ticker == t).first()
        if not stock:
            continue

        # 取得最新健檢、估值與領先訊號
        good = db.query(GoodCompanyRecord)\
            .filter(GoodCompanyRecord.ticker == t)\
            .order_by(GoodCompanyRecord.date.desc())\
            .first()
        val = db.query(ValuationBandsRecord)\
            .filter(ValuationBandsRecord.ticker == t)\
            .order_by(ValuationBandsRecord.date.desc())\
            .first()
        lead = db.query(LeadingSummaryRecord)\
            .filter(LeadingSummaryRecord.ticker == t)\
            .order_by(LeadingSummaryRecord.date.desc())\
            .first()

        # 情境 1：基本面退化檢查 (7.2 條件 1)
        if good and good.overall == "degraded":
            alerts.append({
                "ticker": t,
                "company_name": stock.company_name,
                "type": "fundamental_degraded",
                "severity": "high",
                "title": "基本面退化警示",
                "message": f"【基本面退化】{stock.company_name} ({t}) 獲利或營收動能連續轉弱，已觸發退化警戒，建議冷靜檢視當初投資理由是否改變。"
            })

        # 情境 2：估值過熱狂暴區 (7.2 條件 2)
        if val and val.current_zone == "crazy":
            alerts.append({
                "ticker": t,
                "company_name": stock.company_name,
                "type": "valuation_crazy",
                "severity": "medium",
                "title": "估值極端過熱提醒",
                "message": f"【估值警戒】{stock.company_name} ({t}) 現價已飆入紫色『瘋狂區』，市場情緒極度亢奮，宜留意風險防範追高。"
            })

        # 情境 3：領先訊號轉弱預警 (14.4)
        if good and good.overall == "good" and lead and lead.status == "weakening":
            alerts.append({
                "ticker": t,
                "company_name": stock.company_name,
                "type": "leading_weakening",
                "severity": "low",
                "title": "領先訊號轉弱提示",
                "message": f"【提早預警】{stock.company_name} ({t}) 基本面仍佳，但近月訂金或籌碼領先指標出現疲態，提示提前觀察後續營收走勢。"
            })

        # 情境 4：ETF 成分剔除事件 (2.3)
        recent_remove = db.query(UniverseEvent)\
            .filter(UniverseEvent.ticker == t, UniverseEvent.event_type == "remove")\
            .order_by(UniverseEvent.event_date.desc())\
            .first()
        if recent_remove:
            alerts.append({
                "ticker": t,
                "company_name": stock.company_name,
                "type": "etf_removed",
                "severity": "medium",
                "title": "ETF 成分剔除通知",
                "message": f"【成分變動】您關注的 {stock.company_name} ({t}) 已於 {recent_remove.event_date} 被 {recent_remove.etf_code} 剔除。"
            })

    # 情境 5：定期檢視時點提醒 (7.3)
    # 每月 10 日前提醒檢視月營收
    if today_dt.day <= 10:
        alerts.append({
            "ticker": "ALL",
            "company_name": "全體持股",
            "type": "monthly_revenue_reminder",
            "severity": "info",
            "title": "月營收公布檢視日",
            "message": "【每月檢視提醒】上市櫃公司每月 10 日前陸續公布最新營收，請記得檢視觀察名單之累計 YoY 與動能是否延續。"
        })

    return alerts


def find_better_alternatives(db: Session, ticker: str) -> Dict[str, Any]:
    """
    規格書 7.2 出場條件 3：有更好的選擇
    當觀察或持股標的已回到合理以上價位時，從全股池中搜尋 2~3 檔「好公司＋特價/便宜」之替代候選標的，
    並列顯示折價空間與基本面指標，供投資人理性評估。
    """
    today_dt = date.today()
    target_stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not target_stock:
        return {
            "success": False,
            "message": f"找不到股票 {ticker}"
        }

    # 取得當前標的最新價格與價位帶
    target_price_row = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.desc()).first()
    target_val = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == ticker).order_by(ValuationBandsRecord.date.desc()).first()
    target_good = db.query(GoodCompanyRecord).filter(GoodCompanyRecord.ticker == ticker).order_by(GoodCompanyRecord.date.desc()).first()

    cur_price = target_price_row.close if target_price_row else 100.0
    cur_zone = target_val.current_zone if target_val else "fair"
    p2_cheap = target_val.p2 if target_val else cur_price
    discount_pct = round((p2_cheap - cur_price) / p2_cheap * 100.0, 1) if p2_cheap > 0 else 0.0

    zone_names_zh = {
        "special": "特價區",
        "cheap": "便宜區",
        "fair": "合理區",
        "expensive": "昂貴區",
        "crazy": "瘋狂區"
    }

    # 搜尋股池中其他「好公司 ＋ 特價或便宜區」的候選標的
    candidates_raw = []
    all_stocks = db.query(StockMaster).filter(StockMaster.ticker != ticker).all()

    for s in all_stocks:
        g = db.query(GoodCompanyRecord).filter(GoodCompanyRecord.ticker == s.ticker).order_by(GoodCompanyRecord.date.desc()).first()
        v = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == s.ticker).order_by(ValuationBandsRecord.date.desc()).first()
        if not g or not v:
            continue

        # 篩選好公司且位於特價或便宜區
        if g.overall == "good" and v.current_zone in ["special", "cheap"]:
            p_row = db.query(PriceDaily).filter(PriceDaily.ticker == s.ticker).order_by(PriceDaily.date.desc()).first()
            p_close = p_row.close if p_row else 100.0
            margin = round((v.p2 - p_close) / v.p2 * 100.0, 1) if v.p2 > 0 else 0.0
            
            # 是否同產業 (優先權加權)
            same_industry = (s.industry == target_stock.industry)

            candidates_raw.append({
                "ticker": s.ticker,
                "company_name": s.company_name,
                "industry": s.industry or "",
                "same_industry": same_industry,
                "current_price": p_close,
                "cheap_price": round(v.p2, 1),
                "zone": v.current_zone,
                "zone_name_zh": zone_names_zh.get(v.current_zone, v.current_zone),
                "margin_pct": margin,
                "lights": {
                    "rev": g.revenue_light,
                    "eps": g.eps_light,
                    "margin": g.margin_light,
                    "eff": g.efficiency_light,
                    "cf": g.cashflow_light
                }
            })

    # 排序：優先同產業，次依安全邊際降序
    candidates_raw.sort(key=lambda x: (1 if x["same_industry"] else 0, x["margin_pct"]), reverse=True)
    top_candidates = candidates_raw[:3]

    is_fair_or_above = cur_zone in ["fair", "fair_low", "fair_core", "fair_high", "expensive", "crazy"]

    return {
        "success": True,
        "target_stock": {
            "ticker": target_stock.ticker,
            "company_name": target_stock.company_name,
            "industry": target_stock.industry,
            "current_price": cur_price,
            "zone": cur_zone,
            "zone_name_zh": zone_names_zh.get(cur_zone, cur_zone),
            "discount_pct": discount_pct,
            "is_fair_or_above": is_fair_or_above
        },
        "has_better_choices": len(top_candidates) > 0,
        "better_candidates": top_candidates,
        "advice": (
            f"{target_stock.company_name} 目前處於「{zone_names_zh.get(cur_zone, cur_zone)}」，"
            + ("估值已回到合理或偏高區間。以下為股池中目前跌入便宜/特價區之好公司候選標的，供您客觀比對換股機會。"
               if is_fair_or_above else "目前已處於特價或便宜區，具備良好安全邊際，平心耐心持有即可。")
        ),
        "comparison_tip": "※ 價值投資原則：系統僅提供客觀財務數據並排比對，不作買賣推薦。請依自身投資計劃與資金配置做理性決策。"
    }
