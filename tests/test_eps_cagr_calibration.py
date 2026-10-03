"""
單元測試 - EPS 長期複合成長率 (CAGR) 與歷史預估偏差校準引擎
驗證規格書 §5.4 與 §6.8c 規範：
- 3 年與 5 年 CAGR 計算正確性
- 負值 EPS、上市不足年份之防呆與成長率上限 (25%) 鉗制
- 預估偏差校準比對、MAPE 計算與信心評等
- 3 年與 5 年三情境長期 EPS 與目標價推估
"""

import pytest
from src.engines.eps_cagr_calibration import (
    calculate_eps_cagr,
    evaluate_forecast_calibration,
    project_multi_year_eps_scenarios,
    EPSCagrResult,
    ForecastCalibrationSummary,
    EPSMultiYearProjectionResult
)


def test_eps_cagr_calculation_normal_growth():
    """測試正常逐年成長股之 3 年與 5 年 CAGR 計算"""
    # 2020: 10.0, 2021: 12.0, 2022: 15.0, 2023: 18.0, 2024: 20.0, 2025: 24.0
    records = [
        {"year": 2020, "eps": 10.0},
        {"year": 2021, "eps": 12.0},
        {"year": 2022, "eps": 15.0},
        {"year": 2023, "eps": 18.0},
        {"year": 2024, "eps": 20.0},
        {"year": 2025, "eps": 24.0},
    ]
    res = calculate_eps_cagr(records)
    assert isinstance(res, EPSCagrResult)
    assert res.cagr_3y is not None
    # 3年 CAGR: (24.0 / 15.0)^(1/3) - 1 = 1.6^(1/3) - 1 ≈ 0.1696 (16.96%)
    assert abs(res.cagr_3y - 0.1696) < 0.01
    # 5年 CAGR: (24.0 / 10.0)^(1/5) - 1 = 2.4^0.2 - 1 ≈ 0.1913 (19.13%)
    assert abs(res.cagr_5y - 0.1913) < 0.01
    assert res.is_growth_steady is True
    assert res.effective_growth_rate == round(res.cagr_3y * 100, 2)
    assert "強勁穩健成長" in res.growth_quality_desc


def test_eps_cagr_cap_at_twenty_five_percent():
    """測試高速成長股依規格書 6.8c 設上限 25% 鉗制"""
    # 3年由 5.0 成長至 25.0，CAGR 高達 70%
    records = [
        {"year": 2022, "eps": 5.0},
        {"year": 2023, "eps": 10.0},
        {"year": 2024, "eps": 18.0},
        {"year": 2025, "eps": 25.0},
    ]
    res = calculate_eps_cagr(records)
    assert res.cagr_3y > 0.60
    assert res.effective_growth_rate == 25.0  # 鉗制在 25.0%


def test_eps_cagr_insufficient_or_negative_eps():
    """測試不足年份或負值 EPS 之防呆"""
    # 只有 1 年
    res1 = calculate_eps_cagr([{"year": 2025, "eps": 10.0}])
    assert res1.cagr_3y is None
    assert res1.effective_growth_rate == 0.0
    assert "不足" in res1.growth_quality_desc

    # 含有負值虧損
    records_loss = [
        {"year": 2022, "eps": -2.0},
        {"year": 2023, "eps": 3.0},
        {"year": 2024, "eps": 8.0},
        {"year": 2025, "eps": 12.0},
    ]
    res_loss = calculate_eps_cagr(records_loss)
    assert res_loss.cagr_3y is None  # 起始點為負，CAGR 不可算
    assert "虧損" in res_loss.growth_quality_desc


def test_forecast_calibration_evaluation():
    """測試歷史預估 vs 實際公告比對與 MAPE 評級"""
    history = [
        {"year": 2022, "estimated_eps": 15.0, "actual_eps": 14.5}, # 誤差 +3.45%
        {"year": 2023, "estimated_eps": 20.0, "actual_eps": 19.0}, # 誤差 +5.26%
        {"year": 2024, "estimated_eps": 25.0, "actual_eps": 26.0}, # 誤差 -3.85%
        {"year": 2025, "estimated_eps": 30.0, "actual_eps": 28.5}, # 誤差 +5.26%
    ]
    summary = evaluate_forecast_calibration(history)
    assert isinstance(summary, ForecastCalibrationSummary)
    assert summary.has_sufficient_history is True
    assert summary.comparison_count == 4
    # 平均誤差在 4%~5% 之間，應評為 high (高可信度)
    assert summary.mape < 10.0
    assert summary.confidence_grade == "high"
    assert summary.confidence_score > 90.0
    assert len(summary.calibration_details) == 4


def test_forecast_calibration_volatile_case():
    """測試預估波動較大 (MAPE > 20%) 之場景"""
    history = [
        {"year": 2023, "estimated_eps": 10.0, "actual_eps": 5.0},  # 誤差 +100%
        {"year": 2024, "estimated_eps": 8.0, "actual_eps": 14.0},  # 誤差 -42.8%
    ]
    summary = evaluate_forecast_calibration(history)
    assert summary.comparison_count == 2
    assert summary.mape > 20.0
    assert summary.confidence_grade == "volatile"
    assert summary.confidence_score < 80.0


def test_multi_year_scenario_projections():
    """測試未來 3 年與 5 年三情境 EPS 與目標價推估"""
    current_price = 1000.0
    current_eps = 40.0
    cagr_base = 15.0  # 15%
    target_pe = 20.0

    res = project_multi_year_eps_scenarios(
        current_price=current_price,
        current_eps=current_eps,
        cagr_base_pct=cagr_base,
        target_pe=target_pe
    )
    assert isinstance(res, EPSMultiYearProjectionResult)
    assert len(res.scenarios) == 3

    cons, base, opt = res.scenarios
    assert cons.scenario_type == "conservative"
    assert base.scenario_type == "base"
    assert opt.scenario_type == "optimistic"

    # 基準情境:
    # 3 年 EPS: 40 * 1.15^3 = 40 * 1.520875 = 60.835 ≈ 60.84
    assert abs(base.projected_eps_3y - 60.84) < 0.2
    # 3 年 目標價: 60.84 * 20 = 1216.8
    assert abs(base.projected_price_3y - 1216.8) < 4.0
    # 潛在漲幅約 +21.7%
    assert base.upside_pct_3y > 15.0

    # 5 年 目標價 > 3 年 目標價
    assert base.projected_price_5y > base.projected_price_3y
    # 樂觀 > 基準 > 保守
    assert opt.projected_price_3y > base.projected_price_3y > cons.projected_price_3y


def test_api_eps_cagr_calibration_endpoint():
    """測試 FastAPI 端點 GET /api/stocks/{ticker}/eps-cagr-calibration"""
    from fastapi.testclient import TestClient
    from src.web.app import app

    client = TestClient(app)
    # 測試台積電 2330
    resp = client.get("/api/stocks/2330/eps-cagr-calibration")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "2330"
    assert "cagr_analysis" in data
    assert "calibration_analysis" in data
    assert "multi_year_projections" in data

    # 驗證結構
    cagr = data["cagr_analysis"]
    assert "effective_growth_rate" in cagr
    assert "growth_quality_desc" in cagr

    calib = data["calibration_analysis"]
    assert "confidence_score" in calib
    assert "confidence_grade" in calib
    assert "bias_desc" in calib

    proj = data["multi_year_projections"]
    assert len(proj["scenarios"]) == 3
    assert proj["scenarios"][1]["scenario_type"] == "base"

