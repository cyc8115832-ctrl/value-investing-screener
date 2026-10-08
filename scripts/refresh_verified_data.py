"""人工執行官方資料更新，備份後交易寫入；失敗來源不補值。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hashlib
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import requests
from config.settings import DATA_DIR, BASE_DIR, SETTINGS
from src.database.session import SessionLocal, init_db
from src.database.schema import StockMaster
from src.data.verified_importer import OFFICIAL_SOURCES, import_snapshot


def refresh():
    if SETTINGS.DEMO_MODE:
        raise RuntimeError("示範模式不得匯入正式市場資料")
    init_db()
    with SessionLocal() as db:
        tickers = {s.ticker for s in db.query(StockMaster).all()}
        now = datetime.now(timezone(timedelta(hours=8)))
        snapshot = {"擷取時間": now.isoformat(), "來源": {}, "失敗來源": {}}
        def fetch(item):
            name, url = item
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                rows = response.json()
                if not isinstance(rows, list):
                    raise ValueError("官方回應不是資料列")
                matched = [r for r in rows if r.get("Code", r.get("SecuritiesCompanyCode", r.get("公司代號"))) in tickers]
                return name, {"url": url, "sha256": hashlib.sha256(response.content).hexdigest(), "total_rows": len(rows), "matched_rows": matched}, None
            except Exception as error:
                return name, None, str(error)
        with ThreadPoolExecutor(max_workers=4) as executor:
            for name, data, error in executor.map(fetch, OFFICIAL_SOURCES.items()):
                if data:
                    snapshot["來源"][name] = data
                else:
                    snapshot["失敗來源"][name] = error
        folder = BASE_DIR / "reports" / now.strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"正式來源快照-{now.strftime('%H%M%S')}.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        # 僅在本專案 SQLite 正式資料庫執行；完整備份包含既有未核實紀錄。
        if SETTINGS.DATABASE_URL != f"sqlite:///{DATA_DIR / 'value_investing.db'}":
            raise RuntimeError("更新腳本限定本專案正式 SQLite")
        backup_path = DATA_DIR / f"正式更新前-{now.strftime('%Y%m%d-%H%M%S')}.db"
        with sqlite3.connect(DATA_DIR / "value_investing.db") as source, sqlite3.connect(backup_path) as destination:
            source.backup(destination)
        try:
            counts = import_snapshot(db, snapshot)
            db.commit()
        except Exception:
            db.rollback()
            raise
        print(json.dumps({"更新筆數": counts, "失敗來源": snapshot["失敗來源"], "快照": str(path), "備份": str(backup_path)}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    refresh()
