"""
價值投資選股 App - 宏觀水位：美債 10 年期殖利率適配器 (macro_adapter.py)
嚴格落實技術規格書 V1.7 第 14.6 節：
- 美國 10 年期公債殖利率現值與水位判定
- ≥ 5.0% 顯示警示：「利率偏高，市場給的本益比可能下降」
- ≥ 4.5% 顯示接近提示：「美債殖利率接近 5% 水位，留意高估值標的估值下修風險」
- 限制：僅作風險提示，不作為買賣訊號，亦不改變好公司或價位區判定
"""

import logging
import requests
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.database.schema import MacroDaily

logger = logging.getLogger("macro_adapter")


def fetch_us_10y_yield_from_web() -> Optional[float]:
    """
    從公開財經數據來源獲取最新美債 10 年期殖利率。
    若網路不通或逾時，回傳 None 並安全回退。
    """
    # 備援公共端點 (例如 Yahoo Finance / FRED / Stooq)
    url = "https://stooq.com/q/l/?s=10usy.b&f=sd2t2ohlcv&h&e=csv"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200 and resp.text:
            lines = resp.text.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split(",")
                # CSV format: Symbol,Date,Time,Open,High,Low,Close,Volume
                if len(parts) >= 7:
                    close_val = float(parts[6])
                    if 0.5 <= close_val <= 15.0:
                        return round(close_val, 2)
    except Exception as e:
        logger.warning(f"遠端擷取美債殖利率逾時或失敗: {e}")

    return None


def determine_yield_warning(yield_val: float) -> Dict[str, str]:
    """
    依規格書 14.6 判定利率警示旗標與文案
    """
    if yield_val >= 5.0:
        return {
            "flag": "alert_5_0",
            "level": "alert",
            "message": "⚠️ 利率偏高（≥5.0%），市場給予股票之本益比倍數可能承壓下降。"
        }
    elif yield_val >= 4.5:
        return {
            "flag": "warning_4_5",
            "level": "warning",
            "message": "ℹ️ 美債殖利率接近 5% 水位（≥4.5%），留意高估值標的倍數下修風險。"
        }
    else:
        return {
            "flag": "normal",
            "level": "normal",
            "message": "美債殖利率處於正常平穩區間。"
        }


def sync_macro_yield_to_db(db: Session, target_date: Optional[date] = None, mock_yield: Optional[float] = None) -> MacroDaily:
    """
    同步美債殖利率至 macro_daily 資料表
    """
    from config.settings import SETTINGS
    if not SETTINGS.DEMO_MODE:
        raise RuntimeError("尚未接入帶來源日期的官方美債資料；拒絕以舊值或示範利率寫入今日")
    today_dt = target_date or date.today()
    record = db.query(MacroDaily).filter(MacroDaily.date == today_dt).first()

    if mock_yield is not None:
        rate = mock_yield
    else:
        rate = fetch_us_10y_yield_from_web()
        if rate is None:
            # 查閱前日資料或使用基底值 4.35%
            latest = db.query(MacroDaily).order_by(MacroDaily.date.desc()).first()
            rate = latest.us_10y_yield if latest else 4.35

    warning_info = determine_yield_warning(rate)

    if record:
        record.us_10y_yield = rate
        record.warning_flag = warning_info["flag"]
        record.updated_at = datetime.utcnow()
    else:
        record = MacroDaily(
            date=today_dt,
            us_10y_yield=rate,
            warning_flag=warning_info["flag"],
            updated_at=datetime.utcnow()
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


def get_latest_macro_yield(db: Session) -> Dict[str, Any]:
    """
    取得最新宏觀美債殖利率與警示資訊
    """
    from config.settings import SETTINGS
    if not SETTINGS.DEMO_MODE:
        return {"date": None, "us_10y_yield": None, "warning_flag": "insufficient", "warning_level": "insufficient", "message": "官方來源與資料日期尚未核實", "notice": "未沿用既有示範利率"}
    latest = db.query(MacroDaily).order_by(MacroDaily.date.desc()).first()
    if not latest:
        # 若無資料則自動建立一筆基準資料
        latest = sync_macro_yield_to_db(db)

    warning_info = determine_yield_warning(latest.us_10y_yield)

    return {
        "date": latest.date.isoformat(),
        "us_10y_yield": latest.us_10y_yield,
        "warning_flag": latest.warning_flag,
        "warning_level": warning_info["level"],
        "message": warning_info["message"],
        "notice": "※ 宏觀利率僅作估值倍數風險提示，不作為買賣訊號，亦不改變好公司或價位區判定。"
    }
