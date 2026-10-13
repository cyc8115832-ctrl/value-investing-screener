"""首頁批次查詢保留時點、hash與回應契約，且不隨股數重複查詢。"""
import json
from datetime import date,datetime
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from src.database.schema import Base,StockMaster,MarketEvidenceRevision
from src.services.market_evidence import (save_evidence,evidence_rows,evidence_rows_many,
    stock_view,stock_evidence_bundle,data_quality_report)
from config.settings import SETTINGS


@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with Session(engine) as session:
        for ticker in ('2330','2317'):
            session.add(StockMaster(ticker=ticker,company_name='測試公司',industry='測試'))
            for day in range(1,13):
                save_evidence(session,'price',ticker,f'2026-10-{day:02}',
                    {'close':day*10,'pe':day,'pb':day/10},'https://official.example',
                    date(2026,10,day),datetime(2026,10,day))
        session.commit()
        yield session
    engine.dispose()


def test_summary_window_keeps_full_stock_response_and_period_counts(db,monkeypatch):
    monkeypatch.setattr(SETTINGS,'RIVER_OBSERVATIONS',4)
    monkeypatch.setattr(SETTINGS,'RIVER_MIN_OBSERVATIONS',4)
    stocks=db.query(StockMaster).order_by(StockMaster.ticker).all()
    bundles=stock_evidence_bundle(db,stocks)
    for stock in stocks:
        for metric in ('auto','pe','pb','ps'):
            full=stock_view(db,stock,metric)
            assert stock_view(db,stock,metric,evidence=bundles[stock.ticker])==full
        assert len(bundles[stock.ticker]['price'])==12
        assert 'close' not in bundles[stock.ticker]['price'][0]
    assert data_quality_report(db,stocks,bundles)['verified_coverage']['price']==2


def test_same_time_versions_use_latest_id_but_not_future_or_invalid_versions(db):
    first=save_evidence(db,'income_ytd','2330','2026-Q2',{'eps':1},'https://official.example',
                        date(2026,8,14),datetime(2026,8,14))
    db.commit()
    save_evidence(db,'income_ytd','2330','2026-Q2',{'eps':2},'https://official.example',
                  date(2026,8,14),datetime(2026,8,14));db.commit()
    save_evidence(db,'income_ytd','2330','2026-Q2',{'eps':3},'https://official.example',
                  date(2026,10,14),datetime(2026,10,13,16));db.commit()
    assert evidence_rows_many(db,'income_ytd',['2330'],date(2026,10,13))['2330'][0]['eps']==2
    latest=db.query(MarketEvidenceRevision).order_by(MarketEvidenceRevision.id.desc()).first()
    latest.status='rejected';db.commit()
    assert not evidence_rows(db,'income_ytd','2330',date(2026,10,14))
    first.payload_json=json.dumps({'eps':999});db.commit()
    assert not evidence_rows(db,'income_ytd','2330',date(2026,10,13))


def test_unflushed_transaction_tampering_is_not_hidden_by_raw_read(db):
    from src.database.schema import MarketEvidence
    db.autoflush=False
    row=db.get(MarketEvidence,('price','2330','2026-10-12'))
    row.payload_json='{}'
    assert len(evidence_rows(db,'price','2330'))==11


def test_overview_uses_constant_queries_and_matches_existing_endpoints(db):
    from src.web.api.verified_routes import verified_overview,verified_radar,verified_screener
    queries=[]
    listener=lambda *args:queries.append(args[2])
    event.listen(db.bind,'before_cursor_execute',listener)
    try:
        overview=verified_overview(db)
        assert len(queries)==6
    finally:event.remove(db.bind,'before_cursor_execute',listener)
    assert overview['radar']==verified_radar(db)
    assert overview['stocks']==verified_screener(db=db)
