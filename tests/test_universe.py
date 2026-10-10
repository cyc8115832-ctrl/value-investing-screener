"""
測試股池模組 (Universe Module - 規格書第 2 章)
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.schema import Base, StockMaster, ETFMembership, UniverseEvent
from src.universe.cleaner import clean_etf_holdings, is_valid_tw_stock_ticker
from src.universe.syncer import sync_etf_holdings, get_universe_summary
from src.universe.custom_stock import add_custom_stock, remove_custom_stock

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_clean_etf_holdings():
    """驗證 2.4 清洗規則：排除期貨、現金、債券、特別股等"""
    raw_data = [
        {"ticker": "2330", "name": "台積電", "weight": 52.3},
        {"ticker": "2454", "name": "聯發科", "weight": 4.8},
        {"ticker": "TX", "name": "臺股期貨202610", "weight": 1.2},
        {"ticker": "", "name": "銀行存款與保證金", "weight": 0.5},
        {"ticker": "2881A", "name": "富邦特", "weight": 0.3},
        {"ticker": "0050", "name": "元大台灣50ETF", "weight": 0.0},
    ]

    cleaned, excluded = clean_etf_holdings(raw_data)
    assert len(cleaned) == 2
    tickers = [x["ticker"] for x in cleaned]
    assert "2330" in tickers
    assert "2454" in tickers
    assert len(excluded) == 4


def test_etf_sync_and_events(test_db):
    """驗證 2.3 股池版本管理與事件生成 (新增、剔除、權重變更)"""
    # 第一次同步 (Day 1)
    day1_holdings = [
        {"ticker": "2330", "name": "台積電", "weight": 50.0},
        {"ticker": "2454", "name": "聯發科", "weight": 5.0},
        {"ticker": "2317", "name": "鴻海", "weight": 6.0}
    ]
    res1 = sync_etf_holdings(test_db, "0050", day1_holdings, snapshot_date=date(2026, 9, 1))
    assert res1["total_cleaned"] == 3
    assert res1["events_count"] == 0

    # 第二次同步 (Day 2: 剔除鴻海 2317, 新增廣達 2382, 聯發科 2454 權重從 5.0% 升到 6.5%)
    day2_holdings = [
        {"ticker": "2330", "name": "台積電", "weight": 50.0},
        {"ticker": "2454", "name": "聯發科", "weight": 6.5},  # 權重變動 +1.5%
        {"ticker": "2382", "name": "廣達", "weight": 4.0}    # 新增
        # 2317 剔除
    ]
    res2 = sync_etf_holdings(test_db, "0050", day2_holdings, snapshot_date=date(2026, 9, 2))
    assert res2["events_count"] == 3

    events = test_db.query(UniverseEvent).all()
    event_types = [e.event_type for e in events]
    assert "add" in event_types
    assert "remove" in event_types
    assert "weight_change" in event_types


def test_custom_stock_workflow(test_db):
    """驗證 2.5 自選股加入、上限、ETF防呆與移除流程"""
    # 預先同步 0050 內有台積電 2330
    sync_etf_holdings(test_db, "0050", [{"ticker": "2330", "name": "台積電", "weight": 50.0}])

    # 1. 嘗試加入已在 ETF 股池的台積電 -> 應回傳已在股池，不重複加入
    res_dup = add_custom_stock(test_db, "2330")
    assert res_dup["success"] is False
    assert res_dup["error_code"] == "ALREADY_IN_ETF"

    # 2. 嘗試加入非法代號
    res_inv = add_custom_stock(test_db, "ABCD")
    assert res_inv["success"] is False
    assert res_inv["error_code"] == "INVALID_TICKER"

    # 3. 正常加入全新自選股 (如 6488 環球晶)
    res_ok = add_custom_stock(test_db, "6488", company_name="環球晶", industry="半導體業")
    assert res_ok["success"] is True
    assert res_ok["backfill_status"] == "done"

    stock = test_db.query(StockMaster).filter(StockMaster.ticker == "6488").first()
    assert stock.pool_status == "custom"

    # 4. 移除自選股
    res_rem = remove_custom_stock(test_db, "6488")
    assert res_rem["success"] is True
    assert stock.pool_status == "former"


def test_t04_financial_gap_matrix_report():
    import json
    from pathlib import Path
    t04_report = Path(__file__).resolve().parents[1] / 'reports/2026-10-10/T04-全94檔歷年財報缺口矩陣與回補範圍清單.json'
    assert t04_report.exists()
    data = json.loads(t04_report.read_text(encoding='utf-8'))
    assert data['target_task'] == 'T04'
    assert data['total_stocks'] == 94
    assert data['total_quarters'] == 18
    assert data['total_cells'] == 5076
    assert data['existing_cells'] == 209
    assert data['missing_cells'] == 4867
    assert len(data['batches_plan']) == 5
    assert len(data['stock_summaries']) == 94
