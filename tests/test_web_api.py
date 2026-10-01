"""
測試 Web API 與端點整合 (tests/test_web_api.py)
"""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)

def test_index_page():
    """測試主頁面 HTML 回應"""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "價值投資選股 App" in resp.text
    assert "先選好公司" in resp.text


def test_api_radar():
    """測試雷達首頁統計 API"""
    resp = client.get("/api/radar")
    assert resp.status_code == 200
    data = resp.json()
    assert "universe_summary" in data
    assert "quadrant_counts" in data
    assert "macro_us10y" in data
    assert data["universe_summary"]["union_total_stocks"] > 0


def test_api_screener():
    """測試選股列表與篩選 API"""
    resp = client.get("/api/screener")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "ticker" in first
    assert "current_price" in first
    assert "current_zone" in first
    assert "lights" in first


def test_api_stock_detail():
    """測試個股詳情與河流圖數據 API"""
    resp = client.get("/api/stocks/2330")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "2330"
    assert "conclusion_bar" in data
    assert "river" in data
    assert "good_company" in data
    assert "eps_details" in data
    assert "leading_signals" in data
    assert "alternative_valuations" in data

    # 驗證河流圖價格線 P1 ~ P6 是否存在且由小到大
    rp = data["river"]["prices"]
    assert rp["p1_special"] < rp["p2_cheap"] < rp["p5_expensive"] < rp["p6_crazy"]


def test_api_watchlist():
    """測試觀察清單 API"""
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 4  # 4 個系統分組


def test_api_alerts():
    """測試出場檢視提醒 API"""
    resp = client.get("/api/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_api_manual_and_glossary():
    """測試手冊與詞典 API"""
    resp_m = client.get("/api/manual")
    assert resp_m.status_code == 200
    assert len(resp_m.json()) >= 3

    resp_g = client.get("/api/glossary")
    assert resp_g.status_code == 200
    assert len(resp_g.json()) >= 4


def test_api_push_preview():
    """測試 LINE 推播格式化預覽 API"""
    resp = client.get("/api/push/preview", params={"elder_mode": False})
    # Note: route was defined as POST, let's verify both
    resp = client.post("/api/push/preview?elder_mode=false")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "【價值投資選股】" in data["content"]


def test_api_backtest_report():
    """測試策略回測驗證報告 API"""
    resp = client.get("/api/backtest")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategy_baseline" in data
    assert "strategy_enhanced" in data
    assert "comparison" in data
    assert data["comparison"]["win_rate_improvement_12m"] > 0
