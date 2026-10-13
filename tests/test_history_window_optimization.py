from datetime import date,timedelta
from types import SimpleNamespace
import pytest
from config.settings import SETTINGS
from src.services import time_series
from src.services.market_evidence import valuation_from_history


@pytest.mark.parametrize('late', [False,True])
def test_rolling_window_matches_original_cutoff_rules(monkeypatch,late):
    monkeypatch.setattr(SETTINGS,'RIVER_OBSERVATIONS',5)
    monkeypatch.setattr(SETTINGS,'RIVER_MIN_OBSERVATIONS',3)
    monkeypatch.setattr(time_series,'taiwan_today',lambda:date(2026,10,12))
    prices=[]
    for i in range(12):
        day=(date(2026,9,1)+timedelta(days=i)).isoformat()
        prices.append({'period':day,'close':100+i,'pe':10+i if i!=8 else None,'available_date':day,
                       'knowledge_date':'2026-10-01','source_url':'https://www.twse.com.tw','fetched_at':'2026-10-01'})
    if late:prices[2]['available_date']='2026-09-08'
    monkeypatch.setattr(time_series,'evidence_rows',lambda db,dataset,ticker:prices if dataset=='price' else [])
    stock=SimpleNamespace(ticker='2330',is_cyclical=False,sector_type='general')
    result=time_series.stock_time_series(None,stock,'pe',3)
    for row in result['rows']:
        expected=valuation_from_history([p for p in prices if p['period']<=row['date']],'pe',date.fromisoformat(row['date']),reconstruction=True)
        assert row['model_available']==expected.get('available',False)
        assert row['bands']==expected.get('levels')
        assert row['zone']==expected.get('zone','unknown')
