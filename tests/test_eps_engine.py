"""
測試 EPS Engine (規格書第 5 章、第 4.4 節)
"""

import pytest
from src.engines.eps_engine import (
    calculate_six_step_eps,
    calculate_long_term_scenario_eps
)

def test_six_step_eps_normal():
    """
    測試一般成長股六步驟 EPS 預估模型
    """
    # 假設前一年營收 100 億，今年累計 YoY 15% (0.15)
    # 近 4 季營收分別為 25, 27, 28, 30 億 (總計 110 億)
    # 近 4 季淨利分別為 5, 5.4, 5.6, 6 億 (總計 22 億，淨利率 20%)
    # 流通在外股數 10 億股
    rev_ttm = [25.0, 27.0, 28.0, 30.0]
    ni_ttm = [5.0, 5.4, 5.6, 6.0]
    shares = 10.0

    res = calculate_six_step_eps(
        ticker="2330",
        estimate_year=2026,
        cumulative_rev_yoy_g=0.15,
        prior_full_year_revenue=100.0,
        ttm_revenues=rev_ttm,
        ttm_net_incomes=ni_ttm,
        ttm_non_operating_incomes=[0.1, 0.1, 0.1, 0.1],
        shares_outstanding=shares,
        is_cyclical=False
    )

    assert res.confidence_flag == "normal"
    assert res.estimate_method == "six_step_growth"
    assert res.estimated_eps is not None
    # rev_est = 100 * 1.15 = 115
    # margin = 22 / 110 = 0.20
    # ni_est = 115 * 0.20 = 23
    # eps_est = 23 / 10 = 2.3
    assert pytest.approx(res.estimated_eps, 0.001) == 2.3
    assert res.calc_details is not None
    assert pytest.approx(res.calc_details.estimated_revenue, 0.001) == 115.0
    assert pytest.approx(res.calc_details.margin_ttm, 0.001) == 0.20


def test_cyclical_stock_safeguard():
    """
    測試景氣循環股防呆 (5.2)：隱藏預估 EPS，可信度旗標為 cyclical
    """
    res = calculate_six_step_eps(
        ticker="2603",
        estimate_year=2026,
        cumulative_rev_yoy_g=0.30,
        prior_full_year_revenue=200.0,
        ttm_revenues=[50.0, 55.0, 60.0, 65.0],
        ttm_net_incomes=[10.0, 15.0, 20.0, 25.0],
        ttm_non_operating_incomes=[0.0, 0.0, 0.0, 0.0],
        shares_outstanding=10.0,
        is_cyclical=True  # 循環股
    )

    assert res.confidence_flag == "cyclical"
    assert res.estimated_eps is None
    assert "景氣循環股獲利波動劇烈" in res.warning_message


def test_one_off_non_operating_income():
    """
    測試單季業外收益 > 30% 淨利防呆 (4.4 / 5.3)
    """
    # 最新季淨利 10 億，業外收益 4 億 (40% > 30%)
    res = calculate_six_step_eps(
        ticker="1234",
        estimate_year=2026,
        cumulative_rev_yoy_g=0.10,
        prior_full_year_revenue=100.0,
        ttm_revenues=[25.0, 25.0, 25.0, 25.0],
        ttm_net_incomes=[5.0, 5.0, 5.0, 10.0],
        ttm_non_operating_incomes=[0.1, 0.1, 0.1, 4.0],  # 最新一季業外佔 40%
        shares_outstanding=10.0,
        is_cyclical=False
    )

    assert res.confidence_flag == "one_off"
    assert "超過淨利 30%" in res.warning_message
    assert res.calc_details is not None
    assert res.calc_details.normalized_eps is not None
    # 正常化淨利扣除業外，所以 normalized_eps < estimated_eps_base
    assert res.calc_details.normalized_eps < res.calc_details.estimated_eps_base


def test_short_history_safeguard():
    """
    測試上市未滿四季防呆 (4.4 / 5.3)
    """
    res = calculate_six_step_eps(
        ticker="9999",
        estimate_year=2026,
        cumulative_rev_yoy_g=0.10,
        prior_full_year_revenue=50.0,
        ttm_revenues=[20.0, 25.0],  # 僅兩季
        ttm_net_incomes=[3.0, 4.0],
        ttm_non_operating_incomes=None,
        shares_outstanding=5.0,
        quarters_count=2
    )

    assert res.confidence_flag == "short_history"
    assert res.estimated_eps is None
    assert "未滿四季" in res.warning_message


def test_5_4_long_term_scenario_eps():
    """
    驗證規格書 5.4 長期情境 EPS 試算：
    營收 2.89 兆、CAGR 24%、5 年、淨利率 40%、股數 259.3 億股 ->
    約 8.48 兆營收、約 3.39 兆淨利、EPS 約 130 元；乘 20 倍約 2,600 元
    """
    start_rev = 28900.0  # 億元
    cagr = 0.24
    years = 5
    margin = 0.40
    shares = 259.3  # 億股
    target_pe = 20.0

    res = calculate_long_term_scenario_eps(
        start_revenue=start_rev,
        cagr=cagr,
        years=years,
        net_margin=margin,
        shares_outstanding=shares,
        target_pe=target_pe
    )

    # 預期：84760 億營收 (~8.48 兆), 33904 億淨利 (~3.39 兆), EPS ~ 130.7, 價格 ~ 2615
    assert pytest.approx(res["future_revenue"] / 10000.0, 0.1) == 8.48
    assert pytest.approx(res["future_net_income"] / 10000.0, 0.1) == 3.39
    assert pytest.approx(res["future_eps"], 1.0) == 130.7
    assert pytest.approx(res["target_price"], 20.0) == 2615.0
