"""MOPS歷史合併兩表：依期間及欄位跨度辨識金額，母公司淨利依段落識別。"""
import calendar
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from src.data.historical_cash_flow import SOURCE_URL, parse_amount


def identity(source):
    ticker, period = source['ticker'], source['period']
    if source['source_url'] != SOURCE_URL or not re.fullmatch(r'\d{4}', ticker) or not re.fullmatch(r'20\d{2}-Q[1-4]', period):
        raise ValueError('未核對的來源、公司或季度')
    if source['statement_group'] not in ('ci','fh','basi','mim'):
        raise ValueError('報表產業型態未核對')
    statement = source['statement']
    if statement not in ('合併綜合損益表','合併資產負債表'): raise ValueError('報表類別未核對')
    year, quarter = int(period[:4]),int(period[-1])
    end = date(year,quarter*3,calendar.monthrange(year,quarter*3)[1])
    observed = datetime.fromisoformat(source['fetched_at'].replace('Z','+00:00'))
    if observed.tzinfo is None or observed > datetime.now(timezone.utc): raise ValueError('擷取時間缺時區或晚於現在')
    observed_day = observed.astimezone(timezone(timedelta(hours=8))).date()
    headings = source['headings']
    if end > observed_day or any(x not in headings for x in (statement,f'民國{year-1911}年第{quarter}季',
                            '單位：新台幣仟元','本公司採 月制會計年度(空白表曆年制)')):
        raise ValueError('表頭、期間、曆年制或單位未匹配')
    if source['unit']!='新台幣仟元': raise ValueError('金額單位未匹配')
    links=[]
    for link in source['links']:
        url=urlparse(link['url']); q=parse_qs(url.query)
        if url.scheme=='https' and url.hostname=='mopsov.twse.com.tw' and url.path=='/server-java/t164sb01':
            if all(q.get(k)==[v] for k,v in {'CO_ID':ticker,'SYEAR':str(year),'SSEASON':str(quarter),'REPORT_ID':'C'}.items()):links.append(link['url'])
    if len(links)!=1: raise ValueError('XBRL公司／季度／合併類別未匹配')
    return ticker,period,year,quarter,end,observed,observed_day,links[0]


def columns(source, labels):
    tables, spans=source['tables'],source['table_spans']
    if len(tables)!=1 or len(spans)!=1: raise ValueError('只支援已核對的單一兩層表格')
    t=tables[0]; s=spans[0]
    if len(t)<3 or t[0]!=['會計項目',*labels] or t[1]!=['',*(['金額','%']*len(labels))]:
        raise ValueError('期間或金額／百分比子欄未匹配')
    if len(s)!=len(t) or any(len(a)!=len(b) for a,b in zip(s,t)):
        raise ValueError('表格跨度證據缺失')
    if ([c['colspan'] for c in s[0]]!=[1,*([2]*len(labels))]
        or any(c['rowspan']!=1 for c in s[0])
        or any(c['colspan']!=1 or c['rowspan']!=1 for row in s[1:] for c in row)):
        raise ValueError('未知的欄位跨度，停止而不猜欄')
    if any(len(r)!=len(t[1]) for r in t[2:]): raise ValueError('資料列欄位數不一致')
    return t, [1+2*i for i in range(len(labels))]


def amount_row(table, names, index, required=False):
    # 重複的空白分類標題不是金額列；同名且有數字的兩列不可任選。
    rows=[r for r in table[2:] if r[0].strip() in names and any(v.strip() for v in r[1:])]
    if len(rows)>1: raise ValueError('重複金額科目：'+str(names))
    value=parse_amount(rows[0][index]) if rows else None
    if required and value is None: raise ValueError('缺少必要金額科目：'+str(names))
    return value


def profit_attribution(table,index):
    section=None; parents=[]; minorities=[]
    for r in table[2:]:
        label=r[0].strip()
        if '歸屬' in label and all(not x.strip() for x in r[1:]):
            section='profit' if '淨利' in label and '綜合' not in label else 'other'
        if '綜合' in label:
            section='other'
        if section=='profit' and label.startswith('母公司業主'):
            parents.append(parse_amount(r[index]))
        if section=='profit' and label.startswith(('非控制權益','非控制股權')):
            minorities.append(parse_amount(r[index]))
    if len(parents)!=1 or parents[0] is None or len(minorities)!=1 or minorities[0] is None:
        raise ValueError('母公司／非控制淨利歸屬段落未匹配')
    total=amount_row(table,('本期淨利（淨損）','本期稅後淨利（淨損）'),index,True)
    residual=parents[0]+minorities[0]-total
    if abs(residual)>1: raise ValueError('淨利歸屬勾稽失敗')
    return parents[0], total, residual


def income_values(table,index,group):
    parent,total,residual=profit_attribution(table,index)
    return {'eps':amount_row(table,('基本每股盈餘',),index,True), 'net_income':parent,
            'total_net_income':total,'profit_attribution_residual':residual,
            'revenue':amount_row(table,('營業收入合計',),index,True) if group=='ci' else None,
            'operating_income':amount_row(table,('營業利益（損失）',),index) if group=='ci' else None,
            'net_revenue':amount_row(table,('淨收益',),index,True) if group in ('fh','basi') else None,
            'net_interest_income':amount_row(table,('利息淨收益',),index,True) if group in ('fh','basi') else None,
            'other_industry_income':amount_row(table,('收入合計',),index,True) if group=='mim' else None}


def balance_values(table,index):
    p={'total_assets':amount_row(table,('資產總計','資產總額'),index,True),
       'total_liabilities':amount_row(table,('負債總計','負債總額'),index,True),
       'total_equity':amount_row(table,('權益總計','權益總額'),index,True),
       'parent_equity':amount_row(table,('歸屬於母公司業主之權益合計','歸屬於母公司業主之權益'),index),
       'capital_amount':amount_row(table,('股本合計','股本'),index),
       'current_assets':amount_row(table,('流動資產合計','流動資產總額'),index),
       'current_liabilities':amount_row(table,('流動負債合計','流動負債總額'),index),
       'shares_outstanding':None}
    p['identity_residual']=p['total_assets']-p['total_liabilities']-p['total_equity']
    if abs(p['identity_residual'])>1: raise ValueError('資產負債等式失敗')
    return p


def normalize_statement(source):
    ticker,period,year,q,end,observed,day,url=identity(source)
    roc=year-1911; previous=roc-1
    p={'period':period,'statement':source['statement'],'statement_group':source['statement_group'],
       'currency':'TWD','unit':'新台幣仟元','unit_scale':1000,'eps_unit':'元','eps_unit_scale':1,
       'original_announcement_date':None,'announcement_version_verified':False,
       'availability_basis':'擷取台灣日期，未核實最早申報及歷次更正鏈',
       'raw_tables':source['tables'],'raw_table_spans':source['table_spans'],
       'source_headings':source['headings'],'source_links':source['links']}
    if source['statement']=='合併綜合損益表':
        if q==1:
            labels=[f'{roc}年01月01日至{roc}年{end.month:02}月{end.day:02}日',
                    f'{previous}年01月01日至{previous}年{end.month:02}月{end.day:02}日']
            table,indices=columns(source,labels)
            values=[income_values(table,i,source['statement_group']) for i in indices]
            p.update(values[0]);p.update({'basis':'年初累計，第一季即單季',
                    'standalone':{'period':period,'basis':'第一季累計即單季',**values[0]},
                    'standalone_eps':values[0]['eps'],'standalone_eps_verified':True,
                    'standalone_eps_source_url':url,'standalone_eps_available_date':day.isoformat(),
                    'eps_comparable_basis_verified':False,'amount_comparable_basis_verified':False,
                    'comparative':{'period':f'{year-1}-Q1','basis':'本報告比較欄，非前期原始申報',
                                   'standalone':values[1],'ytd':values[1]}})
        elif q in (2, 3):
            labels=[f'{roc}年第{q}季',f'{previous}年第{q}季',
                    f'{roc}年01月01日至{roc}年{end.month:02}月{end.day:02}日',
                    f'{previous}年01月01日至{previous}年{end.month:02}月{end.day:02}日']
            table,indices=columns(source,labels)
            values=[income_values(table,i,source['statement_group']) for i in indices]
            p.update(values[2]);p.update({'basis':'年初累計，官方另列單季',
                    'standalone':{'period':period,'basis':'官方本期單季欄',**values[0]},
                    'standalone_eps':values[0]['eps'],'standalone_eps_verified':True,
                    'standalone_eps_source_url':url,'standalone_eps_available_date':day.isoformat(),
                    'eps_comparable_basis_verified':False,'amount_comparable_basis_verified':False,
                    'comparative':{'period':f'{year-1}-Q{q}','basis':'本報告比較欄，非前期原始申報',
                                   'standalone':values[1],'ytd':values[3]}})
        elif q==4:
            labels=[f'{roc}年度',f'{previous}年度']
            table,indices=columns(source,labels)
            values=[income_values(table,i,source['statement_group']) for i in indices]
            p.update(values[0]);p.update({'basis':'全年度累計，無官方直接單季欄',
                    'standalone':{'period':period,'basis':'無官方直接單季欄，維持未知','eps':None,'net_income':None},
                    'standalone_eps':None,'standalone_eps_verified':False,
                    'standalone_eps_source_url':None,'standalone_eps_available_date':None,
                    'eps_comparable_basis_verified':False,'amount_comparable_basis_verified':False,
                    'comparative':{'period':f'{year-1}-Q4','basis':'本報告比較欄，非前期原始申報',
                                   'standalone':None,'ytd':values[1]}})
        else:
            raise ValueError('季度超出範圍')
        dataset='income_ytd'
    else:
        labels=[f'{roc}年{end.month:02}月{end.day:02}日',f'{previous}年12月31日',f'{previous}年{end.month:02}月{end.day:02}日']
        table,indices=columns(source,labels);values=[balance_values(table,i) for i in indices]
        p.update(values[0]);p.update({'basis':'季末存量，不拆季',
                'comparative':[{'period':f'{year-1}-12-31',**values[1]}, {'period':f'{year-1}-{end.month:02}-{end.day:02}',**values[2]}]})
        dataset='balance_sheet'
    return {'dataset':dataset,'ticker':ticker,'period':period,'payload':p,'source_url':url,
            'available_date':day.isoformat(),'observed_at':observed.isoformat()}
