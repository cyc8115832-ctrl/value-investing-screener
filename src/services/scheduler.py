"""
價值投資選股 App - 盤後定時自動重算管線與排程服務 (scheduler.py)
嚴格落實技術規格書 V1.7 第 10、11、15 章：
- 15:30 盤後定時重算管線：TWSE 報價同步 → ETF 持股比對 → 全股池重算 (EPS/好公司/河流圖) → 每日精選產出
- 18:30 LINE 自動推播排程：推播價值精選名單、早期轉強與今日心法
- 具備手動即時觸發端點與健全的例外捕捉機制
"""

import threading
import time
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional

from src.database.session import SessionLocal
from src.data.twse_adapter import sync_daily_prices_to_db
from src.universe.syncer import sync_all_etf_holdings
from src.services.daily_screener import run_daily_screener_pipeline
from src.services.exit_checker import check_watchlist_exit_conditions
from src.services.line_push import send_line_broadcast, format_daily_line_message

logger = logging.getLogger("scheduler")


class MarketDataScheduler:
    """盤後定時自動排程服務 (純背景執行，無外部重度依賴)"""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_pipeline_run_date: Optional[date] = None
        self._last_line_push_date: Optional[date] = None
        self._lock = threading.Lock()

    def start(self):
        """啟動排程循環執行緒"""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="MarketDataSchedulerThread")
            self._thread.start()
            logger.info("盤後定時重算與推播排程服務已啟動。")

    def stop(self):
        """停止排程循環"""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
            logger.info("盤後定時排程服務已安全停止。")

    def _loop(self):
        """每分鐘檢查排程時間"""
        while self._running:
            try:
                now = datetime.now()
                today_dt = now.date()

                # 1. 每日 15:30 觸發盤後重算流水線 (排除週末 5=週六, 6=週日)
                if now.weekday() < 5 and (now.hour == 15 and now.minute >= 30 or now.hour > 15):
                    if self._last_pipeline_run_date != today_dt:
                        logger.info(f"觸發每日 15:30 盤後重算管線: {today_dt}")
                        self.execute_daily_pipeline(today_dt)
                        self._last_pipeline_run_date = today_dt

                # 2. 每日 18:30 觸發 LINE Messaging API 推播
                if now.weekday() < 5 and (now.hour == 18 and now.minute >= 30 or now.hour > 18):
                    if self._last_line_push_date != today_dt:
                        logger.info(f"觸發每日 18:30 LINE 推播: {today_dt}")
                        self.execute_evening_push(today_dt)
                        self._last_line_push_date = today_dt

            except Exception as e:
                logger.error(f"排程循環執行異常: {e}", exc_info=True)

            # 休眠 30 秒後進行下一輪檢測
            time.sleep(30)

    def execute_daily_pipeline(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        執行盤後完整計算流水線 (可供排程或 API 手動立即觸發)
        """
        run_dt = target_date or date.today()
        start_time = datetime.now()
        db = SessionLocal()

        summary = {
            "target_date": run_dt.isoformat(),
            "started_at": start_time.isoformat(),
            "status": "success",
            "steps": {}
        }

        try:
            # 步驟 1: 同步真實/快取價格至 PriceDaily
            updated_prices = sync_daily_prices_to_db(db, target_date=run_dt)
            summary["steps"]["sync_prices"] = {"updated_stocks": updated_prices}

            # 步驟 2: 同步四檔 ETF 成分股並產生 universe_event
            from config.settings import SETTINGS
            if SETTINGS.DEMO_MODE:
                etf_sync_events = sync_all_etf_holdings(db, snapshot_date=run_dt)
            else:
                etf_sync_events = []
                summary["steps"]["sync_etf"] = {"status": "insufficient", "reason": "官方成分尚待核實，未使用範例持股"}
            if SETTINGS.DEMO_MODE:
                summary["steps"]["sync_etf"] = {"events_count": len(etf_sync_events)}

            # 步驟 3: 執行全股池計算 (EPS、好公司燈號、河流圖五段價位、兩道門四象限分類、每日精選)
            screener_res = run_daily_screener_pipeline(db, target_date=run_dt)
            if screener_res.get("status") == "insufficient":
                summary["status"] = "insufficient"
                summary["reason"] = screener_res.get("reason")
                return summary
            summary["steps"]["screener_pipeline"] = {
                "stocks_processed": screener_res.get("stocks_processed", 0),
                "daily_picks_count": len(screener_res.get("daily_picks", [])),
                "early_strengthening_count": len(screener_res.get("early_strengthening", []))
            }

            # 步驟 4: 出場條件與定期檢視提醒檢查
            alerts = check_watchlist_exit_conditions(db)
            summary["steps"]["exit_alerts"] = {"alerts_count": len(alerts)}

            elapsed = (datetime.now() - start_time).total_seconds()
            summary["elapsed_seconds"] = round(elapsed, 2)
            logger.info(f"盤後流水線執行完畢，耗時: {summary['elapsed_seconds']} 秒")

        except Exception as e:
            logger.error(f"盤後流水線執行失敗: {e}", exc_info=True)
            summary["status"] = "failed"
            summary["error"] = str(e)
        finally:
            db.close()

        return summary

    def execute_evening_push(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """執行每日晚間收盤推播 (可供排程或 API 手動觸發)"""
        db = SessionLocal()
        try:
            res = send_line_broadcast(db, pick_date=target_date)
            return res
        finally:
            db.close()



# 全域單例排程服務
GLOBAL_SCHEDULER = MarketDataScheduler()
