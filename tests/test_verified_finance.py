"""單季化與真實持有期的會計、未來資訊及虧損案例。"""
from datetime import date
from src.engines.verified_earnings import realized_eps_summary
from src.engines.point_in_time import simulate_hold_period


def test_cumulative_eps_not_counted_four_times():
    rows = [{"period": f"2025-Q{i}", "eps": eps, "available_date": "2026-03-01",
             "eps_comparable_basis_verified": True, "eps_basis_id": "核實同一股數分母"}
            for i, eps in enumerate([2, 5, 4, 10], 1)]
    result = realized_eps_summary(rows, date(2026, 3, 2))
    assert [r["eps"] for r in result["quarters"]] == [2, 3, -1, 6]
    assert result["ttm_eps"] == 10
    assert result["annual_eps"]["2025"] == 10
    assert not realized_eps_summary(rows, date(2026, 2, 28))["available"]


def test_weighted_share_denominators_cannot_be_assumed_equal():
    rows = [{"period": f"2025-Q{i}", "eps": eps, "available_date": "2026-03-01"}
            for i, eps in enumerate([2, 5, 4, 10], 1)]
    assert not realized_eps_summary(rows, date(2026, 3, 2))["available"]
    for row in rows:
        row.update(eps_comparable_basis_verified=True, eps_basis_id=row["period"])
    assert not realized_eps_summary(rows, date(2026, 3, 2))["available"]


def test_direct_quarter_eps_requires_source_and_availability():
    row = {"period": "2026-Q2", "eps": 5, "standalone_eps": 3,
           "standalone_eps_verified": True, "available_date": "2026-08-01",
           "standalone_eps_source_url": "https://example.test/official-quarter",
           "standalone_eps_available_date": "2026-08-15"}
    assert realized_eps_summary([row], date(2026, 8, 14))["quarters"][0]["eps"] is None
    assert realized_eps_summary([row], date(2026, 8, 15))["quarters"][0]["eps"] == 3


def test_quarter_gaps_never_generate_ttm():
    rows = [{"period":"2026-Q2", "eps":49.33, "available_date":"2026-10-07"}]
    result = realized_eps_summary(rows, date(2026, 10, 7))
    assert result["quarters"][0]["eps"] is None
    assert result["ttm_eps"] is None
    assert result["estimated_eps"] is None


def inputs():
    signal = {"decision_date":"2026-01-02", "available_date":"2026-01-02", "verified":True}
    membership = {"effective_date":"2025-01-01", "available_date":"2025-01-01", "verified":True}
    prices = [{"date":"2026-01-05", "available_date":"2026-01-05", "open":100, "close":90, "verified":True}, {"date":"2026-01-06", "available_date":"2026-01-06", "open":90, "close":80, "verified":True}]
    sessions = [p["date"] for p in prices]
    return signal, membership, prices, sessions


def test_losses_are_not_floored_to_success():
    signal, membership, prices, sessions = inputs()
    result = simulate_hold_period(signal, membership, prices, [], sessions, sessions[-1], True)
    assert result["available"]
    assert round(result["total_return_pct"], 6) == -20
    assert round(result["max_drawdown_pct"], 6) == -20
    signal["available_date"] = "2026-01-03"
    assert not simulate_hold_period(signal, membership, prices, [], sessions, sessions[-1], True)["available"]


def test_split_and_dividend_and_missing_days():
    signal, membership, prices, sessions = inputs()
    prices[-1]["close"] = 50
    events = [{"date":sessions[-1], "available_date":"2025-12-31", "verified":True, "type":"split", "ratio":2}, {"date":sessions[-1], "available_date":"2025-12-31", "verified":True, "type":"cash_dividend", "amount":2}]
    result = simulate_hold_period(signal, membership, prices, events, sessions, sessions[-1], True)
    assert round(result["total_return_pct"], 6) == 4
    assert not simulate_hold_period(signal, membership, prices[:-1], events, sessions, sessions[-1], True)["available"]
    assert not simulate_hold_period(signal, membership, prices, events, sessions, sessions[-1], False)["available"]
