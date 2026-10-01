r"""
價值投資選股 App - 資料庫安全熱備份與自動滾動歸檔工具 (backup_db.py)
用途：
  使用 SQLite 官方安全的 Connection.backup() 進行零鎖定熱備份，
  備份檔存入 data/backups/，並自動滾動清理超過指定天數之舊備份，
  防止磁碟膨脹，保障實盤數據資產安全。

用法範例：
  .\.venv\Scripts\python.exe scripts/backup_db.py
  .\.venv\Scripts\python.exe scripts/backup_db.py --keep-days 14
"""

import sys
import os
import sqlite3
import argparse
import time
from datetime import datetime, timedelta

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config.settings import SETTINGS


def backup_sqlite_database(src_db_path: str, backup_dir: str, keep_days: int = 7) -> str:
    """執行 SQLite 熱備份並滾動清理"""
    if not os.path.exists(src_db_path):
        raise FileNotFoundError(f"找不到來源資料庫檔案: {src_db_path}")

    os.makedirs(backup_dir, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(src_db_path))[0]
    dest_filename = f"{base_name}_backup_{timestamp_str}.db"
    dest_path = os.path.join(backup_dir, dest_filename)

    # 1. 執行 SQLite 安全熱備份 (安全複製，不受併發寫入損壞)
    src_conn = sqlite3.connect(src_db_path)
    dest_conn = sqlite3.connect(dest_path)

    try:
        with dest_conn:
            src_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        src_conn.close()

    # 2. 自動滾動清理過期舊備份 (磁碟空間防膨脹)
    cutoff_time = time.time() - (keep_days * 86400)
    cleaned_count = 0

    for fname in os.listdir(backup_dir):
        if fname.startswith(base_name) and fname.endswith(".db"):
            fpath = os.path.join(backup_dir, fname)
            try:
                if os.path.getmtime(fpath) < cutoff_time and fpath != dest_path:
                    os.remove(fpath)
                    cleaned_count += 1
            except OSError as e:
                print(f"[警告] 清理過期檔案失敗 {fname}: {e}")

    return dest_path, cleaned_count


def main():
    parser = argparse.ArgumentParser(description="SQLite 資料庫熱備份與自動歸檔工具")
    parser.add_argument("--keep-days", type=int, default=7, help="保留最近幾天的備份檔 (預設: 7 天)")
    parser.add_argument("--backup-dir", type=str, default=None, help="備份存放目錄 (預設: ./data/backups)")

    args = parser.parse_args()

    # 解析資料庫檔案路徑
    db_url = SETTINGS.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_file = db_url.replace("sqlite:///", "")
    else:
        db_file = os.path.join(ROOT_DIR, "data", "value_investing.db")

    if not os.path.isabs(db_file):
        db_file = os.path.join(ROOT_DIR, db_file)

    backup_folder = args.backup_dir or os.path.join(os.path.dirname(db_file), "backups")

    print("==========================================================")
    print(" 🛡️ 價值投資選股 App - 資料庫安全熱備份")
    print(f" 來源檔案: {db_file}")
    print(f" 備份目錄: {backup_folder}")
    print(f" 滾動保留天數: {args.keep_days} 天")
    print("==========================================================")

    if not os.path.exists(db_file):
        print(f"[錯誤] 來源資料庫不存在: {db_file}")
        sys.exit(1)

    try:
        dest_path, cleaned = backup_sqlite_database(
            src_db_path=db_file,
            backup_dir=backup_folder,
            keep_days=args.keep_days
        )
        file_size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print("\n✅ 熱備份完成！")
        print(f"  ● 產生檔案: {dest_path}")
        print(f"  ● 檔案大小: {file_size_mb:.2f} MB")
        print(f"  ● 清理逾期舊備份檔數: {cleaned} 個")
    except Exception as e:
        print(f"\n❌ 備份過程失敗: {e}")
        sys.exit(1)

    print("\n==========================================================")
    print(" 🏁 備份作業安全結束。")
    print("==========================================================")


if __name__ == "__main__":
    main()
