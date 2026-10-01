"""
價值投資選股 App - 資產配置與資金部位管理引擎測試 (tests/test_portfolio_allocator.py)
驗證項目：
1. 純函式資金部位配置計算 (特價/便宜區加權、安全邊際加成)
2. 戰略現金儲備預留 (預設 20%) 與單一持股風控上限封頂 (預設 20%)
3. 台股整張 (1,000 股向下取整) 與零股試算
4. 無符合標的時 100% 現金保守防禦
5. RESTful API /api/portfolio/calculate-allocation 整合端點測試 (自選與自動股池)
"""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app
from src.engines.portfolio_allocator import calculate_portfolio_allocation

client = TestClient(app)


def test_portfolio_allocator_pure_basic():
    """測試純函式部位計算：特價 2.0x 權重 vs 便宜 1.0x 權重，整張交易單位"""
    candidates = [
        {
            "ticker": "2330",
            "company_name": "台積電",
            "current_price": 500.0,
            "zone": "special",      # 特價區 -> 基礎權重 2.0
            "margin_pct": 10.0,     # 安全邊際 10% -> 權重加成 = 2.0 * (1 + 0.1) = 2.2
            "is_good": True
        },
        {
            "ticker": "2454",
            "company_name": "聯發科",
            "current_price": 800.0,
            "zone": "cheap",        # 便宜區 -> 基礎權重 1.0
            "margin_pct": 5.0,      # 安全邊際 5% -> 權重加成 = 1.0 * (1 + 0.05) = 1.05
            "is_good": True
        },
        {
            "ticker": "2317",
            "company_name": "鴻海",
            "current_price": 100.0,
            "zone": "fair",         # 合理區 -> 不得配置
            "margin_pct": 0.0,
            "is_good": True
        },
        {
            "ticker": "9999",
            "company_name": "劣質股",
            "current_price": 50.0,
            "zone": "special",
            "margin_pct": 20.0,
            "is_good": False        # 劣質公司 -> 不得配置
        }
    ]

    total_capital = 1_000_000.0  # 100 萬
    res = calculate_portfolio_allocation(
        total_capital=total_capital,
        candidates=candidates,
        cash_reserve_pct=20.0,      # 預留 20% = 20 萬
        max_single_stock_pct=25.0,  # 單一上限 25 萬
        allow_odd_lots=False        # 整張 (1,000 股)
    )

    assert res["success"] is True
    assert res["total_capital"] == 1_000_000.0
    assert res["investable_budget"] == 800_000.0
    assert len(res["allocations"]) == 2  # 僅台積電與聯發科入選

    tsmc = next(a for a in res["allocations"] if a["ticker"] == "2330")
    mtk = next(a for a in res["allocations"] if a["ticker"] == "2454")

    # 台積電現價 500，每張 50 萬。單一上限 25 萬 (< 50 萬)，向下取整為 0 股 (0 張)
    # 聯發科現價 800，每張 80 萬。單一上限 25 萬 (< 80 萬)，向下取整為 0 股 (0 張)
    # 驗證整張取整之風控約束
    assert tsmc["suggested_shares"] == 0
    assert mtk["suggested_shares"] == 0
    assert res["remaining_cash"] == 1_000_000.0


def test_portfolio_allocator_pure_odd_lots_and_cap():
    """測試零股試算與單一持股上限封頂"""
    candidates = [
        {
            "ticker": "2330",
            "company_name": "台積電",
            "current_price": 500.0,
            "zone": "special",
            "margin_pct": 10.0,
            "is_good": True
        },
        {
            "ticker": "2454",
            "company_name": "聯發科",
            "current_price": 800.0,
            "zone": "cheap",
            "margin_pct": 5.0,
            "is_good": True
        }
    ]

    total_capital = 1_000_000.0
    # 開啟零股支援，單一上限 20% (20 萬)
    res = calculate_portfolio_allocation(
        total_capital=total_capital,
        candidates=candidates,
        cash_reserve_pct=20.0,      # 可投 80 萬
        max_single_stock_pct=20.0,  # 每檔最多 20 萬
        allow_odd_lots=True
    )

    assert res["success"] is True
    assert len(res["allocations"]) == 2

    for a in res["allocations"]:
        assert a["allocated_amount"] <= 200_000.0 + 1e-5
        # 由於兩檔權重原本計算都超過 20 萬 (80 萬 * 2.2/3.25 = 54.1 萬 > 20 萬)，皆應觸發上限
        assert a["cap_limited"] is True

    tsmc = next(a for a in res["allocations"] if a["ticker"] == "2330")
    # 台積電 20 萬 / 500 = 400 股
    assert tsmc["suggested_shares"] == 400
    assert tsmc["allocated_amount"] == 200_000.0

    mtk = next(a for a in res["allocations"] if a["ticker"] == "2454")
    # 聯發科 20 萬 / 800 = 250 股
    assert mtk["suggested_shares"] == 250
    assert mtk["allocated_amount"] == 200_000.0

    assert res["total_allocated"] == 400_000.0
    assert res["remaining_cash"] == 600_000.0
    assert res["actual_cash_pct"] == 60.0


def test_portfolio_allocator_no_eligible():
    """測試當無符合標的或全為合理/昂貴區時，100% 現金保守留存"""
    candidates = [
        {"ticker": "2330", "company_name": "台積電", "current_price": 1000.0, "zone": "expensive", "margin_pct": 0, "is_good": True},
        {"ticker": "2317", "company_name": "鴻海", "current_price": 200.0, "zone": "fair", "margin_pct": 0, "is_good": True}
    ]

    res = calculate_portfolio_allocation(
        total_capital=500_000.0,
        candidates=candidates
    )

    assert res["success"] is True
    assert res["total_allocated"] == 0.0
    assert res["cash_reserve"] == 500_000.0
    assert res["cash_reserve_pct"] == 100.0
    assert len(res["allocations"]) == 0
    assert "100% 保留現金" in res["summary"]["message"]


def test_portfolio_allocator_invalid_capital():
    """測試資本小於等於 0 異常防呆"""
    res = calculate_portfolio_allocation(total_capital=0, candidates=[])
    assert res["success"] is False
    assert "必須大於 0" in res["error"]


def test_api_portfolio_calculate_allocation_custom():
    """測試 API 端點傳入自選候選名單"""
    payload = {
        "total_capital": 2000000.0,
        "cash_reserve_pct": 15.0,
        "max_single_stock_pct": 20.0,
        "allow_odd_lots": True,
        "custom_candidates": [
            {
                "ticker": "2330",
                "company_name": "台積電",
                "current_price": 600.0,
                "zone": "special",
                "margin_pct": 12.0,
                "is_good": True
            }
        ]
    }
    resp = client.post("/api/portfolio/calculate-allocation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["total_capital"] == 2000000.0
    assert len(data["allocations"]) == 1
    assert data["allocations"][0]["ticker"] == "2330"
    assert data["allocations"][0]["suggested_shares"] > 0


def test_api_portfolio_calculate_allocation_auto_db():
    """測試 API 端點不帶 custom_candidates 時，自動從資料庫股池篩選標的"""
    payload = {
        "total_capital": 3000000.0,
        "cash_reserve_pct": 20.0,
        "max_single_stock_pct": 20.0,
        "allow_odd_lots": False
    }
    resp = client.post("/api/portfolio/calculate-allocation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "allocations" in data
    assert "remaining_cash" in data
    assert "summary" in data
