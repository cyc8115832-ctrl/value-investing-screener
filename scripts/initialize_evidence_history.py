"""將已核實來源加入版本歷史；不將舊模擬價格標為真實行情。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import sqlite3
from datetime import datetime, timezone
from config.settings import SETTINGS, DATA_DIR, BASE_DIR
from src.database.session import SessionLocal
from src.database.schema import MarketEvidence
from src.services.market_evidence import save_evidence
from src.data.verified_importer import import_snapshot


def initialize():
    if SETTINGS.DEMO_MODE or SETTINGS.DATABASE_URL != f"sqlite:///{DATA_DIR / 'value_investing.db'}":
        raise RuntimeError("此遷移限定本專案正式資料庫")
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    backup = DATA_DIR / f"版本遷移前-{stamp}.db"
    with sqlite3.connect(DATA_DIR / "value_investing.db") as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    with SessionLocal() as db:
        current = db.query(MarketEvidence).filter_by(status="verified").all()
        for row in current:
            import hashlib
            if hashlib.sha256(row.payload_json.encode()).hexdigest() != row.payload_sha256:
                raise ValueError("既有證據雜湊不符，停止遷移")
            save_evidence(db, row.dataset, row.ticker, row.period, json.loads(row.payload_json), row.source_url,
                          row.available_date, observed_at=row.fetched_at)
        db.flush()
        # 10/6 上櫃行情來自先前保存的官方原始快照，不是模型生成的歷史。
        snapshot = json.loads((BASE_DIR / "reports/2026-10-07/官方資料快照.json").read_text(encoding="utf-8"))
        snapshot["來源"] = {name: value for name, value in snapshot["來源"].items() if name.endswith(("行情", "倍數"))}
        counts = import_snapshot(db, snapshot)
        db.commit()
        print(json.dumps({"既有證據版本化":len(current), "既有官方行情快照":counts, "備份":str(backup)},ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8")
    initialize()
