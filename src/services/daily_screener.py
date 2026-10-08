"""
價值投資選股 App - 每日選股、兩道門四象限與精選服務 (daily_screener.py)
遵循技術規格書 V1.7：
- 第 3 章 兩道門模型與四象限狀態分類
- 第 14.4 節 領先狀態彙整
- 第 15.1 節 每日價值精選與早期轉強排序 (收盤後計算)
- 第 7.2 節 出場檢查與提醒
"""

from datetime import date, datetime
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from src.database.schema import (
    StockMaster, PriceDaily, RevenueMonthly, FinancialsQuarterly,
    SharesOutstanding, ChipData, EPSRecord, GoodCompanyRecord,
    ValuationBandsRecord, LeadingSummaryRecord, DailyPickRecord, StrategyHit
)
from src.engines.valuation_river import (
    calculate_anchors, calculate_river_prices, classify_price_zone, RiverPrices
)
from src.engines.eps_engine import calculate_six_step_eps
from src.engines.good_company import (
    evaluate_revenue_dimension, evaluate_eps_dimension,
    evaluate_margins_dimension, evaluate_efficiency_dimension,
    evaluate_cashflow_dimension, evaluate_growth_or_dividend_dimension,
    evaluate_good_company
)
from src.engines.leading_signals import (
    evaluate_l1_revenue_accel, evaluate_l2_contract_liabilities,
    evaluate_l3_inventory_vs_revenue, evaluate_l4_capex_growth,
    evaluate_l5_insider_holding, evaluate_l6_institutional_funds,
    evaluate_l7_kd_strength, evaluate_l8_material_keywords,
    summarize_leading_signals
)
from config.tbd_params import TBD_CONFIG

def run_daily_screener_pipeline(db: Session, target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    執行每日收盤後全股池批次計算流水線
    """
    from config.settings import SETTINGS
    if not SETTINGS.DEMO_MODE:
        from src.services.market_evidence import data_quality_report
        return {"status": "insufficient", "processed": 0, "daily_picks": [],
                "reason": "正式資料尚不足以計算好公司與估值，保留舊紀錄但不產生新精選。",
                "quality": data_quality_report(db)}
    calc_date = target_date or date.today()
    stocks = db.query(StockMaster).all()

    processed_stocks = []
    daily_picks = []
    early_picks = []

    for stock in stocks:
        t = stock.ticker
        # 1. 取得最新日行情
        latest_price_rec = db.query(PriceDaily)\
            .filter(PriceDaily.ticker == t)\
            .order_by(PriceDaily.date.desc())\
            .first()
        if not latest_price_rec:
            continue
        cur_price = latest_price_rec.close
        cur_volume = latest_price_rec.volume

        # 2. 取得營收與季報歷史
        rev_records = db.query(RevenueMonthly)\
            .filter(RevenueMonthly.ticker == t)\
            .order_by(RevenueMonthly.month.asc())\
            .all()
        q_records = db.query(FinancialsQuarterly)\
            .filter(FinancialsQuarterly.ticker == t)\
            .order_by(FinancialsQuarterly.quarter.asc())\
            .all()
        sh_record = db.query(SharesOutstanding)\
            .filter(SharesOutstanding.ticker == t)\
            .order_by(SharesOutstanding.date.desc())\
            .first()
        shares = sh_record.shares if sh_record else 1000.0

        # 3. 執行 EPS 引擎
        cum_g = rev_records[-1].cumulative_yoy if rev_records else 0.10
        ttm_revs = [q.revenue for q in q_records[-4:]] if len(q_records) >= 4 else [25.0]*4
        ttm_nis = [q.net_income for q in q_records[-4:]] if len(q_records) >= 4 else [5.0]*4
        ttm_non_ops = [q.non_operating_income for q in q_records[-4:]] if len(q_records) >= 4 else [0.1]*4
        prior_rev = sum(r.revenue for r in rev_records[-12:]) if len(rev_records) >= 12 else sum(ttm_revs)

        eps_res = calculate_six_step_eps(
            ticker=t,
            estimate_year=calc_date.year,
            cumulative_rev_yoy_g=cum_g,
            prior_full_year_revenue=prior_rev,
            ttm_revenues=ttm_revs,
            ttm_net_incomes=ttm_nis,
            ttm_non_operating_incomes=ttm_non_ops,
            shares_outstanding=shares,
            is_cyclical=stock.is_cyclical,
            is_financial=(stock.sector_type == "financial"),
            quarters_count=len(q_records)
        )

        # 清除當日舊紀錄
        db.query(EPSRecord).filter(EPSRecord.ticker == t, EPSRecord.estimate_year == calc_date.year).delete()
        eps_record = EPSRecord(
            ticker=t,
            period=f"{calc_date.year}",
            actual_eps=eps_res.actual_eps_ttm,
            ttm_eps=eps_res.actual_eps_ttm,
            estimated_eps=eps_res.estimated_eps,
            estimate_year=calc_date.year,
            estimate_method=eps_res.estimate_method,
            confidence_flag=eps_res.confidence_flag,
            calc_detail_json=json.dumps(eps_res.to_dict(), ensure_ascii=False)
        )
        db.add(eps_record)

        # 4. 執行好公司引擎
        d_rev = evaluate_revenue_dimension(
            cumulative_yoy=cum_g,
            recent_4q_yoys=[0.15, 0.18, 0.20, cum_g]
        )
        d_eps = evaluate_eps_dimension(
            annual_eps_3y=[eps_res.actual_eps_ttm*0.8 if eps_res.actual_eps_ttm else 3.0,
                           eps_res.actual_eps_ttm*0.9 if eps_res.actual_eps_ttm else 3.5,
                           eps_res.actual_eps_ttm or 4.0],
            estimated_eps_current=eps_res.estimated_eps
        )
        d_mar = evaluate_margins_dimension(
            gross_margins=[q.gross_margin for q in q_records[-4:]] if q_records else [0.45]*4,
            operating_margins=[q.operating_margin for q in q_records[-4:]] if q_records else [0.30]*4,
            net_margins=[q.net_margin for q in q_records[-4:]] if q_records else [0.25]*4,
            is_financial=(stock.sector_type == "financial")
        )
        d_eff = evaluate_efficiency_dimension(
            roe=q_records[-1].roe if q_records else 15.0,
            is_financial=(stock.sector_type == "financial")
        )
        d_cf = evaluate_cashflow_dimension(
            operating_cf_4q=[q.operating_cf for q in q_records[-4:]] if q_records else [50.0]*4,
            free_cf_4q=[q.fcf for q in q_records[-4:]] if q_records else [20.0]*4
        )
        d_growth = evaluate_growth_or_dividend_dimension(capex_growth_pct=15.0)

        good_res = evaluate_good_company(
            ticker=t,
            dim_revenue=d_rev,
            dim_eps=d_eps,
            dim_margin=d_mar,
            dim_efficiency=d_eff,
            dim_cashflow=d_cf,
            dim_growth_div=d_growth,
            previously_good=True
        )

        db.query(GoodCompanyRecord).filter(GoodCompanyRecord.ticker == t, GoodCompanyRecord.date == calc_date).delete()
        good_record = GoodCompanyRecord(
            ticker=t,
            date=calc_date,
            revenue_light=good_res.revenue_light,
            eps_light=good_res.eps_light,
            margin_light=good_res.margin_light,
            efficiency_light=good_res.efficiency_light,
            cashflow_light=good_res.cashflow_light,
            growth_light=good_res.growth_or_dividend_light,
            overall=good_res.overall,
            reasons_json=json.dumps(good_res.reasons, ensure_ascii=False),
            badges_json=json.dumps(good_res.badges, ensure_ascii=False)
        )
        db.add(good_record)

        # 5. 執行估值河流圖引擎
        if stock.is_cyclical or stock.sector_type == "financial":
            metric = "pb"
            base_val = cur_price / (latest_price_rec.pb or 1.5)
            vmin, vmax = 1.0, 3.5
        else:
            metric = "pe"
            base_val = eps_res.estimated_eps or (eps_res.actual_eps_ttm or 5.0)
            vmin, vmax = 12.0, 26.0

        anchors = calculate_anchors(vmin, vmax)
        prices = calculate_river_prices(anchors, base_val)
        zone_info = classify_price_zone(cur_price, prices, TBD_CONFIG.zone_rule_version)

        db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == t, ValuationBandsRecord.date == calc_date).delete()
        bands_record = ValuationBandsRecord(
            ticker=t,
            date=calc_date,
            metric=metric,
            variant="forecast" if eps_res.estimated_eps else "rolling",
            estimate_year=calc_date.year,
            v_min=vmin,
            v_max=vmax,
            delta=anchors.delta,
            a1=anchors.a1, a2=anchors.a2, a3=anchors.a3, a4=anchors.a4, a5=anchors.a5, a6=anchors.a6,
            p1=prices.p1, p2=prices.p2, p3=prices.p3, p4=prices.p4, p5=prices.p5, p6=prices.p6,
            current_zone=zone_info.zone,
            zone_rule_version=TBD_CONFIG.zone_rule_version
        )
        db.add(bands_record)

        # 6. 執行領先訊號引擎
        l1 = evaluate_l1_revenue_accel([r.yoy for r in rev_records[-12:]] if len(rev_records) >= 6 else [0.10]*12)
        l2 = evaluate_l2_contract_liabilities([q.contract_liabilities for q in q_records[-4:]] if q_records else [10.0]*4)
        l3 = evaluate_l3_inventory_vs_revenue(inventory_yoy=0.08, revenue_yoy=0.15)
        l4 = evaluate_l4_capex_growth(capex_quarterly_growth=0.15, revenue_growing=True)
        l5 = evaluate_l5_insider_holding(insider_diff_pct=0.2)
        l6 = evaluate_l6_institutional_funds(foreign_net_20d=2500.0, trust_net_20d=800.0)
        l7 = evaluate_l7_kd_strength(month_k=30.0, month_d=28.0, is_golden_cross=True, is_death_cross=False)
        l8 = evaluate_l8_material_keywords(["產能稼動率滿載與擴廠推進"])

        lead_summary = summarize_leading_signals(t, [l1, l2, l3, l4, l5, l6, l7, l8])
        db.query(LeadingSummaryRecord).filter(LeadingSummaryRecord.ticker == t, LeadingSummaryRecord.date == calc_date).delete()
        lead_record = LeadingSummaryRecord(
            ticker=t,
            date=calc_date,
            status=lead_summary.status,
            green_count=lead_summary.green_count,
            yellow_count=lead_summary.yellow_count,
            red_count=lead_summary.red_count,
            gray_count=lead_summary.gray_count,
            signals_json=json.dumps([{"id": s.signal_id, "name": s.name_zh, "light": s.light, "exp": s.plain_explanation} for s in lead_summary.signals], ensure_ascii=False)
        )
        db.add(lead_record)

        # 7. 兩道門四象限分類 (規格書 3.1)
        is_good = (good_res.overall == "good")
        is_cheap_or_special = (zone_info.zone in ["special", "cheap"])
        is_fair = (zone_info.zone == "fair")
        is_expensive_or_crazy = (zone_info.zone in ["expensive", "crazy"])

        if good_res.overall == "degraded":
            state_tag = "fundamental_warning"
            state_name_zh = "基本面警戒"
        elif is_good and is_cheap_or_special:
            state_tag = "research_priority"
            state_name_zh = "核心研究區 (特價/便宜)"
        elif is_good and is_fair:
            state_tag = "watch"
            state_name_zh = "持續觀察 (合理區)"
        elif is_good and is_expensive_or_crazy:
            state_tag = "val_warning"
            state_name_zh = "估值警戒 (昂貴/瘋狂)"
        elif not is_good and is_cheap_or_special:
            state_tag = "value_trap"
            state_name_zh = "價值陷阱觀察"
        elif not is_good and is_expensive_or_crazy:
            state_tag = "excluded"
            state_name_zh = "排除標的"
        else:
            state_tag = "neutral"
            state_name_zh = "中性觀察"

        # 8. 每日精選與早期轉強篩選 (規格書 15.1)
        daily_turnover = cur_price * cur_volume
        has_liquidity = daily_turnover >= TBD_CONFIG.min_daily_volume_ntd

        if is_cheap_or_special:
            cheap_line = prices.p2
            margin_pct = ((cheap_line - cur_price) / cheap_line * 100.0) if cheap_line > 0 else 0.0
        elif is_fair:
            # 合理區安全緩衝: 相對合理價上限 p4 之折價空間 (避免負數)
            fair_upper = prices.p4
            margin_pct = max(0.0, ((fair_upper - cur_price) / fair_upper * 100.0)) if fair_upper > 0 else 0.0
        else:
            margin_pct = 0.0

        if is_good and is_cheap_or_special and lead_summary.status != "weakening" and has_liquidity:
            daily_picks.append({
                "ticker": t,
                "company_name": stock.company_name,
                "current_price": cur_price,
                "margin_pct": margin_pct,
                "reasons": good_res.reasons,
                "badges": good_res.badges,
                "zone": zone_info.zone,
                "lead_status": lead_summary.status
            })

        if good_res.overall == "watch" and lead_summary.status == "strengthening" and (is_cheap_or_special or is_fair):
            early_picks.append({
                "ticker": t,
                "company_name": stock.company_name,
                "current_price": cur_price,
                "margin_pct": margin_pct,
                "reasons": good_res.reasons,
                "badges": good_res.badges,
                "zone": zone_info.zone,
                "lead_status": lead_summary.status
            })

        processed_stocks.append({
            "ticker": t,
            "company_name": stock.company_name,
            "industry": stock.industry,
            "state_tag": state_tag,
            "state_name_zh": state_name_zh,
            "current_price": cur_price,
            "zone": zone_info.zone,
            "zone_name_zh": zone_info.zone_name_zh,
            "overall_good": good_res.overall,
            "lead_status": lead_summary.status
        })

    daily_picks.sort(key=lambda x: x["margin_pct"], reverse=True)
    early_picks.sort(key=lambda x: x["margin_pct"], reverse=True)

    db.query(DailyPickRecord).filter(DailyPickRecord.pick_date == calc_date).delete()
    for rank, p in enumerate(daily_picks[:10], start=1):
        db.add(DailyPickRecord(
            pick_date=calc_date,
            user_scope="all",
            ticker=p["ticker"],
            list_type="pick",
            rank=rank,
            margin_pct=p["margin_pct"],
            reasons_json=json.dumps(p["reasons"], ensure_ascii=False)
        ))
    for rank, p in enumerate(early_picks[:10], start=1):
        db.add(DailyPickRecord(
            pick_date=calc_date,
            user_scope="all",
            ticker=p["ticker"],
            list_type="early",
            rank=rank,
            margin_pct=p["margin_pct"],
            reasons_json=json.dumps(p["reasons"], ensure_ascii=False)
        ))

    db.commit()

    return {
        "calc_date": calc_date.isoformat(),
        "total_stocks_evaluated": len(processed_stocks),
        "daily_picks_count": len(daily_picks),
        "early_picks_count": len(early_picks),
        "daily_picks": daily_picks[:5],
        "early_picks": early_picks[:5]
    }
