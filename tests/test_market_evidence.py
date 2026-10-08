"""正式來源、未知值與發布時點的回歸測試。"""
import json
from datetime import date, datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from src.database.schema import Base, MarketEvidence, StockMaster, PriceDaily
from src.services.market_evidence import save_evidence, evidence_rows, stock_view, valuation_from_history
from src.data.verified_importer import roc_date, import_snapshot, OFFICIAL_SOURCES
from config.settings import SETTINGS


@pytest.fixture
def clean_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(StockMaster(ticker="2330", company_name="台積電", industry="半導體"))
        db.commit()
        yield db
    engine.dispose()


def test_available_date_and_tampering(clean_db):
    row = save_evidence(clean_db, "income_ytd", "2330", "2026-Q2", {"eps": 30}, "https://openapi.twse.com.tw", date(2026, 8, 14), observed_at=datetime(2026, 8, 14))
    clean_db.commit()
    assert not evidence_rows(clean_db, "income_ytd", "2330", date(2026, 8, 13))
    assert evidence_rows(clean_db, "income_ytd", "2330", date(2026, 8, 14))[0]["eps"] == 30
    row.payload_json = json.dumps({"eps": 100})
    clean_db.commit()
    assert not evidence_rows(clean_db, "income_ytd", "2330")


def test_old_price_never_becomes_verified(clean_db):
    clean_db.add(PriceDaily(ticker="2330", date=date(2026, 10, 7), close=100, volume=10))
    clean_db.commit()
    view = stock_view(clean_db, clean_db.get(StockMaster, "2330"))
    assert view["quote"] is None
    assert not view["valuation"]["available"]
    assert view["company_status"] == "insufficient"


def test_import_preserves_date_and_does_not_mix_ratios(clean_db):
    snapshot = {"來源": {
        "上市行情": {"url": OFFICIAL_SOURCES["上市行情"], "matched_rows": [{"Code": "2330", "Date": "1151006", "Name": "台積電", "ClosingPrice": "2585", "TradeVolume": "1234"}]},
        "上市倍數": {"url": OFFICIAL_SOURCES["上市倍數"], "matched_rows": [{"Code": "2330", "Date": "1151005", "PEratio": "20"}]}}}
    result = import_snapshot(clean_db, snapshot)
    clean_db.commit()
    assert result["price"] == 1
    quote = evidence_rows(clean_db, "price", "2330")[-1]
    assert quote["period"] == "2026-10-06"
    assert quote["pe"] is None
    assert clean_db.get(PriceDaily, ("2330", date(2026, 10, 7))) is None
    with pytest.raises(ValueError):
        roc_date(None)


def test_rolling_model_rejects_future_and_insufficient_samples(monkeypatch):
    monkeypatch.setattr(SETTINGS, "RIVER_MIN_OBSERVATIONS", 4)
    monkeypatch.setattr(SETTINGS, "RIVER_OBSERVATIONS", 4)
    history = [{"period": f"2026-10-0{i}", "available_date": f"2026-10-0{i}", "close": i * 100, "pe": i * 10} for i in range(1, 5)]
    assert not valuation_from_history(history, as_of=date(2026, 10, 3))["available"]
    result = valuation_from_history(history, as_of=date(2026, 10, 4))
    assert result["available"]
    assert result["sample_count"] == 4
    assert result["zone"] == "crazy"
    assert result["levels"][0] < result["levels"][-1] < 400


def test_missing_latest_multiple_does_not_use_earlier_base(monkeypatch):
    monkeypatch.setattr(SETTINGS, "RIVER_MIN_OBSERVATIONS", 2)
    history = [{"period": "2026-10-01", "close": 100, "pe": 10}, {"period": "2026-10-02", "close": 200, "pe": 20}, {"period": "2026-10-03", "close": 300, "pe": None}]
    assert not valuation_from_history(history, as_of=date(2026, 10, 3))["available"]


def test_production_pipeline_cannot_recreate_fake_picks(clean_db, monkeypatch):
    monkeypatch.setattr(SETTINGS, "DEMO_MODE", False)
    from src.services.daily_screener import run_daily_screener_pipeline
    assert run_daily_screener_pipeline(clean_db)["status"] == "insufficient"


def test_revisions_do_not_rewrite_past_financials(clean_db):
    save_evidence(clean_db, "income_ytd", "2330", "2026-Q2", {"eps":30}, "https://openapi.twse.com.tw", date(2026,8,14), observed_at=datetime(2026,8,14))
    clean_db.commit()
    save_evidence(clean_db, "income_ytd", "2330", "2026-Q2", {"eps":40}, "https://openapi.twse.com.tw", date(2026,10,7), observed_at=datetime(2026,10,7))
    clean_db.commit()
    assert evidence_rows(clean_db,"income_ytd","2330",date(2026,9,1))[0]["eps"] == 30
    assert evidence_rows(clean_db,"income_ytd","2330",date(2026,10,7))[0]["eps"] == 40


def test_production_api_excludes_legacy_rows_and_rejects_fake_analysis(clean_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.database.session import get_db
    from src.web.api.verified_routes import verified_router,enforce_evidence_boundary
    monkeypatch.setattr(SETTINGS,"DEMO_MODE",False)
    application=FastAPI()
    application.middleware("http")(enforce_evidence_boundary)
    application.include_router(verified_router,prefix="/api")
    application.dependency_overrides[get_db]=lambda:clean_db
    client=TestClient(application)
    clean_db.add(PriceDaily(ticker="2330",date=date(2026,10,7),close=100,volume=10))
    clean_db.commit()
    detail=client.get('/api/stocks/2330').json()
    assert detail['quote'] is None
    assert client.get('/api/backtest').status_code == 409
    assert client.get('/api/screener?scope=etf').status_code == 409
    assert client.post('/api/push/preview').status_code == 409
    assert client.get('/api/evidence/stocks/2330/history').json()['rows'] == []
    assert not client.get('/api/radar').json()['daily_picks_preview']


def test_source_failure_does_not_create_a_today_quote(clean_db, monkeypatch):
    import src.data.twse_adapter as adapter
    clean_db.add(PriceDaily(ticker='2330',date=date(2026,10,6),close=100,volume=10))
    clean_db.commit()
    monkeypatch.setattr(adapter,'fetch_twse_market_snapshot',lambda:{})
    assert adapter.sync_daily_prices_to_db(clean_db,date(2026,10,7)) == 0
    assert clean_db.get(PriceDaily,('2330',date(2026,10,7))) is None
