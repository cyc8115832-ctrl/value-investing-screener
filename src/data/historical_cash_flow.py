"""已核對的MOPS合併現金流契約；比較期留在本次版本，不倒填公告日。"""
import calendar
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

SOURCE_URL = 'https://mops.twse.com.tw/mops/#/web/t164sb00'
FIELDS = {
    'operating_cash_flow': ('營業活動之淨現金流入（流出）',),
    'investing_cash_flow': ('投資活動之淨現金流入（流出）',),
    'financing_cash_flow': ('籌資活動之淨現金流入（流出）',),
    'fx_effect': ('匯率變動對現金及約當現金之影響',),
    'cash_change': ('本期現金及約當現金增加（減少）數',),
    'opening_cash': ('期初現金及約當現金餘額',),
    'closing_cash': ('期末現金及約當現金餘額',),
    'ppe_acquisition': ('取得不動產、廠房及設備', '取得不動產及設備'),
    'intangible_acquisition': ('取得無形資產',),
}
REQUIRED = tuple(FIELDS)[:7]


def parse_amount(value):
    """只收明確數字；空白不是零，括號表示負值。"""
    value = value.strip().replace(',', '')
    if value in ('', '-', '--'):
        return None
    if re.fullmatch(r'\(\d+(?:\.\d+)?\)', value):
        value = '-' + value[1:-1]
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('現金流金額無法辨識') from exc
    if not number.is_finite():
        raise ValueError('現金流金額非有限值')
    return int(number) if number == number.to_integral_value() else float(number)


def column_values(table, index):
    values = {}
    for key, labels in FIELDS.items():
        matches = [r for r in table[1:] if r and r[0].strip() in labels]
        if len(matches) > 1:
            raise ValueError('重複現金流科目：' + key)
        if matches and len(matches[0]) <= index:
            raise ValueError('現金流欄位不足')
        values[key] = parse_amount(matches[0][index]) if matches else None
    if any(values[k] is None for k in REQUIRED):
        raise ValueError('缺少現金勾稽科目，不補零')
    flow_residual = sum(Decimal(str(values[k])) for k in REQUIRED[:4]) - Decimal(str(values['cash_change']))
    cash_residual = Decimal(str(values['opening_cash'])) + Decimal(str(values['cash_change'])) - Decimal(str(values['closing_cash']))
    if abs(flow_residual) > 1 or abs(cash_residual) > 1:
        raise ValueError('現金勾稽失敗')
    return {**values, 'flow_identity_residual': float(flow_residual), 'cash_identity_residual': float(cash_residual)}


def normalize_cash_flow(source):
    if source['source_url'] != SOURCE_URL:
        raise ValueError('非已核對的MOPS來源入口')
    ticker, period = source['ticker'], source['period']
    if not re.fullmatch(r'\d{4}', ticker) or not re.fullmatch(r'20\d{2}-Q[1-4]', period):
        raise ValueError('股票或季度格式不符')
    if source.get('statement_group') not in ('ci', 'fh', 'basi', 'mim'):
        raise ValueError('尚未驗證的報表產業型態')
    year, quarter = int(period[:4]), int(period[-1])
    observed = datetime.fromisoformat(source['fetched_at'].replace('Z', '+00:00'))
    if observed.tzinfo is None or observed > datetime.now(timezone.utc):
        raise ValueError('擷取時間缺時區或位於未來')
    observed_day = observed.astimezone(timezone(timedelta(hours=8))).date()
    end = date(year, quarter * 3, calendar.monthrange(year, quarter * 3)[1])
    if end > observed_day:
        raise ValueError('財報期間晚於擷取日')
    headings = source['headings']
    required_headings = ['合併現金流量表', f'民國{year-1911}年第{quarter}季', '單位：新台幣仟元',
                         '本公司採 月制會計年度(空白表曆年制)']
    if any(h not in headings for h in required_headings) or source['statement'] != required_headings[0] or source['unit'] != '新台幣仟元':
        raise ValueError('表頭的合併類別、年度或單位未匹配')
    links = []
    for link in source.get('links', []):
        url = urlparse(link['url'])
        if url.scheme == 'https' and url.hostname == 'mopsov.twse.com.tw' and url.path == '/server-java/t164sb01':
            query = parse_qs(url.query)
            if all(query.get(k) == [v] for k,v in {'CO_ID':ticker, 'SYEAR':str(year), 'SSEASON':str(quarter), 'REPORT_ID':'C'}.items()):
                links.append(link['url'])
    if len(links) != 1:
        raise ValueError('XBRL公司、季度或合併報表連結未匹配')
    tables = source['tables']
    if len(tables) != 1 or not tables[0] or len(tables[0][0]) != 3:
        raise ValueError('尚未驗證的現金流表格結構')
    table = tables[0]
    expected = ['會計項目'] + [f'{y-1911}年01月01日至{y-1911}年{end.month:02}月{end.day:02}日' for y in (year,year-1)]
    if table[0] != expected:
        raise ValueError('累計期間欄位未匹配，不能任意取第一金額欄')
    # 比較欄可能重編，只作本報告的比較資料；不發布成前期原始版本。
    current, comparative = column_values(table, 1), column_values(table, 2)
    return {
        'dataset': 'cash_flow_ytd', 'ticker': ticker, 'period': period,
        'source_url': links[0], 'available_date': observed_day.isoformat(), 'observed_at': observed.isoformat(),
        'payload': {**current, 'period':period, 'statement_group':source['statement_group'],
                    'statement':'合併現金流量表', 'currency':'TWD', 'unit_scale':1000, 'unit':'新台幣仟元',
                    'fiscal_start':date(year,1,1).isoformat(), 'fiscal_end':end.isoformat(),
                    'basis':'年初累計，非單季', 'original_announcement_date':None,
                    'availability_basis':'擷取台灣日期，尚未匹配原公告與報表版本',
                    'announcement_version_verified':False, 'free_cash_flow':None,
                    'comparative':{'period':f'{year-1}-Q{quarter}', 'basis':'本報告比較欄，可能重編，非前期原始版本', **comparative},
                    'raw_tables':tables, 'source_headings':headings, 'source_links':source['links']},
    }
