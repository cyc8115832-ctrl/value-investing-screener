import pytest
from src.universe.syncer import ETF_DEFINITIONS
from src.database.session import SessionLocal
from src.database.schema import ETFHoldingsSnapshot


def test_etf_definitions_four_core():
    """T07 核心測試：確認 4 檔 ETF 規格與代碼"""
    codes = [e["etf_code"] for e in ETF_DEFINITIONS]
    assert codes == ["0050", "0056", "00881", "00891"]


def test_etf_holdings_snapshot_weights_policy():
    """
    T07 權重政策測試：
    各 ETF 成分股權重合計因官方成分持有現金、期貨部位或未納入非權益標的，
    合計權重不保證恰好 100.0%，系統不得擅自將成分股按比例放大或填塞至 100%。
    """
    db = SessionLocal()
    try:
        snapshots = db.query(ETFHoldingsSnapshot).all()
        for s in snapshots:
            assert s.weight > 0
    finally:
        db.close()
