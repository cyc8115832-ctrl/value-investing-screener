"""
單元與整合測試套件 - 盤後自動化管線、LINE 綁定 Webhook、定期定額試算機與漲跌拆解
(tests/test_v2_and_pipeline.py)
嚴格落實技術規格書 V1.7：
- 規格書 5.5: 定期定額回測試算機 (不再投入 vs 股息再投入、MDD、費率)
- 規格書 6.9: 漲跌拆解公式 ln(P1/P0) = ln(EPS1/EPS0) + ln(PE1/PE0) 與估值極端旗標 (D-26)
- 規格書 14.6: 宏觀水位美債 10 年期殖利率
- 規格書 15.3: LINE 帳號綁定流程 (6 位一次性驗證碼、Webhook、封鎖)
- 規格書 10, 11: 盤後自動化重算流水線 (TWSE、ETF、全股池重算)
"""

import pytest
import base64
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient

from src.database.session import SessionLocal, init_db
from src.database.schema import (
    StockMaster, PriceDaily, EPSRecord, LineBinding, MacroDaily, DividendHistory
)
from src.engines.dca_backtest import run_dca_backtest
from src.engines.decomposition import calculate_price_decomposition, evaluate_valuation_extreme_flag
from src.data.macro_adapter import determine_yield_warning, sync_macro_yield_to_db, get_latest_macro_yield
from src.services.line_push import (
    generate_binding_code, get_binding_status, unbind_line_account,
    verify_line_signature, handle_line_webhook
)
from src.services.scheduler import MarketDataScheduler
from src.web.app import app


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================================================================
# 1. 測試定期定額回測試算機 (規格書 5.5)
# =========================================================================
def test_dca_backtest_calculator():
    # 建立 3 年模擬價格資料 (每月穩步上漲)
    prices = []
    base_d = date(2023, 1, 1)
    cur_p = 100.0
    for day_offset in range(1100):
        d = base_d + timedelta(days=day_offset)
        cur_p += 0.05
        prices.append({"date": d, "close": cur_p})

    # 除息紀錄 (每年 7 月配息 3.5 元)
    divs = [
        {"ex_date": "2023-07-15", "pay_date": "2023-07-15", "cash_dividend": 3.5, "stock_dividend": 0.0},
        {"ex_date": "2024-07-15", "pay_date": "2024-07-15", "cash_dividend": 4.0, "stock_dividend": 0.0},
        {"ex_date": "2025-07-15", "pay_date": "2025-07-15", "cash_dividend": 4.5, "stock_dividend": 0.0}
    ]

    res = run_dca_backtest(
        prices=prices,
        dividends=divs,
        monthly_amount=10000.0,
        invest_day=5,
        years=3,
        fee_rate=0.001425,
        fee_discount=1.0,
        min_fee=1.0,
        is_etf=False
    )

    assert res["status"] == "success"
    assert "without_reinvestment" in res
    assert "with_reinvestment" in res
    assert "disclosures" in res

    # 檢驗兩種模式指標
    no_reinvest = res["without_reinvestment"]
    reinvest = res["with_reinvestment"]

    assert no_reinvest["total_invested"] > 0
    assert no_reinvest["accumulated_cash_dividends"] > 0
    assert reinvest["total_shares"] > no_reinvest["total_shares"]  # 再投入之股數應大於未再投入
    assert "max_drawdown_pct" in no_reinvest
    assert "max_drawdown_pct" in reinvest
    assert "股票 0.3%" in res["disclosures"]["tax_hint"]


# =========================================================================
# 2. 測試漲跌拆解公式與估值極端旗標 (規格書 6.9 & D-26)
# =========================================================================
def test_price_decomposition_math():
    # 測試股價上漲，由獲利成長驅動
    # P0=100, P1=200 (漲 100%), EPS0=5, EPS1=10 (獲利倍增), PE 保持 20 倍不變
    decomp = calculate_price_decomposition(p0=100.0, p1=200.0, eps0=5.0, eps1=10.0, period_name="1年")
    assert decomp["applicable"] is True
    assert decomp["eps_contribution_pct"] == 100.0
    assert decomp["pe_contribution_pct"] == 0.0

    # 測試股價上漲，由倍數擴張驅動 (獲利不變 EPS0=5, EPS1=5, P0=100, P1=200)
    decomp_pe = calculate_price_decomposition(p0=100.0, p1=200.0, eps0=5.0, eps1=5.0, period_name="1年")
    assert decomp_pe["applicable"] is True
    assert decomp_pe["eps_contribution_pct"] == 0.0
    assert decomp_pe["pe_contribution_pct"] == 100.0

    # 測試 EPS <= 0 時依規格不顯示
    decomp_neg = calculate_price_decomposition(p0=100.0, p1=120.0, eps0=-1.0, eps1=2.0)
    assert decomp_neg["applicable"] is False
    assert "EPS ≤ 0" in decomp_neg["reason"]


def test_extreme_valuation_flags():
    # 案例 1: 本益比 > 100 倍觸發警示
    flag1 = evaluate_valuation_extreme_flag(
        current_price=500.0,
        current_pe=120.0,
        current_eps=4.16,
        week52_high=520.0,
        week52_low=200.0,
        industry_median_pe=20.0
    )
    assert flag1["flagged"] is True
    assert "獲利尚未支撐股價" in flag1["badge"]

    # 案例 2: 虧損 (EPS <= 0) 且股價位於近 52 週上 20%
    flag2 = evaluate_valuation_extreme_flag(
        current_price=95.0,
        current_pe=None,
        current_eps=-0.8,
        week52_high=100.0,
        week52_low=50.0,
        industry_median_pe=20.0
    )
    assert flag2["flagged"] is True
    assert "52 週前 20%" in flag2["message"]

    # 案例 3: 循環股或金融股依規格排除
    flag_cyclical = evaluate_valuation_extreme_flag(
        current_price=500.0,
        current_pe=150.0,
        current_eps=3.0,
        week52_high=520.0,
        week52_low=200.0,
        is_cyclical=True
    )
    assert flag_cyclical["flagged"] is False
    assert flag_cyclical["excluded"] is True


# =========================================================================
# 3. 測試宏觀水位美債殖利率判定 (規格書 14.6)
# =========================================================================
def test_macro_yield_warning():
    # 正常水位 (< 4.5%)
    w_norm = determine_yield_warning(4.25)
    assert w_norm["flag"] == "normal"
    assert w_norm["level"] == "normal"

    # 接近提示 (≥ 4.5%)
    w_appr = determine_yield_warning(4.68)
    assert w_appr["flag"] == "warning_4_5"
    assert w_appr["level"] == "warning"

    # 警戒線 (≥ 5.0%)
    w_alert = determine_yield_warning(5.12)
    assert w_alert["flag"] == "alert_5_0"
    assert w_alert["level"] == "alert"


def test_macro_sync_db(db_session):
    rec = sync_macro_yield_to_db(db_session, mock_yield=4.85)
    assert rec.us_10y_yield == 4.85
    assert rec.warning_flag == "warning_4_5"

    summary = get_latest_macro_yield(db_session)
    assert summary["us_10y_yield"] == 4.85
    assert summary["warning_level"] == "warning"


# =========================================================================
# 4. 測試 LINE 6 位綁定碼與 Webhook (規格書 15.3)
# =========================================================================
def test_line_binding_lifecycle(db_session):
    user_id = "test_user_line"

    # 1. 產生 6 位驗證碼
    bind_res = generate_binding_code(db_session, user_id=user_id)
    code = bind_res["binding_code"]
    assert len(code) == 6
    assert code.isdigit()
    assert bind_res["status"] == "pending"

    # 2. 模擬 LINE Webhook 收到用戶回覆該 6 位代碼
    secret = "test_secret_for_test"
    payload = {
        "events": [
            {
                "type": "message",
                "replyToken": "dummy_reply_token",
                "source": {"userId": "U1234567890abcdef"},
                "message": {"type": "text", "text": code}
            }
        ]
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # 計算合法簽名
    hash_val = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).digest()
    sig = base64.b64encode(hash_val).decode("utf-8")

    # 驗證簽名工具
    assert verify_line_signature(body_bytes, sig, secret=secret) is True

    # 處理 Webhook
    webhook_res = handle_line_webhook(db_session, body_bytes, sig)
    assert webhook_res["status"] == "success"
    assert webhook_res["processed_events"] == 1

    # 3. 檢驗綁定狀態
    st = get_binding_status(db_session, user_id=user_id)
    assert st["is_bound"] is True
    assert st["status"] == "bound"
    assert st["line_user_id_masked"] is not None

    # 4. 模擬用戶解除綁定
    unbind_res = unbind_line_account(db_session, user_id=user_id)
    assert unbind_res["status"] == "success"
    st2 = get_binding_status(db_session, user_id=user_id)
    assert st2["is_bound"] is False


# =========================================================================
# 5. 測試盤後排程管線執行
# =========================================================================
def test_pipeline_execution():
    scheduler = MarketDataScheduler()
    res = scheduler.execute_daily_pipeline()
    assert res["status"] == "success"
    assert "sync_prices" in res["steps"]
    assert "screener_pipeline" in res["steps"]
    assert "exit_alerts" in res["steps"]


# =========================================================================
# 6. 測試 RESTful API 端點
# =========================================================================
def test_api_endpoints(client):
    # 宏觀 API
    resp_macro = client.get("/api/macro/us-10y")
    assert resp_macro.status_code == 200
    assert "us_10y_yield" in resp_macro.json()

    # 定期定額試算 API
    resp_dca = client.get("/api/stocks/2330/dca-backtest?monthly_amount=10000&years=3")
    assert resp_dca.status_code == 200
    data_dca = resp_dca.json()
    assert data_dca["ticker"] == "2330"
    assert "without_reinvestment" in data_dca
    assert "with_reinvestment" in data_dca

    # 漲跌拆解 API
    resp_decomp = client.get("/api/stocks/2330/decomposition")
    assert resp_decomp.status_code == 200
    data_decomp = resp_decomp.json()
    assert data_decomp["ticker"] == "2330"
    assert "decomposition_1y" in data_decomp
    assert "extreme_flag" in data_decomp

    # LINE 綁定狀態 API
    resp_line_st = client.get("/api/line/binding-status")
    assert resp_line_st.status_code == 200
    assert "is_bound" in resp_line_st.json()

    # LINE 產生 6 位驗證碼 API
    resp_line_code = client.post("/api/line/binding-code")
    assert resp_line_code.status_code == 200
    assert len(resp_line_code.json()["binding_code"]) == 6

    # 手動觸發重算流水線 API
    resp_pipeline = client.post("/api/pipeline/run")
    assert resp_pipeline.status_code == 200
    assert resp_pipeline.json()["status"] == "success"
