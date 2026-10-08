"""回補官方月查詢行情與各日倍數；明示事後回補，保留原始回應。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import json
import sqlite3
import time
import threading
from urllib.parse import urlparse, parse_qs
from datetime import date,datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from config.settings import BASE_DIR,DATA_DIR,SETTINGS
from src.database.session import SessionLocal
from src.database.schema import StockMaster,PriceDaily,MarketEvidence,MarketEvidenceRevision
from src.services.market_evidence import encode_payload,taiwan_today
from src.data.verified_importer import roc_date,number

PRICE_URL='https://www.twse.com.tw/exchangeReport/STOCK_DAY'
RATIO_URL='https://www.twse.com.tw/exchangeReport/BWIBBU'
TPEX_PRICE_URL='https://www.tpex.org.tw/www/afterTrading/tradingStock'
TPEX_RATIO_URL='https://www.tpex.org.tw/www/afterTrading/peQryStock'


class SourceBlocked(RuntimeError):
    """官方流量防護觸發時終止本輪，不以重試持續衝擊來源。"""


def monthly_rows(payload):
    if payload.get('stat') != 'OK':
        raise ValueError('官方回應沒有可用資料：'+str(payload.get('stat')))
    fields=payload['fields']
    return [dict(zip(fields,row)) for row in payload['data']]


def tpex_rows(result,ticker,month,kind):
    """核對官方月份、請求代碼及行情代碼；只讀第一張日資料表。"""
    payload=result['data']
    expected=TPEX_PRICE_URL if kind=='price' else TPEX_RATIO_URL
    parsed=urlparse(result['url'])
    if parsed.scheme!='https' or parsed.netloc!='www.tpex.org.tw' or parsed.path!=urlparse(expected).path:
        raise ValueError('上櫃來源不在允許清單')
    params=parse_qs(parsed.query)
    if params.get('code')!=[ticker] or params.get('date')!=[f'{month[:4]}/{month[4:6]}/01']:
        raise ValueError('上櫃請求股票／月份不符')
    if str(payload.get('stat','')).lower()!='ok' or str(payload.get('date',''))[:6]!=month[:6]:
        raise ValueError('上櫃回應沒有要求月份的可用資料')
    if kind=='price' and payload.get('code')!=ticker:
        raise ValueError('上櫃行情回應股票代號不符')
    table=payload['tables'][0]
    rows=[dict(zip(table['fields'],row)) for row in table['data']]
    date_field='日 期' if kind=='price' else '日期'
    if any(roc_date(row[date_field]).strftime('%Y%m')!=month[:6] for row in rows):
        raise ValueError('上櫃資料列月份不符')
    return rows


def normalized_tpex_month(ticker,month,price_result,ratio_result):
    price_rows=tpex_rows(price_result,ticker,month,'price')
    volume_fields=price_result['data']['tables'][0]['fields']
    volume_field=next((f for f in ('成交仟股','成交張數') if f in volume_fields),None)
    if volume_field is None:
        raise ValueError('上櫃成交量單位未知，拒絕略過整月資料')
    ratios={roc_date(row['日期']).isoformat():row for row in tpex_rows(ratio_result,ticker,month,'ratio')} if ratio_result else {}
    result=[]
    for raw in price_rows:
        trade_date=roc_date(raw['日 期'])
        close,volume=number(raw.get('收盤')),number(raw.get(volume_field))
        if trade_date>taiwan_today() or close is None or close<=0 or volume is None or volume<0:
            continue
        ratio=ratios.get(trade_date.isoformat(),{})
        pe,pb=number(ratio.get('本益比')),number(ratio.get('股價淨值比'))
        result.append({'period':trade_date.isoformat(),'close':close,'volume':volume*1000,
                       'open':number(raw.get('開盤')),'high':number(raw.get('最高')),'low':number(raw.get('最低')),
                       'pe':pe if pe and pe>0 else None,'pb':pb if pb and pb>0 else None,'ps':None,
                       'source_url':price_result['url'],'ratio_source_url':ratio_result['url'] if ratio else None,
                       'availability_basis':'官方各日歷史行情，事後回補；不是當時已留存的預估',
                       'unit':f'新臺幣元／成交股數（官方{volume_field}乘1000）',
                       'volume_precision':'依官方仟股／張數精度換算，非逐股精度','raw':raw,'raw_ratio':ratio})
    return result


def normalized_month(ticker,month,price_result,ratio_result):
    price_rows=monthly_rows(price_result['data'])
    if ratio_result and (ratio_result['data'].get('date','')[:6] != month[:6] or any(roc_date(row['日期']).strftime('%Y%m') != month[:6] for row in monthly_rows(ratio_result['data']))):
        raise ValueError('官方倍數資料不是要求的月份')
    if ratio_result:
        requested=parse_qs(urlparse(ratio_result['url']).query).get('stockNo')
        if requested is not None and requested!=[ticker]:
            raise ValueError('官方倍數請求股票代號不符')
    ratios={roc_date(row['日期']).isoformat():row for row in monthly_rows(ratio_result['data'])} if ratio_result else {}
    if ticker not in price_result['data'].get('title','') or price_result['data'].get('date','')[:6] != month[:6]:
        raise ValueError('官方資料不是要求的股票／月份')
    result=[]
    for raw in price_rows:
        trade_date=roc_date(raw['日期'])
        if trade_date.strftime('%Y%m') != month[:6]:
            raise ValueError('資料列日期不在要求的月份')
        if trade_date>taiwan_today():
            continue
        ratio=ratios.get(trade_date.isoformat(),{})
        close=number(raw.get('收盤價'))
        volume=number(raw.get('成交股數'))
        if close is None or close<=0 or volume is None or volume<0:
            continue
        pe,pb=number(ratio.get('本益比')),number(ratio.get('股價淨值比'))
        result.append({'period':trade_date.isoformat(),'close':close,'volume':volume,
                       'open':number(raw.get('開盤價')),'high':number(raw.get('最高價')),'low':number(raw.get('最低價')),
                       'pe':pe if pe and pe>0 else None,'pb':pb if pb and pb>0 else None,'ps':None,
                       'source_url':price_result['url'],'ratio_source_url':ratio_result['url'] if ratio and ratio_result else None,
                       'availability_basis':'官方各日歷史行情，事後回補；不是當時已留存的預估',
                       'unit':'新臺幣元／成交股數','raw':raw,'raw_ratio':ratio})
    return result


def save_month(db,ticker,rows,fetched_at,observations=None):
    """按月預載既有證據與版本，保留與逐筆匯入相同的時間與修訂邊界。"""
    if not rows:
        return
    periods=[p['period'] for p in rows]
    evidence={r.period:r for r in db.query(MarketEvidence).filter(
        MarketEvidence.dataset=='price',MarketEvidence.ticker==ticker,MarketEvidence.period.in_(periods)).all()}
    versions=db.query(MarketEvidenceRevision).filter(
        MarketEvidenceRevision.dataset=='price',MarketEvidenceRevision.ticker==ticker,
        MarketEvidenceRevision.period.in_(periods)).order_by(
            MarketEvidenceRevision.observed_at,MarketEvidenceRevision.id).all()
    latest={r.period:r for r in versions}
    prices={r.date:r for r in db.query(PriceDaily).filter(
        PriceDaily.ticker==ticker,PriceDaily.date.in_([date.fromisoformat(p) for p in periods])).all()}
    for payload in rows:
        period=payload['period'];trade_date=date.fromisoformat(period)
        observed=datetime.fromisoformat((observations or {}).get(period,fetched_at)).astimezone(timezone.utc).replace(tzinfo=None)
        encoded=encode_payload(payload);digest=hashlib.sha256(encoded.encode()).hexdigest()
        previous=latest.get(period)
        if previous is None or previous.payload_sha256!=digest or previous.available_date!=trade_date or previous.source_url!=payload['source_url'] or previous.observed_at>observed:
            db.add(MarketEvidenceRevision(dataset='price',ticker=ticker,period=period,
                source_url=payload['source_url'],available_date=trade_date,observed_at=observed,
                payload_json=encoded,payload_sha256=digest,status='verified'))
        record=evidence.get(period)
        if record is not None and record.fetched_at>observed:
            continue
        if record is None:
            record=MarketEvidence(dataset='price',ticker=ticker,period=period);db.add(record)
        record.source_url=payload['source_url'];record.available_date=trade_date;record.fetched_at=observed
        record.payload_json=encoded;record.payload_sha256=digest;record.status='verified'
        row=prices.get(trade_date)
        if row is None:
            row=PriceDaily(ticker=ticker,date=trade_date);db.add(row)
        for field in ('close','volume','pe','pb','ps'):
            setattr(row,field,payload.get(field))


def backfill(tickers,months=48,force_refresh=False,workers=2,interval=2.0):
    if SETTINGS.DEMO_MODE or SETTINGS.DATABASE_URL != f"sqlite:///{DATA_DIR / 'value_investing.db'}":
        raise RuntimeError('回補限定本專案正式 SQLite')
    today=taiwan_today()
    with SessionLocal() as db:
        pool={s.ticker for s in db.query(StockMaster).all()}
        markets={r.ticker:('tpex' if 'tpex.org.tw' in r.source_url else 'twse')
                 for r in db.query(MarketEvidence).filter_by(dataset='price',status='verified').all()}
    if tickers==['all']:
        tickers=sorted(pool)
    tickers=list(dict.fromkeys(tickers))
    if any(t not in pool or t not in markets for t in tickers):
        raise ValueError('股票不在股池或缺已核實市場來源')
    if not 1<=workers<=4:
        raise ValueError('同時連線限1–4，避免過量查詢官方網站')
    if interval<0.5:
        raise ValueError('全程序請求間隔至少0.5秒')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    backup=DATA_DIR/f'歷史回補前-{stamp}.db'
    with sqlite3.connect(DATA_DIR/'value_investing.db') as source,sqlite3.connect(backup) as destination:
        source.backup(destination)
    folder=BASE_DIR/'reports'/today.isoformat()/'官方歷史快照'
    folder.mkdir(parents=True,exist_ok=True)
    jobs=[]
    job_results=[]
    blocked=threading.Event()
    pace_lock=threading.Lock()
    last_request=[0.0]
    for ticker in tickers:
        for offset in range(months,-1,-1):
            ordinal=today.year*12+today.month-1-offset
            year,zero_month=divmod(ordinal,12)
            jobs.append((ticker,f'{year}{zero_month+1:02d}01'))
    def fetch_job(job):
        if blocked.is_set():
            raise SourceBlocked('官方防護已觸發，本輪停止查詢')
        ticker,month=job
        results={}
        errors=[]
        market=markets[ticker]
        urls=[('price',TPEX_PRICE_URL),('ratio',TPEX_RATIO_URL)] if market=='tpex' else [('price',PRICE_URL),('ratio',RATIO_URL)]
        for name,url in urls:
            cache=folder/f'{ticker}-{month[:6]}-{name}.json'
            try:
                # 當月仍會新增交易日，不能永久沿用第一次月快照。
                prior=sorted((BASE_DIR/'reports').glob(f'*/官方歷史快照/{ticker}-{month[:6]}-{name}.json'))
                reusable=cache if cache.exists() else (prior[-1] if prior else None)
                if reusable and month[:6] < today.strftime('%Y%m') and not force_refresh:
                    result=json.loads(reusable.read_text(encoding='utf-8'))
                else:
                    params={'response':'json','date':f'{month[:4]}/{month[4:6]}/01','code':ticker} if market=='tpex' else {'response':'json','date':month,'stockNo':ticker}
                    for attempt in range(3):
                        try:
                            with pace_lock:
                                if blocked.is_set():
                                    raise SourceBlocked('官方防護已觸發，本輪停止查詢')
                                time.sleep(max(0,interval-(time.monotonic()-last_request[0])))
                                last_request[0]=time.monotonic()
                            response=requests.get(url,params=params,timeout=15)
                            if response.status_code in (403,428,429):
                                blocked.set()
                                raise SourceBlocked(f'{market} 官方HTTP {response.status_code}，停止本輪：{response.url}')
                            response.raise_for_status()
                            result={'url':response.url,'fetched_at':datetime.now(timezone.utc).isoformat(),'data':response.json()}
                            if market=='tpex':
                                tpex_rows(result,ticker,month,name)
                            else:
                                monthly_rows(result['data'])
                            break
                        except (requests.RequestException,ValueError):
                            if attempt==2:
                                raise
                            time.sleep(2*(attempt+1))
                    if month[:6] == today.strftime('%Y%m') or force_refresh:
                        versions=folder/'更新版本'
                        versions.mkdir(exist_ok=True)
                        if cache.exists():
                            previous_bytes=cache.read_bytes()
                            previous_hash=hashlib.sha256(previous_bytes).hexdigest()[:16]
                            (versions/f'{ticker}-{month[:6]}-既有-{previous_hash}-{name}.json').write_bytes(previous_bytes)
                        (versions/f'{ticker}-{month[:6]}-{stamp}-{name}.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                    cache.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                    time.sleep(.4)
                results[name]=result
            except Exception as error:
                if isinstance(error,SourceBlocked):
                    raise
                errors.append(f'{ticker} {month} {name}: {error}')
        try:
            normalize=normalized_tpex_month if market=='tpex' else normalized_month
            rows=normalize(ticker,month,results['price'],results.get('ratio')) if 'price' in results else []
        except Exception as error:
            rows=[];errors.append(str(error))
        observed=max((r['fetched_at'] for r in results.values()),default=None)
        return ticker,month,rows,observed,errors
    counts={ticker:0 for ticker in tickers};failures=[]
    report_path=folder.parent/f'歷史回補報告-{stamp}.json'
    def report():
        return {'狀態':'complete' if len(job_results)==len(jobs) and not failures else 'partial',
                '匯入筆數':counts,'失敗項':failures,'逐月結果':job_results,'完成工作':len(job_results),'總工作':len(jobs),
                '備份':str(backup),'口徑':'官方歷史資料事後回補，未宣稱當時已留存模型'}
    with SessionLocal() as db,ThreadPoolExecutor(max_workers=workers) as executor:
        try:
            for index,(ticker,month,rows,fetched_at,errors) in enumerate(executor.map(fetch_job,jobs),1):
                if not db.get(StockMaster,ticker):
                    raise ValueError('股票不在研究股池：'+ticker)
                save_month(db,ticker,rows,fetched_at)
                counts[ticker]+=len(rows)
                db.commit()
                failures.extend(errors)
                job_results.append({'ticker':ticker,'month':month[:6],'market':markets[ticker],'rows':len(rows),
                                    'status':'partial' if errors else 'imported' if rows else 'no_rows','errors':errors})
                if index%12==0:
                    report_path.write_text(json.dumps(report(),ensure_ascii=False,indent=2),encoding='utf-8')
                    print(json.dumps({'進度':f'{index}/{len(jobs)}','已匯入總筆數':sum(counts.values()),'股票':ticker,'失敗項':len(failures)},ensure_ascii=False),flush=True)
        except SourceBlocked as error:
            failures.append(str(error))
            executor.shutdown(wait=True,cancel_futures=True)
    report_path.write_text(json.dumps(report(),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'報告':str(report_path),'完成工作':len(job_results),'總工作':len(jobs),'匯入總筆數':sum(counts.values()),'失敗項':len(failures)},ensure_ascii=False),flush=True)
    return report()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='官方上市個股歷史回補')
    parser.add_argument('--tickers',default='2330,2317,2454')
    parser.add_argument('--months',type=int,default=48)
    parser.add_argument('--current-only',action='store_true',help='只補當月已公布交易日，填補月底與最近行情之間的缺口')
    parser.add_argument('--refresh',action='store_true',help='重取過往官方資料以留存修訂，不沿用完整月份快取')
    parser.add_argument('--workers',type=int,default=2,help='同時查詢數1–4；--tickers all查詢已核實市場來源的完整股池')
    parser.add_argument('--interval',type=float,default=2.0,help='全程序官方請求間隔秒數，最低0.5；觸發官方防護即停止')
    args=parser.parse_args()
    if not 12<=args.months<=60:
        raise ValueError('回補範圍限 12–60 個月')
    result=backfill(args.tickers.split(','),0 if args.current_only else args.months,args.refresh,args.workers,args.interval)
    sys.exit(2 if result['失敗項'] or result['完成工作']!=result['總工作'] else 0)
