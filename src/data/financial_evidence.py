"""官方最新財報證據：區分報表類型、累計口徑與出表日，不推測歷史公告日。"""
import math
import re
from datetime import date, datetime, timedelta, timezone
from src.data.verified_importer import roc_date


FINANCIAL_SOURCES = {}
for market, base, prefix, groups in (
    ('上市', 'https://openapi.twse.com.tw/v1/opendata/', 't187ap', ('ci', 'fh', 'basi', 'mim')),
    ('上櫃', 'https://www.tpex.org.tw/openapi/v1/', 'mopsfin_t187ap', ('ci',)),
):
    for table, dataset in (('06', 'income_ytd'), ('07', 'balance_sheet')):
        for group in groups:
            suffix = 'L' if market == '上市' else 'O'
            FINANCIAL_SOURCES[f'{base}{prefix}{table}_{suffix}_{group}'] = (dataset, market, group)


def field_value(raw, *names):
    found = [raw[n] for n in names if n in raw]
    if not found:
        return None
    if any(str(v).strip() != str(found[0]).strip() for v in found[1:]):
        raise ValueError('來源別名欄位衝突：' + '/'.join(names))
    return found[0]


def amount(raw, *names):
    value = field_value(raw, *names)
    if value is None or str(value).strip() in ('', '-', '--', 'N/A'):
        return None
    number = float(str(value).replace(',', ''))
    if not math.isfinite(number):
        raise ValueError('財報數字必須為有限值：' + '/'.join(names))
    return number


def normalize_financial(source_url, raw, fetched_at):
    if source_url not in FINANCIAL_SOURCES:
        raise ValueError('財報來源不在官方明確清單')
    dataset, market, group = FINANCIAL_SOURCES[source_url]
    ticker = str(field_value(raw, '公司代號', 'SecuritiesCompanyCode') or '').strip()
    if not re.fullmatch(r'\d{4}', ticker):
        raise ValueError('缺有效四位股票代號')
    year = int(field_value(raw, '年度', 'Year'))
    year = year + 1911 if year < 1911 else year
    quarter = int(field_value(raw, '季別', 'Season'))
    if quarter not in (1, 2, 3, 4):
        raise ValueError('季別不在1至4')
    observed = datetime.fromisoformat(fetched_at)
    if observed.tzinfo is None:
        raise ValueError('擷取時間必須含時區')
    if observed > datetime.now(timezone.utc):
        raise ValueError('擷取時間不得在未來，拒絕錯誤可得時點')
    captured_day = observed.astimezone(timezone(timedelta(hours=8))).date()
    published = roc_date(field_value(raw, '出表日期', 'Date'))
    last_day = date(year + 1, 1, 1) - timedelta(days=1) if quarter == 4 else date(year, quarter * 3 + 1, 1) - timedelta(days=1)
    if not last_day <= published <= captured_day:
        raise ValueError('季度、出表日與擷取日順序不符')
    payload = {'period': f'{year}-Q{quarter}', 'market': market, 'statement_group': group,
               'availability_basis': '官方出表日期（保守可得日；不是個別公司原公告日）',
               'unit': '金額依來源原值，未跨表換算／EPS欄位元', 'raw': raw}
    if dataset == 'income_ytd':
        payload.update(eps=amount(raw, '基本每股盈餘（元）'),
                       revenue=amount(raw, '營業收入') if group == 'ci' else None,
                       operating_income=amount(raw, '營業利益（損失）') if group == 'ci' else None,
                       net_income=amount(raw, '淨利（淨損）歸屬於母公司業主', '淨利（損）歸屬於母公司業主'),
                       net_revenue=amount(raw, '淨收益') if group == 'fh' else None,
                       net_interest_income=amount(raw, '利息淨收益') if group in ('fh', 'basi') else None,
                       other_industry_income=amount(raw, '收入') if group == 'mim' else None,
                       basis='年初至當季累計，未單季化', eps_basis='累計基本EPS，分母為期間加權平均股數',
                       standalone_eps=None, eps_comparable_basis_verified=False)
    else:
        payload.update(total_assets=amount(raw, '資產總計', '資產總額'),
                       total_liabilities=amount(raw, '負債總計', '負債總額'),
                       total_equity=amount(raw, '權益總計', '權益總額'),
                       parent_equity=amount(raw, '歸屬於母公司業主之權益合計', '歸屬於母公司業主之權益'),
                       capital_amount=amount(raw, '股本'), current_assets=amount(raw, '流動資產'),
                       current_liabilities=amount(raw, '流動負債'), book_value_per_share=amount(raw, '每股參考淨值'),
                       basis='季末時點存量，不能用累計差額單季化', shares_outstanding=None)
        assets, liabilities, equity = (payload[k] for k in ('total_assets', 'total_liabilities', 'total_equity'))
        if any(v is None for v in (assets, liabilities, equity)):
            raise ValueError('缺資產／負債／權益總額，拒絕匯入不完整財報')
        if abs(assets - liabilities - equity) > 1:
            raise ValueError('資產不等於負債加權益（容許來源末位捨入1）')
        payload['identity_residual'] = assets - liabilities - equity
    return dataset, ticker, payload['period'], payload, published
