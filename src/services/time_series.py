"""官方歷史河流圖重建；財報只展示當時已保存的可得版本。"""
from datetime import date
from config.settings import SETTINGS
from src.services.market_evidence import evidence_rows, valuation_from_history, taiwan_today
from src.engines.verified_earnings import realized_eps_summary


def stock_time_series(db, stock, metric="auto", years=3):
    today = taiwan_today()
    cutoff = date(today.year - years, today.month, min(today.day, 28))
    quotes = [p for p in evidence_rows(db, "price", stock.ticker) if p["period"] >= cutoff.isoformat()]
    all_prices = evidence_rows(db, "price", stock.ticker)
    financials_today = evidence_rows(db, "income_ytd", stock.ticker)
    selected = ("pb" if stock.is_cyclical or stock.sector_type == "financial" else "pe") if metric == "auto" else metric
    rows = []
    for quote in quotes:
        point_date = date.fromisoformat(quote["period"])
        historical_prices = [p for p in all_prices if p['period'] <= quote['period']]
        financials = [p for p in financials_today if p['knowledge_date'] <= quote['period']]
        earnings = realized_eps_summary(financials, point_date)
        valuation = valuation_from_history(historical_prices, selected, point_date, reconstruction=True) if selected in ("pe", "pb", "ps") else {"available": False}
        rows.append({"date": quote["period"], "close": quote["close"], "open": quote.get("open"),
                     "high": quote.get("high"), "low": quote.get("low"), "volume": quote.get("volume"),
                     "pe": quote.get("pe"), "pb": quote.get("pb"), "eps_ttm": earnings["ttm_eps"],
                     "roe": None, "peg": None, "bands": valuation.get("levels"),
                     "zone": valuation.get("zone", "unknown"), "source_url": quote["source_url"],
                     "known_at": quote["fetched_at"], "model_available": valuation.get("available", False)})
    return {"evidence_version": 1, "ticker": stock.ticker, "metric": selected, "years": years, "as_of_date":today.isoformat(),
            "rows": rows, "verified_price_points": len(rows),
            "river_points": sum(r["model_available"] for r in rows),
            "required_observations": SETTINGS.RIVER_MIN_OBSERVATIONS,
            "method": "依官方各日收盤與倍數回補重建；不是當時已留存預估，不把今日財報或價位線倒填過去。回測另需當時可得版本。",
            "price_basis": "未還原官方行情；此表為已核實版本歷史展示，真實回測另需股利與分割事件",
            "status": "ready" if rows and all(r["model_available"] for r in rows) else "partial"}
