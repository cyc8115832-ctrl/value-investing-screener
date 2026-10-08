"""歷史回補日期隔離與河流圖重建的真實邊界。"""
from datetime import date
import pytest
from config.settings import SETTINGS
from scripts.backfill_verified_history import normalized_month, normalized_tpex_month
from src.services.market_evidence import valuation_from_history


def test_monthly_import_requires_same_stock_and_month():
    price={'url':'https://www.twse.com.tw/exchangeReport/STOCK_DAY', 'data':{
        'stat':'OK','date':'20260901','title':'115年09月 2330 台積電',
        'fields':['日期','成交股數','開盤價','最高價','最低價','收盤價'],
        'data':[['115/09/01','1,000','100','102','99','101']]}}
    ratios={'url':'https://www.twse.com.tw/exchangeReport/BWIBBU','data':{
        'stat':'OK','date':'20260901','fields':['日期','本益比','股價淨值比'],
        'data':[['115年09月01日','10.1','2.02']]}}
    row=normalized_month('2330','20260901',price,ratios)[0]
    assert (row['period'],row['close'],row['volume'],row['pe']) == ('2026-09-01',101,1000,10.1)
    assert row['ps'] is None
    with pytest.raises(ValueError):
        normalized_month('2317','20260901',price,ratios)
    ratios['url']='https://www.twse.com.tw/exchangeReport/BWIBBU?stockNo=2317'
    with pytest.raises(ValueError):
        normalized_month('2330','20260901',price,ratios)
    ratios['url']='https://www.twse.com.tw/exchangeReport/BWIBBU?stockNo=2330'
    ratios['data']['date']='20260801'
    with pytest.raises(ValueError):
        normalized_month('2330','20260901',price,ratios)


def test_historical_reconstruction_changes_bands_without_claiming_past_knowledge(monkeypatch):
    monkeypatch.setattr(SETTINGS,'RIVER_MIN_OBSERVATIONS',3)
    monkeypatch.setattr(SETTINGS,'RIVER_OBSERVATIONS',3)
    prices=[{'period':f'2026-09-0{i}', 'available_date':f'2026-09-0{i}',
             'knowledge_date':'2026-10-07','close':close,'pe':pe}
            for i,close,pe in [(1,100,10),(2,150,15),(3,200,20),(4,600,30)]]
    assert not valuation_from_history(prices,'pe',date(2026,9,3))['available']
    earlier=valuation_from_history(prices,'pe',date(2026,9,3),reconstruction=True)
    later=valuation_from_history(prices,'pe',date(2026,9,4),reconstruction=True)
    assert earlier['levels'] != later['levels']
    assert earlier['base_value'] == 10 and later['base_value'] == 20
    assert earlier['historical_reconstruction']
    assert earlier['date'] == '2026-09-03'


def test_tpex_history_converts_thousand_shares_and_rejects_wrong_identity():
    price={'url':'https://www.tpex.org.tw/www/afterTrading/tradingStock?code=3105&date=2022%2F10%2F01',
           'data':{'stat':'ok','date':'20221001','code':'3105','tables':[{
               'fields':['日 期','成交仟股','開盤','最高','最低','收盤'],
               'data':[['111/10/03','3,753','121.50','126','120','123.50']]}]}}
    ratio={'url':'https://www.tpex.org.tw/www/afterTrading/peQryStock?code=3105&date=2022%2F10%2F01',
           'data':{'stat':'ok','date':'20221001','tables':[{
               'fields':['日期','本益比','股價淨值比'],
               'data':[['111/10/03','10.8','1.59']]}]}}
    row=normalized_tpex_month('3105','20221001',price,ratio)[0]
    assert (row['period'],row['close'],row['volume'],row['pe'],row['pb']) == ('2022-10-03',123.5,3753000,10.8,1.59)
    assert row['ps'] is None
    assert normalized_tpex_month('3105','20221001',price,None)[0]['pe'] is None
    price['data']['tables'][0]['fields'][1]='成交張數'
    assert normalized_tpex_month('3105','20221001',price,ratio)[0]['volume']==3753000
    price['data']['tables'][0]['fields'][1]='未知成交量'
    with pytest.raises(ValueError):
        normalized_tpex_month('3105','20221001',price,ratio)
    price['data']['tables'][0]['fields'][1]='成交仟股'
    with pytest.raises(ValueError):
        normalized_tpex_month('3529','20221001',price,ratio)
    price['data']['code']='3529'
    with pytest.raises(ValueError):
        normalized_tpex_month('3105','20221001',price,ratio)
    price['data']['code']='3105'
    ratio['data']['tables'][0]['data'][0][0]='111/09/30'
    with pytest.raises(ValueError):
        normalized_tpex_month('3105','20221001',price,ratio)


def test_month_batch_preserves_newest_price_and_revision_history():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from scripts.backfill_verified_history import save_month
    from src.database.schema import Base, MarketEvidence, MarketEvidenceRevision, PriceDaily
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    payload={'period':'2022-10-03','close':100,'volume':1000,'pe':10,'pb':1,'ps':None,
             'source_url':'https://www.twse.com.tw/exchangeReport/STOCK_DAY'}
    with Session(engine) as db:
        save_month(db,'2330',[payload],'2026-10-07T01:00:00+00:00');db.commit()
        save_month(db,'2330',[payload],'2026-10-07T01:00:00+00:00');db.commit()
        assert db.query(MarketEvidenceRevision).count()==1
        revised={**payload,'close':110}
        save_month(db,'2330',[revised],'2026-10-08T01:00:00+00:00');db.commit()
        save_month(db,'2330',[payload],'2026-10-07T01:00:00+00:00');db.commit()
        assert db.get(PriceDaily,('2330',date(2022,10,3))).close==110
        assert '110' in db.get(MarketEvidence,('price','2330','2022-10-03')).payload_json
        assert db.query(MarketEvidenceRevision).count()==3
        another={**payload,'period':'2022-10-04'}
        save_month(db,'2330',[another],None,{'2022-10-04':'2026-10-08T02:03:04+00:00'});db.commit()
        assert db.get(MarketEvidence,('price','2330','2022-10-04')).fetched_at.isoformat()=='2026-10-08T02:03:04'
    engine.dispose()


def test_bulk_official_history_rejects_wrong_day_and_conflicting_quotes():
    from scripts.backfill_verified_market import normalize_day
    market={'url':'https://www.twse.com.tw/exchangeReport/MI_INDEX','data':{'stat':'OK','date':'20221003',
        'tables':[{'fields':['證券代號','收盤價','成交股數','開盤價','最高價','最低價'],
                   'data':[['1101','33.65','24,684,067','33.65','33.90','33.40'],['1216','-','0','-','-','-']]}]}}
    ratios={'url':'https://www.twse.com.tw/exchangeReport/BWIBBU_d','data':{'stat':'OK','date':'20221003',
        'fields':['證券代號','收盤價','本益比','股價淨值比'],'data':[['1101','33.65','19.68','1.06']]}}
    rows=normalize_day('2022-10-03',{'1101','1216'},market,ratios)
    assert len(rows)==1 and rows[0][0]=='1101'
    assert rows[0][1]['volume']==24684067 and rows[0][1]['pb']==1.06
    ratios['data']['date']='20221004'
    with pytest.raises(ValueError):
        normalize_day('2022-10-03',{'1101'},market,ratios)
    ratios['data']['date']='20221003';ratios['data']['data'][0][1]='99'
    with pytest.raises(ValueError):
        normalize_day('2022-10-03',{'1101'},market,ratios)
