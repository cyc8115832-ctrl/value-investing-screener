import pytest
from src.engines.point_in_time import simulate_hold_period


def test_point_in_time_rejects_lookahead_and_fixed_pool():
    """
    T10 真實時點回測鐵律測試：
    1. 決策日訊號若晚於決策日可得，拒絕回測。
    2. 歷史成分若未在決策日生效或缺證據，拒絕回測。
    3. 不允許使用今日固定股池替代過去名單。
    """
    signal = {"decision_date": "2026-01-02", "available_date": "2026-01-03", "verified": True}
    membership = {"effective_date": "2025-01-01", "available_date": "2025-01-01", "verified": True}
    prices = [
        {"date": "2026-01-05", "available_date": "2026-01-05", "open": 100, "close": 95, "verified": True},
        {"date": "2026-01-06", "available_date": "2026-01-06", "open": 95, "close": 90, "verified": True}
    ]
    sessions = [p["date"] for p in prices]

    # 1. 訊號未來可得 (Lookahead)
    res1 = simulate_hold_period(signal, membership, prices, [], sessions, sessions[-1], True)
    assert not res1["available"]
    assert "訊號在決策日尚不可得" in res1["reason"]

    # 2. 歷史成分生效日晚於決策日 (NotInPool)
    signal["available_date"] = "2026-01-02"
    membership["effective_date"] = "2026-02-01"
    res2 = simulate_hold_period(signal, membership, prices, [], sessions, sessions[-1], True)
    assert not res2["available"]
    assert "決策日不在股池" in res2["reason"]
