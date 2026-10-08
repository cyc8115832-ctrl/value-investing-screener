"""唯讀財報查核：重新解析來源、比對最新證據與修訂hash及會計等式。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from config.settings import BASE_DIR, DATA_DIR
from src.data.financial_evidence import FINANCIAL_SOURCES
from scripts.refresh_verified_financials import prepare_sources
from src.services.market_evidence import encode_payload, taiwan_today


def verify_financials(folder, database=DATA_DIR / 'value_investing.db'):
    failures, sources, manifest = [], [], []
    for path in sorted(Path(folder).glob('*.json')):
        value = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(value, dict) and value.get('url') in FINANCIAL_SOURCES:
            sources.append(value)
            manifest.append({'file':str(path.resolve().relative_to(BASE_DIR)),
                             'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'url':value['url'], 'fetched_at':value['fetched_at']})
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        integrity = db.execute('pragma integrity_check').fetchone()[0]
        if integrity != 'ok':
            failures.append({'check':'SQLite完整性', 'result':integrity})
        pool = {r[0] for r in db.execute('select ticker from stock_master')}
        records, coverage = prepare_sources(sources, pool)
        for dataset, tickers in coverage.items():
            if pool - set(tickers):
                failures.append({'check':'財報覆蓋缺口', 'dataset':dataset, 'tickers':sorted(pool-set(tickers))})
        for dataset, ticker, period, payload, published, url, observed in records:
            row = db.execute('select * from market_evidence where dataset=? and ticker=? and period=?',
                             (dataset,ticker,period)).fetchone()
            expected_observed = datetime.fromisoformat(observed).astimezone(timezone.utc).replace(tzinfo=None)
            if (row is None or row['payload_json'] != encode_payload(payload) or row['source_url'] != url
                    or row['available_date'] != published.isoformat() or row['status'] != 'verified'
                    or datetime.fromisoformat(row['fetched_at']) != expected_observed):
                failures.append({'check':'保留來源與正式證據不符','dataset':dataset,'ticker':ticker,'period':period})
            if dataset == 'balance_sheet' and abs(payload['total_assets']-payload['total_liabilities']-payload['total_equity']) > 1:
                failures.append({'check':'資產負債等式','ticker':ticker})
        checked = {}
        for table in ('market_evidence','market_evidence_revision'):
            count = 0
            for row in db.execute(f"select * from {table} where dataset in ('income_ytd','balance_sheet')"):
                count += 1
                if hashlib.sha256(row['payload_json'].encode()).hexdigest() != row['payload_sha256']:
                    failures.append({'check':table+' hash','ticker':row['ticker'],'period':row['period']})
            checked[table] = count
    return {'verified_at':datetime.now(timezone.utc).isoformat(), 'integrity':integrity,
            'source_files':manifest, 'records_compared':len(records), 'coverage':{k:len(v) for k,v in coverage.items()},
            'financial_hash_checked':checked, 'periods':sorted({r[2] for r in records}),
            'failures':failures, 'checks_passed':not failures, 'investment_ready':False,
            'boundary':'核對最新一期來源與資料庫；未驗證歷年公告、單季EPS分母、現金流、股數或策略。來源檔案hash可重算；HTTP原始回應hash僅為擷取紀錄，非本工具重驗的項目。'}


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-directory', type=Path, required=True)
    args = parser.parse_args()
    report = verify_financials(args.source_directory)
    output = BASE_DIR / 'reports' / taiwan_today().isoformat() / '財報證據查核.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output':str(output), 'passed':report['checks_passed'], 'records':report['records_compared'],
                      'coverage':report['coverage'], 'failures':len(report['failures'])}, ensure_ascii=False))
    raise SystemExit(0 if report['checks_passed'] else 1)
