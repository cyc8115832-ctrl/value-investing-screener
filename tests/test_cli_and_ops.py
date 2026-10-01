"""
測試運維 CLI 工具 (tests/test_cli_and_ops.py)
驗證：
1. backup_db.py SQLite 安全熱備份與滾動清理邏輯
2. send_test_push.py 推播格式產出與 Dry Run 流程
3. daily_pipeline.py 盤後流水線 CLI 調用邏輯
"""

import os
import sys
import tempfile
import sqlite3
import pytest
from datetime import date

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.backup_db import backup_sqlite_database
from src.database.session import SessionLocal, init_db
from src.services.line_push import format_daily_line_message, send_line_push_with_retry
from src.services.scheduler import GLOBAL_SCHEDULER


def test_sqlite_hot_backup_and_cleanup():
    """驗證 SQLite 熱備份能正確複製資料且不損毀，並能滾動清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_db = os.path.join(tmpdir, "test_source.db")
        backup_dir = os.path.join(tmpdir, "backups")

        # 建立測試來源資料庫並寫入假資料
        conn = sqlite3.connect(src_db)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, note TEXT);")
        cursor.execute("INSERT INTO test_data (note) VALUES ('價值投資');")
        conn.commit()
        conn.close()

        # 建立一個模擬的「過期」舊備份檔案
        os.makedirs(backup_dir, exist_ok=True)
        old_backup = os.path.join(backup_dir, "test_source_backup_20200101_000000.db")
        with open(old_backup, "w") as f:
            f.write("old dummy backup")
        # 修改舊檔案的時間戳記為 10 天前
        past_time = os.path.getmtime(old_backup) - (10 * 86400)
        os.utime(old_backup, (past_time, past_time))

        # 執行熱備份
        dest_path, cleaned = backup_sqlite_database(
            src_db_path=src_db,
            backup_dir=backup_dir,
            keep_days=7
        )

        assert os.path.exists(dest_path), "熱備份目標檔案應當存在"
        assert cleaned >= 1, "逾期之舊備份檔應當被滾動清理"
        assert not os.path.exists(old_backup), "10 天前的過期備份應被刪除"

        # 驗證備份檔案內容完整性
        check_conn = sqlite3.connect(dest_path)
        c = check_conn.cursor()
        c.execute("SELECT note FROM test_data WHERE id = 1;")
        row = c.fetchone()
        check_conn.close()

        assert row is not None and row[0] == "價值投資", "備份資料應與來源完全一致"


def test_cli_push_format_and_dryrun():
    """驗證 send_test_push 所依賴之訊息格式化與 Dry-Run 流程"""
    init_db()
    db = SessionLocal()
    try:
        # 1. 驗證標準版與長輩版文案
        std_msg = format_daily_line_message(db, elder_mode=False)
        elder_msg = format_daily_line_message(db, elder_mode=True)

        assert "價值投資" in std_msg
        assert "今日" in std_msg
        assert "價值投資" in elder_msg
        assert "好公司" in elder_msg

        # 2. 驗證無 Token 時自動回退至 Dry-Run 模式
        res = send_line_push_with_retry(db, message_text=std_msg, user_id="test_cli_user")
        assert res["status"] in ["dry_run", "success"]
    finally:
        db.close()


def test_cli_daily_pipeline_execution():
    """驗證 daily_pipeline 所調用之全流程執行"""
    init_db()
    summary = GLOBAL_SCHEDULER.execute_daily_pipeline(target_date=date.today())

    assert summary["status"] == "success"
    assert "sync_prices" in summary["steps"]
    assert "screener_pipeline" in summary["steps"]
    assert summary["elapsed_seconds"] >= 0.0
