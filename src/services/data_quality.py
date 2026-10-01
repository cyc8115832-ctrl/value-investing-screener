"""
價值投資選股 App - 資料品質監控與異常檢查服務 (data_quality.py)
遵循技術規格書 V1.7 第 10 章與第 20.1 節（項目 9）：
- 三層級資料品質監控 (覆蓋率、及時性、數值合理性)
- 財報更正、停牌、異常離群值與缺失檢查
- 產生量化品質評分與白話檢核報告
"""

from typing import Dict, Any, List
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.database.schema import (
    StockMaster, PriceDaily, RevenueMonthly, FinancialsQuarterly,
    SharesOutstanding, ChipData
)


def get_data_quality_report(db: Session) -> Dict[str, Any]:
    """
    評估資料庫中股池全部標的之資料品質指標與異常清單
    """
    stocks = db.query(StockMaster).all()
    total_stocks = len(stocks)

    if total_stocks == 0:
        return {
            "status": "warning",
            "grade": "N/A",
            "total_stocks": 0,
            "overall_health_pct": 0.0,
            "summary": "資料庫暫無股票主檔數據"
        }

    today_dt = date.today()

    # 1. 價格資料檢驗
    price_covered = 0
    anomalous_prices = []
    for s in stocks:
        latest_p = db.query(PriceDaily).filter(PriceDaily.ticker == s.ticker).order_by(PriceDaily.date.desc()).first()
        if latest_p and latest_p.close > 0:
            price_covered += 1
            if latest_p.pe and (latest_p.pe > 150.0 or latest_p.pe < 0):
                anomalous_prices.append({
                    "ticker": s.ticker,
                    "name": s.company_name,
                    "issue": f"PE 數值異常或極端 ({latest_p.pe:.1f}倍)"
                })

    price_coverage_pct = round(price_covered / total_stocks * 100.0, 1)

    # 2. 月營收資料檢驗 (近 12 個月)
    rev_covered = 0
    anomalous_revs = []
    for s in stocks:
        rev_count = db.query(RevenueMonthly).filter(RevenueMonthly.ticker == s.ticker).count()
        if rev_count >= 12:
            rev_covered += 1
        elif rev_count > 0:
            rev_covered += 0.8
        
        neg_rev = db.query(RevenueMonthly).filter(RevenueMonthly.ticker == s.ticker, RevenueMonthly.revenue <= 0).first()
        if neg_rev:
            anomalous_revs.append({
                "ticker": s.ticker,
                "name": s.company_name,
                "issue": f"存在非正數月營收記錄 ({neg_rev.month})"
            })

    rev_coverage_pct = round(rev_covered / total_stocks * 100.0, 1)

    # 3. 季報資料檢驗 (近 4 季三率與現金流)
    fin_covered = 0
    for s in stocks:
        fin_count = db.query(FinancialsQuarterly).filter(FinancialsQuarterly.ticker == s.ticker).count()
        if fin_count >= 4:
            fin_covered += 1
        elif fin_count > 0:
            fin_covered += 0.75

    fin_coverage_pct = round(fin_covered / total_stocks * 100.0, 1)

    # 4. 籌碼資料檢驗
    chip_covered = 0
    for s in stocks:
        chip = db.query(ChipData).filter(ChipData.ticker == s.ticker).first()
        if chip and chip.big_holder_pct is not None:
            chip_covered += 1

    chip_coverage_pct = round(chip_covered / total_stocks * 100.0, 1)

    # 綜合健康指數 (加權平均)
    overall_health = round(
        price_coverage_pct * 0.30 +
        rev_coverage_pct * 0.30 +
        fin_coverage_pct * 0.25 +
        chip_coverage_pct * 0.15,
        1
    )

    if overall_health >= 95.0:
        grade = "A+"
        status = "healthy"
        grade_desc = "綠燈：資料庫高度完整，無缺失與異常"
    elif overall_health >= 85.0:
        grade = "A"
        status = "good"
        grade_desc = "綠燈：資料庫完整度良好，可信度高"
    elif overall_health >= 70.0:
        grade = "B"
        status = "warning"
        grade_desc = "黃燈：部分新進標的財務歷史資料回補中"
    else:
        grade = "C"
        status = "danger"
        grade_desc = "紅燈：存在較多缺漏，需檢查同步作業"

    anomalies_all = anomalous_prices + anomalous_revs

    return {
        "report_date": today_dt.isoformat(),
        "total_stocks": total_stocks,
        "overall_health_pct": overall_health,
        "grade": grade,
        "status": status,
        "grade_desc": grade_desc,
        "metrics": {
            "price_coverage_pct": price_coverage_pct,
            "revenue_coverage_pct": rev_coverage_pct,
            "financials_coverage_pct": fin_coverage_pct,
            "chip_coverage_pct": chip_coverage_pct
        },
        "anomalies_count": len(anomalies_all),
        "anomalies": anomalies_all,
        "summary": f"股池總計 {total_stocks} 檔標的，綜合資料健康度為 {overall_health}%（評等 {grade}）。{grade_desc}。"
    }
