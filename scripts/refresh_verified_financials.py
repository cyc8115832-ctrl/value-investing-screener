"""先核對整批最新財報、備份後匯入；保留未知的歷史公告日與單季EPS。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
import requests
from config.settings import BASE_DIR, DATA_DIR, SETTINGS
from src.database.session import SessionLocal
from src.database.schema import StockMaster
from src.data.financial_evidence import FINANCIAL_SOURCES, normalize_financial
from src.services.market_evidence import save_evidence, taiwan_today


def prepare_sources(sources, pool):
    """整批先驗證：任何重複、識別或會計等式失敗均不寫正式DB。"""
    records = {}
    for source in sources:
        if not isinstance(source['data'], list):
            raise ValueError('財報來源不是資料列清單')
        for raw in source['data']:
            ticker = str(raw.get('公司代號', raw.get('SecuritiesCompanyCode', '')))
            if ticker not in pool:
                continue
            record = normalize_financial(source['url'], raw, source['fetched_at'])
            dataset, ticker, period, payload, published = record
            key = (dataset, ticker, period)
            if key in records:
                raise ValueError('跨來源重複季度，須核對報表類型而非任意覆寫：' + str(key))
            records[key] = (*record, source['url'], source['fetched_at'])
    coverage = {dataset: sorted({r[1] for r in records.values() if r[0] == dataset})
                for dataset in ('income_ytd', 'balance_sheet')}
    periods = {r[2] for r in records.values()}
    if len(periods) != 1:
        raise ValueError('本輪最新財報季度不一致，須先核對各公司期間')
    return list(records.values()), coverage


def refresh_financials(cached_directory=None):
    if SETTINGS.DEMO_MODE or SETTINGS.DATABASE_URL != f"sqlite:///{DATA_DIR / 'value_investing.db'}":
        raise RuntimeError('財報匯入僅限本專案正式SQLite，禁止示範／其他DB')
    folder = BASE_DIR / 'reports' / taiwan_today().isoformat() / '財報來源'
    folder.mkdir(parents=True, exist_ok=True)
    sources = []
    if cached_directory:
        for path in sorted(Path(cached_directory).glob('*.json')):
            source = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(source, dict) and source.get('url') in FINANCIAL_SOURCES:
                sources.append(source)
    else:
        for index, url in enumerate(FINANCIAL_SOURCES):
            if index:
                time.sleep(3)
            response = requests.get(url, timeout=20)
            if response.status_code in (403, 428, 429):
                raise RuntimeError('官方流量防護，本輪立即停止且不匯入')
            response.raise_for_status()
            source = {'url': response.url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                      'response_sha256': hashlib.sha256(response.content).hexdigest(), 'data': response.json()}
            (folder / (url.rsplit('/', 1)[1] + '-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '.json')).write_text(
                json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
            sources.append(source)
    with SessionLocal() as db:
        pool = {r.ticker for r in db.query(StockMaster).all()}
        records, coverage = prepare_sources(sources, pool)
        missing = {dataset: sorted(pool - set(tickers)) for dataset, tickers in coverage.items()}
        # 本輪目標為94檔最新一期；缺任一股先保留快照與明確缺口，不半途更新正式表。
        if any(missing.values()):
            raise ValueError('最新財報未覆蓋全股池：' + json.dumps(missing, ensure_ascii=False))
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        backup = DATA_DIR / ('財報匯入前-' + stamp + '.db')
        with sqlite3.connect(DATA_DIR / 'value_investing.db') as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('匯入前備份完整性失敗，停止正式寫入')
        for dataset, ticker, period, payload, published, url, observed in records:
            save_evidence(db, dataset, ticker, period, payload, url, published,
                          datetime.fromisoformat(observed).astimezone(timezone.utc).replace(tzinfo=None))
        db.commit()
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'source_count': len(sources),
              'records': len(records), 'coverage': coverage, 'missing': missing,
              'periods': sorted({r[2] for r in records}), 'backup': str(backup),
              'boundary': '最新一期來源快照；出表日不是原公告日，沒有歷年財報、現金流、單季EPS、股數或策略驗收。'}
    output = folder.parent / ('最新財報匯入結果-' + stamp + '.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(output), 'records': len(records), 'coverage': {k: len(v) for k,v in coverage.items()}}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached-directory', type=Path, help='本輪保存的官方來源目錄；重新核對後匯入')
    args = parser.parse_args()
    refresh_financials(args.cached_directory)
