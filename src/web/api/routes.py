"""
價值投資選股 App - RESTful API 路由模組 (routes.py)
涵蓋雷達、選股、個股五大分頁、河流圖、自選股、觀察清單、出場提醒、設定與手冊。
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import json
from datetime import date

from src.database.session import get_db
from src.database.schema import (
    StockMaster, PriceDaily, RevenueMonthly, FinancialsQuarterly,
    SharesOutstanding, ChipData, EPSRecord, GoodCompanyRecord,
    ValuationBandsRecord, LeadingSummaryRecord, DailyPickRecord,
    WatchGroup, WatchGroupMember, CustomStock, MindsetTip,
    ManualArticle, GlossaryTerm, UserSettingRecord, ETFMaster, ETFMembership,
    ChecklistRecord, StrategyHit
)
from src.services.daily_screener import run_daily_screener_pipeline
from src.services.exit_checker import check_watchlist_exit_conditions
from src.services.line_push import format_daily_line_message, send_line_broadcast
from src.services.backtester import run_strategy_backtest
from src.universe.custom_stock import add_custom_stock, remove_custom_stock, list_custom_stocks
from src.universe.syncer import get_universe_summary
from src.engines.valuation_river import (
    calculate_anchors, calculate_river_prices, classify_price_zone,
    calculate_peg_valuation, calculate_dividend_357
)
from src.engines.checklist import PRE_ORDER_QUESTIONS, FIVE_STAGE_QUESTIONS, get_checklist_template
from src.engines.historical_touches import analyze_historical_touches
from config.settings import SETTINGS
from config.tbd_params import TBD_CONFIG

api_router = APIRouter()

# ----------------- 1. 雷達首頁 (Radar) -----------------
@api_router.get("/radar")
def get_radar_summary(db: Session = Depends(get_db)):
    """雷達首頁統計資料"""
    # 確保當日資料已計算，若無則執行
    today_dt = date.today()
    bands_count = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.date == today_dt).count()
    if bands_count == 0:
        run_daily_screener_pipeline(db, target_date=today_dt)

    universe_sum = get_universe_summary(db)

    # 統計好公司狀態與四象限
    all_bands = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.date == today_dt).all()
    bands_map = {b.ticker: b.current_zone for b in all_bands}

    all_goods = db.query(GoodCompanyRecord).filter(GoodCompanyRecord.date == today_dt).all()
    
    counts = {
        "good_company": 0,
        "watch_company": 0,
        "degraded_company": 0,
        "research_priority": 0,  # 好公司 + 特價/便宜
        "watch_fair": 0,          # 好公司 + 合理
        "val_warning": 0,        # 好公司 + 昂貴/瘋狂
        "value_trap": 0,         # 非好公司 + 特價/便宜
        "fundamental_warning": 0,# 基本面退化
        "excluded": 0            # 非好公司 + 昂貴/瘋狂
    }

    for g in all_goods:
        z = bands_map.get(g.ticker, "fair")
        is_good = (g.overall == "good")
        is_degraded = (g.overall == "degraded")
        is_cheap = z in ["special", "cheap"]
        is_fair = z == "fair"
        is_expensive = z in ["expensive", "crazy"]

        if is_good:
            counts["good_company"] += 1
        elif is_degraded:
            counts["degraded_company"] += 1
        else:
            counts["watch_company"] += 1

        if is_degraded:
            counts["fundamental_warning"] += 1
        elif is_good and is_cheap:
            counts["research_priority"] += 1
        elif is_good and is_fair:
            counts["watch_fair"] += 1
        elif is_good and is_expensive:
            counts["val_warning"] += 1
        elif not is_good and is_cheap:
            counts["value_trap"] += 1
        elif not is_good and is_expensive:
            counts["excluded"] += 1

    # 宏觀水位：美債殖利率 (規格書 14.6)
    us10y_yield = 4.28  # 模擬最新美國 10 年期公債殖利率
    us10y_status = "normal"
    us10y_msg = "美債殖利率處於正常區間 (4.28%)"
    if us10y_yield >= TBD_CONFIG.macro_us10y_alert:
        us10y_status = "alert"
        us10y_msg = "⚠️ 美債殖利率達 5.0% 警戒線！市場評價本益比可能承壓修正。"
    elif us10y_yield >= TBD_CONFIG.macro_us10y_approach:
        us10y_status = "approach"
        us10y_msg = "💡 美債殖利率接近 4.5% 提示水位，留意高估值股票波動。"

    # 每日精選摘要
    picks = db.query(DailyPickRecord).filter(DailyPickRecord.pick_date == today_dt, DailyPickRecord.list_type == "pick").limit(3).all()
    pick_items = []
    for p in picks:
        stk = db.query(StockMaster).filter(StockMaster.ticker == p.ticker).first()
        pick_items.append({
            "ticker": p.ticker,
            "company_name": stk.company_name if stk else p.ticker,
            "margin_pct": p.margin_pct
        })

    return {
        "calc_date": today_dt.isoformat(),
        "universe_summary": universe_sum,
        "quadrant_counts": counts,
        "macro_us10y": {
            "yield": us10y_yield,
            "status": us10y_status,
            "message": us10y_msg
        },
        "daily_picks_preview": pick_items
    }


# ----------------- 2. 選股篩選 (Screener) -----------------
@api_router.get("/screener")
def get_screener_stocks(
    scope: str = Query("all", description="all | etf | custom"),
    quadrant: str = Query("all", description="all | research_priority | watch | val_warning | value_trap | fundamental_warning"),
    zone: str = Query("all", description="all | special | cheap | fair | expensive | crazy"),
    search: Optional[str] = Query(None, description="搜尋代號或名稱"),
    db: Session = Depends(get_db)
):
    """選股清單與多維度篩選"""
    today_dt = date.today()
    stocks = db.query(StockMaster).all()

    bands_records = {b.ticker: b for b in db.query(ValuationBandsRecord).filter(ValuationBandsRecord.date == today_dt).all()}
    good_records = {g.ticker: g for g in db.query(GoodCompanyRecord).filter(GoodCompanyRecord.date == today_dt).all()}
    lead_records = {l.ticker: l for l in db.query(LeadingSummaryRecord).filter(LeadingSummaryRecord.date == today_dt).all()}
    etf_mems = db.query(ETFMembership).all()
    etf_map: Dict[str, List[str]] = {}
    for m in etf_mems:
        etf_map.setdefault(m.ticker, []).append(m.etf_code)

    results = []

    for s in stocks:
        t = s.ticker
        # 搜尋關鍵字過濾
        if search:
            kw = search.strip().lower()
            if kw not in t.lower() and kw not in s.company_name.lower():
                continue

        # 股池範圍過濾 (2.5)
        in_etf = len(etf_map.get(t, [])) > 0
        is_custom = (s.pool_status in ["custom", "both"])
        if scope == "etf" and not in_etf:
            continue
        elif scope == "custom" and not is_custom:
            continue

        b = bands_records.get(t)
        g = good_records.get(t)
        l = lead_records.get(t)
        p_row = db.query(PriceDaily).filter(PriceDaily.ticker == t).order_by(PriceDaily.date.desc()).first()

        current_price = p_row.close if p_row else 100.0
        current_zone = b.current_zone if b else "fair"
        overall_good = g.overall if g else "watch"
        lead_status = l.status if l else "neutral"

        # 兩道門標籤
        is_good = (overall_good == "good")
        is_degraded = (overall_good == "degraded")
        is_cheap = current_zone in ["special", "cheap"]
        is_fair = current_zone == "fair"
        is_expensive = current_zone in ["expensive", "crazy"]

        if is_degraded:
            state_tag = "fundamental_warning"
            state_name = "基本面警戒"
        elif is_good and is_cheap:
            state_tag = "research_priority"
            state_name = "核心研究區"
        elif is_good and is_fair:
            state_tag = "watch"
            state_name = "持續觀察"
        elif is_good and is_expensive:
            state_tag = "val_warning"
            state_name = "估值警戒"
        elif not is_good and is_cheap:
            state_tag = "value_trap"
            state_name = "價值陷阱觀察"
        elif not is_good and is_expensive:
            state_tag = "excluded"
            state_name = "排除標的"
        else:
            state_tag = "neutral"
            state_name = "中性觀察"

        # 象限與價位區過濾
        if quadrant != "all" and state_tag != quadrant:
            continue
        if zone != "all" and current_zone != zone:
            continue

        # 安全邊際
        cheap_line = b.p2 if b else current_price
        margin_pct = ((cheap_line - current_price) / cheap_line * 100.0) if cheap_line > 0 else 0.0

        badges = json.loads(g.badges_json or "[]") if g else []
        reasons = json.loads(g.reasons_json or "[]") if g else []

        results.append({
            "ticker": t,
            "company_name": s.company_name,
            "industry": s.industry,
            "is_cyclical": s.is_cyclical,
            "sector_type": s.sector_type,
            "current_price": current_price,
            "current_zone": current_zone,
            "state_tag": state_tag,
            "state_name_zh": state_name,
            "overall_good": overall_good,
            "lead_status": lead_status,
            "margin_pct": round(margin_pct, 1),
            "badges": badges[:2],  # 列表僅顯示前 2 個小徽章 (規格書 4.5)
            "reasons": reasons,
            "etfs": etf_map.get(t, []),
            "lights": {
                "rev": g.revenue_light if g else "gray",
                "eps": g.eps_light if g else "gray",
                "margin": g.margin_light if g else "gray",
                "eff": g.efficiency_light if g else "gray",
                "cf": g.cashflow_light if g else "gray",
                "growth": g.growth_light if g else "gray"
            }
        })

    # 預設依安全邊際降序排列
    results.sort(key=lambda x: x["margin_pct"], reverse=True)
    return results


# ----------------- 3. 個股多標的比較器 (7.4, 8.9.6) -----------------
@api_router.get("/stocks/compare")
def compare_stocks(tickers: str = Query(..., description="以逗號分隔之股票代號，例如 2330,2454,2317"), db: Session = Depends(get_db)):
    """多標的並排橫向比較 (2 至 4 檔)"""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        raise HTTPException(status_code=400, detail="比較器需至少選擇 2 檔標的")
    if len(ticker_list) > 4:
        ticker_list = ticker_list[:4]

    comparison_items = []

    for t in ticker_list:
        stock = db.query(StockMaster).filter(StockMaster.ticker == t).first()
        if not stock:
            continue

        latest_p = db.query(PriceDaily).filter(PriceDaily.ticker == t).order_by(PriceDaily.date.desc()).first()
        cur_price = latest_p.close if latest_p else 100.0
        good = db.query(GoodCompanyRecord).filter(GoodCompanyRecord.ticker == t).order_by(GoodCompanyRecord.date.desc()).first()
        eps_rec = db.query(EPSRecord).filter(EPSRecord.ticker == t).order_by(EPSRecord.created_at.desc()).first()
        lead = db.query(LeadingSummaryRecord).filter(LeadingSummaryRecord.ticker == t).order_by(LeadingSummaryRecord.date.desc()).first()
        bands = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == t).order_by(ValuationBandsRecord.date.desc()).first()
        fin = db.query(FinancialsQuarterly).filter(FinancialsQuarterly.ticker == t).order_by(FinancialsQuarterly.quarter.desc()).first()
        rev = db.query(RevenueMonthly).filter(RevenueMonthly.ticker == t).order_by(RevenueMonthly.month.desc()).first()

        # 估值價格區
        base_val = eps_rec.estimated_eps or (eps_rec.actual_eps or 5.0) if eps_rec else 5.0
        anchors = calculate_anchors(12.0, 26.0)
        prices = calculate_river_prices(anchors, base_val)
        zone_class = classify_price_zone(cur_price, prices, TBD_CONFIG.zone_rule_version)

        # 規格書 6.9：極端估值旗標
        pe_val = latest_p.pe if (latest_p and latest_p.pe) else 0.0
        eps_val = eps_rec.actual_eps if eps_rec else 0.0
        extreme_flag = False
        extreme_reason = ""
        if not stock.is_cyclical and stock.sector_type != "financial":
            if pe_val > 100.0:
                extreme_flag = True
                extreme_reason = "本益比 > 100 倍，獲利尚未支撐股價"
            elif eps_val <= 0:
                extreme_flag = True
                extreme_reason = "EPS 虧損且處於高位區，獲利尚未支撐股價"

        # 兩道門四象限分類
        overall_good = good.overall if good else "watch"
        if overall_good == "degraded":
            state_name = "基本面警戒"
        elif overall_good == "good" and zone_class.zone in ["special", "cheap"]:
            state_name = "核心研究區 (好公司+便宜)"
        elif overall_good == "good" and zone_class.zone == "fair":
            state_name = "持續觀察 (好公司+合理)"
        elif overall_good == "good" and zone_class.zone in ["expensive", "crazy"]:
            state_name = "估值警戒 (好公司+昂貴)"
        else:
            state_name = "一般觀察"

        # 安全邊際
        cheap_line = prices.p2
        margin_pct = round(((cheap_line - cur_price) / cheap_line * 100.0), 1) if cheap_line > 0 else 0.0

        comparison_items.append({
            "ticker": t,
            "company_name": stock.company_name,
            "industry": stock.industry,
            "is_cyclical": stock.is_cyclical,
            "sector_type": stock.sector_type,
            "current_price": cur_price,
            "zone": zone_class.zone,
            "zone_name_zh": zone_class.zone_name_zh,
            "color_hex": zone_class.color_hex,
            "two_doors_state": state_name,
            "margin_pct": margin_pct,
            "good_company_overall": overall_good,
            "good_company_badges": json.loads(good.badges_json or "[]") if good else [],
            "leading_score": f"{lead.green_count}/8" if lead else "0/8",
            "leading_status": lead.status if lead else "neutral",
            "eps_ttm": eps_rec.actual_eps if eps_rec else None,
            "eps_estimated": eps_rec.estimated_eps if eps_rec else None,
            "pe": pe_val,
            "pb": latest_p.pb if latest_p else None,
            "ps": latest_p.ps if latest_p else None,
            "revenue_yoy": rev.yoy if rev else None,
            "gross_margin": fin.gross_margin if fin else None,
            "operating_margin": fin.operating_margin if fin else None,
            "roe": fin.roe if fin else None,
            "bands": {
                "special": round(prices.p1, 1),
                "cheap": round(prices.p2, 1),
                "fair_mid": round(prices.p3, 1),
                "expensive": round(prices.p5, 1),
                "crazy": round(prices.p6, 1)
            },
            "extreme_valuation_flag": extreme_flag,
            "extreme_valuation_reason": extreme_reason
        })

    return {
        "count": len(comparison_items),
        "items": comparison_items,
        "disclaimer": "系統僅並排呈現各項財務指標與價位區，不排名、不推薦、無任何買賣指向。"
    }


# ----------------- 4. 歷史觸及與反彈紀錄獨立端點 (6.7) -----------------
@api_router.get("/stocks/{ticker}/historical-touches")
def get_stock_historical_touches(ticker: str, db: Session = Depends(get_db)):
    """取得個股過去 3 年觸及特價/便宜區記錄與歷史反彈幅度 (6.7)"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    prices_history = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.asc()).all()
    bands = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == ticker).order_by(ValuationBandsRecord.date.desc()).first()
    strat_hits = db.query(StrategyHit).filter(StrategyHit.ticker == ticker).all()

    a1 = bands.p1 if bands else 80.0
    a2 = bands.p2 if bands else 100.0

    hits_list = [{"date": sh.date.isoformat() if hasattr(sh.date, "isoformat") else str(sh.date), "strategy_id": sh.strategy_id, "badge_code": sh.badge_code} for sh in strat_hits]
    prices_raw = [{"date": p.date.isoformat(), "close": p.close, "high": getattr(p, "high", p.close), "low": getattr(p, "low", p.close)} for p in prices_history]

    report = analyze_historical_touches(
        daily_prices=prices_raw,
        a1_threshold=a1,
        a2_threshold=a2,
        strategy_hits=hits_list
    )
    report["ticker"] = ticker
    report["company_name"] = stock.company_name
    return report


# ----------------- 5. 個股詳情與河流圖 (Stock Detail) -----------------
@api_router.get("/stocks/{ticker}")
def get_stock_detail(ticker: str, metric: str = Query("auto", description="auto | pe | pb | ps"), db: Session = Depends(get_db)):
    """個股 1-5 完整資訊與河流圖"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    today_dt = date.today()
    latest_p = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.desc()).first()
    cur_price = latest_p.close if latest_p else 100.0

    # 取得最新計算結果
    good = db.query(GoodCompanyRecord).filter(GoodCompanyRecord.ticker == ticker).order_by(GoodCompanyRecord.date.desc()).first()
    eps_rec = db.query(EPSRecord).filter(EPSRecord.ticker == ticker).order_by(EPSRecord.created_at.desc()).first()
    lead = db.query(LeadingSummaryRecord).filter(LeadingSummaryRecord.ticker == ticker).order_by(LeadingSummaryRecord.date.desc()).first()
    bands = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == ticker).order_by(ValuationBandsRecord.date.desc()).first()

    # 自動推薦評價法 (規格書 6.4)
    if metric == "auto":
        if stock.is_cyclical or stock.sector_type == "financial":
            chosen_metric = "pb"
            metric_reason = "循環股或金融股預設採用 P/B 淨值比河流圖"
        else:
            chosen_metric = "pe"
            metric_reason = "一般成長股預設採用 P/E 本益比河流圖"
    else:
        chosen_metric = metric
        metric_reason = f"使用者手動指定採用 {metric.upper()}"

    # 計算河流圖五段價位線
    if chosen_metric == "pb":
        base_val = cur_price / (latest_p.pb or 1.5)
        vmin, vmax = 1.0, 3.5
    elif chosen_metric == "ps":
        base_val = cur_price / (latest_p.ps or 3.0)
        vmin, vmax = 1.5, 6.0
    else:
        base_val = eps_rec.estimated_eps or (eps_rec.actual_eps or 5.0) if eps_rec else 5.0
        vmin, vmax = 12.0, 26.0

    anchors = calculate_anchors(vmin, vmax)
    prices = calculate_river_prices(anchors, base_val)
    zone_class = classify_price_zone(cur_price, prices, TBD_CONFIG.zone_rule_version)

    # 規格書 8.9.4：頂部一句話結論條
    overall_good_zh = "好公司" if (good and good.overall == "good") else ("持續觀察" if (good and good.overall == "watch") else "基本面退化")
    lead_zh = "領先訊號轉強" if (lead and lead.status == "strengthening") else "訊號中性整理"
    conclusion_bar = f"【結論】{overall_good_zh}｜現價位於{zone_class.zone_name_zh}區（{zone_class.sub_zone_desc}）｜{lead_zh}｜安全邊際 {((prices.p2 - cur_price)/prices.p2*100):+.1f}%"

    # 評價法擴充：PEG 保守估值 (6.8c) 與 357 股利法 (6.8b)
    peg_val = calculate_peg_valuation(
        eps_ttm=eps_rec.actual_eps if (eps_rec and eps_rec.actual_eps) else 8.0,
        growth_rate_forecast=25.0,
        growth_rate_cagr_3y=20.0,
        is_cyclical=stock.is_cyclical,
        is_financial=(stock.sector_type == "financial")
    )
    div_357 = calculate_dividend_357(
        avg_5y_dividend=cur_price * 0.04,
        estimated_eps=base_val,
        avg_3y_payout_ratio=0.65,
        is_cyclical=stock.is_cyclical
    )

    # 歷史價格走勢模擬序列 (5 天)
    prices_history = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.asc()).all()
    history_points = [
        {
            "date": p.date.isoformat(),
            "close": p.close,
            "p1": round(prices.p1, 1),
            "p2": round(prices.p2, 1),
            "p3": round(prices.p3, 1),
            "p4": round(prices.p4, 1),
            "p5": round(prices.p5, 1),
            "p6": round(prices.p6, 1)
        }
        for p in prices_history
    ]

    # 歷史觸及與反彈紀錄 (規格書 6.7)
    strat_hits = db.query(StrategyHit).filter(StrategyHit.ticker == ticker).all()
    hits_list = [{"date": sh.date.isoformat() if hasattr(sh.date, "isoformat") else str(sh.date), "strategy_id": sh.strategy_id, "badge_code": sh.badge_code} for sh in strat_hits]
    prices_raw = [{"date": p.date.isoformat(), "close": p.close, "high": getattr(p, "high", p.close), "low": getattr(p, "low", p.close)} for p in prices_history]
    historical_touches_report = analyze_historical_touches(
        daily_prices=prices_raw,
        a1_threshold=prices.p1,
        a2_threshold=prices.p2,
        strategy_hits=hits_list
    )

    return {
        "ticker": ticker,
        "company_name": stock.company_name,
        "industry": stock.industry,
        "is_cyclical": stock.is_cyclical,
        "sector_type": stock.sector_type,
        "conclusion_bar": conclusion_bar,
        "current_price": cur_price,
        "zone": zone_class.zone,
        "zone_name_zh": zone_class.zone_name_zh,
        "sub_zone_desc": zone_class.sub_zone_desc,
        "color_hex": zone_class.color_hex,
        "is_buy_research_zone": zone_class.is_buy_research_zone,
        "is_warning_zone": zone_class.is_warning_zone,
        
        # 河流圖數據
        "river": {
            "metric": chosen_metric,
            "metric_reason": metric_reason,
            "base_value": round(base_val, 2),
            "anchors": {
                "a1": round(anchors.a1, 2), "a2": round(anchors.a2, 2),
                "a3": round(anchors.a3, 2), "a4": round(anchors.a4, 2),
                "a5": round(anchors.a5, 2), "a6": round(anchors.a6, 2)
            },
            "prices": {
                "p1_special": round(prices.p1, 1),
                "p2_cheap": round(prices.p2, 1),
                "p3_fair_low": round(prices.p3, 1),
                "p4_fair_high": round(prices.p4, 1),
                "p5_expensive": round(prices.p5, 1),
                "p6_crazy": round(prices.p6, 1)
            },
            "history": history_points
        },

        # 好公司六面向
        "good_company": {
            "overall": good.overall if good else "watch",
            "reasons": json.loads(good.reasons_json or "[]") if good else [],
            "badges": json.loads(good.badges_json or "[]") if good else [],
            "lights": {
                "revenue": good.revenue_light if good else "gray",
                "eps": good.eps_light if good else "gray",
                "margin": good.margin_light if good else "gray",
                "efficiency": good.efficiency_light if good else "gray",
                "cashflow": good.cashflow_light if good else "gray",
                "growth": good.growth_light if good else "gray"
            }
        },

        # EPS 引擎計算細節
        "eps_details": json.loads(eps_rec.calc_detail_json or "{}") if eps_rec else {},

        # 領先訊號
        "leading_signals": {
            "status": lead.status if lead else "neutral",
            "signals": json.loads(lead.signals_json or "[]") if lead else []
        },

        # 輔助評價法
        "alternative_valuations": {
            "peg": {
                "applicable": peg_val.is_applicable,
                "reason": peg_val.reason,
                "cheap": round(peg_val.p_cheap, 1),
                "fair": round(peg_val.p_fair, 1),
                "expensive": round(peg_val.p_expensive, 1)
            },
            "dividend_357": {
                "applicable": div_357.is_applicable,
                "reason": div_357.reason,
                "cheap": round(div_357.p_cheap, 1),
                "fair": round(div_357.p_fair, 1),
                "expensive": round(div_357.p_expensive, 1)
            }
        },

        # 歷史觸及與反彈紀錄 (規格書 6.7)
        "historical_touches": historical_touches_report
    }


# ----------------- 4. 我的觀察清單 (Watchlist) -----------------
@api_router.get("/watchlist")
def get_user_watchlist(user_id: str = "default_user", db: Session = Depends(get_db)):
    """取得使用者觀察清單分組與成員"""
    groups = db.query(WatchGroup).filter(WatchGroup.user_id == user_id).order_by(WatchGroup.sort_order.asc()).all()
    res = []
    today_dt = date.today()

    for g in groups:
        members = db.query(WatchGroupMember, StockMaster)\
            .join(StockMaster, WatchGroupMember.ticker == StockMaster.ticker)\
            .filter(WatchGroupMember.user_id == user_id, WatchGroupMember.group_id == g.group_id)\
            .all()
        
        m_list = []
        for m, s in members:
            p_row = db.query(PriceDaily).filter(PriceDaily.ticker == s.ticker).order_by(PriceDaily.date.desc()).first()
            b_row = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == s.ticker, ValuationBandsRecord.date == today_dt).first()
            m_list.append({
                "ticker": s.ticker,
                "company_name": s.company_name,
                "current_price": p_row.close if p_row else 100.0,
                "zone": b_row.current_zone if b_row else "fair",
                "note": m.note
            })

        res.append({
            "group_id": g.group_id,
            "name": g.name,
            "stocks": m_list
        })
    return res


@api_router.post("/watchlist/add")
def add_to_watchlist(group_id: str, ticker: str, note: Optional[str] = None, user_id: str = "default_user", db: Session = Depends(get_db)):
    """加入個股至觀察分組"""
    existing = db.query(WatchGroupMember)\
        .filter(WatchGroupMember.user_id == user_id, WatchGroupMember.group_id == group_id, WatchGroupMember.ticker == ticker)\
        .first()
    if existing:
        return {"success": False, "message": "已在該觀察分組中"}

    new_m = WatchGroupMember(user_id=user_id, group_id=group_id, ticker=ticker, note=note)
    db.add(new_m)
    db.commit()
    return {"success": True, "message": f"成功加入 {ticker} 至觀察清單"}


# ----------------- 5. 自選股加入與管理 (Custom Stocks) -----------------
@api_router.get("/custom-stocks")
def get_custom_stocks(user_id: str = "default_user", db: Session = Depends(get_db)):
    """列出自選股"""
    return list_custom_stocks(db, user_id=user_id)


@api_router.post("/custom-stocks/add")
def post_add_custom_stock(ticker: str, name: Optional[str] = None, user_id: str = "default_user", db: Session = Depends(get_db)):
    """加入新自選股"""
    return add_custom_stock(db, ticker=ticker, company_name=name, user_id=user_id)


@api_router.delete("/custom-stocks/{ticker}")
def delete_custom_stock(ticker: str, user_id: str = "default_user", db: Session = Depends(get_db)):
    """移除自選股"""
    return remove_custom_stock(db, ticker=ticker, user_id=user_id)


# ----------------- 6. 出場與檢視提醒 (Alerts) -----------------
@api_router.get("/alerts")
def get_alerts(user_id: str = "default_user", db: Session = Depends(get_db)):
    """取得出場檢視提醒清單"""
    return check_watchlist_exit_conditions(db, user_id=user_id)


# ----------------- 7. 手冊與詞典 (Manual & Glossary) -----------------
@api_router.get("/manual")
def get_manual_articles(db: Session = Depends(get_db)):
    """取得內建操作手冊章節"""
    arts = db.query(ManualArticle).all()
    return [
        {
            "id": a.article_id,
            "chapter": a.chapter,
            "title": a.title,
            "body": a.body_md,
            "screen": a.related_screen
        }
        for a in arts
    ]


@api_router.get("/glossary")
def get_glossary(db: Session = Depends(get_db)):
    """取得專有名詞詞典"""
    terms = db.query(GlossaryTerm).all()
    return [
        {
            "id": t.term_id,
            "term": t.term,
            "explain": t.plain_explain,
            "example": t.example
        }
        for t in terms
    ]


# ----------------- 8. LINE 推播測試 (LINE Push) -----------------
@api_router.post("/push/preview")
def preview_line_push(elder_mode: bool = False, db: Session = Depends(get_db)):
    """預覽今日收盤後推播內容"""
    return {
        "elder_mode": elder_mode,
        "content": format_daily_line_message(db, elder_mode=elder_mode)
    }


# ----------------- 9. 策略回測報告 (Backtest) -----------------
@api_router.get("/backtest")
def get_backtest_report(db: Session = Depends(get_db)):
    """取得領先訊號與兩道門回測驗證報告 (14.5)"""
    return run_strategy_backtest(db)


# ----------------- 10. 五階段檢核表與下單前五問 (Checklist 16.5, 16.6) -----------------
class ChecklistItemPayload(BaseModel):
    stage: str
    item_index: int = 0
    checked: bool = False
    note: Optional[str] = None

class ChecklistBatchPayload(BaseModel):
    items: List[ChecklistItemPayload]
    user_id: str = "default_user"


@api_router.get("/checklist/{ticker}")
def get_stock_checklist(ticker: str, user_id: str = "default_user", db: Session = Depends(get_db)):
    """取得個股之五階段檢核表與下單前 5 問（含勾選狀態與筆記）"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    records = db.query(ChecklistRecord).filter(
        ChecklistRecord.user_id == user_id,
        ChecklistRecord.ticker == ticker
    ).all()
    rec_map = {(r.stage, r.item_index): r for r in records}

    template = get_checklist_template()
    # 填充 pre_order
    pre_order_result = []
    for q in template["pre_order"]:
        key = ("pre_order", q["index"])
        rec = rec_map.get(key)
        pre_order_result.append({
            "index": q["index"],
            "question": q["question"],
            "hint": q["hint"],
            "checked": rec.checked if rec else False,
            "note": rec.note if rec else "",
            "updated_at": rec.updated_at.isoformat() if rec and rec.updated_at else None
        })

    # 填充 five_stages
    stages_result = []
    for s in template["five_stages"]:
        key = (s["stage"], s["index"])
        rec = rec_map.get(key)
        stages_result.append({
            "stage": s["stage"],
            "stage_name": s["stage_name"],
            "index": s["index"],
            "question": s["question"],
            "note_placeholder": s["note_placeholder"],
            "is_subjective": s["is_subjective"],
            "checked": rec.checked if rec else False,
            "note": rec.note if rec else "",
            "updated_at": rec.updated_at.isoformat() if rec and rec.updated_at else None
        })

    return {
        "ticker": ticker,
        "company_name": stock.company_name,
        "pre_order": pre_order_result,
        "five_stages": stages_result,
        "disclaimer": template["disclaimer"]
    }


@api_router.post("/checklist/{ticker}")
def update_stock_checklist(ticker: str, payload: ChecklistBatchPayload, db: Session = Depends(get_db)):
    """更新個股五階段檢核表或下單前五問之勾選狀態與備忘筆記"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    updated_count = 0
    for item in payload.items:
        rec = db.query(ChecklistRecord).filter(
            ChecklistRecord.user_id == payload.user_id,
            ChecklistRecord.ticker == ticker,
            ChecklistRecord.stage == item.stage,
            ChecklistRecord.item_index == item.item_index
        ).first()

        if rec:
            rec.checked = item.checked
            if item.note is not None:
                rec.note = item.note
        else:
            rec = ChecklistRecord(
                user_id=payload.user_id,
                ticker=ticker,
                stage=item.stage,
                item_index=item.item_index,
                checked=item.checked,
                note=item.note
            )
            db.add(rec)
        updated_count += 1

    db.commit()
    return {"success": True, "ticker": ticker, "updated_count": updated_count}
