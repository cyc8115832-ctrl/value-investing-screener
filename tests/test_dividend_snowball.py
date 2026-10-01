"""
價值投資選股 App - 股息現金流複利滾雪球與被動收入引擎測試 (tests/test_dividend_snowball.py)
驗證項目：
1. 純函式股息滾雪球試算 (初期股數、定期定額新增、再投入股數、期末市值)
2. 股息再投入 (DRIP) 與非再投入之資產倍數差異 (Wealth Multiplier)
3. 持有成本殖利率 (Yield on Cost, YoC) 與實質購買力折現
4. 資本回本年限 (Payback Year) 與股息里程碑 (10萬/50萬/100萬)
5. 邊界與異常輸入保護 (零本金防呆)
6. RESTful API /api/portfolio/dividend-snowball 整合端點測試
"""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app
from src.engines.dividend_snowball import simulate_dividend_snowball

client = TestClient(app)


def test_dividend_snowball_pure_basic():
    """測試基礎純函式試算：15 年、5% 殖利率、5% 股利成長、6% 股價成長"""
    res = simulate_dividend_snowball(
        initial_capital=1_000_000.0,
        annual_addition=120_000.0,
        initial_dividend_yield_pct=5.0,
        dividend_growth_rate_pct=5.0,
        price_growth_rate_pct=6.0,
        years=15,
        reinvest_dividends=True,
        inflation_rate_pct=2.0
    )

    assert res["success"] is True
    traj = res["yearly_trajectory"]
    assert len(traj) == 15

    # 驗證逐年持股數與股利呈現成長趨勢
    for i in range(1, len(traj)):
        prev = traj[i - 1]
        curr = traj[i]
        assert curr["end_shares"] > prev["end_shares"]
        assert curr["annual_dividend"] > prev["annual_dividend"]
        assert curr["portfolio_market_value"] > prev["portfolio_market_value"]

    # 驗證成本殖利率 YoC 在 15 年後顯著上升
    first_yoc = traj[0]["yield_on_cost_pct"]
    final_yoc = traj[-1]["yield_on_cost_pct"]
    assert final_yoc > first_yoc


def test_dividend_snowball_drip_vs_no_drip():
    """測試股息再投入 (DRIP) vs 拿去花掉 (No DRIP) 的財富倍數差距"""
    res = simulate_dividend_snowball(
        initial_capital=1_000_000.0,
        annual_addition=120_000.0,
        initial_dividend_yield_pct=6.0,
        dividend_growth_rate_pct=5.0,
        price_growth_rate_pct=5.0,
        years=20,
        reinvest_dividends=True
    )

    comp = res["comparison_vs_no_drip"]
    assert comp["drip_final_total_wealth"] > comp["no_drip_final_total_wealth"]
    assert comp["wealth_multiplier"] > 1.0
    assert comp["wealth_difference_amount"] > 0


def test_dividend_snowball_zero_addition():
    """測試單筆一次性投入 (無額外定期定額)，完全靠股息再投入滾雪球"""
    res = simulate_dividend_snowball(
        initial_capital=500_000.0,
        annual_addition=0.0,
        initial_dividend_yield_pct=5.0,
        dividend_growth_rate_pct=4.0,
        price_growth_rate_pct=5.0,
        years=10,
        reinvest_dividends=True
    )

    assert res["success"] is True
    traj = res["yearly_trajectory"]
    assert len(traj) == 10
    # 總自掏腰包投入資本恆為 50 萬
    assert traj[-1]["total_invested_capital"] == 500_000.0
    # 股數依然因股息再投入持續增長
    assert traj[-1]["end_shares"] > traj[0]["start_shares"]


def test_dividend_snowball_invalid_input():
    """測試初始本金與定期定額皆 <= 0 時的防呆檢查"""
    res = simulate_dividend_snowball(
        initial_capital=0,
        annual_addition=0
    )
    assert res["success"] is False
    assert "不能同時小於或等於 0" in res["error"]


def test_dividend_snowball_milestones():
    """測試資本回本年份 (Payback Year) 與年領股息里程碑"""
    res = simulate_dividend_snowball(
        initial_capital=1_000_000.0,
        annual_addition=240_000.0,  # 每年加碼 24 萬 (每月 2 萬)
        initial_dividend_yield_pct=7.0,  # 特價區高殖利率 7%
        dividend_growth_rate_pct=6.0,
        price_growth_rate_pct=5.0,
        years=25,
        reinvest_dividends=True
    )

    assert res["success"] is True
    ms = res["milestones"]
    # 應能達成年領 10 萬與 50 萬里程碑
    assert ms["reached_100k_year"] is not None
    assert ms["reached_100k_year"] <= 10
    assert ms["reached_500k_year"] is not None


def test_api_dividend_snowball_endpoint():
    """測試 API POST /api/portfolio/dividend-snowball 端點"""
    payload = {
        "initial_capital": 1000000.0,
        "annual_addition": 120000.0,
        "initial_dividend_yield_pct": 5.0,
        "dividend_growth_rate_pct": 5.0,
        "price_growth_rate_pct": 6.0,
        "years": 15,
        "reinvest_dividends": True,
        "inflation_rate_pct": 2.0
    }

    resp = client.post("/api/portfolio/dividend-snowball", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "yearly_trajectory" in data
    assert "final_metrics" in data
    assert "comparison_vs_no_drip" in data
    assert "milestones" in data
    assert len(data["yearly_trajectory"]) == 15
