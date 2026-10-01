"""
測試 Leading Signals Engine (規格書第 14 章)
"""

import pytest
from src.engines.leading_signals import (
    evaluate_l1_revenue_accel,
    evaluate_l2_contract_liabilities,
    evaluate_l3_inventory_vs_revenue,
    evaluate_l4_capex_growth,
    evaluate_l5_insider_holding,
    evaluate_l6_institutional_funds,
    evaluate_l7_kd_strength,
    evaluate_l8_material_keywords,
    summarize_leading_signals
)

def test_l1_l8_individual_signals():
    """測試各單一領先訊號判定邏輯"""
    # L1: 月營收加速度
    s1 = evaluate_l1_revenue_accel(monthly_yoys_12m=[0.05]*9 + [0.12, 0.15, 0.18])
    assert s1.light == "green"
    assert "營收加速" in s1.plain_explanation

    # L2: 合約負債
    s2 = evaluate_l2_contract_liabilities([10.0, 15.0, 20.0, 25.0])
    assert s2.light == "green"
    assert "訂金大增" in s2.plain_explanation

    # L3: 存貨健康度
    s3 = evaluate_l3_inventory_vs_revenue(inventory_yoy=0.05, revenue_yoy=0.20)
    assert s3.light == "green"

    # L4: 資本支出
    s4 = evaluate_l4_capex_growth(capex_quarterly_growth=0.30, revenue_growing=True)
    assert s4.light == "green"

    # L5: 內部人
    s5 = evaluate_l5_insider_holding(insider_diff_pct=1.2)
    assert s5.light == "green"

    # L6: 法人籌碼
    s6 = evaluate_l6_institutional_funds(foreign_net_20d=5000, trust_net_20d=2000)
    assert s6.light == "green"

    # L7: 月 KD
    s7 = evaluate_l7_kd_strength(month_k=25.0, month_d=22.0, is_golden_cross=True, is_death_cross=False)
    assert s7.light == "green"

    # L8: 重大訊息
    s8 = evaluate_l8_material_keywords(["董事會決議海外大擴廠與產能上修"])
    assert s8.light == "green"


def test_leading_summary_strengthening():
    """測試轉強狀態：>= 3 綠且 0 紅 -> strengthening"""
    s1 = evaluate_l1_revenue_accel(monthly_yoys_12m=[0.05]*9 + [0.12, 0.15, 0.18])  # green
    s2 = evaluate_l2_contract_liabilities([10.0, 15.0, 20.0, 25.0])                 # green
    s3 = evaluate_l3_inventory_vs_revenue(inventory_yoy=0.05, revenue_yoy=0.20)      # green
    s4 = evaluate_l4_capex_growth(capex_quarterly_growth=0.05, revenue_growing=True) # yellow
    s5 = evaluate_l5_insider_holding(insider_diff_pct=0.0)                           # yellow
    s6 = evaluate_l6_institutional_funds(foreign_net_20d=100, trust_net_20d=-50)    # yellow
    s7 = evaluate_l7_kd_strength(month_k=50.0, month_d=50.0, is_golden_cross=False, is_death_cross=False) # yellow
    s8 = evaluate_l8_material_keywords(["一般例行公告"])                              # yellow

    res = summarize_leading_signals("2330", [s1, s2, s3, s4, s5, s6, s7, s8])
    assert res.status == "strengthening"
    assert res.status_name_zh == "訊號轉強"
    assert res.green_count == 3
    assert res.red_count == 0


def test_leading_summary_weakening():
    """測試轉弱狀態：>= 2 紅 -> weakening"""
    s1 = evaluate_l1_revenue_accel(monthly_yoys_12m=[0.20]*9 + [0.05, 0.02, -0.05]) # red
    s2 = evaluate_l2_contract_liabilities([25.0, 20.0, 15.0])                       # red
    s3 = evaluate_l3_inventory_vs_revenue(inventory_yoy=0.05, revenue_yoy=0.20)      # green

    res = summarize_leading_signals("9999", [s1, s2, s3])
    assert res.status == "weakening"
    assert res.status_name_zh == "訊號轉弱"
    assert res.red_count >= 2
