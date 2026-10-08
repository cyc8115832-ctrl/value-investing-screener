"""本次稽核的一次性官方資料核對；不執行選股、種子、排程或推播。"""
import concurrent.futures
import hashlib
import json
import math
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TODAY = date(2026, 10, 7)
URLS = {
    "上市行情": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
    "上市倍數": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
    "上櫃行情": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
    "上櫃倍數": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
    "上市月營收": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    "上櫃月營收": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
    "上市一般業損益表": "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci",
}


def download(item):
    name, url = item
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    rows = json.loads(response.content.decode("utf-8-sig"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{name}：來源沒有有效資料")
    return name, rows, hashlib.sha256(response.content).hexdigest()


def num(value):
    try:
        parsed = float(str(value).replace(",", ""))
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def roc_date(value):
    value = str(value).replace("/", "").replace("-", "")
    if len(value) != 7:
        raise ValueError(f"非預期民國日期：{value}")
    result = date(int(value[:3]) + 1911, int(value[3:5]), int(value[5:]))
    if result > TODAY:
        raise ValueError("來源日期晚於稽核日期")
    return result.isoformat()


if __name__ == "__main__":
    conn = sqlite3.connect(f"file:{ROOT / 'data/value_investing.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    stocks = {row["ticker"]: dict(row) for row in conn.execute("SELECT * FROM stock_master")}
    sources, failed = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(download, item): item[0] for item in URLS.items()}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                _, rows, digest = future.result()
                matched = [row for row in rows if str(row.get("Code", row.get("SecuritiesCompanyCode", row.get("公司代號", "")))) in stocks]
                sources[name] = {"url": URLS[name], "sha256": digest, "total_rows": len(rows), "matched_rows": matched}
            except Exception as error:
                failed[name] = str(error)
    fetched_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    snapshot = {"稽核日期": TODAY.isoformat(), "擷取時間": fetched_at, "來源": sources, "失敗來源": failed}
    (OUT / "官方資料快照.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    updates, names, revenue_updates = [], [], []
    for price_source, ratio_source, code_key, close_key, volume_key, pe_key, pb_key, name_key in [
        ("上市行情", "上市倍數", "Code", "ClosingPrice", "TradeVolume", "PEratio", "PBratio", "Name"),
        ("上櫃行情", "上櫃倍數", "SecuritiesCompanyCode", "Close", "TradingShares", "PriceEarningRatio", "PriceBookRatio", "CompanyName"),
    ]:
        ratio_map = {r[code_key]: r for r in sources.get(ratio_source, {}).get("matched_rows", [])}
        seen = set()
        for row in sources.get(price_source, {}).get("matched_rows", []):
            ticker, day = row[code_key], roc_date(row["Date"])
            if (ticker, day) in seen:
                raise ValueError("同來源同代號日期重複")
            seen.add((ticker, day))
            close, volume = num(row[close_key]), num(row[volume_key])
            if close is None or close <= 0 or volume is None or volume < 0:
                continue
            ratio = ratio_map.get(ticker, {})
            same_date = ratio and roc_date(ratio["Date"]) == day
            pe, pb = (num(ratio.get(pe_key)), num(ratio.get(pb_key))) if same_date else (None, None)
            # 空白/無意義倍數保持未知；不沿用模擬 P/S。
            pe = pe if pe is not None and pe > 0 else None
            pb = pb if pb is not None and pb > 0 else None
            before = conn.execute("SELECT * FROM price_daily WHERE ticker=? AND date=?", (ticker, day)).fetchone()
            updates.append({"代號": ticker, "日期": day, "來源": price_source, "倍數來源": ratio_source if same_date else None, "原值": dict(before) if before else None, "新值": {"close": close, "volume": volume, "pe": pe, "pb": pb, "ps": None}})
            name = row.get(name_key)
            if name and name != stocks[ticker]["company_name"]:
                names.append({"代號": ticker, "原名稱": stocks[ticker]["company_name"], "新名稱": name, "來源": price_source})
    for source in ["上市月營收", "上櫃月營收"]:
        for row in sources.get(source, {}).get("matched_rows", []):
            ticker = row["公司代號"]
            period = str(row["資料年月"]).replace("/", "")
            if len(period) != 5:
                continue
            month = f"{int(period[:3])+1911}-{int(period[3:]):02d}"
            if month >= "2026-10":
                continue
            export_date = roc_date(row["出表日期"])
            # 出表日期不是原始公告日，不能用於歷史資訊可得性。
            raw = [num(row.get(k)) for k in ["營業收入-當月營收", "營業收入-去年同月增減(%)", "累計營業收入-當月累計營收", "累計營業收入-前期比較增減(%)"]]
            if any(v is None for v in raw) or raw[0] < 0 or raw[2] < 0:
                continue
            new = {"revenue": raw[0]/1000, "yoy": raw[1]/100, "cumulative_revenue": raw[2]/1000, "cumulative_yoy": raw[3]/100}
            before = conn.execute("SELECT * FROM revenue_monthly WHERE ticker=? AND month=?", (ticker, month)).fetchone()
            revenue_updates.append({"代號": ticker, "月份": month, "來源": source, "出表日期": export_date, "原值": dict(before) if before else None, "新值": new, "單位": "百萬元；年增率為小數"})
    counts = {}
    for table, field in [("price_daily", "date"), ("revenue_monthly", "month"), ("financials_quarterly", "quarter"), ("shares_outstanding", "date"), ("chip_data", "date")]:
        counts[table] = dict(conn.execute(f"SELECT COUNT(*) rows,COUNT(DISTINCT ticker) stocks,MIN({field}) earliest,MAX({field}) latest FROM {table}").fetchone())
    etfs = [dict(r) for r in conn.execute("SELECT etf_code,COUNT(*) count,SUM(weight) total_weight FROM etf_membership GROUP BY etf_code")]
    matched_tickers = {r["代號"] for r in updates}
    summary = {"擷取時間": fetched_at, "資料表更新前": counts, "ETF權重檢查": etfs, "價格更新": updates, "名稱更新": names, "營收更新": revenue_updates, "行情來源未匹配": [stocks[t] for t in sorted(set(stocks)-matched_tickers)], "失敗來源": failed, "備註": "僅核對官方原始事實，既有歷史種子、季報、股數、籌碼與衍生結論尚未修正；損益表為累計口徑，尚未拆季匯入。"}
    (OUT / "資料更新明細.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()
    # 保存 SQLite 完整備份；只有來源驗證完後才進入單一寫入交易。
    backup_path = ROOT / "data" / "稽核備份-2026-10-07.db"
    if backup_path.exists():
        raise FileExistsError("既有稽核備份不可覆蓋")
    live = sqlite3.connect(ROOT / "data/value_investing.db")
    backup = sqlite3.connect(backup_path)
    live.backup(backup)
    backup.close()
    with live:
        for update in updates:
            n = update["新值"]
            live.execute("INSERT INTO price_daily(ticker,date,close,volume,pe,pb,ps) VALUES(?,?,?,?,?,?,?) ON CONFLICT(ticker,date) DO UPDATE SET close=excluded.close,volume=excluded.volume,pe=excluded.pe,pb=excluded.pb,ps=excluded.ps", (update["代號"], update["日期"], n["close"], n["volume"], n["pe"], n["pb"], n["ps"]))
        for update in revenue_updates:
            n = update["新值"]
            live.execute("INSERT INTO revenue_monthly(ticker,month,revenue,yoy,cumulative_revenue,cumulative_yoy) VALUES(?,?,?,?,?,?) ON CONFLICT(ticker,month) DO UPDATE SET revenue=excluded.revenue,yoy=excluded.yoy,cumulative_revenue=excluded.cumulative_revenue,cumulative_yoy=excluded.cumulative_yoy", (update["代號"], update["月份"], n["revenue"], n["yoy"], n["cumulative_revenue"], n["cumulative_yoy"]))
        for update in names:
            live.execute("UPDATE stock_master SET company_name=? WHERE ticker=?", (update["新名稱"], update["代號"]))
    assert live.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    for update in updates:
        got = live.execute("SELECT close,volume,pe,pb,ps FROM price_daily WHERE ticker=? AND date=?", (update["代號"], update["日期"])).fetchone()
        assert got == tuple(update["新值"][k] for k in ["close", "volume", "pe", "pb", "ps"])
    for update in revenue_updates:
        got = live.execute("SELECT revenue,yoy,cumulative_revenue,cumulative_yoy FROM revenue_monthly WHERE ticker=? AND month=?", (update["代號"], update["月份"])).fetchone()
        assert got == tuple(update["新值"][k] for k in ["revenue", "yoy", "cumulative_revenue", "cumulative_yoy"])
    live.close()
    print(json.dumps({"價格更新筆數": len(updates), "日期": sorted({u["日期"] for u in updates}), "名稱更新": names, "營收更新筆數": len(revenue_updates), "營收月份": sorted({u["月份"] for u in revenue_updates}), "未匹配行情": [r["ticker"] for r in summary["行情來源未匹配"]], "來源失敗": failed, "備份": str(backup_path), "完整性與逐筆回讀驗證": "通過"}, ensure_ascii=False, indent=2))
