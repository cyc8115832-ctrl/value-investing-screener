"""五類真實兩表：檢查段落、金額欄、單季EPS及整批來源完整性。"""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
import pytest
from src.data.historical_statements import normalize_statement
from scripts.backfill_verified_statements import prepare_batch

SOURCES=Path(__file__).resolve().parents[1]/'reports/2026-10-09/財報來源'


@pytest.fixture
def tmp_path():
    # 本模組會複製PDF測試hash；暫存留在專案D槽，結束後自動清除。
    with tempfile.TemporaryDirectory(prefix='statement-tests-',dir=SOURCES.parents[2]/'data') as directory:
        yield Path(directory)


def source(ticker='2330',statement='合併綜合損益表'):
    return json.loads((SOURCES/f'MOPS-{ticker}-2025Q2-{statement}.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('ticker,quarter,ytd,parent',[
    ('2330',15.36,29.31,759837230),('2881',0.49,3.49,51383519),
    ('5876',0.65,1.61,7804075),('2207',7.10,14.83,8264307),('3105',-0.99,-0.96,-405338)])
def test_official_eps_and_parent_income_not_comprehensive(ticker,quarter,ytd,parent):
    r=normalize_statement(source(ticker));p=r['payload']
    assert p['standalone_eps']==quarter and p['eps']==ytd and p['net_income']==parent
    assert p['standalone_eps_verified'] and not p['eps_comparable_basis_verified']
    assert r['available_date']=='2026-10-09' and p['original_announcement_date'] is None
    assert p['profit_attribution_residual']==p['standalone']['profit_attribution_residual']==0
    assert p['comparative']['period']=='2024-Q2'
    assert p['currency']=='TWD' and p['unit_scale']==1000 and p['eps_unit_scale']==1


@pytest.mark.parametrize('ticker,assets',[
    ('2330',7006349549),('2881',11902138662),('5876',2363102091),('2207',504687597),('3105',61131507)])
def test_balance_three_periods_identity_no_share_inference(ticker,assets):
    p=normalize_statement(source(ticker,'合併資產負債表'))['payload']
    assert p['total_assets']==assets and p['identity_residual']==0 and p['shares_outstanding'] is None
    assert all(v['identity_residual']==0 for v in p['comparative'])


@pytest.mark.parametrize('change',['period','percent','span','unit','issuer','future','duplicate','missing','attribution'])
def test_bad_evidence_stops_before_import(change):
    s=copy.deepcopy(source())
    if change=='period':s['tables'][0][0][3]='114年01月01日至114年03月31日'
    if change=='percent':s['tables'][0][1][5]='%'
    if change=='span':s['table_spans'][0][0][1]['colspan']=1
    if change=='unit':s['unit']='元'
    if change=='issuer':s['ticker']='2317'
    if change=='future':s['fetched_at']='2099-01-01T00:00:00Z'
    if change in ('duplicate','missing'):
        index=next(i for i,r in enumerate(s['tables'][0]) if r[0].strip()=='基本每股盈餘' and r[5])
        if change=='missing':s['tables'][0][index][5]='--'
        else:
            s['tables'][0].append(s['tables'][0][index][:]);s['table_spans'][0].append(s['table_spans'][0][index][:])
    if change=='attribution':next(r for r in s['tables'][0] if r[0].strip()=='母公司業主（淨利∕損）')[5]='1'
    with pytest.raises(ValueError):normalize_statement(s)
    if change=='span':
        s=source();s['table_spans'][0][0][1]['rowspan']=2
        with pytest.raises(ValueError,match='跨度'):normalize_statement(s)


def test_balance_bad_comparative_identity_is_not_silently_ignored():
    s=source(statement='合併資產負債表')
    next(r for r in s['tables'][0] if r[0].strip()=='資產總額')[5]='1'
    with pytest.raises(ValueError,match='等式'):normalize_statement(s)


def test_direct_quarter_eps_does_not_subtract_weighted_ytd():
    from datetime import date
    from src.engines.verified_earnings import normalize_cumulative_income,realized_eps_summary
    r=normalize_statement(source('2881'));p=r['payload']
    row={**p,'available_date':r['available_date'],'source_url':r['source_url']}
    assert normalize_cumulative_income([row],date(2026,10,8))==[]
    assert normalize_cumulative_income([row],date(2026,10,9))[0]['eps']==0.49
    assert not realized_eps_summary([row],date(2026,10,9))['available']


def test_expanded_year_and_stock_are_real_reports_not_comparative_imports():
    records,_=prepare_batch(SOURCES/'歷史三表批次清單.json')
    assert len(records)==16
    old=next(r for r in records if (r['dataset'],r['ticker'],r['period'])==('income_ytd','2330','2024-Q2'))
    assert old['payload']['eps']==18.25 and old['payload']['standalone_eps']==9.56
    assert old['payload']['comparative']['period']=='2023-Q2'
    new=next(r for r in records if (r['dataset'],r['ticker'])==('cash_flow_ytd','2317'))
    assert new['payload']['operating_cash_flow']==21875585 and new['payload']['closing_cash']==870519926
    assert all(r['available_date']=='2026-10-09' for r in records)


def test_existing_book_capture_cannot_destroy_old_observation(tmp_path,monkeypatch):
    from scripts.capture_statement_books import capture_book
    old=tmp_path/'電子書版本-2330-2025-Q2.json';old.write_bytes(b'original')
    monkeypatch.setattr('scripts.capture_statement_books.requests.get',lambda *a,**k:pytest.fail('不可重新上網覆寫已保存來源'))
    with pytest.raises(ValueError,match='新目錄'):capture_book('2330','2025-Q2',tmp_path)
    assert old.read_bytes()==b'original'


def test_manifest_all_reports_and_source_books_hashes():
    records,_=prepare_batch(SOURCES/'歷史兩表批次清單.json')
    assert len(records)==10 and len({(r['dataset'],r['ticker'],r['period']) for r in records})==10
    assert all(r['available_date']=='2026-10-09' and not r['payload']['statement_book']['original_version_verified'] for r in records)


@pytest.mark.parametrize('change',['missing','duplicate','tamper','escape','book'])
def test_batch_rejects_incomplete_or_tampered_input(tmp_path,change):
    original=json.loads((SOURCES/'歷史兩表批次清單.json').read_text(encoding='utf-8'))
    item=copy.deepcopy(original['files'][0]);manifest={'expected':[original['expected'][0]],'files':[item]}
    for entry in [item,*item['book'].values()]:
        (tmp_path/entry['path']).write_bytes((SOURCES/entry['path']).read_bytes())
    if change=='missing':manifest['files']=[]
    if change=='duplicate':manifest['files']=[item,item]
    if change=='tamper':(tmp_path/item['path']).write_bytes(b'{}')
    if change=='escape':item['path']='../outside.json'
    if change=='book':(tmp_path/item['book']['pdf']['path']).write_bytes(b'%PDF-tampered')
    path=tmp_path/'manifest.json';path.write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError):prepare_batch(path)
