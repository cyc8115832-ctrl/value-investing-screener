"""官方財報類型、報表口徑、整批停止與可得日防護。"""
import pytest
from datetime import datetime, timedelta, timezone
from src.data.financial_evidence import FINANCIAL_SOURCES, normalize_financial
from scripts.refresh_verified_financials import prepare_sources


OBSERVED = '2026-10-08T01:00:00+00:00'


def source(dataset, market='上市', group='ci'):
    return next(url for url, spec in FINANCIAL_SOURCES.items() if spec == (dataset, market, group))


def raw(market='上市'):
    identity = {'公司代號': '2330', '年度': '115', '季別': '2', '出表日期': '1151008'}
    if market == '上櫃':
        identity = {'SecuritiesCompanyCode': '2330', 'Year': '115', 'Season': '2', 'Date': '1151007'}
    return {**identity, '基本每股盈餘（元）': '5.2', '營業收入': '1,000',
            '營業利益（損失）': '100', '淨利（淨損）歸屬於母公司業主': '90',
            '淨收益': '300', '利息淨收益': '150', '收入': '700',
            '資產總計': '1,000', '負債總計': '600', '權益總計': '400', '股本': '200'}


@pytest.mark.parametrize('market,group', [('上市','ci'), ('上市','fh'), ('上市','basi'), ('上市','mim'), ('上櫃','ci')])
def test_income_types_keep_distinct_amounts_and_no_assumed_eps_basis(market, group):
    _, ticker, period, payload, published = normalize_financial(source('income_ytd', market, group), raw(market), OBSERVED)
    assert ticker == '2330' and period == '2026-Q2'
    assert payload['eps'] == 5.2
    assert payload['revenue'] == (1000 if group == 'ci' else None)
    assert payload['net_revenue'] == (300 if group == 'fh' else None)
    assert payload['net_interest_income'] == (150 if group in ('fh','basi') else None)
    assert payload['other_industry_income'] == (700 if group == 'mim' else None)
    assert not payload['eps_comparable_basis_verified'] and payload['standalone_eps'] is None
    assert published.isoformat() == ('2026-10-08' if market == '上市' else '2026-10-07')


def test_balance_identity_and_capital_never_implies_shares():
    row = raw()
    payload = normalize_financial(source('balance_sheet'), row, OBSERVED)[3]
    assert payload['identity_residual'] == 0 and payload['shares_outstanding'] is None
    row['權益總計'] = '390'
    with pytest.raises(ValueError, match='資產不等於'):
        normalize_financial(source('balance_sheet'), row, OBSERVED)


def test_future_observation_cannot_create_verified_current_coverage():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match='擷取時間不得在未來'):
        normalize_financial(source('income_ytd'), raw(), future)


@pytest.mark.parametrize('mutation', [{'Date':'1151007'}, {'出表日期':'1151009'}, {'年度':'116'}, {'基本每股盈餘（元）':'NaN'}])
def test_conflicts_future_periods_and_invalid_numbers_stop(mutation):
    with pytest.raises(ValueError):
        normalize_financial(source('income_ytd'), {**raw(), **mutation}, OBSERVED)


def test_duplicate_sources_or_mixed_quarters_are_not_silently_overwritten():
    snapshot = {'url':source('income_ytd'), 'fetched_at':OBSERVED, 'data':[raw()]}
    with pytest.raises(ValueError, match='重複季度'):
        prepare_sources([snapshot, snapshot], {'2330'})
    other = {'url':source('balance_sheet'), 'fetched_at':OBSERVED, 'data':[{**raw(), '季別':'1'}]}
    with pytest.raises(ValueError, match='季度不一致'):
        prepare_sources([snapshot, other], {'2330'})
