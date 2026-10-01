"""
測試 Valuation River Engine (規格書 6.2, 6.2b, 6.3, 6.8b, 6.8c)
"""

import pytest
from src.engines.valuation_river import (
    calculate_anchors,
    calculate_river_prices,
    classify_price_zone,
    calculate_peg_valuation,
    calculate_dividend_357,
    filter_outliers_iqr,
    RiverPrices
)

def test_6_2_tsmc_test_case():
    """
    驗證規格書 6.2 驗收測試案例：
    PEmin = 12.81, PEmax = 31.2, 預估 EPS = 135
    Δ = (31.2 - 12.81) / 5 = 3.678
    六個價格錨點容許誤差 ±1 元：
    A1: 1729
    A2: 2226
    A3: 2722
    A4: 3219
    A5: 3715
    A6: 4212
    """
    pe_min = 12.81
    pe_max = 31.20
    base_eps = 135.0

    anchors = calculate_anchors(pe_min, pe_max)
    assert pytest.approx(anchors.delta, 0.001) == 3.678
    assert pytest.approx(anchors.a1, 0.01) == 12.81
    assert pytest.approx(anchors.a2, 0.01) == 16.49
    assert pytest.approx(anchors.a3, 0.01) == 20.17
    assert pytest.approx(anchors.a4, 0.01) == 23.84
    assert pytest.approx(anchors.a5, 0.01) == 27.52
    assert pytest.approx(anchors.a6, 0.01) == 31.20

    prices = calculate_river_prices(anchors, base_eps)
    
    # 誤差 <= 1 元
    assert abs(round(prices.p1) - 1729) <= 1, f"P1: {prices.p1} vs 1729"
    assert abs(round(prices.p2) - 2226) <= 1, f"P2: {prices.p2} vs 2226"
    assert abs(round(prices.p3) - 2722) <= 1, f"P3: {prices.p3} vs 2722"
    assert abs(round(prices.p4) - 3219) <= 1, f"P4: {prices.p4} vs 3219"
    assert abs(round(prices.p5) - 3715) <= 1, f"P5: {prices.p5} vs 3715"
    assert abs(round(prices.p6) - 4212) <= 1, f"P6: {prices.p6} vs 4212"


def test_6_2b_zone_classification():
    """
    驗證規格書 6.2b 價位區歸屬測試案例：
    以 6.2 台積電範例價格錨點 (P1=1729, P2=2226, P3=2722, P4=3219, P5=3715, P6=4212) 測試
    """
    # 顯式建構精確價格基準
    prices = RiverPrices(
        base=135.0,
        p1=1729.0,
        p2=2226.0,
        p3=2722.0,
        p4=3219.0,
        p5=3715.0,
        p6=4212.0
    )

    # 1700 -> 特價
    c1 = classify_price_zone(1700.0, prices)
    assert c1.zone == "special"
    assert c1.zone_name_zh == "特價"
    assert c1.is_buy_research_zone is True
    assert c1.is_warning_zone is False

    # 2210 (來源案例) -> 便宜
    c2 = classify_price_zone(2210.0, prices)
    assert c2.zone == "cheap"
    assert c2.zone_name_zh == "便宜"
    assert c2.is_buy_research_zone is True
    assert c2.is_warning_zone is False

    # 2226 (邊界，含 A2) -> 便宜
    c3 = classify_price_zone(2226.0, prices)
    assert c3.zone == "cheap"
    assert c3.zone_name_zh == "便宜"
    assert c3.is_buy_research_zone is True
    assert c3.is_warning_zone is False

    # 2500 -> 合理
    c4 = classify_price_zone(2500.0, prices)
    assert c4.zone == "fair"
    assert c4.zone_name_zh == "合理"
    assert c4.is_buy_research_zone is False
    assert c4.is_warning_zone is False

    # 3715 (邊界，含 A5) -> 昂貴
    c5 = classify_price_zone(3715.0, prices)
    assert c5.zone == "expensive"
    assert c5.zone_name_zh == "昂貴"
    assert c5.is_buy_research_zone is False
    assert c5.is_warning_zone is True

    # 4300 -> 瘋狂
    c6 = classify_price_zone(4300.0, prices)
    assert c6.zone == "crazy"
    assert c6.zone_name_zh == "瘋狂"
    assert c6.is_buy_research_zone is False
    assert c6.is_warning_zone is True


def test_6_2b_han_tang_case():
    """
    漢唐案例：昂貴價 1,433 元，現價 1,450 元，預期「至少為昂貴」
    """
    prices = RiverPrices(
        base=100.0,
        p1=800.0,
        p2=1000.0,
        p3=1150.0,
        p4=1300.0,
        p5=1433.0,
        p6=1600.0
    )
    c = classify_price_zone(1450.0, prices)
    assert c.zone in ["expensive", "crazy"]
    assert c.is_warning_zone is True


def test_6_8c_peg_conservative_valuation():
    """
    驗證規格書 6.8c PEG 保守估值案例：
    近 4 季 EPS = 8 元，預估成長 40%，3 年 CAGR 20%，取較低者 20% (未超上限 25%)
    便宜價 = 0.75 * 20 * 8 = 120
    合理價 = 1.00 * 20 * 8 = 160
    昂貴價 = 1.50 * 20 * 8 = 240
    """
    res = calculate_peg_valuation(
        eps_ttm=8.0,
        growth_rate_forecast=40.0,
        growth_rate_cagr_3y=20.0
    )
    assert res.is_applicable is True
    assert res.effective_growth_rate == 20.0
    assert pytest.approx(res.p_cheap, 0.01) == 120.0
    assert pytest.approx(res.p_fair, 0.01) == 160.0
    assert pytest.approx(res.p_expensive, 0.01) == 240.0

    # 測試超過 25% 上限封頂
    res_cap = calculate_peg_valuation(
        eps_ttm=8.0,
        growth_rate_forecast=40.0,
        growth_rate_cagr_3y=30.0
    )
    assert res_cap.is_applicable is True
    assert res_cap.effective_growth_rate == 25.0
    assert pytest.approx(res_cap.p_cheap, 0.01) == 0.75 * 25.0 * 8.0  # 150.0

    # 測試循環股或金融股防呆
    res_cyclical = calculate_peg_valuation(8.0, 20.0, 20.0, is_cyclical=True)
    assert res_cyclical.is_applicable is False

    res_fin = calculate_peg_valuation(8.0, 20.0, 20.0, is_financial=True)
    assert res_fin.is_applicable is False


def test_6_8b_dividend_357():
    """
    驗證 6.8b 357 股利法案例：
    D = 5 元 -> 便宜約 71.4, 合理 100, 昂貴約 166.7
    """
    res = calculate_dividend_357(
        avg_5y_dividend=5.0,
        estimated_eps=10.0,
        avg_3y_payout_ratio=0.70  # 10 * 0.7 = 7, min(5, 7) = 5
    )
    assert res.is_applicable is True
    assert res.dividend_base_d == 5.0
    assert pytest.approx(res.p_cheap, 0.1) == 71.43
    assert pytest.approx(res.p_fair, 0.1) == 100.0
    assert pytest.approx(res.p_expensive, 0.1) == 166.67


def test_outlier_filtering():
    """
    驗證 IQR 離群值剔除
    """
    data = [10.0, 11.0, 12.0, 11.5, 10.8, 12.2, 100.0]  # 100.0 為明顯離群值
    filtered = filter_outliers_iqr(data)
    assert 100.0 not in filtered
    assert len(filtered) == 6
