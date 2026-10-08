"""以官方全市場日資料補上市歷史；單一程序低頻查詢、快照續跑與來源防護即停止。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import gzip
import json
import sqlite3
import time
from datetime import date,datetime,timezone
import requests
from config.settings import BASE_DIR,DATA_DIR,SETTINGS
from src.database.session import SessionLocal
from src.database.schema import MarketEvidence,StockMaster
from src.services.market_evidence import taiwan_today
from src.data.verified_importer import number
from scripts.backfill_verified_history import save_month,SourceBlocked

MARKET_URL='https://www.twse.com.tw/exchangeReport/MI_INDEX'
RATIOS_URL='https://www.twse.com.tw/exchangeReport/BWIBBU_d'


def normalize_day(day,tickers,market,ratios):
    """日期與識別不符時拒絕；倍數缺失不造值，跨源收盤不同則拒絕混搭。"""
    for result in (market,ratios):
        if result['data'].get('stat')!='OK' or result['data'].get('date')!=day.replace('-',''):
            raise ValueError('官方全市場回應日期或狀態不符')
    tables=[t for t in market['data'].get('tables',[]) if '證券代號' in t.get('fields',[]) and '成交股數' in t.get('fields',[])]
    if len(tables)!=1:
        raise ValueError('找不到唯一的官方每日收盤行情表')
    prices=[dict(zip(tables[0]['fields'],row)) for row in tables[0]['data']]
    multiples={r['證券代號']:r for r in [dict(zip(ratios['data']['fields'],row)) for row in ratios['data']['data']]}
    results=[]
    for raw in prices:
        ticker=raw['證券代號']
        if ticker not in tickers:
            continue
        close,volume=number(raw.get('收盤價')),number(raw.get('成交股數'))
        if close is None or close<=0 or volume is None or volume<0:
            continue
        ratio=multiples.get(ticker,{})
        if ratio.get('收盤價') is not None and number(ratio['收盤價'])!=close:
            raise ValueError(f'{ticker} 同日兩個官方來源收盤不同')
        pe,pb=number(ratio.get('本益比')),number(ratio.get('股價淨值比'))
        payload={'period':day,'close':close,'volume':volume,'open':number(raw.get('開盤價')),
                 'high':number(raw.get('最高價')),'low':number(raw.get('最低價')),
                 'pe':pe if pe and pe>0 else None,'pb':pb if pb and pb>0 else None,'ps':None,
                 'source_url':market['url'],'ratio_source_url':ratios['url'] if ratio else None,
                 'availability_basis':'官方各日歷史行情，事後回補；不是當時已留存的預估',
                 'unit':'新臺幣元／成交股數','raw':raw,'raw_ratio':ratio}
        results.append((ticker,payload))
    return results


def backfill_market(tickers,interval=3.0):
    if SETTINGS.DEMO_MODE or SETTINGS.DATABASE_URL!=f"sqlite:///{DATA_DIR/'value_investing.db'}":
        raise RuntimeError('限定本專案正式SQLite')
    if interval<3:
        raise ValueError('上市全市場查詢間隔至少3秒')
    today=taiwan_today();stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    folder=BASE_DIR/'reports'/today.isoformat()/'官方上市日快照';folder.mkdir(parents=True,exist_ok=True)
    with SessionLocal() as db:
        pool={s.ticker for s in db.query(StockMaster).all()}
        if not tickers or not tickers<=pool:
            raise ValueError('股票不在研究股池')
        tpex={r.ticker for r in db.query(MarketEvidence).filter(
            MarketEvidence.dataset=='price',MarketEvidence.source_url.like('%tpex.org.tw%')).all()}
        if tickers&tpex:
            raise ValueError('上櫃股票須使用個股月查詢來源，不可宣稱上市整批已回補')
        # 官方三檔實際交易日聯集；不用平日猜測假日，不宣稱已核對全部市場日曆。
        days=sorted({r.period for r in db.query(MarketEvidence).filter(
            MarketEvidence.dataset=='price',MarketEvidence.status=='verified',
            MarketEvidence.ticker.in_(['2330','2317','2454'])).all()})
    backup=DATA_DIR/f'上市整批回補前-{stamp}.db'
    with sqlite3.connect(DATA_DIR/'value_investing.db') as source,sqlite3.connect(backup) as destination:
        source.backup(destination)
    report_path=folder.parent/f'上市整批回補報告-{stamp}.json'
    report={'completed_days':0,'total_days':len(days),'tickers':sorted(tickers),'counts':{t:0 for t in sorted(tickers)},
            'failures':[],'days':[],'backup':str(backup),'status':'running',
            'boundary':'三檔官方交易日聯集回補；掛牌、下市及停牌事件仍須核實；事後歷史不是當時模型。'}
    last_request=0.0
    pending={};observations={};pending_day_results=[]
    def save_report():
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def flush(db):
        for ticker,rows in pending.items():
            save_month(db,ticker,rows,None,observations)
        db.commit()
        for ticker,rows in pending.items():
            report['counts'][ticker]+=len(rows)
        report['days'].extend(pending_day_results);report['completed_days']+=len(pending_day_results)
        pending.clear();observations.clear();pending_day_results.clear();save_report()
    with requests.Session() as session,SessionLocal() as db:
        try:
            for index,day in enumerate(days):
                results={}
                for name,url in [('market',MARKET_URL),('ratios',RATIOS_URL)]:
                    path=folder/f'{day}-{name}.json.gz'
                    if path.exists():
                        result=json.loads(gzip.decompress(path.read_bytes()).decode('utf-8'))
                    else:
                        for attempt in range(3):
                            time.sleep(max(0,interval-(time.monotonic()-last_request)))
                            last_request=time.monotonic()
                            try:
                                response=session.get(url,params={'date':day.replace('-',''),'response':'json','type':'ALLBUT0999' if name=='market' else 'ALL'},timeout=20)
                                if response.status_code in (403,428,429) or 'Anti-DDoS Flood Protection' in response.text[:1500]:
                                    raise SourceBlocked(f'官方HTTP {response.status_code}或流量防護，本輪停止：{response.url}')
                                response.raise_for_status();data=response.json()
                                break
                            except (requests.RequestException,ValueError) as error:
                                if attempt==2:
                                    raise ValueError(f'{day} {url} 重試後失敗：{error}') from error
                                time.sleep(6*(attempt+1))
                        if data.get('stat')!='OK' or data.get('date')!=day.replace('-',''):
                            raise ValueError('官方日資料日期或狀態不符：'+day)
                        result={'url':response.url,'fetched_at':datetime.now(timezone.utc).isoformat(),
                                'response_sha256':hashlib.sha256(response.content).hexdigest(),'data':data}
                        # 公開原始JSON內容完整壓縮保存，不以自建行情替代。
                        path.write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf-8'),mtime=0))
                    results[name]=result
                rows=normalize_day(day,tickers,results['market'],results['ratios'])
                for ticker,payload in rows:
                    pending.setdefault(ticker,[]).append(payload)
                observations[day]=max(r['fetched_at'] for r in results.values())
                pending_day_results.append({'date':day,'rows':len(rows),'missing_tickers':sorted(tickers-{t for t,_ in rows})})
                report['downloaded_days']=index+1;report['last_fetched_date']=day;save_report()
                next_month=days[index+1][:7] if index+1<len(days) else None
                if next_month!=day[:7]:
                    flush(db)
                    print(json.dumps({'完成日':report['completed_days'],'總日':len(days),'匯入筆數':sum(report['counts'].values()),'月份':day[:7]},ensure_ascii=False),flush=True)
            report['status']='complete'
        except (SourceBlocked,requests.RequestException,ValueError) as error:
            flush(db);report['failures'].append(str(error));report['status']='partial'
        save_report()
    print(json.dumps({'報告':str(report_path),'完成日':report['completed_days'],'總日':len(days),'失敗':report['failures']},ensure_ascii=False),flush=True)
    return report


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tickers',required=True,help='明確的上市股池代號，以逗號分隔')
    parser.add_argument('--interval',type=float,default=3)
    args=parser.parse_args()
    result=backfill_market(set(args.tickers.split(',')),args.interval)
    sys.exit(0 if result['status']=='complete' else 2)
