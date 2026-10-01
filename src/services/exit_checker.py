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
    LeadingSummaryRecord, WatchGroupMember, UniverseEvent
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
