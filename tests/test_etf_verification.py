import pytest
from src.universe.syncer import ETF_DEFINITIONS
from src.database.session import SessionLocal
from src.database.schema import ETFHoldingsSnapshot


def test_etf_definitions_four_core():
    """T07 核心測試：確認 4 檔 ETF 規格與代碼"""
    codes = [e["etf_code"] for e in ETF_DEFINITIONS]
    assert codes == ["0050", "0056", "00881", "00891"]


def test_demo_holdings_are_not_official_weight_evidence(monkeypatch):
    """
    只驗示範資料型態，不據此驗收官方權重、現金或期貨原因。
    """
    db = SessionLocal()
    try:
        snapshots = db.query(ETFHoldingsSnapshot).all()
        assert snapshots
        for s in snapshots:
            assert s.weight > 0
        from config.settings import SETTINGS
        from src.universe.syncer import sync_all_etf_holdings
        monkeypatch.setattr(SETTINGS, 'DEMO_MODE', False)
        with pytest.raises(RuntimeError, match='官方成分'):
            sync_all_etf_holdings(db)
        assert db.query(ETFHoldingsSnapshot).count() == len(snapshots)
    finally:
        db.close()
