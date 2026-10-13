"""UI 驗證只啟動正式資料的一致複本；不升級／修改正式 SQLite。"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FOLDER = ROOT / 'data' / 'UI驗證-20261012'
FOLDER.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'data' / 'value_investing.db'
COPY = FOLDER / 'isolated.db'
before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
with sqlite3.connect(SOURCE.resolve().as_uri() + '?mode=ro', uri=True) as original, sqlite3.connect(COPY) as target:
    original.backup(target)
    assert target.execute('pragma integrity_check').fetchone()[0] == 'ok'
os.environ['DATABASE_URL'] = 'sqlite:///' + str(COPY)
os.environ['DEMO_MODE'] = 'false'
os.environ['ENABLE_SCHEDULER'] = 'false'
os.environ['ALLOW_LINE_SEND'] = 'false'
os.environ['LINE_CHANNEL_ACCESS_TOKEN'] = ''
os.environ['LINE_CHANNEL_SECRET'] = ''
from scripts.export_gh_pages import generate_static_site
from scripts.verify_static_snapshot import verify_static_snapshot
from src.database.session import engine

REPORT = ROOT / 'reports' / '2026-10-12'
REPORT.mkdir(parents=True, exist_ok=True)
generate_static_site()
result = verify_static_snapshot()
engine.dispose()
after = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
result['formal_db_sha256_before'] = before
result['formal_db_sha256_after'] = after
result['formal_db_unchanged'] = before == after
result['isolated_db'] = str(COPY.relative_to(ROOT))
(REPORT / 'UI修改靜態與資料查核.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
assert before == after, '正式 DB 意外修改'
assert result['checks_passed'], result['failures']
print('UI快照比對與正式DB未修改查核通過', flush=True)
