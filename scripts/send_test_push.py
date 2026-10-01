r"""
價值投資選股 App - LINE 訊息推播測試與格式預覽工具 (send_test_push.py)
用途：
  提供快速測試 LINE 推播格式、預覽今日好公司名單與安心心法內容，
  並可發送真實測試訊息至已綁定之使用者或進行廣播。

用法範例：
  .\.venv\Scripts\python.exe scripts/send_test_push.py --preview
  .\.venv\Scripts\python.exe scripts/send_test_push.py --preview --elder
  .\.venv\Scripts\python.exe scripts/send_test_push.py --send --user-id default_user
"""

import sys
import os
import argparse
from datetime import date

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database.session import SessionLocal, init_db
from src.services.line_push import (
    format_daily_line_message,
    send_line_push_with_retry,
    send_line_broadcast
)
from config.settings import SETTINGS


def main():
    parser = argparse.ArgumentParser(description="LINE 推播測試與格式預覽工具")
    parser.add_argument("--preview", action="store_true", help="在終端機預覽今日推播格式內容")
    parser.add_argument("--elder", action="store_true", help="切換為長輩友善大字版樣式")
    parser.add_argument("--send", action="store_true", help="實際呼叫 LINE Messaging API 發送推播")
    parser.add_argument("--user-id", type=str, default="default_user", help="目標使用者 ID (預設: default_user)")
    parser.add_argument("--broadcast", action="store_true", help="執行全域廣播推播")

    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        print("==========================================================")
        print(" 📱 LINE 推播測試與預覽工具")
        print(f" 模式: {'長輩大字版' if args.elder else '標準專業版'}")
        print(f" Token 狀態: {'已配置' if SETTINGS.LINE_CHANNEL_ACCESS_TOKEN else '未配置 (將以 Dry-Run 模式模擬)'}")
        print("==========================================================")

        # 1. 產生推播文案
        message_content = format_daily_line_message(db, elder_mode=args.elder)

        print("\n【📋 產出訊息預覽】\n")
        print(message_content)
        print("\n----------------------------------------------------------")

        # 2. 若指定發送
        if args.send:
            print(f"\n🚀 正在向使用者 [{args.user_id}] 發送訊息...")
            res = send_line_push_with_retry(db, message_text=message_content, user_id=args.user_id)
            print(f"發送結果: {res}")

        elif args.broadcast:
            print("\n📢 正在發動全體已綁定訂閱者廣播推播...")
            res = send_line_broadcast(db, pick_date=date.today())
            print(f"廣播結果: {res}")

        else:
            if not args.preview:
                print("💡 提示: 若要實際發送訊息，請加上 --send 或 --broadcast 參數。")

    finally:
        db.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    main()
