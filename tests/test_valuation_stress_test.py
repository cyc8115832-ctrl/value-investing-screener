"""
價值投資選股 App - 多情境估值敏感度與黑天鵝壓力測試測試套件 (tests/test_valuation_stress_test.py)
驗證項目：
1. 純函式三情境估值敏感度試算 (樂觀超預期、基準中位、悲觀逆風)
2. 黑天鵝防守底線 (每股有形淨值線、歷史 PE/PB 極限底線、下行安全緩衝)
3. 風險報酬比 (Risk / Reward Ratio) 與進場吸引力評級
4. 景氣循環股防守底線適配 (偏重有形淨值)
5. 異常輸入防呆 (現價 <= 0 檢查)
6. RESTful API GET /api/stocks/{ticker}/stress-test 整合端點測試
"""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app
from src.engines.valuation_stress_test import calculate_valuation_stress_test

client = TestClient(app)


def test_valuation_stress_test_pure_basic():
    """測試純函式三情境試算：樂觀 +20%、基準、悲觀 -20%"""
    anchors = {"a1": 12.0, "a2": 15.0, "a3": 18.0, "a4": 21.0, "a5": 24.0, "a6": 28.0}
    res = calculate_valuation_stress_test(
        ticker="2330",
        current_price=500.0,
        base_eps=30.0,
        book_value_per_share=150.0,
        pe_anchors=anchors,
        historical_min_pe=12.0,
        historical_min_pb=3.0,
        optimistic_growth_pct=20.0,
        pessimistic_growth_pct=-20.0,
        is_cyclical=False
    )

    assert res["success"] is True
    scenarios = res["scenarios"]
    opt = scenarios["optimistic"]
    base = scenarios["base"]
    pess = scenarios["pessimistic"]

    # 樂觀 EPS: 30 * 1.2 = 36, target PE: a4 (21) -> 756
    assert opt["projected_eps"] == 36.0
    assert opt["projected_price"] == 756.0
    assert opt["change_pct"] > 0

    # 基準 EPS: 30, target PE: a3 (18) -> 540
    assert base["projected_eps"] == 30.0
    assert base["projected_price"] == 540.0
    assert base["change_pct"] > 0

    # 悲觀 EPS: 30 * 0.8 = 24, target PE: a2 (15) -> 360
    assert pess["projected_eps"] == 24.0
    assert pess["projected_price"] == 360.0
    assert pess["change_pct"] < 0


def test_valuation_stress_test_floor_price_and_cushion():
    """測試黑天鵝極限防守底線與安全緩衝評級"""
    anchors = {"a1": 10.0, "a2": 12.0, "a3": 15.0, "a4": 18.0, "a5": 22.0, "a6": 25.0}
    res = calculate_valuation_stress_test(
        ticker="2317",
        current_price=100.0,
        base_eps=10.0,
        book_value_per_share=90.0,
        pe_anchors=anchors,
        historical_min_pe=8.0,
        historical_min_pb=0.9,
        is_cyclical=False
    )

    floor = res["floor_test"]
    assert floor["ultimate_floor_price"] <= 100.0
    assert floor["ultimate_floor_price"] > 0
    assert floor["safety_cushion_pct"] >= 0
    assert floor["cushion_grade"] in ["very_strong", "moderate", "wide"]


def test_valuation_stress_test_cyclical():
    """測試景氣循環股偏重淨值底線之防守特性"""
    anchors = {"a1": 10.0, "a2": 12.0, "a3": 15.0, "a4": 18.0, "a5": 20.0, "a6": 24.0}
    res = calculate_valuation_stress_test(
        ticker="2603",
        current_price=150.0,
        base_eps=15.0,
        book_value_per_share=200.0,
        pe_anchors=anchors,
        historical_min_pe=5.0,
        historical_min_pb=0.6,
        is_cyclical=True
    )

    assert res["success"] is True
    assert res["base_metrics"]["is_cyclical"] is True
    assert res["floor_test"]["tangible_floor_price"] == 160.0  # 200 * 0.8 = 160


def test_valuation_stress_test_risk_reward():
    """測試風險報酬比 (Risk / Reward Ratio)"""
    anchors = {"a1": 12.0, "a2": 15.0, "a3": 20.0, "a4": 25.0, "a5": 30.0, "a6": 35.0}
    # 現價 100，基準預估價 200 (賺 100)，極限防守底價 80 (賠 20) -> 風報比 5:1
    res = calculate_valuation_stress_test(
        ticker="2454",
        current_price=100.0,
        base_eps=10.0,
        book_value_per_share=100.0,
        pe_anchors=anchors,
        historical_min_pe=8.0,
        historical_min_pb=0.8
    )

    rr = res["risk_reward"]
    assert rr["risk_reward_ratio"] > 1.5
    assert rr["is_favorable"] is True
    assert "高風報比" in rr["summary_tag"]


def test_valuation_stress_test_invalid_price():
    """測試現價 <= 0 防呆"""
    res = calculate_valuation_stress_test(
        ticker="2330",
        current_price=0.0,
        base_eps=10.0,
        book_value_per_share=50.0,
        pe_anchors={}
    )
    assert res["success"] is False
    assert "現價必須大於 0" in res["error"]


def test_api_valuation_stress_test_endpoint():
    """測試 API 端點 GET /api/stocks/{ticker}/stress-test"""
    resp = client.get("/api/stocks/2330/stress-test?optimistic_growth=25&pessimistic_growth=-15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["ticker"] == "2330"
    assert "scenarios" in data
    assert "floor_test" in data
    assert "risk_reward" in data
    assert "summary" in data
    assert data["scenarios"]["optimistic"]["growth_pct"] == 25.0
    assert data["scenarios"]["pessimistic"]["growth_pct"] == -15.0
