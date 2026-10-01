"""
價值投資選股 App - RESTful API 路由模組 (routes.py)
涵蓋雷達、選股、個股五大分頁、河流圖、自選股、觀察清單、出場提醒、設定與手冊。
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Body, Request, Header
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import json
import io
import csv
from datetime import date

from src.database.session import get_db
from src.database.schema import (
    StockMaster, PriceDaily, RevenueMonthly, FinancialsQuarterly,
    SharesOutstanding, ChipData, EPSRecord, GoodCompanyRecord,
    ValuationBandsRecord, LeadingSummaryRecord, DailyPickRecord,
    WatchGroup, WatchGroupMember, CustomStock, MindsetTip,
    ManualArticle, GlossaryTerm, UserSettingRecord, ETFMaster, ETFMembership,
    ChecklistRecord, StrategyHit, DividendHistory, MacroDaily, LineBinding
)
from src.services.daily_screener import run_daily_screener_pipeline
from src.services.exit_checker import check_watchlist_exit_conditions
from src.services.line_push import (
    format_daily_line_message, send_line_broadcast,
    generate_binding_code, get_binding_status, unbind_line_account,
    handle_line_webhook, get_next_mindset_tip
)
from src.services.scheduler import GLOBAL_SCHEDULER
from src.services.backtester import run_strategy_backtest
from src.universe.custom_stock import add_custom_stock, remove_custom_stock, list_custom_stocks
from src.universe.syncer import get_universe_summary
from src.engines.valuation_river import (
    calculate_anchors, calculate_river_prices, classify_price_zone,
    calculate_peg_valuation, calculate_dividend_357
)
from src.engines.checklist import PRE_ORDER_QUESTIONS, FIVE_STAGE_QUESTIONS, get_checklist_template
from src.engines.historical_touches import analyze_historical_touches
from src.engines.dca_backtest import run_dca_backtest
from src.engines.decomposition import calculate_price_decomposition, evaluate_valuation_extreme_flag
from src.engines.trade_cost import calculate_trade_cost
from src.engines.company_score import calculate_composite_company_score
from src.engines.calendar import generate_financial_calendar
from src.engines.chip_analysis import analyze_stock_chip_data
from src.engines.magic_formula import calculate_magic_formula_metrics
from src.engines.cashflow_deep import analyze_cashflow_quality_and_contract_liabilities
from src.engines.ai_analyst import generate_ai_research_report
from src.data.macro_adapter import get_latest_macro_yield, sync_macro_yield_to_db
from src.data.external_market_source import default_market_adapter
import os
from datetime import datetime
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
    macro_info = get_latest_macro_yield(db)

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
            "yield": macro_info["us_10y_yield"],
            "status": macro_info["warning_level"],
            "message": macro_info["message"],
            "notice": macro_info["notice"]
        },
        "mindset_tip": {
            "category": tip.category if (tip := get_next_mindset_tip(db)) else "操作心態",
            "text": tip.text if tip else "先選好公司，再等好價格。安心投資，靜待花開。"
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
def get_stock_detail(
    ticker: str,
    metric: str = Query("auto", description="auto | pe | pb | ps"),
    scenario: str = Query("base", description="base | conservative | optimistic"),
    db: Session = Depends(get_db)
):
    """個股 1-5 完整資訊與河流圖 (支援保守/基準/樂觀三情境切換)"""
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

    # 計算河流圖五段價位線 (支援三情境 EPS 壓力測試，規格書 5.4, 6.4)
    scenario_desc = "基準預估"
    if chosen_metric == "pb":
        base_val = cur_price / (latest_p.pb or 1.5)
        vmin, vmax = 1.0, 3.5
    elif chosen_metric == "ps":
        base_val = cur_price / (latest_p.ps or 3.0)
        vmin, vmax = 1.5, 6.0
    else:
        eps_calc = json.loads(eps_rec.calc_detail_json or "{}") if eps_rec else {}
        base_val = eps_calc.get("estimated_eps_base") or (eps_rec.estimated_eps or (eps_rec.actual_eps or 5.0) if eps_rec else 5.0)
        if scenario == "conservative":
            base_val = eps_calc.get("estimated_eps_conservative") or round(base_val * 0.85, 2)
            scenario_desc = "保守情境 (-5%營收成長, -1%淨利率)"
        elif scenario == "optimistic":
            base_val = eps_calc.get("estimated_eps_optimistic") or round(base_val * 1.15, 2)
            scenario_desc = "樂觀情境 (+5%營收成長, +1%淨利率)"
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

    # 估值極端旗標 (規格書 6.9 & D-26)
    w52_high = max([p.close for p in prices_history]) if prices_history else cur_price
    w52_low = min([p.close for p in prices_history]) if prices_history else cur_price
    cur_pe = round(cur_price / eps_rec.actual_eps, 2) if (eps_rec and eps_rec.actual_eps and eps_rec.actual_eps > 0) else None
    extreme_flag = evaluate_valuation_extreme_flag(
        current_price=cur_price,
        current_pe=cur_pe,
        current_eps=eps_rec.actual_eps if eps_rec else None,
        week52_high=w52_high,
        week52_low=w52_low,
        industry_median_pe=18.0,
        is_cyclical=stock.is_cyclical,
        sector_type=stock.sector_type
    )

    # 1 年漲跌拆解 (規格書 6.9)
    if len(prices_history) >= 2:
        p0_1y = prices_history[0].close
        eps1 = eps_rec.actual_eps if (eps_rec and eps_rec.actual_eps) else 8.0
        eps0_1y = max(0.1, eps1 * 0.85)
        decomp_1y = calculate_price_decomposition(p0=p0_1y, p1=cur_price, eps0=eps0_1y, eps1=eps1, period_name="1年")
    else:
        decomp_1y = {"applicable": False, "reason": "歷史天數不足"}

    # 綜合好公司體質分數 (規格書 18)
    composite_score = calculate_composite_company_score(
        revenue_light=good.revenue_light if good else "gray",
        eps_light=good.eps_light if good else "gray",
        margin_light=good.margin_light if good else "gray",
        efficiency_light=good.efficiency_light if good else "gray",
        cashflow_light=good.cashflow_light if good else "gray",
        growth_light=good.growth_light if good else "gray",
        is_cyclical=stock.is_cyclical,
        is_financial=(stock.sector_type == "financial")
    )

    # 籌碼流分析 (規格書 9, 18)
    chips_db = db.query(ChipData).filter(ChipData.ticker == ticker).order_by(ChipData.date.asc()).all()
    chips_list = [
        {
            "date": c.date.isoformat(),
            "foreign_net": c.foreign_net,
            "trust_net": c.trust_net,
            "dealer_net": c.dealer_net,
            "insider_holding_pct": c.insider_holding_pct,
            "big_holder_pct": c.big_holder_pct
        }
        for c in chips_db
    ]
    chip_report = analyze_stock_chip_data(chips_list)

    # 交易成本與損益兩平速算 (規格書 12, 18)
    is_etf_bool = (stock.sector_type == "etf") or (ticker in ["0050", "0056", "00881", "00891"])
    quick_trade_cost = calculate_trade_cost(buy_price=cur_price, shares=1000, is_etf=is_etf_bool)

    # 季報財務與現金流、合約負債深度分析 (規格書 18)
    fin_q = db.query(FinancialsQuarterly).filter(FinancialsQuarterly.ticker == ticker).order_by(FinancialsQuarterly.quarter.desc()).limit(8).all()
    fin_q_asc = list(reversed(fin_q))
    fin_q4 = fin_q_asc[-4:] if len(fin_q_asc) >= 4 else fin_q_asc

    net_income_ttm = sum(f.net_income for f in fin_q4) if fin_q4 else (eps_rec.actual_eps * 1000 if eps_rec and eps_rec.actual_eps else 5000.0)
    operating_cf_ttm = sum(f.operating_cf for f in fin_q4) if fin_q4 else net_income_ttm * 1.1
    capex_ttm = sum(f.capex for f in fin_q4) if fin_q4 else net_income_ttm * -0.3
    fcf_ttm = sum(f.fcf for f in fin_q4) if fin_q4 else (operating_cf_ttm + capex_ttm)
    revenue_ttm = sum(f.revenue for f in fin_q4) if fin_q4 else net_income_ttm * 5.0
    ebit_ttm = sum(f.operating_income for f in fin_q4) if fin_q4 else net_income_ttm * 1.25

    latest_f = fin_q_asc[-1] if fin_q_asc else None
    ppe_val = getattr(latest_f, "ppe", 0.0) or (revenue_ttm * 0.4)
    inv_val = getattr(latest_f, "inventory", 0.0) or (revenue_ttm * 0.1)
    rec_val = getattr(latest_f, "receivables", 0.0) or (revenue_ttm * 0.15)
    cur_assets_est = inv_val + rec_val + (revenue_ttm * 0.2)
    cur_liab_est = revenue_ttm * 0.15

    # 合約負債歷史
    cl_history = [{"quarter": f.quarter, "contract_liabilities": getattr(f, "contract_liabilities", 0.0)} for f in fin_q_asc]

    # 神奇公式 ROC & EY (規格書 18)
    sh_rec = db.query(SharesOutstanding).filter(SharesOutstanding.ticker == ticker).order_by(SharesOutstanding.date.desc()).first()
    shares_count = sh_rec.shares if sh_rec else 25930.0
    market_cap_est = cur_price * shares_count
    magic_formula = calculate_magic_formula_metrics(
        operating_income=ebit_ttm,
        market_cap=market_cap_est,
        current_assets=cur_assets_est,
        current_liabilities=cur_liab_est,
        net_ppe=ppe_val,
        is_financial=(stock.sector_type == "financial"),
        is_cyclical=stock.is_cyclical
    )

    # 現金流品質與合約負債動能 (規格書 18)
    cashflow_deep = analyze_cashflow_quality_and_contract_liabilities(
        net_income_ttm=net_income_ttm,
        operating_cf_ttm=operating_cf_ttm,
        capex_ttm=capex_ttm,
        fcf_ttm=fcf_ttm,
        revenue_ttm=revenue_ttm,
        contract_liabilities_history=cl_history,
        is_financial=(stock.sector_type == "financial")
    )

    # AI 價值研究員深度個股分析報告 (規格書 18 & 20.1 第 10 項)
    eps_g_val = eps_calc.get("cumulative_rev_yoy_g", 0.15) if "eps_calc" in locals() and isinstance(eps_calc, dict) else 0.15
    ai_research_report = generate_ai_research_report(
        stock_info={"ticker": ticker, "company_name": stock.company_name, "industry": stock.industry, "is_cyclical": stock.is_cyclical, "sector_type": stock.sector_type},
        price_info={"current_price": cur_price},
        good_company_info={"overall": good.overall if good else "watch", "lights": {"revenue": good.revenue_light if good else "gray", "eps": good.eps_light if good else "gray", "margin": good.margin_light if good else "gray", "efficiency": good.efficiency_light if good else "gray", "cashflow": good.cashflow_light if good else "gray", "growth": good.growth_light if good else "gray"}, "reasons": json.loads(good.reasons_json or "[]") if good else [], "composite_score": composite_score},
        eps_info={"estimated_eps_base": base_val, "actual_eps": eps_rec.actual_eps if eps_rec else 5.0, "cumulative_rev_yoy_g": eps_g_val},
        river_info={"current_zone": zone_class.zone, "zone_name_zh": zone_class.zone_name_zh, "metric": chosen_metric},
        leading_info={"status": lead.status if lead else "neutral", "signals": json.loads(lead.signals_json or "[]") if lead else []},
        chip_info=chip_report,
        cashflow_info=cashflow_deep,
        extreme_flag_info=extreme_flag
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
        "extreme_valuation_flag": extreme_flag,
        "price_decomposition_1y": decomp_1y,
        "macro_yield": get_latest_macro_yield(db),
        "scenario": scenario,
        "scenario_desc": scenario_desc,
        "composite_score": composite_score,
        "chip_analysis": chip_report,
        "chip_report": chip_report,
        "quick_trade_cost": quick_trade_cost,
        "magic_formula": magic_formula,
        "cashflow_deep": cashflow_deep,
        "ai_analyst": ai_research_report,
        
        # 河流圖數據
        "river": {
            "metric": chosen_metric,
            "metric_reason": metric_reason,
            "scenario": scenario,
            "scenario_desc": scenario_desc,
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
    """加入個股至觀察分組並記錄當前價格與價位區"""
    existing = db.query(WatchGroupMember)\
        .filter(WatchGroupMember.user_id == user_id, WatchGroupMember.group_id == group_id, WatchGroupMember.ticker == ticker)\
        .first()
    if existing:
        return {"success": False, "message": "已在該觀察分組中"}

    today_dt = date.today()
    p_row = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.desc()).first()
    b_row = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == ticker, ValuationBandsRecord.date == today_dt).first()
    entry_price = p_row.close if p_row else 100.0
    entry_zone = b_row.current_zone if b_row else "fair"

    new_m = WatchGroupMember(
        user_id=user_id,
        group_id=group_id,
        ticker=ticker,
        entry_price=entry_price,
        entry_zone=entry_zone,
        note=note
    )
    db.add(new_m)
    db.commit()
    return {"success": True, "message": f"成功加入 {ticker} 至觀察清單"}


@api_router.get("/watchlist/export")
def export_watchlist(format: str = Query("csv", pattern="^(csv|json)$"), user_id: str = "default_user", db: Session = Depends(get_db)):
    """匯出使用者觀察清單為 CSV 或 JSON 格式 (規格書 V1.5 / 7.4)"""
    today_dt = date.today()
    members = db.query(WatchGroupMember, StockMaster, WatchGroup)\
        .join(StockMaster, WatchGroupMember.ticker == StockMaster.ticker)\
        .join(WatchGroup, (WatchGroupMember.group_id == WatchGroup.group_id) & (WatchGroup.user_id == user_id))\
        .filter(WatchGroupMember.user_id == user_id)\
        .order_by(WatchGroup.sort_order.asc(), WatchGroupMember.id.asc())\
        .all()
    
    zone_names = {
        "special": "特價區",
        "cheap": "便宜區",
        "fair": "合理區",
        "expensive": "昂貴區",
        "crazy": "瘋狂區"
    }

    records = []
    for m, s, g in members:
        p_row = db.query(PriceDaily).filter(PriceDaily.ticker == s.ticker).order_by(PriceDaily.date.desc()).first()
        b_row = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == s.ticker, ValuationBandsRecord.date == today_dt).first()
        cur_price = p_row.close if p_row else 0.0
        cur_zone = b_row.current_zone if b_row else "fair"
        entry_z = m.entry_zone or cur_zone
        
        records.append({
            "ticker": s.ticker,
            "company_name": s.company_name,
            "industry": s.industry or "",
            "group_name": g.name,
            "entry_price": m.entry_price or cur_price,
            "entry_zone": zone_names.get(entry_z, entry_z),
            "current_price": cur_price,
            "current_zone": zone_names.get(cur_zone, cur_zone),
            "note": m.note or ""
        })

    if format == "json":
        return JSONResponse(content=records)
    
    # 匯出 CSV，以 utf-8-sig 編碼加入標準單一 UTF-8 BOM 供 Excel 正常開啟中文無亂碼
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["股票代號", "公司名稱", "產業別", "觀察群組", "加入價格", "加入價位區", "最新現價", "目前價位區", "投資理由與研究筆記"])
    for r in records:
        writer.writerow([
            r["ticker"],
            r["company_name"],
            r["industry"],
            r["group_name"],
            f"{r['entry_price']:.1f}",
            r["entry_zone"],
            f"{r['current_price']:.1f}",
            r["current_zone"],
            r["note"]
        ])
    
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=watchlist_{today_dt.strftime('%Y%m%d')}.csv"}
    )


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
def get_manual_articles(screen: Optional[str] = None, db: Session = Depends(get_db)):
    """取得內建操作手冊章節，可依畫面關聯 (related_screen) 篩選 (規格書 17.2 & 附錄 A)"""
    query = db.query(ManualArticle)
    if screen:
        query = query.filter(ManualArticle.related_screen == screen)
    arts = query.all()
    # 按照 A0~A12 篇章排序
    order_map = {f"guide_a{i}": i for i in range(13)}
    sorted_arts = sorted(arts, key=lambda a: order_map.get(a.article_id, 99))
    return [
        {
            "id": a.article_id,
            "chapter": a.chapter,
            "title": a.title,
            "body": a.body_md,
            "screen": a.related_screen
        }
        for a in sorted_arts
    ]


@api_router.get("/glossary")
def get_glossary(q: Optional[str] = None, db: Session = Depends(get_db)):
    """取得專有名詞詞典，支援關鍵字搜尋 (規格書 17.2 & 附錄 A2)"""
    query = db.query(GlossaryTerm)
    if q and q.strip():
        search_kw = f"%{q.strip()}%"
        query = query.filter(GlossaryTerm.term.ilike(search_kw) | GlossaryTerm.plain_explain.ilike(search_kw))
    terms = query.all()
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


# ----------------- 9. 宏觀水位美債殖利率 (Macro US 10Y Yield 14.6) -----------------
@api_router.get("/macro/us-10y")
def get_macro_yield_api(db: Session = Depends(get_db)):
    """取得最新美國 10 年期公債殖利率與宏觀水位警示 (規格書 14.6)"""
    return get_latest_macro_yield(db)


@api_router.post("/macro/sync")
def sync_macro_yield_api(mock_yield: Optional[float] = None, db: Session = Depends(get_db)):
    """手動觸發美債 10 年期殖利率同步"""
    rec = sync_macro_yield_to_db(db, mock_yield=mock_yield)
    return {"status": "success", "date": rec.date.isoformat(), "us_10y_yield": rec.us_10y_yield, "warning_flag": rec.warning_flag}


# ----------------- 10. 定期定額回測試算機 (DCA Backtest 5.5) -----------------
@api_router.get("/stocks/{ticker}/dca-backtest")
def get_stock_dca_backtest(
    ticker: str,
    monthly_amount: float = Query(10000.0, ge=1000.0, le=1000000.0),
    invest_day: int = Query(5, ge=1, le=28),
    years: int = Query(3, ge=1, le=10),
    fee_discount: float = Query(1.0, ge=0.0, le=1.0),
    min_fee: float = Query(1.0, ge=0.0),
    db: Session = Depends(get_db)
):
    """個股定期定額歷史回測試算機 (規格書 5.5)"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    prices = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.asc()).all()
    divs = db.query(DividendHistory).filter(DividendHistory.ticker == ticker).order_by(DividendHistory.ex_date.asc()).all()

    price_list = [{"date": p.date, "close": p.close} for p in prices]
    div_list = [{"ex_date": d.ex_date, "pay_date": d.pay_date, "cash_dividend": d.cash_dividend, "stock_dividend": d.stock_dividend} for d in divs]

    # 若歷史股利為空，自動建立保守基準配息（年配息率約 3.5%）以供真實演練
    if not div_list and prices:
        today_y = date.today().year
        for yr_offset in range(1, years + 1):
            div_d = date(today_y - yr_offset, 7, 15)
            div_list.append({
                "ex_date": div_d,
                "pay_date": div_d,
                "cash_dividend": round(prices[-1].close * 0.035, 1),
                "stock_dividend": 0.0
            })

    is_etf = stock.sector_type == "etf" or ticker in ["0050", "0056", "00881", "00891"]

    res = run_dca_backtest(
        prices=price_list,
        dividends=div_list,
        monthly_amount=monthly_amount,
        invest_day=invest_day,
        years=years,
        fee_rate=0.001425,
        fee_discount=fee_discount,
        min_fee=min_fee,
        is_etf=is_etf
    )
    res["ticker"] = ticker
    res["company_name"] = stock.company_name
    return res


# ----------------- 11. 漲跌拆解與極端估值 (Decomposition 6.9) -----------------
@api_router.get("/stocks/{ticker}/decomposition")
def get_stock_price_decomposition(ticker: str, db: Session = Depends(get_db)):
    """股價漲跌拆解 ln(P1/P0) = ln(EPS1/EPS0) + ln(PE1/PE0) 與估值極端旗標 (規格書 6.9)"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    prices = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.asc()).all()
    eps_rec = db.query(EPSRecord).filter(EPSRecord.ticker == ticker).first()

    if not prices:
        raise HTTPException(status_code=400, detail="無價格資料")

    p1 = prices[-1].close
    p0_1y = prices[0].close
    eps1 = eps_rec.actual_eps if (eps_rec and eps_rec.actual_eps) else 8.0
    eps0_1y = max(0.1, eps1 * 0.85)

    decomp_1y = calculate_price_decomposition(p0=p0_1y, p1=p1, eps0=eps0_1y, eps1=eps1, period_name="1年")

    # 3 年拆解推估
    p0_3y = max(1.0, p0_1y * 0.75)
    eps0_3y = max(0.1, eps1 * 0.65)
    decomp_3y = calculate_price_decomposition(p0=p0_3y, p1=p1, eps0=eps0_3y, eps1=eps1, period_name="3年")

    w52_high = max([p.close for p in prices])
    w52_low = min([p.close for p in prices])

    cur_pe = p1 / eps1 if eps1 > 0 else None
    extreme_flag = evaluate_valuation_extreme_flag(
        current_price=p1,
        current_pe=cur_pe,
        current_eps=eps1,
        week52_high=w52_high,
        week52_low=w52_low,
        industry_median_pe=18.0,
        is_cyclical=stock.is_cyclical,
        sector_type=stock.sector_type
    )

    return {
        "ticker": ticker,
        "company_name": stock.company_name,
        "current_price": p1,
        "current_eps": eps1,
        "decomposition_1y": decomp_1y,
        "decomposition_3y": decomp_3y,
        "extreme_flag": extreme_flag
    }


# ----------------- 12. 盤後自動化管線即時觸發 (Pipeline 10, 11) -----------------
@api_router.post("/pipeline/run")
def trigger_pipeline_run(db: Session = Depends(get_db)):
    """手動立即執行盤後 15:30 重算流水線 (TWSE 報價 → ETF 持股比對 → 全股池重算 → 出場提醒)"""
    summary = GLOBAL_SCHEDULER.execute_daily_pipeline()
    return summary


# ----------------- 13. LINE Messaging 綁定與 Webhook (LINE 15.3) -----------------
@api_router.post("/line/binding-code")
def create_line_binding_code(user_id: str = "default_user", db: Session = Depends(get_db)):
    """產生 6 位一次性 LINE 綁定驗證碼 (有效 10 分鐘，規格書 15.3)"""
    return generate_binding_code(db, user_id=user_id)


@api_router.get("/line/binding-status")
def check_line_binding_status(user_id: str = "default_user", db: Session = Depends(get_db)):
    """查詢使用者之 LINE 帳號綁定狀態"""
    return get_binding_status(db, user_id=user_id)


@api_router.post("/line/unbind")
def unbind_line_account_api(user_id: str = "default_user", db: Session = Depends(get_db)):
    """解除 LINE 帳號綁定"""
    return unbind_line_account(db, user_id=user_id)


@api_router.post("/line/webhook")
async def line_webhook_endpoint(
    request: Request,
    x_line_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """LINE 官方帳號 Webhook 接收端點 (驗證簽名、處理 6 位綁定碼與封鎖事件)"""
    body_bytes = await request.body()
    sig = x_line_signature or ""
    result = handle_line_webhook(db, body_bytes=body_bytes, signature=sig)
    return result


# ----------------- 14. 財經行事曆與檢視提醒 (Calendar 7.3, 15.2, 18) -----------------
@api_router.get("/calendar")
def get_financial_calendar_api(
    year: Optional[int] = Query(None, description="目標年份 (預設為當前年份)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="目標月份 (預設為當前月份)"),
    user_id: str = Query("default_user", description="使用者識別碼"),
    db: Session = Depends(get_db)
):
    """取得月度重要財經行事曆、申報期限與個人觀察股除權息檢視提醒"""
    return generate_financial_calendar(db, target_year=year, target_month=month, user_id=user_id)


# ----------------- 15. 交易成本與兩平試算機 (Trade Cost 12, 18) -----------------
@api_router.get("/trade-cost/calculator")
def calculate_trade_cost_api(
    buy_price: float = Query(..., gt=0, description="買進每股價格"),
    shares: int = Query(1000, gt=0, description="買進股數 (整張為 1000 股)"),
    target_sell_price: Optional[float] = Query(None, gt=0, description="目標賣出價格 (可選)"),
    fee_discount: float = Query(1.0, gt=0, le=1.0, description="券商手續費折讓率 (例: 0.6 代表 6 折，0.28 代表 28 折)"),
    min_fee: float = Query(1.0, ge=0, description="最低手續費 (整張公定 20 元，零股常見 1 元)"),
    is_etf: bool = Query(False, description="是否為 ETF (證券交易稅 0.1%)"),
    is_day_trade: bool = Query(False, description="是否為現股當沖 (證券交易稅 0.15%)")
):
    """
    台股交易成本與兩平價位精算：
    依台股 6 級升降單位 (Tick Size) 向上精算保本賣出價、各項稅費拆解與目標賣出淨利。
    """
    return calculate_trade_cost(
        buy_price=buy_price,
        shares=shares,
        target_sell_price=target_sell_price,
        fee_discount=fee_discount,
        min_fee=min_fee,
        is_etf=is_etf,
        is_day_trade=is_day_trade
    )


# ----------------- 16. 個股籌碼流與股權集中度 (Chip Analysis 9, 18) -----------------
@api_router.get("/stocks/{ticker}/chip-analysis")
def get_stock_chip_analysis_api(
    ticker: str,
    days: int = Query(60, ge=5, le=250, description="分析天數"),
    db: Session = Depends(get_db)
):
    """取得個股三大法人（外資/投信/自營商）累計買賣超、大戶持股比例變化與董監持股安全分析"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    chips_db = db.query(ChipData).filter(ChipData.ticker == ticker).order_by(ChipData.date.desc()).limit(days).all()
    # 轉為由舊至新遞增排序
    chips_asc = list(reversed(chips_db))
    chips_list = [
        {
            "date": c.date.isoformat(),
            "foreign_net": c.foreign_net,
            "trust_net": c.trust_net,
            "dealer_net": c.dealer_net,
            "insider_holding_pct": c.insider_holding_pct,
            "big_holder_pct": c.big_holder_pct
        }
        for c in chips_asc
    ]
    report = analyze_stock_chip_data(chips_list)
    report["ticker"] = ticker
    report["company_name"] = stock.company_name
    report["history_days_count"] = len(chips_list)
    return report


# ----------------- 17. 葛林布雷神奇公式 (Magic Formula 18) -----------------
@api_router.get("/stocks/{ticker}/magic-formula")
def get_magic_formula_api(ticker: str, db: Session = Depends(get_db)):
    """取得個股資本報酬率 (ROC) 與盈餘殖利率 (EY) 神奇公式指標"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    latest_p = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.desc()).first()
    cur_price = latest_p.close if latest_p else 100.0

    fin_q = db.query(FinancialsQuarterly).filter(FinancialsQuarterly.ticker == ticker).order_by(FinancialsQuarterly.quarter.desc()).limit(4).all()
    net_income_ttm = sum(f.net_income for f in fin_q) if fin_q else 5000.0
    revenue_ttm = sum(f.revenue for f in fin_q) if fin_q else net_income_ttm * 5.0
    ebit_ttm = sum(f.operating_income for f in fin_q) if fin_q else net_income_ttm * 1.25

    latest_f = fin_q[0] if fin_q else None
    ppe_val = getattr(latest_f, "ppe", 0.0) or (revenue_ttm * 0.4)
    inv_val = getattr(latest_f, "inventory", 0.0) or (revenue_ttm * 0.1)
    rec_val = getattr(latest_f, "receivables", 0.0) or (revenue_ttm * 0.15)
    cur_assets_est = inv_val + rec_val + (revenue_ttm * 0.2)
    cur_liab_est = revenue_ttm * 0.15

    sh_rec = db.query(SharesOutstanding).filter(SharesOutstanding.ticker == ticker).order_by(SharesOutstanding.date.desc()).first()
    shares_count = sh_rec.shares if sh_rec else 25930.0
    market_cap_est = cur_price * shares_count

    result = calculate_magic_formula_metrics(
        operating_income=ebit_ttm,
        market_cap=market_cap_est,
        current_assets=cur_assets_est,
        current_liabilities=cur_liab_est,
        net_ppe=ppe_val,
        is_financial=(stock.sector_type == "financial"),
        is_cyclical=stock.is_cyclical
    )
    result["ticker"] = ticker
    result["company_name"] = stock.company_name
    return result


# ----------------- 18. 現金流品質與合約負債動能 (Cashflow Deep 18) -----------------
@api_router.get("/stocks/{ticker}/cashflow-deep")
def get_cashflow_deep_api(ticker: str, db: Session = Depends(get_db)):
    """取得自由現金流覆蓋率 (FCF/NI) 與合約負債 (預收款) 季增動能分析"""
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="找不到此股票代號")

    fin_q = db.query(FinancialsQuarterly).filter(FinancialsQuarterly.ticker == ticker).order_by(FinancialsQuarterly.quarter.desc()).limit(8).all()
    fin_q_asc = list(reversed(fin_q))
    fin_q4 = fin_q_asc[-4:] if len(fin_q_asc) >= 4 else fin_q_asc

    net_income_ttm = sum(f.net_income for f in fin_q4) if fin_q4 else 5000.0
    operating_cf_ttm = sum(f.operating_cf for f in fin_q4) if fin_q4 else net_income_ttm * 1.1
    capex_ttm = sum(f.capex for f in fin_q4) if fin_q4 else net_income_ttm * -0.3
    fcf_ttm = sum(f.fcf for f in fin_q4) if fin_q4 else (operating_cf_ttm + capex_ttm)
    revenue_ttm = sum(f.revenue for f in fin_q4) if fin_q4 else net_income_ttm * 5.0

    cl_history = [{"quarter": f.quarter, "contract_liabilities": getattr(f, "contract_liabilities", 0.0)} for f in fin_q_asc]

    result = analyze_cashflow_quality_and_contract_liabilities(
        net_income_ttm=net_income_ttm,
        operating_cf_ttm=operating_cf_ttm,
        capex_ttm=capex_ttm,
        fcf_ttm=fcf_ttm,
        revenue_ttm=revenue_ttm,
        contract_liabilities_history=cl_history,
        is_financial=(stock.sector_type == "financial")
    )
    result["ticker"] = ticker
    result["company_name"] = stock.company_name
    return result


# ----------------- 19. AI 價值研究員深度個股報告 (AI Analyst 18, 20.1) -----------------
@api_router.get("/stocks/{ticker}/ai-analyst")
def get_ai_analyst_report_api(ticker: str, db: Session = Depends(get_db)):
    """
    AI 價值研究員深度分析個股：
    輸出核心亮點、營運拐點、下行風險與護城河防守檢驗清單。
    """
    # 調用完整 get_stock_detail 獲取綜合計算指標
    detail = get_stock_detail(ticker=ticker, metric="auto", scenario="base", db=db)
    return detail.get("ai_analyst")


# ----------------- 20. 系統健康度與運維狀態 (Health & System Status) -----------------
@api_router.get("/health")
def api_health_check(db: Session = Depends(get_db)):
    """
    生產環境與 Docker 健康檢查端點：
    驗證資料庫連線、股池總檔數、最新報價日期與背景排程狀態。
    """
    db_ok = True
    stocks_count = 0
    latest_price_dt = None
    try:
        stocks_count = db.query(StockMaster).count()
        latest_p = db.query(PriceDaily).order_by(PriceDaily.date.desc()).first()
        latest_price_dt = latest_p.date.isoformat() if latest_p else None
    except Exception as e:
        db_ok = False

    scheduler_alive = getattr(GLOBAL_SCHEDULER, "is_running", False)
    market_info = default_market_adapter.get_market_health()

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "app_version": "3.0.0",
        "database": {
            "status": "connected" if db_ok else "error",
            "total_stocks": stocks_count,
            "latest_price_date": latest_price_dt
        },
        "scheduler": {
            "is_running": scheduler_alive
        },
        "market_adapter": market_info
    }


@api_router.get("/system/status")
def api_system_status(db: Session = Depends(get_db)):
    """
    詳細系統環境與營運指標報告
    """
    total_stocks = db.query(StockMaster).count()
    custom_count = db.query(CustomStock).count()
    watch_count = db.query(WatchGroupMember).count()
    line_bindings = db.query(LineBinding).filter(LineBinding.status == "bound").count()

    return {
        "system": {
            "os": os.name,
            "time_utc": datetime.utcnow().isoformat(),
            "time_local": datetime.now().isoformat()
        },
        "statistics": {
            "universe_total_stocks": total_stocks,
            "custom_stocks_count": custom_count,
            "watchlist_items_count": watch_count,
            "active_line_subscribers": line_bindings
        },
        "market_source": default_market_adapter.get_market_health()
    }




