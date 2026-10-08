"""只接受有期間與可得日期的累計財報，避免半年數字重複計入 TTM。"""
from datetime import date


def quarter_number(period):
    year, quarter = period.split("-Q")
    quarter = int(quarter)
    if quarter not in range(1, 5):
        raise ValueError("季別必須為 1 到 4")
    return int(year) * 4 + quarter - 1


def normalize_cumulative_income(rows, as_of: date):
    """Q1 保留；Q2–Q4 必須減同年度上一季累計。缺上一季時保持未知。"""
    available = {r["period"]: r for r in rows if r.get("available_date") and r["available_date"] <= as_of.isoformat()
                 and r.get("knowledge_date", r["available_date"]) <= as_of.isoformat()}
    result = []
    for period, row in sorted(available.items(), key=lambda pair: quarter_number(pair[0])):
        year, quarter_text = period.split("-Q")
        quarter = int(quarter_text)
        # 財報期間不得晚於截止日所屬季。
        if quarter_number(period) > as_of.year * 4 + (as_of.month - 1) // 3:
            continue
        previous = available.get(f"{year}-Q{quarter - 1}") if quarter > 1 else None
        item = {"period": period, "available_date": row["available_date"], "source_url": row.get("source_url")}
        for field in ("eps", "revenue", "operating_income", "net_income"):
            current = row.get(field)
            prior = previous.get(field) if previous else None
            item[field] = current if quarter == 1 else (current - prior if current is not None and prior is not None else None)
        item["available"] = item["eps"] is not None
        item["reason"] = "累計已轉為單季" if item["available"] else "缺同年度前一季累計，不能單季化"
        result.append(item)
    return result


def realized_eps_summary(rows, as_of: date):
    quarters = normalize_cumulative_income(rows, as_of)
    recent = quarters[-4:]
    consecutive = len(recent) == 4 and all(quarter_number(b["period"]) - quarter_number(a["period"]) == 1 for a, b in zip(recent, recent[1:]))
    ready = consecutive and all(r["eps"] is not None for r in recent)
    annual = {}
    for year in {r["period"][:4] for r in quarters}:
        fiscal = [r for r in quarters if r["period"].startswith(year)]
        if len(fiscal) == 4 and all(r["eps"] is not None for r in fiscal):
            annual[year] = round(sum(r["eps"] for r in fiscal), 4)
    return {"available": ready, "ttm_eps": round(sum(r["eps"] for r in recent), 4) if ready else None,
            "annual_eps": annual, "quarters": quarters,
            "estimated_eps": None,
            "reason": "已公布連續四季實現 EPS" if ready else "TTM 需要已公布且可單季化的連續四季 EPS；未來 EPS 不以固定成長率補值。"}
