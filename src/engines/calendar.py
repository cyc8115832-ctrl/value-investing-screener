"""
價值投資選股 App - 財經行事曆與檢視提醒引擎 (calendar.py)
嚴格落實技術規格書 V1.7 第 7.3、15.2、18 章：
- 法定營收截止日：每月 10 日公布上月營收（逢假日順延至次一營業日）
- 法定財報公布日：Q1 (5/15)、Q2 (8/14)、Q3 (11/14)、Q4 及年報 (3/31)
- 觀察股除權息行事曆 (ex-dividend calendar)
- 提供使用者觀察標的專屬重要事件檢視提醒
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from src.database.schema import (
    StockMaster, WatchGroupMember, DividendHistory, PriceDaily
)


def get_month_revenue_deadline(year: int, month: int) -> date:
    """取得特定月份營收公布之截止日 (每月 10 號，若為週六日則順延)"""
    d = date(year, month, 10)
    if d.weekday() == 5:  # 週六順延至週一
        d += timedelta(days=2)
    elif d.weekday() == 6:  # 週日順延至週一
        d += timedelta(days=1)
    return d


def generate_financial_calendar(
    db: Session,
    target_year: Optional[int] = None,
    target_month: Optional[int] = None,
    user_id: str = "default_user"
) -> Dict[str, Any]:
    """
    產生日曆事件與檢視提醒清單
    """
    today = date.today()
    cur_year = target_year or today.year
    cur_month = target_month or today.month

    # 1. 取得使用者觀察清單代碼
    watchlist_tickers = [
        row[0] for row in db.query(WatchGroupMember.ticker)\
            .filter(WatchGroupMember.user_id == user_id)\
            .distinct()\
            .all()
    ]

    events = []

    # 2. 法定營收截止日事件 (每月 10 日)
    rev_deadline = get_month_revenue_deadline(cur_year, cur_month)
    prior_month_name = f"{(cur_month - 1) if cur_month > 1 else 12} 月"
    is_today_rev = (rev_deadline == today)
    events.append({
        "date": rev_deadline.isoformat(),
        "type": "revenue_deadline",
        "title": f"📊 {prior_month_name}份全體上市櫃月營收公告截止日",
        "category": "法定重大申報",
        "description": f"依證交所法規，所有上市櫃公司必須於本日 23:59 前申報 {prior_month_name} 營業收入。好公司引擎將即時重算最新營收動能燈號。",
        "is_today": is_today_rev,
        "is_past": rev_deadline < today,
        "highlight": True
    })

    # 3. 季報法定公告截止日
    quarterly_deadlines = [
        (3, 31, "年度年報及 Q4 財報申報截止日", "Q4"),
        (5, 15, "第一季 (Q1) 季報申報截止日", "Q1"),
        (8, 14, "第二季 (Q2) 季報申報截止日", "Q2"),
        (11, 14, "第三季 (Q3) 季報申報截止日", "Q3")
    ]

    for m, d_day, q_title, q_code in quarterly_deadlines:
        if m == cur_month:
            q_date = date(cur_year, m, d_day)
            # 若遇週末順延
            if q_date.weekday() == 5:
                q_date += timedelta(days=2)
            elif q_date.weekday() == 6:
                q_date += timedelta(days=1)

            events.append({
                "date": q_date.isoformat(),
                "type": "earnings_deadline",
                "title": f"📑 {q_title}",
                "category": "法定重大申報",
                "description": f"全體上市櫃公司 {q_code} 財務報表揭露期限。請檢視觀察股三率（毛利率、營業利益率、淨利率）與 ROE 變化。",
                "is_today": (q_date == today),
                "is_past": q_date < today,
                "highlight": True
            })

    # 4. 除息與除權日程 (涵蓋觀察清單與股池)
    # 查詢當前月份之除息事件
    month_start = date(cur_year, cur_month, 1)
    next_month_start = date(cur_year + (1 if cur_month == 12 else 0), 1 if cur_month == 12 else cur_month + 1, 1)
    month_end = next_month_start - timedelta(days=1)

    divs = db.query(DividendHistory, StockMaster)\
        .join(StockMaster, DividendHistory.ticker == StockMaster.ticker)\
        .filter(DividendHistory.ex_date >= month_start, DividendHistory.ex_date <= month_end)\
        .order_by(DividendHistory.ex_date.asc())\
        .all()

    for div, stock in divs:
        is_my_watch = stock.ticker in watchlist_tickers
        events.append({
            "date": div.ex_date.isoformat(),
            "type": "ex_dividend",
            "ticker": stock.ticker,
            "company_name": stock.company_name,
            "title": f"💰 {stock.company_name} ({stock.ticker}) 除息日",
            "category": "除權息事件",
            "description": f"配發現金股利 {div.cash_dividend:.2f} 元" + (f"、股票股利 {div.stock_dividend:.2f} 元" if div.stock_dividend > 0 else "") + f"（預計發放日: {div.pay_date or '待定'}）",
            "is_my_watch": is_my_watch,
            "is_today": (div.ex_date == today),
            "is_past": div.ex_date < today,
            "highlight": is_my_watch
        })

    # 排序事件 (依日期升冪)
    events.sort(key=lambda x: x["date"])

    # 5. 彙整「本週/近期觀察清單檢視提醒」
    watchlist_reminders = []
    for t in watchlist_tickers:
        stk = db.query(StockMaster).filter(StockMaster.ticker == t).first()
        if stk:
            watchlist_reminders.append({
                "ticker": t,
                "company_name": stk.company_name,
                "monthly_rev_reminder": f"每月 10 日前關注 {stk.company_name} 最新營收是否持續維持 YoY 成長。",
                "earnings_reminder": "季報公布日請特別檢查毛利率是否連續 2 季衰退或業外佔比過高。"
            })

    return {
        "year": cur_year,
        "month": cur_month,
        "calendar_name": f"{cur_year} 年 {cur_month} 月 財經行事曆",
        "total_events": len(events),
        "events": events,
        "watchlist_reminders": watchlist_reminders,
        "notice": "※ 行事曆依證交所公告日程編排，遇例假日自動順延至次一營業日。"
    }
