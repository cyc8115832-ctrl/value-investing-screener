"""真實時點持有期驗證：訊號當日不成交、只使用當時可得資料。"""
from datetime import date
import math


def simulate_hold_period(signal, membership, prices, events, sessions, end_date,
                         event_coverage_verified=False, buy_fee=0.0, sell_fee=0.0, sell_tax=0.0):
    """費稅由呼叫者明示；現金股利不再投入，未還原價格配合分割事件計算。"""
    unavailable = lambda reason: {"available": False, "reason": reason}
    decision = signal["decision_date"]
    if not signal.get("verified") or not signal.get("available_date") or signal["available_date"] > decision:
        return unavailable("訊號在決策日尚不可得")
    if not membership.get("verified") or not membership.get("available_date") or membership["available_date"] > decision:
        return unavailable("歷史股池成分缺當時可得證據")
    if membership["effective_date"] > decision or membership.get("removed_date") and membership["removed_date"] <= decision:
        return unavailable("決策日不在股池，不能用今日股池替代")
    if not event_coverage_verified:
        return unavailable("股利與分割事件覆蓋尚未核實")
    if any(not math.isfinite(value) or not 0 <= value < 1 for value in (buy_fee, sell_fee, sell_tax)) or sell_fee + sell_tax >= 1:
        raise ValueError("費稅率需為有效小數")
    required = sorted(s for s in sessions if decision < s <= end_date)
    if not required:
        return unavailable("決策後沒有完整交易期間")
    lookup = {p["date"]: p for p in prices if p.get("verified") and p.get("available_date") and p["available_date"] <= p["date"]}
    if any(day not in lookup for day in required):
        return unavailable("交易日行情缺漏，不以跨日或生成行情補值")
    buy = lookup[required[0]].get("open")
    if buy is None or not math.isfinite(buy) or buy <= 0:
        return unavailable("缺訊號翌交易日真實開盤價")
    quantity, cash, peak, drawdown = 1.0, 0.0, buy * (1 + buy_fee), 0.0
    cost = peak
    curve = []
    for day in required:
        for event in events:
            # 訊號翌日開盤買入；當日已除息／分割，不可再取得開盤前權利。
            if event["date"] == day and day > required[0]:
                if not event.get("verified") or event.get("available_date", "9999") > day:
                    return unavailable("持有期事件缺已核實來源或可得日期")
                if event.get("type") == "split":
                    ratio = event.get("ratio")
                    if ratio is None or not math.isfinite(ratio) or ratio <= 0:
                        return unavailable("分割比率無效")
                    quantity *= ratio
                elif event.get("type") == "cash_dividend":
                    amount = event.get("amount")
                    if amount is None or not math.isfinite(amount) or amount < 0:
                        return unavailable("現金股利數值無效")
                    cash += quantity * amount
                else:
                    return unavailable("事件類型尚未支援，不跳過影響報酬的事件")
        close = lookup[day].get("close")
        if close is None or not math.isfinite(close) or close <= 0:
            return unavailable("收盤價無效")
        equity = quantity * close + cash
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
        curve.append({"date": day, "equity": equity})
    proceeds = quantity * lookup[required[-1]]["close"] * (1 - sell_fee - sell_tax) + cash
    drawdown = min(drawdown, proceeds / peak - 1)
    curve[-1]["equity_after_exit_fees"] = proceeds
    return {"available": True, "entry_date": required[0], "exit_date": required[-1],
            "total_return_pct": (proceeds / cost - 1) * 100,
            "max_drawdown_pct": drawdown * 100, "equity_curve": curve,
            "fees": {"buy_fee": buy_fee, "sell_fee": sell_fee, "sell_tax": sell_tax},
            "dividend_policy": "現金股利不再投入；以除息日記為應收股利，非可即時支用現金"}
