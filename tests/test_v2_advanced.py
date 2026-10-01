"""
測試 V2.0 交易輔助深化模組 (tests/test_v2_advanced.py)
涵蓋：
1. 交易成本與損益兩平試算 (trade_cost.py)
2. 綜合好公司體質評分卡 (company_score.py)
3. 財經行事曆與檢視提醒 (calendar.py)
4. 三大法人籌碼流與股權集中度分析 (chip_analysis.py)
5. RESTful API 端點整合與三情境河流圖切換
"""

import pytest
from datetime import date
from fastapi.testclient import TestClient

from src.engines.trade_cost import (
    get_taiwan_tick_size, round_up_to_tick, calculate_trade_cost
)
from src.engines.company_score import calculate_composite_company_score
from src.engines.calendar import (
    get_month_revenue_deadline, generate_financial_calendar
)
from src.engines.chip_analysis import analyze_stock_chip_data
from src.database.session import SessionLocal
from src.web.app import app

client = TestClient(app)


# ---------------- 1. 交易成本與 Tick Size 檔位測試 ----------------
def test_taiwan_tick_size_rules():
    """驗證台股 6 級股價升降單位符合證交所規定"""
    assert get_taiwan_tick_size(5.5) == 0.01
    assert get_taiwan_tick_size(9.99) == 0.01
    assert get_taiwan_tick_size(10.0) == 0.05
    assert get_taiwan_tick_size(49.9) == 0.05
    assert get_taiwan_tick_size(50.0) == 0.10
    assert get_taiwan_tick_size(99.5) == 0.10
    assert get_taiwan_tick_size(100.0) == 0.50
    assert get_taiwan_tick_size(499.0) == 0.50
    assert get_taiwan_tick_size(500.0) == 1.00
    assert get_taiwan_tick_size(999.0) == 1.00
    assert get_taiwan_tick_size(1000.0) == 5.00
    assert get_taiwan_tick_size(2500.0) == 5.00


def test_round_up_to_tick():
    """驗證價格無條件進位至合法跳動檔位"""
    assert round_up_to_tick(23.21) == 23.25
    assert round_up_to_tick(80.05) == 80.10
    assert round_up_to_tick(102.1) == 102.5
    assert round_up_to_tick(550.2) == 551.0
    assert round_up_to_tick(1001.0) == 1005.0


def test_trade_cost_breakeven_stock_and_etf():
    """驗證交易規費計算與保本損益兩平點"""
    # 股票 100 元買進 1000 股，無折讓
    res_stock = calculate_trade_cost(buy_price=100.0, shares=1000, fee_discount=1.0, is_etf=False)
    be_stock = res_stock["breakeven"]
    # 兩平價必須高於買進價
    assert be_stock["breakeven_price"] > 100.0
    # 100 元股票跳動檔位為 0.5 元，兩平價必須能被 0.5 整除
    assert be_stock["breakeven_price"] % 0.5 == 0.0
    # 買進手續費 (100 * 1000 * 0.001425 = 142.5 -> 142)
    assert res_stock["buy_summary"]["buy_fee"] == 142

    # ETF 100 元買進 1000 股，證交稅率僅 0.1% (對照股票 0.3%)
    res_etf = calculate_trade_cost(buy_price=100.0, shares=1000, fee_discount=1.0, is_etf=True)
    assert res_etf["inputs"]["tax_rate_pct"] == 0.1
    # ETF 兩平價格應小於或等於一般股票
    assert res_etf["breakeven"]["breakeven_price"] <= be_stock["breakeven_price"]


def test_trade_cost_target_sell_and_discount():
    """驗證目標賣出價淨損益試算與券商折讓優惠"""
    res = calculate_trade_cost(
        buy_price=50.0,
        shares=1000,
        target_sell_price=55.0,
        fee_discount=0.6  # 6 折
    )
    assert res["simulation"] is not None
    sim = res["simulation"]
    # 價差毛利 (55 - 50) * 1000 = 5000 元，扣除稅費後淨利應介於 4700 ~ 4900 之間
    assert 4700 < sim["net_profit"] < 5000
    assert sim["net_return_pct"] > 0
    # 驗證手續費折讓已生效
    assert res["buy_summary"]["buy_fee"] < 71  # 50000 * 0.001425 = 71.25 -> 71 * 0.6 = 42


# ---------------- 2. 綜合體質評分卡測試 ----------------
def test_company_composite_score_all_green():
    """六面向全綠燈應獲得滿分 100 分與 AAA 卓越評級"""
    score = calculate_composite_company_score(
        revenue_light="green",
        eps_light="green",
        margin_light="green",
        efficiency_light="green",
        cashflow_light="green",
        growth_light="green"
    )
    assert score["total_score"] == 100.0
    assert score["grade"] == "AAA"
    assert "卓越" in score["grade_desc"]


def test_company_composite_score_all_red():
    """六面向全紅燈應獲得 0 分與 C 評級"""
    score = calculate_composite_company_score(
        revenue_light="red",
        eps_light="red",
        margin_light="red",
        efficiency_light="red",
        cashflow_light="red",
        growth_light="red"
    )
    assert score["total_score"] == 0.0
    assert score["grade"] == "C"
    assert "退化" in score["grade_desc"]


def test_company_composite_score_mixed():
    """混合燈號與權重分值測試"""
    score = calculate_composite_company_score(
        revenue_light="green",      # 20分
        eps_light="green",          # 20分
        margin_light="yellow",      # 15 * 0.5 = 7.5分
        efficiency_light="green",   # 15分
        cashflow_light="yellow",    # 15 * 0.5 = 7.5分
        growth_light="red"          # 0分
    )
    # 總分應為 20 + 20 + 7.5 + 15 + 7.5 + 0 = 70 分
    assert score["total_score"] == 70.0
    assert score["grade"] == "AA"


# ---------------- 3. 財經行事曆引擎測試 ----------------
def test_revenue_deadline_weekend_postponement():
    """驗證營收截止日遇例假日自動順延至次一營業日 (週一)"""
    # 2026 年 5 月 10 日為週日，應順延至 5 月 11 日 (週一)
    d = get_month_revenue_deadline(2026, 5)
    assert d.weekday() == 0  # 週一
    assert d.day == 11

    # 2026 年 8 月 10 日為週一，不順延
    d8 = get_month_revenue_deadline(2026, 8)
    assert d8.day == 10


def test_financial_calendar_generation():
    """驗證行事曆事件產生包含法定申報期限"""
    db = SessionLocal()
    try:
        cal = generate_financial_calendar(db, target_year=2026, target_month=8)
        assert "year" in cal
        assert "month" in cal
        assert "events" in cal
        assert len(cal["events"]) > 0

        types = [e["type"] for e in cal["events"]]
        assert "revenue_deadline" in types
        # 8月份有 Q2 季報法定申報截止日 (8/14)
        assert "earnings_deadline" in types
    finally:
        db.close()


# ---------------- 4. 籌碼流與股權集中度分析測試 ----------------
def test_chip_analysis_insufficient():
    """資料不足時回傳安全提示"""
    res = analyze_stock_chip_data([])
    assert res["status"] == "insufficient_data"


def test_chip_analysis_accumulation_and_stances():
    """驗證法人 5日/20日累計買賣超與態度標籤"""
    sample_records = [
        {
            "date": f"2026-08-{i:02d}",
            "foreign_net": 150.0,
            "trust_net": 80.0,
            "dealer_net": 20.0,
            "insider_holding_pct": 28.5,
            "big_holder_pct": 65.0 + i * 0.1
        }
        for i in range(1, 21)
    ]
    report = analyze_stock_chip_data(sample_records)
    assert report["status"] == "success"
    # 近 5 日法人合計 (150 + 80 + 20) * 5 = 1250 張
    assert report["cumulative_5d"]["total"] == 1250.0
    # 法人積極加碼
    assert "積極加碼" in report["stance"]["tag"]
    # 大戶持股比例呈現增加
    assert report["concentration"]["status"] == "concentrating"
    # 董監持股大於 15%，判定安全
    assert report["insider"]["is_safe"] is True


# ---------------- 5. API 端點整合與三情境河流圖切換測試 ----------------
def test_api_calendar_endpoint():
    """測試 GET /api/calendar"""
    resp = client.get("/api/calendar?year=2026&month=8")
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert data["month"] == 8
    assert len(data["events"]) > 0


def test_api_trade_cost_calculator_endpoint():
    """測試 GET /api/trade-cost/calculator"""
    resp = client.get("/api/trade-cost/calculator?buy_price=650&shares=1000&fee_discount=0.6&target_sell_price=700")
    assert resp.status_code == 200
    data = resp.json()
    assert data["inputs"]["buy_price"] == 650.0
    assert data["breakeven"]["breakeven_price"] > 650.0
    assert data["simulation"]["net_profit"] > 0


def test_api_stock_chip_analysis_endpoint():
    """測試 GET /api/stocks/2330/chip-analysis"""
    resp = client.get("/api/stocks/2330/chip-analysis?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "2330"
    assert "stance" in data


def test_api_stock_detail_three_scenarios():
    """測試個股詳情在保守、基準與樂觀三情境切換時之河流圖價位動態響應"""
    # 基準情境
    resp_base = client.get("/api/stocks/2330?metric=pe&scenario=base")
    assert resp_base.status_code == 200
    d_base = resp_base.json()
    p2_base = d_base["river"]["prices"]["p2_cheap"]

    # 保守情境 (-5%營收成長, -1%淨利率)
    resp_cons = client.get("/api/stocks/2330?metric=pe&scenario=conservative")
    assert resp_cons.status_code == 200
    d_cons = resp_cons.json()
    p2_cons = d_cons["river"]["prices"]["p2_cheap"]
    assert "保守" in d_cons["scenario_desc"]

    # 樂觀情境 (+5%營收成長, +1%淨利率)
    resp_opt = client.get("/api/stocks/2330?metric=pe&scenario=optimistic")
    assert resp_opt.status_code == 200
    d_opt = resp_opt.json()
    p2_opt = d_opt["river"]["prices"]["p2_cheap"]
    assert "樂觀" in d_opt["scenario_desc"]

    # 驗證五段價位線：保守價位 < 基準價位 < 樂觀價位
    assert p2_cons < p2_base < p2_opt

    # 驗證綜合體質卡、籌碼卡與交易成本速算資料已包含在回傳中
    assert "composite_score" in d_base
    assert "chip_analysis" in d_base
    assert "quick_trade_cost" in d_base
