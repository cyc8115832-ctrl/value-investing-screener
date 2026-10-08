"""正式市場資料的證據邊界、期間與單位；未知值不補成投資訊號。"""
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.database.schema import MarketEvidence, MarketEvidenceRevision, StockMaster
from config.settings import SETTINGS


def taiwan_today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def encode_payload(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)


def save_evidence(db, dataset, ticker, period, payload, source_url, available_date, observed_at=None):
    """呼叫者需先核對官方資料；發布日期缺失時使用出表日期保守處理。"""
    encoded = encode_payload(payload)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    observed_at = observed_at or datetime.now(timezone.utc).replace(tzinfo=None)
    previous = db.query(MarketEvidenceRevision).filter_by(dataset=dataset, ticker=ticker, period=str(period)).order_by(MarketEvidenceRevision.observed_at.desc(), MarketEvidenceRevision.id.desc()).first()
    if previous is None or previous.payload_sha256 != digest or previous.available_date != available_date or previous.source_url != source_url or previous.observed_at > observed_at:
        db.add(MarketEvidenceRevision(dataset=dataset, ticker=ticker, period=str(period), source_url=source_url,
                                     available_date=available_date, observed_at=observed_at,
                                     payload_json=encoded, payload_sha256=digest, status="verified"))
    record = db.get(MarketEvidence, (dataset, ticker, str(period)))
    if record is None:
        record = MarketEvidence(dataset=dataset, ticker=ticker, period=str(period))
        db.add(record)
    elif record.fetched_at > observed_at:
        return record
    record.payload_json = encoded
    record.payload_sha256 = digest
    record.source_url = source_url
    record.available_date = available_date
    record.fetched_at = observed_at
    record.status = "verified"
    return record


def evidence_rows(db, dataset, ticker, as_of=None):
    cutoff = as_of or taiwan_today()
    cutoff_utc = datetime.combine(cutoff + timedelta(days=1), datetime.min.time()) - timedelta(hours=8)
    rows = db.query(MarketEvidence).filter(
        MarketEvidence.dataset == dataset, MarketEvidence.ticker == ticker,
        MarketEvidence.status == "verified",
    ).order_by(MarketEvidence.period).all()
    versions = db.query(MarketEvidenceRevision).filter(
        MarketEvidenceRevision.dataset == dataset, MarketEvidenceRevision.ticker == ticker,
        MarketEvidenceRevision.available_date <= cutoff, MarketEvidenceRevision.observed_at < cutoff_utc,
    ).order_by(MarketEvidenceRevision.observed_at, MarketEvidenceRevision.id).all()
    visible_versions = {r.period: r for r in versions}
    result = []
    for row in rows:
        if dataset in ("price", "revenue") and row.period > cutoff.isoformat():
            continue
        if hashlib.sha256(row.payload_json.encode()).hexdigest() != row.payload_sha256:
            continue
        revision = visible_versions.get(row.period)
        selected = revision or row
        observed = revision.observed_at if revision else row.fetched_at
        if selected.available_date > cutoff or observed >= cutoff_utc or selected.status != "verified" or hashlib.sha256(selected.payload_json.encode()).hexdigest() != selected.payload_sha256:
            continue
        payload = json.loads(selected.payload_json)
        knowledge_date = max(selected.available_date, (observed + timedelta(hours=8)).date())
        result.append({**payload, "period": row.period, "source_url": selected.source_url,
                       "available_date": selected.available_date.isoformat(), "knowledge_date": knowledge_date.isoformat(),
                       "fetched_at": observed.isoformat() + "Z"})
    return result


def unknown(reason):
    return {"available": False, "status": "insufficient", "reason": reason}


def valuation_from_history(prices, metric="pe", as_of=None, reconstruction=False):
    """本系統暫定分位數河流圖；同一截止日、真實倍數與同日基本值。"""
    cutoff = as_of or taiwan_today()
    window = sorted([p for p in prices if p["period"] <= cutoff.isoformat()
                     and p.get("available_date", p["period"]) <= cutoff.isoformat()
                     and (reconstruction or p.get("knowledge_date", p["period"]) <= cutoff.isoformat())], key=lambda p: p["period"])[-SETTINGS.RIVER_OBSERVATIONS:]
    usable = [p for p in window if p.get(metric) is not None and math.isfinite(p[metric]) and p[metric] > 0
              and p.get("close", 0) > 0]
    usable = sorted(usable, key=lambda p: p["period"])[-SETTINGS.RIVER_OBSERVATIONS:]
    if len(usable) < SETTINGS.RIVER_MIN_OBSERVATIONS:
        return {**unknown(f"{metric.upper()} 已核實倍數僅 {len(usable)} 日，需 {SETTINGS.RIVER_MIN_OBSERVATIONS} 日；不以模擬歷史補足。"), "sample_count": len(usable)}
    current = usable[-1]
    # 最新當日倍數不可由更早的基本值回推；不同日期不得混搭。
    if not window or current["period"] != window[-1]["period"]:
        return unknown("最新行情缺同日有效倍數，無法確認基本值。")
    multiples = sorted(p[metric] for p in usable)
    anchors = []
    for quantile in SETTINGS.RIVER_QUANTILES:
        position = quantile * (len(multiples) - 1)
        low = int(position)
        high = min(low + 1, len(multiples) - 1)
        anchors.append(multiples[low] + (multiples[high] - multiples[low]) * (position - low))
    if len(anchors) != 6 or any(a >= b for a, b in zip(anchors, anchors[1:])):
        return unknown("歷史倍數不足以形成六條不同價位線。")
    base = current["close"] / current[metric]
    levels = [round(base * a, 2) for a in anchors]
    close = current["close"]
    zone = ("special" if close <= levels[0] else "cheap" if close <= levels[1]
            else "fair" if close < levels[4] else "expensive" if close < levels[5] else "crazy")
    return {"available": True, "metric": metric, "zone": zone, "levels": levels,
            "base_value": base, "sample_count": len(usable), "date": current["period"],
            "center_multiple": sum(p[metric] for p in usable) / len(usable),
            "method": "已核實交易日倍數之可設定分位數；本系統研究模型，非孫慶龍原公式。",
            "historical_reconstruction": reconstruction,
            "margin_to_fair_pct": round((levels[3] / close - 1) * 100, 2)}


def stock_view(db: Session, stock: StockMaster, metric="auto", scenario="base", as_of=None):
    prices = evidence_rows(db, "price", stock.ticker, as_of)
    revenues = evidence_rows(db, "revenue", stock.ticker, as_of)
    financials = evidence_rows(db, "income_ytd", stock.ticker, as_of)
    balance_rows = evidence_rows(db, "balance_sheet", stock.ticker, as_of)
    quote = prices[-1] if prices else None
    revenue = revenues[-1] if revenues else None
    income = financials[-1] if financials else None
    from src.engines.verified_earnings import realized_eps_summary
    realized = realized_eps_summary(financials, as_of or taiwan_today())
    factors = []
    if revenue:
        growth = revenue.get("yoy")
        if growth is not None:
            factors.append({"label": "月營收成長", "color": "green" if growth > 0 else "red" if growth < 0 else "yellow",
                            "value": f"{growth * 100:+.2f}%", "period": revenue["period"],
                            "reason": "較去年同月增加" if growth > 0 else "較去年同月減少" if growth < 0 else "與去年同月持平"})
        cumulative = revenue.get("cumulative_yoy")
        if cumulative is not None:
            factors.append({"label": "累計營收成長", "color": "green" if cumulative > 0 else "red" if cumulative < 0 else "yellow",
                            "value": f"{cumulative * 100:+.2f}%", "period": revenue["period"], "reason": "年初至當月與去年同期比較"})
    if income and income.get("eps") is not None:
        factors.append({"label": "累計已實現 EPS", "color": "red" if income["eps"] < 0 else "yellow",
                        "value": f"{income['eps']:.2f} 元", "period": income["period"],
                        "reason": "今年累計值；不是單季、全年或未來預估 EPS"})
    for label in ["獲利持續成長", "自由現金流", "資本效率與負債", "股利可持續性"]:
        factors.append({"label": label, "color": "gray", "value": "待核實", "reason": "需要已公布的連續財報與現金流證據"})
    selected_metric = ("pb" if stock.is_cyclical or stock.sector_type == "financial" else "pe") if metric == "auto" else metric
    valuation = valuation_from_history(prices, selected_metric, as_of) if selected_metric in ("pe", "pb", "ps") else unknown("不支援的估值指標")
    if scenario != "base":
        valuation = unknown("尚無可查證的預估 EPS 情境，不能以固定成長率冒充未來獲利。")
    risks = [f["label"] + "：" + f["reason"] for f in factors if f["color"] == "red"]
    return {"evidence_version": 1, "ticker": stock.ticker, "company_name": stock.company_name,
            "industry": stock.industry, "quote": quote, "revenue": revenue, "income_ytd": income,
            "balance_sheet": balance_rows[-1] if balance_rows else None, "realized_eps": realized,
            "value_factors": factors, "company_status": "insufficient", "company_label": "體質待核實",
            "risk_color": "red" if income and income.get("eps") is not None and income["eps"] < 0 else "yellow" if risks else "gray",
            "risks": risks, "valuation": valuation, "current_zone": valuation.get("zone", "unknown"),
            "conclusion": "先確認獲利與現金流，再判斷價格是否值得等待。",
            "missing": ["連續單季財報與公告日期", "股數、現金流及歷年資產負債表", "ETF 歷史成分與權重", "完整真實歷史行情"],
            "research": {"status": "evidence_summary", "label": "價值證據摘要", "reason": "依官方資料整理，不以規則文字宣稱 AI 已證明護城河。"}}


def data_quality_report(db):
    stocks = db.query(StockMaster).all()
    coverage = {dataset: sum(bool(evidence_rows(db, dataset, s.ticker)) for s in stocks)
                for dataset in ("price", "revenue", "income_ytd", "balance_sheet")}
    fields = {}
    for dataset, names in {"price": ["close", "volume", "pe", "pb", "ps"], "revenue": ["revenue", "yoy", "cumulative_revenue", "cumulative_yoy"], "income_ytd": ["eps", "revenue", "operating_income", "net_income", "net_revenue", "net_interest_income", "other_industry_income"], "balance_sheet": ["total_assets", "total_liabilities", "total_equity", "current_assets", "current_liabilities", "book_value_per_share"]}.items():
        rows = [evidence_rows(db, dataset, s.ticker) for s in stocks]
        fields[dataset] = {field: sum(bool(records) and records[-1].get(field) is not None for records in rows) for field in names}
        fields[dataset]["periods"] = sorted({records[-1]["period"] for records in rows if records})
    return {"evidence_version": 1, "stocks": len(stocks), "verified_coverage": coverage, "field_coverage": fields,
            "unverified_datasets": ["financials_quarterly", "historical_balance_sheet", "shares_outstanding", "cash_flow", "dividend_history", "chip_data", "etf_membership", "macro_daily", "historical_prices"],
            "investment_ready": False, "status": "insufficient",
            "reason": "行情與月營收可查證，不代表估值與好公司判定已具備完整證據。舊種子歷史不納入。"}
