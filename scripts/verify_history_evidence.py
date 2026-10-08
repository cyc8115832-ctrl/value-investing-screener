"""唯讀查核歷史證據、版本hash、最新行情一致性與逐股覆蓋；缺口不冒充完整。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import gzip
import json
import sqlite3
from datetime import datetime,timezone
from config.settings import DATA_DIR,BASE_DIR
from src.services.market_evidence import taiwan_today


def verify_history(database=DATA_DIR/'value_investing.db'):
    failures=[]
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        integrity=db.execute('pragma integrity_check').fetchone()[0]
        if integrity!='ok':
            failures.append({'檢查':'SQLite完整性','結果':integrity})
        hash_counts={}
        for table in ('market_evidence','market_evidence_revision'):
            count=0
            for row in db.execute(f'select dataset,ticker,period,payload_json,payload_sha256 from {table}'):
                count+=1
                if hashlib.sha256(row['payload_json'].encode()).hexdigest()!=row['payload_sha256']:
                    failures.append({'檢查':table+' hash','ticker':row['ticker'],'period':row['period']})
            hash_counts[table]=count
        prices=list(db.execute("select e.*,p.close,p.volume,p.pe,p.pb,p.ps from market_evidence e left join price_daily p on e.ticker=p.ticker and e.period=p.date where e.dataset='price' and e.status='verified'"))
        coverage={r['ticker']:{'ticker':r['ticker'],'company_name':r['company_name'],'points':0,'months':set(),'dates':[],
                               'pe_points':0,'pb_points':0,'sources':set()} for r in db.execute('select ticker,company_name from stock_master order by ticker')}
        for row in prices:
            payload=json.loads(row['payload_json'])
            if payload.get('period',row['period'])!=row['period'] or row['period']>taiwan_today().isoformat():
                failures.append({'檢查':'期間','ticker':row['ticker'],'period':row['period']})
            for field in ('close','volume','pe','pb','ps'):
                if payload.get(field)!=row[field]:
                    failures.append({'檢查':'證據與行情表不一致','ticker':row['ticker'],'period':row['period'],'field':field})
            item=coverage[row['ticker']]
            item['points']+=1;item['months'].add(row['period'][:7]);item['dates'].append(row['period'])
            item['pe_points']+=payload.get('pe') is not None;item['pb_points']+=payload.get('pb') is not None
            item['sources'].add('上櫃' if 'tpex.org.tw' in row['source_url'] else '上市')
        reference=set(coverage.get('2330',{}).get('dates',[]))
        for item in coverage.values():
            dates=sorted(item.pop('dates'))
            item['first_date']=dates[0] if dates else None;item['last_date']=dates[-1] if dates else None
            item['months']=sorted(item['months']);item['sources']=sorted(item['sources'])
            # 參考日差集只是查核線索：仍需市場別交易日、上市與停牌事件才能認定缺漏。
            item['reference_days_absent']=sorted(reference-set(dates))
        return {'verified_at':datetime.now(timezone.utc).isoformat(),'integrity':integrity,
                'hash_checked':hash_counts,'verified_price_points':len(prices),'stocks':list(coverage.values()),
                'failures':failures,'checks_passed':not failures,'investment_ready':False,
                'boundary':'只查核已取得資料。交易日差集未核對掛牌／下市／停牌事件，不宣稱四年全量完整；事後回補不是當時預估，財報、歷史股池及公司事件仍待核實。'}


def verify_snapshots(result,database=DATA_DIR/'value_investing.db'):
    """從保留的官方月快照重新解析；核對股票／月份及實際匯入數值。"""
    from scripts.backfill_verified_history import normalized_month,normalized_tpex_month
    paths={}
    for path in sorted((BASE_DIR/'reports').glob('*/官方歷史快照/*-price.json')):
        paths[path.name]=path
    checked=0;matched=0;other_versions=0
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        evidence={(t,p):(u,json.loads(j)) for t,p,u,j in db.execute("select ticker,period,source_url,payload_json from market_evidence where dataset='price' and status='verified'")}
        for path in paths.values():
            ticker,month,_=path.stem.split('-')
            price=json.loads(path.read_text(encoding='utf-8'))
            ratio_path=path.with_name(path.name.replace('-price.json','-ratio.json'))
            ratio=json.loads(ratio_path.read_text(encoding='utf-8')) if ratio_path.exists() else None
            try:
                normalize=normalized_tpex_month if 'tpex.org.tw' in price['url'] else normalized_month
                rows=normalize(ticker,month+'01',price,ratio)
                checked+=1
                for payload in rows:
                    current=evidence.get((ticker,payload['period']))
                    if current is None:
                        result['failures'].append({'檢查':'快照尚未匯入','ticker':ticker,'period':payload['period']})
                        continue
                    if current[0]!=payload['source_url']:
                        other_versions+=1
                        continue
                    for field in ('close','volume','pe','pb','ps','open','high','low'):
                        if current[1].get(field)!=payload.get(field):
                            result['failures'].append({'檢查':'官方月快照數值不符','ticker':ticker,'period':payload['period'],'field':field})
                    matched+=1
            except Exception as error:
                result['failures'].append({'檢查':'官方月快照格式／識別','path':str(path.relative_to(BASE_DIR)),'reason':str(error)})
    result['snapshot_checked']={'months':checked,'matching_source_points':matched,'other_source_version_points':other_versions}
    result['checks_passed']=not result['failures']
    from scripts.backfill_verified_market import normalize_day
    daily_checked=0;daily_points=0
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        pool={r[0] for r in db.execute('select ticker from stock_master')}
    daily_paths={}
    for path in sorted((BASE_DIR/'reports').glob('*/官方上市日快照/*-market.json.gz')):
        daily_paths[path.name]=path
    for path in daily_paths.values():
        day=path.name[:-len('-market.json.gz')]
        ratio_path=path.with_name(path.name.replace('-market.json.gz','-ratios.json.gz'))
        if not ratio_path.exists():
            result['failures'].append({'檢查':'每日快照倍數回應缺失','date':day})
            continue
        try:
            market=json.loads(gzip.decompress(path.read_bytes()).decode('utf-8'))
            ratios=json.loads(gzip.decompress(ratio_path.read_bytes()).decode('utf-8'))
            rows=normalize_day(day,pool,market,ratios)
            daily_checked+=1
            for ticker,payload in rows:
                current=evidence.get((ticker,day))
                if current is None:
                    result['failures'].append({'檢查':'每日快照尚未匯入','ticker':ticker,'period':day})
                    continue
                if current[0]!=payload['source_url']:
                    continue
                for field in ('close','volume','pe','pb','ps','open','high','low'):
                    if current[1].get(field)!=payload.get(field):
                        result['failures'].append({'檢查':'官方日快照數值不符','ticker':ticker,'period':day,'field':field})
                daily_points+=1
        except Exception as error:
            result['failures'].append({'檢查':'官方日快照格式／識別','date':day,'reason':str(error)})
    result['snapshot_checked']['bulk_days']=daily_checked
    result['snapshot_checked']['bulk_matching_points']=daily_points
    result['checks_passed']=not result['failures']
    return result


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=BASE_DIR/'reports'/taiwan_today().isoformat()/'歷史證據查核.json')
    parser.add_argument('--check-snapshots',action='store_true',help='重新解析已保存的官方月快照，核對實際匯入數值')
    args=parser.parse_args()
    result=verify_history()
    if args.check_snapshots:
        result=verify_snapshots(result)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'報告':str(args.output),'價格筆數':result['verified_price_points'],'hash筆數':result['hash_checked'],'失敗':len(result['failures'])},ensure_ascii=False))
    sys.exit(0 if result['checks_passed'] else 1)
