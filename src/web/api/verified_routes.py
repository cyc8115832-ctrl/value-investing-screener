"""正式模式只提供有證據的資料；示範模式保留原教學 API。"""
import re
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from src.database.session import get_db, SessionLocal
from src.database.schema import StockMaster, CustomStock, WatchGroup, WatchGroupMember
from src.services.market_evidence import stock_view, data_quality_report, taiwan_today, unknown
from config.settings import SETTINGS

verified_router = APIRouter()


@verified_router.get("/evidence/stocks/{ticker}/history")
def verified_history(ticker: str, metric="auto", years: int = 3, db=Depends(get_db)):
    from src.services.time_series import stock_time_series
    stock = db.get(StockMaster, ticker)
    if not stock:
        raise HTTPException(404, "找不到個股")
    if years not in (1, 2, 3) or metric not in ("auto", "pe", "pb", "ps"):
        raise HTTPException(422, "時間範圍限 1／2／3 年，指標限 auto／pe／pb／ps")
    return stock_time_series(db, stock, metric, years)


@verified_router.get("/stocks/{ticker}")
def verified_stock(ticker: str, metric: str = "auto", scenario: str = "base", db=Depends(get_db)):
    stock = db.get(StockMaster, ticker)
    if not stock:
        raise HTTPException(404, "找不到個股")
    return stock_view(db, stock, metric, scenario)


@verified_router.get("/screener")
def verified_screener(scope="all", quadrant="all", zone="all", search="", db=Depends(get_db)):
    if scope == "etf":
        raise HTTPException(409, "ETF 現行有效成分尚未重新核實，不能沿用舊名單篩選。")
    if scope not in ("all", "custom"):
        raise HTTPException(422, "不支援的股池範圍")
    stocks = db.query(StockMaster).order_by(StockMaster.ticker).all()
    custom = {r.ticker for r in db.query(CustomStock).all()}
    result = []
    for stock in stocks:
        if search and search.lower() not in (stock.ticker + stock.company_name).lower():
            continue
        if scope == "custom" and stock.ticker not in custom:
            continue
        if scope == "etf" and stock.pool_status not in ("etf", "both"):
            continue
        item = stock_view(db, stock)
        if zone not in ("", "all") and item["current_zone"] != zone:
            continue
        if quadrant not in ("", "all", "insufficient"):
            continue
        result.append(item)
    return result


@verified_router.get("/radar")
def verified_radar(db=Depends(get_db)):
    report = data_quality_report(db)
    stocks = db.query(StockMaster).order_by(StockMaster.ticker).all()
    views = [stock_view(db, s) for s in stocks]
    dates = [s["quote"]["period"] for s in views if s["quote"]]
    return {"evidence_version": 1, "calc_date": taiwan_today().isoformat(),
            "quote_date": max(dates) if dates else None, "quality": report,
            "daily_picks_preview": [], "pick_status": "insufficient",
            "message": "價值來自可持續獲利與現金流。先補齊體質證據，再等待價格；目前不產生買進精選。",
            "growth_signals": sum(any(f["color"] == "green" for f in s["value_factors"]) for s in views),
            "risk_signals": sum(bool(s["risks"]) for s in views)}


@verified_router.get("/data-quality/report")
def verified_quality(db=Depends(get_db)):
    return data_quality_report(db)


@verified_router.get("/health")
def verified_health(db=Depends(get_db)):
    return {"status": "healthy", "mode": "verified", "investment_data": data_quality_report(db)}


@verified_router.get("/evidence/status")
def evidence_status(db=Depends(get_db)):
    return data_quality_report(db)


@verified_router.get("/evidence/watchlist")
def verified_watchlist(db=Depends(get_db)):
    result = []
    for member in db.query(WatchGroupMember).filter(WatchGroupMember.user_id == "default_user").order_by(WatchGroupMember.group_id, WatchGroupMember.sort_order).all():
        stock = db.get(StockMaster, member.ticker)
        if stock:
            group = db.query(WatchGroup).filter_by(user_id="default_user", group_id=member.group_id).first()
            result.append({**stock_view(db, stock), "group_id": member.group_id,
                           "group_name": group.name if group else member.group_id,
                           "note": member.note or ""})
    return result


@verified_router.post("/evidence/watchlist/{ticker}")
def save_observation(ticker: str, payload: dict = Body(...), db=Depends(get_db)):
    stock = db.get(StockMaster, ticker)
    if not stock:
        raise HTTPException(404, "找不到個股")
    group_id = str(payload.get("group_id", "value"))[:50]
    group = db.query(WatchGroup).filter_by(user_id="default_user", group_id=group_id).first()
    if not group:
        group = WatchGroup(user_id="default_user", group_id=group_id, name=str(payload.get("group_name", "價值研究"))[:50])
        db.add(group)
    member = db.query(WatchGroupMember).filter_by(user_id="default_user", group_id=group_id, ticker=ticker).first()
    if not member:
        view = stock_view(db, stock)
        member = WatchGroupMember(user_id="default_user", group_id=group_id, ticker=ticker,
                                  entry_price=view["quote"]["close"] if view["quote"] else None,
                                  entry_zone=view["current_zone"], sort_order=0)
        db.add(member)
    if "note" in payload:
        member.note = str(payload["note"])[:10000]
    db.commit()
    return {"success": True, "message": "觀察與筆記已儲存", "storage": "database"}


@verified_router.delete("/evidence/watchlist/{ticker}")
def delete_observation(ticker: str, group_id="value", db=Depends(get_db)):
    db.query(WatchGroupMember).filter_by(user_id="default_user", group_id=group_id, ticker=ticker).delete()
    db.commit()
    return {"success": True}


async def enforce_evidence_boundary(request, call_next):
    """阻止舊衍生 API 或推播越過正式模式的資料邊界。"""
    if SETTINGS.DEMO_MODE:
        return await call_next(request)
    path = request.url.path
    unsupported = (
        re.match(r"^/api/stocks/[^/]+/.+", path)
        or path == "/api/stocks/compare"
        or path.startswith("/api/watchlist")
        or path.startswith(("/api/macro/", "/api/backtest", "/api/calendar", "/api/alerts",
                            "/api/portfolio/calculate-allocation", "/api/push/", "/api/line/webhook"))
    )
    if unsupported:
        return JSONResponse({"evidence_version": 1, **unknown("此分析缺完整已核實資料，暫停舊模擬計算／推播。" )}, status_code=409)
    return await call_next(request)
