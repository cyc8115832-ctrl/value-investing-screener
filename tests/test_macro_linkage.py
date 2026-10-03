"""
單元測試 - 宏觀市場水位與美債殖利率聯動引擎
驗證規格書 §10 與 §14.6 規範：
- 4.5% 與 5.0% 關鍵警戒線之三態警示判定
- 單一個股之盈餘殖利率 (1/PE) 與股權風險溢酬 (ERP) 計算
- 利率折現敏感度矩陣
- 全市場宏觀概況彙整
"""

import pytest
from src.engines.macro_linkage import (
    evaluate_macro_status,
    calculate_macro_stock_sensitivity,
    generate_macro_market_overview,
    MacroStockSensitivityResult,
    MacroMarketOverviewResult
)


def test_evaluate_macro_status_levels():
    """測試正常(<4.5)、接近(4.5~5.0)與高利率(>=5.0)三態判定"""
    # 正常
    res_norm = evaluate_macro_status(4.25)
    assert res_norm["flag"] == "normal"
    assert res_norm["level"] == "normal"
    assert "平穩" in res_norm["title"]

    # 接近警戒 (4.5% ~ 5.0%)
    res_warn = evaluate_macro_status(4.68)
    assert res_warn["flag"] == "warning_4_5"
    assert res_warn["level"] == "warning"
    assert "接近" in res_warn["title"]

    # 高利率警戒 (>= 5.0%)
    res_alert = evaluate_macro_status(5.12)
    assert res_alert["flag"] == "alert_5_0"
    assert res_alert["level"] == "alert"
    assert "高利率警戒" in res_alert["title"]


def test_calculate_macro_stock_sensitivity():
    """測試個股 ERP 與利率折現敏感度計算"""
    current_price = 1000.0
    current_eps = 50.0  # PE = 20, 盈餘殖利率 = 5.0%
    base_pe = 20.0
    us_yield = 4.20     # ERP = 5.0% - 4.2% = +0.80%

    res = calculate_macro_stock_sensitivity(
        ticker="2330",
        current_price=current_price,
        current_eps=current_eps,
        base_target_pe=base_pe,
        current_us_10y_yield=us_yield
    )

    assert isinstance(res, MacroStockSensitivityResult)
    assert res.ticker == "2330"
    assert res.current_pe == 20.0
    assert res.earning_yield_pct == 5.0
    assert res.equity_risk_premium_pct == 0.8
    assert "ERP" in res.erp_assessment_zh

    # 檢查敏感度矩陣
    table = res.sensitivity_table
    assert len(table) == 5
    # 3.5% 利率低時，折現 factor > 1.0，目標價高於基準
    assert table[0]["simulated_yield_pct"] == 3.5
    assert table[0]["adjusted_price"] > res.base_fair_price
    # 5.5% 利率高時，折現 factor < 1.0，目標價低於基準
    assert table[-1]["simulated_yield_pct"] == 5.5
    assert table[-1]["adjusted_price"] < res.base_fair_price


def test_calculate_macro_stock_sensitivity_negative_eps():
    """測試負值虧損股票之防呆"""
    res = calculate_macro_stock_sensitivity(
        ticker="2603",
        current_price=100.0,
        current_eps=-5.0,
        base_target_pe=10.0,
        current_us_10y_yield=4.30
    )
    assert res.current_pe is None
    assert res.earning_yield_pct is None
    assert res.equity_risk_premium_pct is None
    assert "虧損" in res.erp_assessment_zh


def test_generate_macro_market_overview():
    """測試過去 1 年美債殖利率概況與統計"""
    history = [
        {"date": "2025-10-01", "us_10y_yield": 4.10},
        {"date": "2026-01-01", "us_10y_yield": 4.45},
        {"date": "2026-05-01", "us_10y_yield": 4.75},
        {"date": "2026-10-01", "us_10y_yield": 4.38},
    ]
    overview = generate_macro_market_overview(history)
    assert isinstance(overview, MacroMarketOverviewResult)
    assert overview.current_us_10y_yield == 4.38
    assert overview.historical_1y_high == 4.75
    assert overview.historical_1y_low == 4.10
    assert overview.historical_1y_avg > 4.0
    assert len(overview.historical_points) == 4


def test_api_macro_endpoints():
    """測試 FastAPI 端點 GET /api/macro/market-overview 與 GET /api/stocks/{ticker}/macro-sensitivity"""
    from fastapi.testclient import TestClient
    from src.web.app import app

    client = TestClient(app)

    # 1. 市場概況端點
    resp1 = client.get("/api/macro/market-overview")
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert "current_us_10y_yield" in d1
    assert "warning_flag" in d1
    assert "historical_1y_high" in d1
    assert "impact_summary_zh" in d1

    # 2. 個股敏感度端點 (測試 2330)
    resp2 = client.get("/api/stocks/2330/macro-sensitivity")
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["ticker"] == "2330"
    assert "earning_yield_pct" in d2
    assert "equity_risk_premium_pct" in d2
    assert "sensitivity_table" in d2
    assert len(d2["sensitivity_table"]) == 5

