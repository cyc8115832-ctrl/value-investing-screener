"""真實五類表格與批次破壞測試：期間、現金定義、來源與時間不得猜測。"""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from src.data.historical_cash_flow import normalize_cash_flow, parse_amount
from scripts.backfill_verified_cash_flow import prepare_batch

SOURCES = Path(__file__).resolve().parents[1] / 'reports/2026-10-08/財報來源'


def source(ticker='2330'):
    return json.loads((SOURCES / f'MOPS-{ticker}-2025Q2-現金流來源.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('ticker', ['2330','2881','5876','2207','3105'])
def test_real_five_groups_keep_current_and_comparative_separate(ticker):
    r = normalize_cash_flow(source(ticker))
    p = r['payload']
    assert r['available_date'] == '2026-10-08'
    assert p['fiscal_start'] == '2025-01-01' and p['fiscal_end'] == '2025-06-30'
    assert p['currency'] == 'TWD' and p['unit_scale'] == 1000
    assert p['original_announcement_date'] is None and not p['announcement_version_verified']
    assert p['comparative']['period'] == '2024-Q2' and p['free_cash_flow'] is None
    assert p['flow_identity_residual'] == p['cash_identity_residual'] == 0
    assert p['comparative']['flow_identity_residual'] == p['comparative']['cash_identity_residual'] == 0


def test_independent_tsmc_values_and_bank_cash_definition():
    p = normalize_cash_flow(source())['payload']
    assert p['operating_cash_flow'] == 1122637757 and p['ppe_acquisition'] == -628052531
    assert p['closing_cash'] == 2364524340
    bank = normalize_cash_flow(source('2881'))['payload']
    assert bank['closing_cash'] == 626124360
    # 金控表內現金範圍包含同業等項目，不能強制等同BS現金科目。
    assert any(r[0].strip() == '資產負債表帳列之現金及約當現金' and r[1] == '413,560,838' for r in bank['raw_tables'][0])


@pytest.mark.parametrize('mutation', ['period','unit','issuer','missing','identity','duplicate','future','comparative'])
def test_reject_bad_evidence_before_import(mutation):
    s = copy.deepcopy(source())
    if mutation == 'period': s['tables'][0][0][1] = '114年04月01日至114年06月30日'
    if mutation == 'unit': s['headings'].remove('單位：新台幣仟元')
    if mutation == 'issuer': s['links'][0]['url'] = s['links'][0]['url'].replace('CO_ID=2330','CO_ID=2317')
    if mutation in ('missing','identity','comparative'):
        row = next(r for r in s['tables'][0] if r[0].strip() == '期末現金及約當現金餘額')
        row[2 if mutation == 'comparative' else 1] = '' if mutation == 'missing' else '1'
    if mutation == 'duplicate':
        s['tables'][0].append(next(r for r in s['tables'][0] if r[0].strip() == '期末現金及約當現金餘額'))
    if mutation == 'future': s['fetched_at'] = '2099-01-01T00:00:00Z'
    with pytest.raises(ValueError): normalize_cash_flow(s)


def test_unknown_is_not_zero_and_nonfinite_rejected():
    assert parse_amount('--') is None and parse_amount('(1,234)') == -1234
    with pytest.raises(ValueError): parse_amount('NaN')


def test_batch_tamper_duplicate_and_missing_are_atomic_preparation(tmp_path):
    raw = json.dumps(source(),ensure_ascii=False).encode()
    (tmp_path/'source.json').write_bytes(raw)
    item = {'path':'source.json','sha256':hashlib.sha256(raw).hexdigest()}
    manifest = {'expected':[['2330','2025-Q2']], 'files':[item]}
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest),encoding='utf-8')
    assert len(prepare_batch(path)[0]) == 1
    (tmp_path/'source.json').write_bytes(raw+b' ')
    with pytest.raises(ValueError,match='hash'): prepare_batch(path)
    (tmp_path/'source.json').write_bytes(raw)
    manifest['files'] = [item,item]
    path.write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='重複'): prepare_batch(path)
    manifest['files'] = []
    path.write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ValueError,match='缺少'): prepare_batch(path)


def test_cash_flow_observed_today_does_not_backdate_or_import_comparative():
    from datetime import date, datetime
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.database.schema import Base, MarketEvidence
    from src.services.market_evidence import save_evidence, evidence_rows
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    r = normalize_cash_flow(source())
    with Session(engine) as db:
        save_evidence(db, r['dataset'], r['ticker'], r['period'], r['payload'], r['source_url'],
                      date.fromisoformat(r['available_date']),
                      datetime.fromisoformat(r['observed_at']).replace(tzinfo=None))
        db.commit()
        assert evidence_rows(db, 'cash_flow_ytd', '2330', date(2026,10,7)) == []
        rows = evidence_rows(db, 'cash_flow_ytd', '2330', date(2026,10,8))
        assert len(rows) == 1 and rows[0]['knowledge_date'] == '2026-10-08'
        assert db.query(MarketEvidence).count() == 1
    engine.dispose()
