"""
測試 Good Company Engine (規格書第 4 章)
"""

import pytest
from src.engines.good_company import (
    evaluate_revenue_dimension,
    evaluate_eps_dimension,
    evaluate_margins_dimension,
    evaluate_efficiency_dimension,
    evaluate_cashflow_dimension,
    evaluate_growth_or_dividend_dimension,
    evaluate_good_company
)

def test_good_company_pass():
    """
    測試各面向皆優之標的獲得 good (好公司) 三態判定
    """
    d_rev = evaluate_revenue_dimension(cumulative_yoy=0.20, recent_4q_yoys=[0.15, 0.18, 0.22, 0.25])
    assert d_rev.light == "green"

    d_eps = evaluate_eps_dimension(annual_eps_3y=[10.0, 12.0, 15.0], estimated_eps_current=18.0)
    assert d_eps.light == "green"

    d_mar = evaluate_margins_dimension(
        gross_margins=[0.45, 0.46, 0.48, 0.50],
        operating_margins=[0.30, 0.31, 0.32, 0.34],
        net_margins=[0.25, 0.26, 0.27, 0.28]
    )
    assert d_mar.light == "green"

    d_eff = evaluate_efficiency_dimension(roe=22.0)
    assert d_eff.light == "green"

    d_cf = evaluate_cashflow_dimension(
        operating_cf_4q=[50.0, 60.0, 55.0, 70.0],
        free_cf_4q=[20.0, 25.0, 18.0, 30.0]
    )
    assert d_cf.light == "green"

    d_growth = evaluate_growth_or_dividend_dimension(capex_growth_pct=25.0, revenue_growth_sync=True)
    assert d_growth.light == "green"

    res = evaluate_good_company(
        ticker="2330",
        dim_revenue=d_rev,
        dim_eps=d_eps,
        dim_margin=d_mar,
        dim_efficiency=d_eff,
        dim_cashflow=d_cf,
        dim_growth_div=d_growth,
        previously_good=True,
        is_in_buy_zone=True
    )

    assert res.overall == "good"
    assert res.overall_name_zh == "好公司"
    assert "good" in res.badges
    assert "cheap" in res.badges
    assert "capex" in res.badges
    assert any("EPS 連續成長" in r for r in res.reasons)
    assert len(res.warnings) == 0


def test_good_company_degraded():
    """
    測試原本好公司但獲利或營收顯著衰退，轉為 degraded (基本面退化)
    """
    d_rev = evaluate_revenue_dimension(cumulative_yoy=-0.15, recent_4q_yoys=[-0.10, -0.12, -0.15, -0.20])
    assert d_rev.light == "red"

    d_eps = evaluate_eps_dimension(annual_eps_3y=[15.0, 12.0, 8.0], estimated_eps_current=6.0)
    assert d_eps.light == "red"

    d_mar = evaluate_margins_dimension(
        gross_margins=[0.45, 0.40, 0.35, 0.30],
        operating_margins=[0.30, 0.25, 0.20, 0.15],
        net_margins=[0.25, 0.20, 0.15, 0.10]
    )
    assert d_mar.light == "red"

    d_eff = evaluate_efficiency_dimension(roe=3.0)
    assert d_eff.light == "red"

    d_cf = evaluate_cashflow_dimension(
        operating_cf_4q=[-10.0, -5.0, -10.0, -15.0],
        free_cf_4q=[-20.0, -15.0, -20.0, -25.0]
    )
    assert d_cf.light == "red"

    d_growth = evaluate_growth_or_dividend_dimension(payout_ratio=150.0, fcf_covers_dividend=False)
    assert d_growth.light == "red"

    res = evaluate_good_company(
        ticker="9999",
        dim_revenue=d_rev,
        dim_eps=d_eps,
        dim_margin=d_mar,
        dim_efficiency=d_eff,
        dim_cashflow=d_cf,
        dim_growth_div=d_growth,
        previously_good=True
    )

    assert res.overall == "degraded"
    assert res.overall_name_zh == "基本面退化"
    assert len(res.warnings) >= 3


def test_financial_stock_margin_adaptation():
    """
    測試金融股在三率指標上的自動適配 (4.4)
    """
    d_mar = evaluate_margins_dimension(
        gross_margins=[],
        operating_margins=[],
        net_margins=[],
        is_financial=True
    )
    assert d_mar.light == "gray"
    assert "金融股不適用" in d_mar.value_display
