"""
價值投資選股 App - 歷史觸及與反彈紀錄純函式計算引擎 (historical_touches.py)
嚴格落實技術規格書 V1.7 第 6.7 章：
- 列出過去 3 年曾進入特價／便宜區的日期，及其後至區間內最高點的漲幅
- 列出各策略（擴產、合約負債創高等）的歷史命中日期
- 註明「歷史不代表未來」
- 本模組為純函式，無副作用，易於單元測試
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta


DISCLAIMER_TEXT = "歷史不代表未來。過去進入特價／便宜區之反彈紀錄僅供參考，市場環境隨時變化，不構成任何獲利保證或投資建議。"


def analyze_historical_touches(
    daily_prices: List[Dict[str, Any]],
    a1_threshold: float,
    a2_threshold: float,
    strategy_hits: Optional[List[Dict[str, Any]]] = None,
    lookback_days: int = 365 * 3,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    分析過去 N 年（預設 3 年）進入特價/便宜區的波段歷史與後續最高反彈幅度。

    :param daily_prices: 每日價格字典列表，鍵需包含 'date' (YYYY-MM-DD 或 date 物件), 'close', 可選 'high'
    :param a1_threshold: 特價區上限（<= A1 為特價區）
    :param a2_threshold: 便宜區上限（A1 < price <= A2 為便宜區）
    :param strategy_hits: 歷史策略命中記錄，鍵包含 'date', 'badge_code', 'strategy_id' 等
    :param lookback_days: 回測歷史天數，預設 3 年 (1095 天)
    :param as_of_date: 基準日期，若未提供則以最新價格日為基準
    :return: 結構化歷史觸及報告字典
    """
    if not daily_prices or a1_threshold <= 0 or a2_threshold <= 0:
        return {
            "episodes": [],
            "strategy_events": [],
            "summary": {
                "total_episodes": 0,
                "avg_rebound_pct": 0.0,
                "max_rebound_pct": 0.0,
                "avg_duration_days": 0,
            },
            "disclaimer": DISCLAIMER_TEXT,
        }

    # 標準化與排序
    prices = []
    for p in daily_prices:
        p_date = p["date"]
        if isinstance(p_date, str):
            p_date = datetime.strptime(p_date, "%Y-%m-%d").date()
        prices.append({
            "date": p_date,
            "close": float(p["close"]),
            "high": float(p.get("high", p["close"])),
            "low": float(p.get("low", p["close"])),
        })
    prices.sort(key=lambda x: x["date"])

    if not prices:
        return {
            "episodes": [],
            "strategy_events": [],
            "summary": {
                "total_episodes": 0,
                "avg_rebound_pct": 0.0,
                "max_rebound_pct": 0.0,
                "avg_duration_days": 0,
            },
            "disclaimer": DISCLAIMER_TEXT,
        }

    target_as_of = as_of_date or prices[-1]["date"]
    start_date = target_as_of - timedelta(days=lookback_days)

    # 濾出在觀察窗內的價格，但最高點計算可延伸至目前最新
    window_prices = [p for p in prices if p["date"] >= start_date]
    if not window_prices:
        return {
            "episodes": [],
            "strategy_events": [],
            "summary": {
                "total_episodes": 0,
                "avg_rebound_pct": 0.0,
                "max_rebound_pct": 0.0,
                "avg_duration_days": 0,
            },
            "disclaimer": DISCLAIMER_TEXT,
        }

    episodes = []
    current_episode: Optional[Dict[str, Any]] = None

    for i, p in enumerate(window_prices):
        close_p = p["close"]
        is_bargain = close_p <= (a1_threshold + 1e-6)
        is_cheap = not is_bargain and close_p <= (a2_threshold + 1e-6)
        in_value_zone = is_bargain or is_cheap

        if in_value_zone:
            zone_name = "bargain" if is_bargain else "cheap"
            if current_episode is None:
                # 新波段開始
                current_episode = {
                    "entry_date": p["date"].isoformat(),
                    "entry_price": close_p,
                    "entry_zone": zone_name,
                    "lowest_price": close_p,
                    "exit_date": None,
                    "start_idx_in_window": i,
                    "days_in_zone": 1,
                }
            else:
                # 波段持續中
                current_episode["days_in_zone"] += 1
                if close_p < current_episode["lowest_price"]:
                    current_episode["lowest_price"] = close_p
                # 若跌入特價區，更新標籤
                if zone_name == "bargain":
                    current_episode["entry_zone"] = "bargain"
        else:
            if current_episode is not None:
                # 離開便宜區，波段結算
                current_episode["exit_date"] = p["date"].isoformat()
                episodes.append(current_episode)
                current_episode = None

    if current_episode is not None:
        # 當前仍在便宜/特價區
        current_episode["exit_date"] = None
        episodes.append(current_episode)

    # 計算各波段後續至最高點的漲幅
    final_episodes = []
    total_rebound = 0.0
    total_duration = 0
    max_rebound = 0.0

    for ep in episodes:
        start_idx = ep["start_idx_in_window"]
        entry_price = ep["entry_price"]
        entry_date = datetime.strptime(ep["entry_date"], "%Y-%m-%d").date()

        # 找尋進入日起未來 365 天內（或至最新）的最高價
        future_sub = [
            p for p in window_prices[start_idx:]
            if 0 <= (p["date"] - entry_date).days <= 365
        ]

        if not future_sub:
            future_sub = [window_prices[start_idx]]

        peak_price = max(p["high"] for p in future_sub)
        peak_item = next(p for p in future_sub if p["high"] == peak_price)
        peak_date = peak_item["date"].isoformat()
        days_to_peak = (peak_item["date"] - entry_date).days

        rebound_pct = round(((peak_price - entry_price) / entry_price) * 100.0, 2)
        duration_days = ep["days_in_zone"]

        total_rebound += rebound_pct
        total_duration += duration_days
        if rebound_pct > max_rebound:
            max_rebound = rebound_pct

        final_episodes.append({
            "entry_date": ep["entry_date"],
            "entry_price": ep["entry_price"],
            "entry_zone": ep["entry_zone"],
            "entry_zone_name": "特價區" if ep["entry_zone"] == "bargain" else "便宜區",
            "lowest_price": ep["lowest_price"],
            "exit_date": ep["exit_date"],
            "duration_days": duration_days,
            "peak_price_after": peak_price,
            "peak_date": peak_date,
            "days_to_peak": days_to_peak,
            "max_rebound_pct": rebound_pct,
            "is_current": ep["exit_date"] is None,
        })

    # 策略事件整理
    parsed_strategy_events = []
    if strategy_hits:
        for s in strategy_hits:
            s_date = s.get("date")
            if isinstance(s_date, str):
                try:
                    s_date_obj = datetime.strptime(s_date, "%Y-%m-%d").date()
                except Exception:
                    continue
            else:
                s_date_obj = s_date

            if s_date_obj and s_date_obj >= start_date:
                parsed_strategy_events.append({
                    "date": s_date_obj.isoformat(),
                    "strategy_id": s.get("strategy_id", ""),
                    "badge_code": s.get("badge_code", ""),
                    "strategy_name": s.get("strategy_name", s.get("strategy_id", "歷史策略訊號")),
                })
        parsed_strategy_events.sort(key=lambda x: x["date"], reverse=True)

    count = len(final_episodes)
    summary = {
        "total_episodes": count,
        "avg_rebound_pct": round(total_rebound / count, 2) if count > 0 else 0.0,
        "max_rebound_pct": round(max_rebound, 2) if count > 0 else 0.0,
        "avg_duration_days": round(total_duration / count, 1) if count > 0 else 0,
    }

    return {
        "episodes": sorted(final_episodes, key=lambda x: x["entry_date"], reverse=True),
        "strategy_events": parsed_strategy_events,
        "summary": summary,
        "disclaimer": DISCLAIMER_TEXT,
    }
