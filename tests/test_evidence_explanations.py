"""缺項說明依公司已核實期別產生，不把已取得資料重列為缺件。"""
from src.services.evidence_explanations import explain_stock_evidence, recent_periods


def row(period):
    return {'period': period, 'available_date': '2026-10-09', 'source_url': 'https://example.test/source'}


def details(periods, balances=None, cashflows=None, ready=False):
    realized = {'available': ready, 'reason': '缺同分母證據',
                'quarters': [{'period': p, 'available': ready} for p in periods]}
    return explain_stock_evidence([row('2026-10-07')], [row('2026-09')], [row(p) for p in periods],
                                  balances or [], cashflows or [], realized,
                                  {'available': False, 'reason': 'PS 缺同日倍數'})


def test_periods_cross_year_and_do_not_target_future():
    assert recent_periods([row('2026-Q2')]) == ['2025-Q3', '2025-Q4', '2026-Q1', '2026-Q2']
    assert recent_periods([]) == []


def test_latest_balance_is_available_and_not_marked_as_missing():
    report = details(['2026-Q2'], balances=[row('2026-Q2')])['company']
    gap = next(g for g in report['missing_items'] if g['label'] == '歷年資產負債表')
    assert gap['periods'] == ['2025-Q3', '2025-Q4', '2026-Q1']
    assert any(d['label'] == '資產負債表' and d['period'] == '2026-Q2' for d in report['available_data'])
    assert not any('ETF' in g['label'] or '行情' in g['label'] for g in report['missing_items'])


def test_existing_cashflow_keeps_coverage_without_claiming_four_quarters():
    report = details(['2026-Q2'], cashflows=[row('2025-Q4'), row('2026-Q2')])['company']
    gap = next(g for g in report['missing_items'] if g['label'] == '累計現金流報表')
    assert gap['periods'] == ['2025-Q3', '2026-Q1']
    assert next(d for d in report['available_data'] if d['label'] == '累計現金流')['period_count'] == 2


def test_complete_eps_is_not_repeated_as_a_gap_but_company_remains_unknown():
    periods = ['2025-Q3', '2025-Q4', '2026-Q1', '2026-Q2']
    report = details(periods, [row(p) for p in periods], [row(p) for p in periods], True)['company']
    assert not any(g['label'] in ('連續四季單季 EPS', '歷年資產負債表', '累計現金流報表') for g in report['missing_items'])
    assert report['status'] == 'insufficient'
    assert any(g['status'] == '功能未實作' for g in report['missing_items'])


def test_metric_failure_explains_actual_selected_metric():
    report = details(['2026-Q2'])['valuation']
    assert report['reason'] == 'PS 缺同日倍數'
    assert report['missing_items'][0]['reason'] == report['reason']


def test_empty_financials_never_invents_missing_report_periods():
    report = details([])['company']
    assert report['target_periods'] == []
    assert all(not g['periods'] for g in report['missing_items'])
