"""上市／上櫃官方行情；來源日期缺失或連線失敗時不建立替代行情。"""
import logging
from datetime import date
from typing import Optional
import requests
from src.database.schema import PriceDaily, StockMaster
from src.data.verified_importer import OFFICIAL_SOURCES, roc_date, number
from src.services.market_evidence import save_evidence, taiwan_today

logger = logging.getLogger("twse_adapter")
TWSE_STOCK_DAY_URL = OFFICIAL_SOURCES["上市行情"]
TWSE_BWIBBU_URL = OFFICIAL_SOURCES["上市倍數"]


def fetch_twse_market_snapshot():
    """同時讀取 TWSE／TPEx。只合併交易日期一致的行情及倍數。"""
    snapshot = {}
    for market in ("上市", "上櫃"):
        price_url = OFFICIAL_SOURCES[market + "行情"]
        ratio_url = OFFICIAL_SOURCES[market + "倍數"]
        try:
            response = requests.get(price_url, timeout=6)
            response.raise_for_status()
            prices = response.json()
        except Exception as error:
            logger.warning("官方行情擷取失敗，保留原資料：%s", error)
            continue
        ratios = {}
        try:
            response = requests.get(ratio_url, timeout=6)
            response.raise_for_status()
            ratios = {r.get("Code", r.get("SecuritiesCompanyCode")): r for r in response.json()}
        except Exception as error:
            logger.warning("官方倍數擷取失敗，不沿用舊倍數：%s", error)
        for raw in prices:
            ticker = raw.get("Code", raw.get("SecuritiesCompanyCode"))
            try:
                trade_date = roc_date(raw.get("Date"))
            except (ValueError, TypeError):
                continue
            close = number(raw.get("ClosingPrice", raw.get("Close")))
            volume = number(raw.get("TradeVolume", raw.get("TradingShares")))
            if not ticker or close is None or close <= 0 or volume is None or volume < 0:
                continue
            ratio = ratios.get(ticker, {})
            if ratio.get("Date") != raw.get("Date"):
                ratio = {}
            pe = number(ratio.get("PEratio", ratio.get("PriceEarningRatio")))
            pb = number(ratio.get("PBratio", ratio.get("PriceBookRatio")))
            snapshot[ticker] = {"ticker": ticker, "name": raw.get("Name", raw.get("CompanyName", "")),
                "date": trade_date.isoformat(), "close": close, "volume": volume,
                "pe": pe if pe and pe > 0 else None, "pb": pb if pb and pb > 0 else None, "ps": None,
                "open": number(raw.get("OpeningPrice", raw.get("Open"))),
                "high": number(raw.get("HighestPrice", raw.get("High"))),
                "low": number(raw.get("LowestPrice", raw.get("Low"))),
                "source_url": price_url, "ratio_source_url": ratio_url if ratio else None,
                "unit": "新臺幣元／成交股數", "raw": raw, "raw_ratio": ratio}
    return snapshot


def sync_daily_prices_to_db(db, target_date: Optional[date] = None):
    """更新來源交易日，拒絕將昨日行情寫成今日；失敗回傳零筆。"""
    cutoff = target_date or taiwan_today()
    market = fetch_twse_market_snapshot()
    count = 0
    for stock in db.query(StockMaster).all():
        payload = market.get(stock.ticker)
        if not payload or not payload.get("date") or not payload.get("source_url"):
            continue
        trade_date = date.fromisoformat(payload["date"])
        if trade_date > cutoff:
            continue
        row = db.get(PriceDaily, (stock.ticker, trade_date))
        if row is None:
            row = PriceDaily(ticker=stock.ticker, date=trade_date)
            db.add(row)
        for field in ("close", "volume", "pe", "pb", "ps"):
            setattr(row, field, payload.get(field))
        save_evidence(db, "price", stock.ticker, trade_date.isoformat(), payload, payload["source_url"], trade_date)
        count += 1
    db.commit()
    return count
