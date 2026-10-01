"""
測試 LINE 官方帳號雙向智能指令引擎與新手沙盒模擬模式 (Sandbox Mode)
對應規格書第 15.3 節、第 15.4 節與第 17.2 節
"""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app
from src.database.session import SessionLocal
from src.data.mock_fixtures import seed_database_fixtures
from src.services.line_push import process_line_incoming_text

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def init_db():
    db = SessionLocal()
    seed_database_fixtures(db)
    yield db
    db.close()


def test_line_incoming_stock_query(init_db):
    """驗證輸入 4 碼股票代號即時查詢現價、位階與好公司健檢 (規格書 15.4)"""
    db = init_db
    # 測試查詢 2330
    reply = process_line_incoming_text(db, "2330")
    assert "台積電" in reply
    assert "2330" in reply
    assert "最新收盤價" in reply
    assert "河流圖位階" in reply
    assert "好公司健檢" in reply
    assert "先選好公司，再等好價格" in reply

    # 測試帶有自然語言前綴 "查詢 2454"
    reply_prefix = process_line_incoming_text(db, "查詢 2454")
    assert "聯發科" in reply_prefix
    assert "2454" in reply_prefix


def test_line_incoming_stock_query_not_found(init_db):
    """驗證查詢非股池標的時之引導加入自選股提示"""
    db = init_db
    reply = process_line_incoming_text(db, "9998")
    assert "股池中暫無股票代號【9998】" in reply
    assert "新增自選股" in reply


def test_line_incoming_tips_and_screener(init_db):
    """驗證查詢投資心法與盤後精選名單指令"""
    db = init_db
    # 查詢心法
    reply_tip = process_line_incoming_text(db, "心法")
    assert "安心投資心法" in reply_tip

    # 查詢精選
    reply_picks = process_line_incoming_text(db, "精選")
    assert "價值投資選股" in reply_picks


def test_line_incoming_glossary(init_db):
    """驗證白話辭典雙向查詢功能 (規格書 17.2)"""
    db = init_db
    # 查詢特定名詞
    reply_pe = process_line_incoming_text(db, "辭典 本益比")
    assert "本益比" in reply_pe
    assert "白話解釋" in reply_pe

    # 未指定名詞時列出範例
    reply_empty = process_line_incoming_text(db, "辭典")
    assert "常用查詢範例" in reply_empty
    assert "辭典 本益比" in reply_empty


def test_line_incoming_help_menu(init_db):
    """驗證預設幫助選單指南"""
    db = init_db
    reply_help = process_line_incoming_text(db, "幫助")
    assert "智能助理指令指南" in reply_help
    assert "4 碼股票代號" in reply_help
    assert "精選" in reply_help


def test_simulation_sample_stock_api():
    """驗證新手教學沙盒模擬標的 API (規格書 17.2)"""
    res = client.get("/api/simulation/sample-stock")
    assert res.status_code == 200
    data = res.json()
    assert data["is_simulation"] is True
    assert data["ticker"] == "9999"
    assert "範例科技" in data["company_name"]
    assert "valuation" in data
    assert "p1" in data["valuation"]
    assert "p6" in data["valuation"]
    assert "lights" in data
    assert "ai_analyst" in data
    assert "notice" in data
