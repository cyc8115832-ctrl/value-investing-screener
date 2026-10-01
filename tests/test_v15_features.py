"""
價值投資選股 App - V1.5 決策深化功能測試套件 (test_v15_features.py)
驗證項目：
1. 歷史觸及與反彈紀錄純函式計算 (6.7)
2. 下單前 5 問與五階段檢核表讀寫 API (16.5, 16.6)
3. 多標的並排比較器 API (7.4, 8.9.6, 6.9)
4. 歷史觸及紀錄專屬端點與個股頁整合 (6.7)
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from src.web.app import app
from src.engines.historical_touches import analyze_historical_touches
from src.engines.checklist import get_checklist_template

client = TestClient(app)


def test_historical_touches_engine_logic():
    """驗證歷史觸及波段與最高反彈幅度演算法 (6.7)"""
    base_date = date(2025, 1, 1)
    mock_prices = []

    # 模擬 100 天走勢：
    # Day 0-10: 價格 120 (合理區)
    # Day 11-20: 價格跌至 75 (<= A1=80，特價區)
    # Day 21-30: 價格回到 90 (A1-A2=100，便宜區)
    # Day 31-50: 價格反彈至 150 (脫離便宜區，波段結束，最高 150)
    # Day 51-60: 價格 110 (合理區)
    # Day 61-70: 價格再度落入 95 (便宜區)
    # Day 71-80: 價格反彈至 130
    for i in range(80):
        d = base_date + timedelta(days=i)
        if i <= 10:
            p = 120.0
        elif i <= 20:
            p = 75.0
        elif i <= 30:
            p = 90.0
        elif i <= 50:
            p = 150.0
        elif i <= 60:
            p = 110.0
        elif i <= 70:
            p = 95.0
        else:
            p = 130.0

        mock_prices.append({
            "date": d.isoformat(),
            "close": p,
            "high": p + 2.0,
            "low": p - 2.0
        })

    report = analyze_historical_touches(
        daily_prices=mock_prices,
        a1_threshold=80.0,
        a2_threshold=100.0,
        strategy_hits=[
            {"date": "2025-01-15", "strategy_id": "capex_surge", "badge_code": "capex", "strategy_name": "資本支出大增"}
        ],
        as_of_date=base_date + timedelta(days=80)
    )

    # 應有 2 次進入便宜/特價區波段
    assert len(report["episodes"]) == 2
    assert "歷史不代表未來" in report["disclaimer"]

    # 檢驗第一次波段的反彈幅度
    # 第一次進入價為 Day 11 的 75.0，後續高點為 152.0 (high)
    first_ep = [e for e in report["episodes"] if "2025-01-12" in e["entry_date"] or "2025-01-11" in e["entry_date"]][0]
    assert first_ep["entry_price"] == 75.0
    assert first_ep["max_rebound_pct"] > 50.0
    assert len(report["strategy_events"]) == 1


def test_checklist_template_and_api():
    """驗證五階段檢核表與下單前 5 問 API (16.5, 16.6)"""
    template = get_checklist_template()
    assert len(template["pre_order"]) == 5
    assert len(template["five_stages"]) == 5

    # 1. 取得台積電檢核表
    resp = client.get("/api/checklist/2330")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "2330"
    assert len(data["pre_order"]) == 5
    assert len(data["five_stages"]) == 5

    # 2. 更新勾選狀態與寫入筆記
    payload = {
        "user_id": "test_user_v15",
        "items": [
            {
                "stage": "selection",
                "item_index": 0,
                "checked": True,
                "note": "先進製程市佔高達 90%，產業趨勢長期成長明確。"
            },
            {
                "stage": "pre_order",
                "item_index": 0,
                "checked": True,
                "note": "確認為 3 年以上閒置資金。"
            }
        ]
    }
    post_resp = client.post("/api/checklist/2330", json=payload)
    assert post_resp.status_code == 200
    assert post_resp.json()["success"] is True

    # 3. 再次查詢確認已持久化
    get_resp = client.get("/api/checklist/2330?user_id=test_user_v15")
    assert get_resp.status_code == 200
    updated_data = get_resp.json()

    sel_item = [s for s in updated_data["five_stages"] if s["stage"] == "selection"][0]
    assert sel_item["checked"] is True
    assert "先進製程" in sel_item["note"]

    pre_item = updated_data["pre_order"][0]
    assert pre_item["checked"] is True
    assert "3 年以上" in pre_item["note"]


def test_stock_compare_api():
    """驗證個股多標的並排比較器 API (7.4, 8.9.6)"""
    # 正常 2 至 3 檔比較
    resp = client.get("/api/stocks/compare?tickers=2330,2454,2317")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 2
    assert "不排名、不推薦" in data["disclaimer"]

    # 檢查每個股票欄位完整性
    for item in data["items"]:
        assert "ticker" in item
        assert "current_price" in item
        assert "zone_name_zh" in item
        assert "pe" in item
        assert "roe" in item
        assert "bands" in item
        assert "two_doors_state" in item

    # 測試少於 2 檔之錯誤處理
    resp_err = client.get("/api/stocks/compare?tickers=2330")
    assert resp_err.status_code == 400


def test_historical_touches_api_endpoint():
    """驗證個股歷史觸及獨立端點 (6.7)"""
    resp = client.get("/api/stocks/2330/historical-touches")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "2330"
    assert "summary" in data
    assert "episodes" in data
    assert "disclaimer" in data
    assert "歷史不代表未來" in data["disclaimer"]
