"""官方行情、月營收與累計損益匯入；保留日期、來源、單位與原始快照。"""
import json
from datetime import date, datetime, timezone
from src.database.schema import StockMaster, PriceDaily, RevenueMonthly
from src.services.market_evidence import save_evidence

OFFICIAL_SOURCES = {
    "上市行情": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
    "上市倍數": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
    "上櫃行情": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
    "上櫃倍數": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
    "上市月營收": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    "上櫃月營收": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
    "上市一般業損益表": "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci",
}


def roc_date(text):
    import re
    digits = re.sub(r"[^0-9]", "", str(text))
    if len(digits) == 7:
        return date(int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:]))
    if len(digits) == 8:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    raise ValueError("官方交易日期缺失，拒絕以今天代替")


def number(value):
    try:
        import math
        result = float(str(value).replace(",", ""))
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def import_snapshot(db, snapshot):
    """整批交易由呼叫者 commit；不修改缺證據的舊季報。"""
    sources = snapshot["來源"]
    observed_at = datetime.fromisoformat(snapshot["擷取時間"]).astimezone(timezone.utc).replace(tzinfo=None) if snapshot.get("擷取時間") else None
    pool = {s.ticker: s for s in db.query(StockMaster).all()}
    counts = {"price": 0, "revenue": 0, "income_ytd": 0}
    for name, source in sources.items():
        if name not in OFFICIAL_SOURCES or source["url"] != OFFICIAL_SOURCES[name]:
            raise ValueError("資料來源不在官方允許清單")
        if name.endswith("行情"):
            ratios_source = sources.get(name.replace("行情", "倍數"), {})
            ratios = {r.get("Code", r.get("SecuritiesCompanyCode")): r for r in ratios_source.get("matched_rows", [])}
            for raw in source["matched_rows"]:
                ticker = raw.get("Code", raw.get("SecuritiesCompanyCode"))
                if ticker not in pool:
                    continue
                trade_date = roc_date(raw.get("Date"))
                close = number(raw.get("ClosingPrice", raw.get("Close")))
                volume = number(raw.get("TradeVolume", raw.get("TradingShares")))
                if close is None or close <= 0 or volume is None or volume < 0:
                    continue
                ratio = ratios.get(ticker, {})
                if ratio.get("Date") != raw.get("Date"):
                    ratio = {}
                pe = number(ratio.get("PEratio", ratio.get("PriceEarningRatio")))
                pb = number(ratio.get("PBratio", ratio.get("PriceBookRatio")))
                values = {"close": close, "volume": volume, "pe": pe if pe and pe > 0 else None,
                          "pb": pb if pb and pb > 0 else None, "ps": None}
                payload = {**values, "open": number(raw.get("OpeningPrice", raw.get("Open"))),
                           "high": number(raw.get("HighestPrice", raw.get("High"))),
                           "low": number(raw.get("LowestPrice", raw.get("Low"))),
                           "ratio_source_url": ratios_source.get("url") if ratio else None,
                           "unit": "新臺幣元／成交股數", "raw": raw, "raw_ratio": ratio}
                save_evidence(db, "price", ticker, trade_date.isoformat(), payload, source["url"], trade_date, observed_at)
                row = db.get(PriceDaily, (ticker, trade_date))
                if row is None:
                    row = PriceDaily(ticker=ticker, date=trade_date)
                    db.add(row)
                for key, value in values.items():
                    setattr(row, key, value)
                pool[ticker].company_name = raw.get("Name", raw.get("CompanyName", pool[ticker].company_name))
                counts["price"] += 1
        elif name.endswith("月營收"):
            for raw in source["matched_rows"]:
                ticker = raw["公司代號"]
                if ticker not in pool:
                    continue
                ym = raw["資料年月"]
                month = f"{int(ym[:-2]) + 1911}-{int(ym[-2:]):02d}"
                published = roc_date(raw["出表日期"])
                values = {"revenue": number(raw.get("營業收入-當月營收")),
                          "yoy": number(raw.get("營業收入-去年同月增減(%)")),
                          "cumulative_revenue": number(raw.get("累計營業收入-當月累計營收")),
                          "cumulative_yoy": number(raw.get("累計營業收入-前期比較增減(%)"))}
                if values["revenue"] is None:
                    continue
                for key in values:
                    if values[key] is not None:
                        values[key] /= 100 if key.endswith("yoy") else 1000
                payload = {**values, "unit": "百萬元／年增率小數", "availability_basis": "出表日期（保守使用，非個別公司公告日期）", "raw": raw}
                save_evidence(db, "revenue", ticker, month, payload, source["url"], published, observed_at)
                row = db.get(RevenueMonthly, (ticker, month))
                if row is None:
                    row = RevenueMonthly(ticker=ticker, month=month)
                    db.add(row)
                for key, value in values.items():
                    setattr(row, key, value)
                counts["revenue"] += 1
        elif name == "上市一般業損益表":
            for raw in source["matched_rows"]:
                ticker = raw["公司代號"]
                if ticker not in pool:
                    continue
                quarter = f"{int(raw['年度']) + 1911}-Q{raw['季別']}"
                payload = {"eps": number(raw.get("基本每股盈餘（元）")),
                           "revenue": number(raw.get("營業收入")),
                           "operating_income": number(raw.get("營業利益（損失）")),
                           "net_income": number(raw.get("淨利（淨損）歸屬於母公司業主")),
                           "unit": "金額千元／EPS 元", "basis": "年初至當季累計，未單季化",
                           "availability_basis": "出表日期（保守使用）", "raw": raw}
                save_evidence(db, "income_ytd", ticker, quarter, payload, source["url"], roc_date(raw["出表日期"]), observed_at)
                counts["income_ytd"] += 1
    db.flush()
    return counts
