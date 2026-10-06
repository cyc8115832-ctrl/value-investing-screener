"""
測試產業集中度風控分析模組與系統資料庫品質監控服務
對應規格書待決事項 D-14、第 10 章、第 13.10 節、第 15.1 節與第 20.1 節
"""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app
from src.database.session import SessionLocal
from src.data.mock_fixtures import seed_database_fixtures
from src.engines.industry_concentration import analyze_industry_concentration
from src.services.data_quality import get_data_quality_report
from src.services.line_push import format_daily_line_message

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def init_db():
    db = SessionLocal()
    seed_database_fixtures(db)
    yield db
    db.close()


def test_industry_concentration_diversified():
    """驗證高度分散之產業組合（10 檔不同產業，HHI = 1000）：無警示、低 HHI、高分散分數"""
    stocks = [
        {"ticker": f"STK_{i}", "company_name": f"公司_{i}", "industry": f"產業_{i}"}
        for i in range(10)
    ]
    res = analyze_industry_concentration(stocks, threshold=3)
    assert res["total_stocks"] == 10
    assert res["unique_industries_count"] == 10
    assert res["is_concentrated"] is False
    assert len(res["alerts"]) == 1
    assert "🟢" in res["alerts"][0]
    assert res["level"] == "low"
    assert "🟢" in res["level_label"]
    assert res["diversification_score"] >= 85.0
    assert res["hhi"] == 1000  # 10 * (10)^2 = 1000


def test_industry_concentration_concentrated_alert():
    """驗證單一產業達門檻（>=3 檔）時觸發風控警示與 HHI 提高"""
    stocks = [
        {"ticker": "2330", "company_name": "台積電", "industry": "半導體業"},
        {"ticker": "2454", "company_name": "聯發科", "industry": "半導體業"},
        {"ticker": "2303", "company_name": "聯電", "industry": "半導體業"},
        {"ticker": "2379", "company_name": "瑞昱", "industry": "半導體業"},
        {"ticker": "2412", "company_name": "中華電", "industry": "通信網路業"},
    ]
    res = analyze_industry_concentration(stocks, threshold=3)
    assert res["total_stocks"] == 5
    assert res["is_concentrated"] is True
    assert len(res["alerts"]) >= 1
    assert "半導體業" in res["alerts"][0]
    assert "80.0%" in res["alerts"][0]
    assert res["level"] == "high"
    assert "🔴" in res["level_label"]
    assert res["diversification_score"] <= 50.0
    # HHI = 80^2 + 20^2 = 6400 + 400 = 6800
    assert res["hhi"] == 6800


def test_industry_concentration_empty():
    """驗證空股票清單的防呆回傳"""
    res = analyze_industry_concentration([])
    assert res["total_stocks"] == 0
    assert res["hhi"] == 0.0
    assert res["diversification_score"] == 100.0
    assert res["is_concentrated"] is False
    assert len(res["alerts"]) == 0


def test_data_quality_report_service(init_db):
    """驗證資料庫資料品質監控報告計算 (覆蓋率、健康指數、評等)"""
    db = init_db
    report = get_data_quality_report(db)
    
    assert report["total_stocks"] >= 10
    assert report["overall_health_pct"] >= 70.0
    assert report["grade"] in ["A+", "A", "B", "C"]
    assert report["status"] in ["healthy", "good", "warning", "danger"]
    assert "metrics" in report
    
    m = report["metrics"]
    assert 0.0 <= m["price_coverage_pct"] <= 100.0
    assert 0.0 <= m["revenue_coverage_pct"] <= 100.0
    assert 0.0 <= m["financials_coverage_pct"] <= 100.0
    assert 0.0 <= m["chip_coverage_pct"] <= 100.0
    assert isinstance(report["anomalies_count"], int)
    assert isinstance(report["anomalies"], list)


def test_data_quality_report_api():
    """驗證 GET /api/data-quality/report 端點規格與回傳內容"""
    res = client.get("/api/data-quality/report")
    assert res.status_code == 200
    data = res.json()
    assert "overall_health_pct" in data
    assert "grade" in data
    assert "summary" in data
    assert "metrics" in data
    assert "price_coverage_pct" in data["metrics"]


def test_radar_industry_concentration_integration():
    """驗證 GET /api/radar 端點回傳包含 industry_concentration 欄位"""
    res = client.get("/api/radar")
    assert res.status_code == 200
    data = res.json()
    assert "industry_concentration" in data
    ic = data["industry_concentration"]
    assert "total_stocks" in ic
    assert "hhi" in ic
    assert "diversification_score" in ic
    assert "alerts" in ic
    assert "industry_breakdown" in ic
    assert len(ic["industry_breakdown"]) > 0


def test_line_push_industry_concentration_alert(init_db):
    """驗證 LINE 推播訊息中當選入標的產業集中 (>=2 檔) 時自動附加風控提醒 (規格書 15.1)"""
    from datetime import date
    from src.database.schema import DailyPickRecord
    import json

    db = init_db
    today = date.today()

    # 先清除該日期可能已由 pipeline 產生的舊精選紀錄，以確保測試環境隔離
    existing_picks = db.query(DailyPickRecord).filter(DailyPickRecord.pick_date == today).all()
    for ep in existing_picks:
        db.delete(ep)
    db.commit()

    # 插入兩筆同屬於半導體業的精選標的 (2330 與 2454)
    p1 = DailyPickRecord(
        pick_date=today,
        ticker="2330",
        list_type="pick",
        rank=1,
        margin_pct=15.2,
        reasons_json=json.dumps(["✓ 本益比河流圖位於便宜區間", "✓ 好公司健檢五燈全亮"])
    )
    p2 = DailyPickRecord(
        pick_date=today,
        ticker="2454",
        list_type="pick",
        rank=2,
        margin_pct=12.8,
        reasons_json=json.dumps(["✓ 本益比河流圖位於特價區間", "✓ 連續 5 年 ROE 大於 15%"])
    )
    db.add(p1)
    db.add(p2)
    db.commit()

    try:
        # 測試標準版
        msg_std = format_daily_line_message(db, pick_date=today, elder_mode=False)
        assert "產業分散提醒" in msg_std
        assert "半導體業" in msg_std

        # 測試長輩版
        msg_elder = format_daily_line_message(db, pick_date=today, elder_mode=True)
        assert "半導體業" in msg_elder
        assert "產業分散" in msg_elder
    finally:
        # 清理測試紀錄
        db.delete(p1)
        db.delete(p2)
        db.commit()
