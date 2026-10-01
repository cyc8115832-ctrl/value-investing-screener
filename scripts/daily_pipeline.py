r"""
價值投資選股 App - 盤後自動化重算管線 CLI 執行腳本 (daily_pipeline.py)
用途：
  提供獨立命令列執行介面，可由 Windows 工作排程器 (Task Scheduler)
  或 Linux crontab 在每日 15:30 收盤後自動排程觸發。

用法範例：
  .\.venv\Scripts\python.exe scripts/daily_pipeline.py
  .\.venv\Scripts\python.exe scripts/daily_pipeline.py --push
  .\.venv\Scripts\python.exe scripts/daily_pipeline.py --date 2026-10-01
"""

import sys
import os
import argparse
from datetime import datetime, date

# 確保專案根目錄在 sys.path 中
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database.session import SessionLocal, init_db
from src.services.scheduler import GLOBAL_SCHEDULER
from src.services.line_push import send_line_broadcast


def main():
    parser = argparse.ArgumentParser(description="價值投資選股 App - 每日盤後重算流水線")
    parser.add_argument("--date", type=str, default=None, help="目標運算日期 (格式: YYYY-MM-DD，預設為今日)")
    parser.add_argument("--push", action="store_true", help="管線執行完畢後立即執行 LINE 收盤推播")
    parser.add_argument("--dry-run", action="store_true", help="模擬執行，不實際發送 LINE 外部請求")

    args = parser.parse_args()

    # 初始化資料庫結構
    init_db()

    target_dt = date.today()
    if args.date:
        try:
            target_dt = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"[錯誤] 日期格式不正確: {args.date}，請使用 YYYY-MM-DD 格式。")
            sys.exit(1)

    print("==========================================================")
    print(" 🚀 價值投資選股 App - 盤後自動化管線啟動")
    print(f" 📅 目標日期: {target_dt.isoformat()}")
    print(f" ⏰ 開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==========================================================")

    # 執行盤後管線
    summary = GLOBAL_SCHEDULER.execute_daily_pipeline(target_date=target_dt)

    if summary.get("status") == "success":
        steps = summary.get("steps", {})
        print("\n✅ 盤後重算管線執行成功！")
        print(f"  ● 耗費時間: {summary.get('elapsed_seconds', 0)} 秒")
        print(f"  ● 價格同步標的數: {steps.get('sync_prices', {}).get('updated_stocks', 0)}")
        print(f"  ● ETF 持股變動事件數: {steps.get('sync_etf', {}).get('events_count', 0)}")
        print(f"  ● 全股池處理標的數: {steps.get('screener_pipeline', {}).get('stocks_processed', 0)}")
        print(f"  ● 今日特價/便宜好公司精選數: {steps.get('screener_pipeline', {}).get('daily_picks_count', 0)}")
        print(f"  ● 早期轉強候選數: {steps.get('screener_pipeline', {}).get('early_strengthening_count', 0)}")
        print(f"  ● 出場與檢視提醒數: {steps.get('exit_alerts', {}).get('alerts_count', 0)}")
    else:
        print(f"\n❌ 管線執行遇到錯誤: {summary.get('error')}")
        sys.exit(1)

    # 若指定 --push，發動收盤推播
    if args.push:
        print("\n----------------------------------------------------------")
        print(" 📤 發動 LINE 收盤推播程序...")
        db = SessionLocal()
        try:
            push_res = send_line_broadcast(db, pick_date=target_dt)
            print(f"  ● 推播發送狀態: {push_res.get('status')}")
            if "total_subscribers" in push_res:
                print(f"  ● 成功推送訂閱者數: {push_res.get('total_subscribers')}")
            if "message" in push_res:
                print(f"  ● 系統回饋訊息: {push_res.get('message')}")
        finally:
            db.close()

    print("\n==========================================================")
    print(" 🏁 管線全部作業完成。")
    print("==========================================================")


if __name__ == "__main__":
    main()
