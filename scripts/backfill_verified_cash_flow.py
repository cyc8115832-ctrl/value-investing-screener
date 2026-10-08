"""依明確hash清單驗證現金流批次；預設僅產出驗證報告，--apply才備份匯入。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from config.settings import DATA_DIR, SETTINGS
from src.data.historical_cash_flow import normalize_cash_flow


def prepare_batch(manifest_path):
    """全批檢查完成前不寫DB，清單不允許路徑跳脫、重複或未核對檔案。"""
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    expected = {tuple(x) for x in manifest['expected']}
    if not expected or len(expected) != len(manifest['expected']):
        raise ValueError('批次目標空白或重複')
    records, files, keys = [], [], set()
    for item in manifest['files']:
        path = (manifest_path.parent / item['path']).resolve()
        if not path.is_relative_to(manifest_path.parent) or path == manifest_path:
            raise ValueError('來源路徑超出批次目錄')
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != item['sha256']:
            raise ValueError('來源hash不符：' + path.name)
        record = normalize_cash_flow(json.loads(content))
        key = (record['ticker'], record['period'])
        if key in keys or key not in expected:
            raise ValueError('批次重複或清單外季度：' + str(key))
        keys.add(key)
        record['payload']['source_capture_sha256'] = digest
        records.append(record)
        files.append({'path':item['path'], 'sha256':digest})
    if keys != expected:
        raise ValueError('批次缺少指定股票／季度')
    return records, files


def run_batch(manifest_path, apply=False):
    records, files = prepare_batch(manifest_path)
    db_path = DATA_DIR / 'value_investing.db'
    backup = None
    if apply:
        if SETTINGS.DEMO_MODE or SETTINGS.DATABASE_URL != f'sqlite:///{db_path}':
            raise RuntimeError('只允許本專案正式SQLite，禁止示範DB')
        from src.database.session import SessionLocal
        from src.database.schema import StockMaster
        from src.database.schema import MarketEvidence
        from src.services.market_evidence import save_evidence
        with SessionLocal() as db:
            pool = {r.ticker for r in db.query(StockMaster).all()}
            if any(r['ticker'] not in pool for r in records):
                raise ValueError('批次股票不在本專案股池')
            for r in records:
                existing = db.get(MarketEvidence, (r['dataset'], r['ticker'], r['period']))
                observed = datetime.fromisoformat(r['observed_at']).astimezone(timezone.utc).replace(tzinfo=None)
                if existing is not None and existing.fetched_at > observed:
                    raise ValueError('批次來源早於已存在版本，停止全批而不覆寫')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
            backup = DATA_DIR / ('現金流匯入前-' + stamp + '.db')
            with sqlite3.connect(db_path) as src, sqlite3.connect(backup) as dst:
                src.backup(dst)
                if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('備份完整性失敗，停止匯入')
            for r in records:
                save_evidence(db, r['dataset'], r['ticker'], r['period'], r['payload'], r['source_url'],
                              datetime.fromisoformat(r['available_date']).date(),
                              datetime.fromisoformat(r['observed_at']).astimezone(timezone.utc).replace(tzinfo=None))
            db.commit()
    report = {'generated_at':datetime.now(timezone.utc).isoformat(), 'mode':'imported' if apply else 'validated_only',
              'manifest_sha256':hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),
              'records':records, 'files':files, 'backup':str(backup) if backup else None,
              'boundary':'本批合併現金流的本期與比較期已勾稽；原公告版本未匹配，不產生單季、自由現金流或策略判定。'}
    if apply:
        # 原始來源、資料庫payload、hash、可得日及版本逐筆重新比較。
        from src.database.schema import MarketEvidence, MarketEvidenceRevision
        with SessionLocal() as db:
            for r in records:
                row = db.get(MarketEvidence, (r['dataset'], r['ticker'], r['period']))
                if (json.loads(row.payload_json) != r['payload'] or row.source_url != r['source_url']
                    or row.available_date.isoformat() != r['available_date']
                    or row.fetched_at != datetime.fromisoformat(r['observed_at']).astimezone(timezone.utc).replace(tzinfo=None)
                    or row.status != 'verified' or hashlib.sha256(row.payload_json.encode()).hexdigest() != row.payload_sha256):
                    raise RuntimeError('匯入後來源／DB核對失敗')
                versions = db.query(MarketEvidenceRevision).filter_by(dataset=r['dataset'], ticker=r['ticker'], period=r['period']).all()
                if not versions or any(hashlib.sha256(v.payload_json.encode()).hexdigest() != v.payload_sha256 for v in versions):
                    raise RuntimeError('修訂版本hash核對失敗')
        with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as connection:
            report['integrity_check'] = connection.execute('PRAGMA integrity_check').fetchone()[0]
        if report['integrity_check'] != 'ok':
            raise RuntimeError('匯入後SQLite完整性失敗')
        report['source_database_checks'] = len(records)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    output = Path(manifest_path).with_name('現金流批次-' + ('匯入結果' if apply else '驗證結果') + '-' + stamp + '.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report':str(output), 'mode':report['mode'], 'records':len(records)}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    run_batch(args.manifest, args.apply)
