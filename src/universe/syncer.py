"""
價值投資選股 App - ETF 同步與快照事件模組 (syncer.py)
遵循技術規格書 V1.7 第 2.1 至 2.3 節：
- 0050, 0056, 00881, 00891 四檔 ETF 同步
- 持股清洗過濾 (排除期貨、現金等)
- 快照保存 (etf_holdings_snapshot)
- 快照前後比對並產出新增/剔除/權重變化事件 (universe_event)
- 股池狀態更新 (stock_master: etf, custom, both, former)
- 計算各 ETF 檔數、聯集總檔數與 ETF 重疊數
"""

from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.database.schema import (
    StockMaster, ETFMaster, ETFMembership, ETFHoldingsSnapshot, UniverseEvent
)
from src.universe.cleaner import clean_etf_holdings

# 四檔 ETF 定義 (規格書 2.2)
ETF_DEFINITIONS = [
    {
        "etf_code": "0050",
        "name": "元大台灣50",
        "issuer": "元大投信",
        "tracking_index": "富時臺灣證券交易所臺灣50指數"
    },
    {
        "etf_code": "0056",
        "name": "元大高股息",
        "issuer": "元大投信",
        "tracking_index": "臺灣高股息指數"
    },
    {
        "etf_code": "00881",
        "name": "國泰台灣科技龍頭",
        "issuer": "國泰投信",
        "tracking_index": "臺灣指數公司特選臺灣上市上櫃 FactSet 科技龍頭通訊指數"
    },
    {
        "etf_code": "00891",
        "name": "中信關鍵半導體",
        "issuer": "中國信託投信",
        "tracking_index": "NYSE FactSet 臺灣 ESG 永續關鍵半導體指數"
    }
]

def init_etf_master(db: Session):
    """初始化 ETF 主檔資料"""
    for item in ETF_DEFINITIONS:
        etf = db.query(ETFMaster).filter(ETFMaster.etf_code == item["etf_code"]).first()
        if not etf:
            etf = ETFMaster(
                etf_code=item["etf_code"],
                name=item["name"],
                issuer=item["issuer"],
                tracking_index=item["tracking_index"],
                last_sync_at=None
            )
            db.add(etf)
    db.commit()


def sync_etf_holdings(
    db: Session,
    etf_code: str,
    raw_holdings: List[Dict[str, Any]],
    snapshot_date: Optional[date] = None,
    industry_map: Optional[Dict[str, str]] = None,
    cyclical_set: Optional[set] = None
) -> Dict[str, Any]:
    """
    同步單一 ETF 持股並產生快照與事件
    """
    init_etf_master(db)
    target_date = snapshot_date or date.today()
    ind_map = industry_map or {}
    cyc_set = cyclical_set or set()

    # 1. 執行清洗
    cleaned_holdings, excluded = clean_etf_holdings(raw_holdings)

    # 2. 取得前次快照以進行比對
    last_snapshot_date_row = db.query(func.max(ETFHoldingsSnapshot.snapshot_date))\
        .filter(ETFHoldingsSnapshot.etf_code == etf_code, ETFHoldingsSnapshot.snapshot_date < target_date)\
        .first()
    
    last_date = last_snapshot_date_row[0] if last_snapshot_date_row else None
    old_holdings_dict: Dict[str, float] = {}
    if last_date:
        old_rows = db.query(ETFHoldingsSnapshot)\
            .filter(ETFHoldingsSnapshot.etf_code == etf_code, ETFHoldingsSnapshot.snapshot_date == last_date)\
            .all()
        old_holdings_dict = {row.ticker: row.weight for row in old_rows}

    # 3. 儲存本次快照 (覆蓋當日既有快照)
    db.query(ETFHoldingsSnapshot)\
        .filter(ETFHoldingsSnapshot.etf_code == etf_code, ETFHoldingsSnapshot.snapshot_date == target_date)\
        .delete()

    new_holdings_dict: Dict[str, float] = {}
    for item in cleaned_holdings:
        ticker = item["ticker"]
        name = item["name"]
        weight = item["weight"]
        new_holdings_dict[ticker] = weight

        # 寫入快照
        snap = ETFHoldingsSnapshot(
            etf_code=etf_code,
            snapshot_date=target_date,
            ticker=ticker,
            weight=weight
        )
        db.add(snap)

        # 維護 StockMaster
        stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
        if not stock:
            industry = ind_map.get(ticker, "其他電子業")
            is_cyc = (ticker in cyc_set) or (industry in ["記憶體", "DRAM", "面板", "航運", "鋼鐵", "塑化", "被動元件"])
            sector_type = "cyclical" if is_cyc else ("financial" if "金控" in industry or "銀行" in industry else "general")
            stock = StockMaster(
                ticker=ticker,
                company_name=name,
                industry=industry,
                sector_type=sector_type,
                is_cyclical=is_cyc,
                pool_status="etf"
            )
            db.add(stock)
        else:
            if stock.pool_status == "custom":
                stock.pool_status = "both"
            elif stock.pool_status == "former":
                stock.pool_status = "etf"

    # 4. 比對前後快照產生事件
    events_generated = []
    if old_holdings_dict:
        # 新增
        for t, w in new_holdings_dict.items():
            if t not in old_holdings_dict:
                evt = UniverseEvent(
                    event_date=target_date,
                    ticker=t,
                    etf_code=etf_code,
                    event_type="add",
                    detail=f"新增納入成分股，權重 {w:.2f}%"
                )
                db.add(evt)
                events_generated.append(f"新增 {t} ({w:.2f}%)")
            elif abs(w - old_holdings_dict[t]) >= 0.5:  # 權重顯著變動 >= 0.5%
                diff = w - old_holdings_dict[t]
                evt = UniverseEvent(
                    event_date=target_date,
                    ticker=t,
                    etf_code=etf_code,
                    event_type="weight_change",
                    detail=f"權重調整 {diff:+.2f}% (由 {old_holdings_dict[t]:.2f}% → {w:.2f}%)"
                )
                db.add(evt)
                events_generated.append(f"權重變動 {t} ({diff:+.2f}%)")

        # 剔除
        for t, old_w in old_holdings_dict.items():
            if t not in new_holdings_dict:
                evt = UniverseEvent(
                    event_date=target_date,
                    ticker=t,
                    etf_code=etf_code,
                    event_type="remove",
                    detail=f"自成分股剔除 (原權重 {old_w:.2f}%)"
                )
                db.add(evt)
                events_generated.append(f"剔除 {t}")

    # 5. 更新 ETFMembership
    db.query(ETFMembership).filter(ETFMembership.etf_code == etf_code).delete()
    for t, w in new_holdings_dict.items():
        mem = ETFMembership(
            etf_code=etf_code,
            ticker=t,
            weight=w,
            effective_date=target_date
        )
        db.add(mem)

    # 6. 更新 ETFMaster 的 last_sync_at
    etf_record = db.query(ETFMaster).filter(ETFMaster.etf_code == etf_code).first()
    if etf_record:
        etf_record.last_sync_at = datetime.utcnow()

    db.commit()

    return {
        "etf_code": etf_code,
        "snapshot_date": target_date.isoformat(),
        "total_raw": len(raw_holdings),
        "total_cleaned": len(cleaned_holdings),
        "excluded_count": len(excluded),
        "events_count": len(events_generated),
        "events": events_generated
    }


def get_universe_summary(db: Session) -> Dict[str, Any]:
    """
    規格書 2.3 設定頁與雷達頁統計：
    - 各 ETF 最新成分日期、最後同步時間、各 ETF 檔數
    - 聯集總檔數
    - 重疊數 (同時被幾檔 ETF 持有)
    """
    etfs = db.query(ETFMaster).all()
    etf_stats = []
    
    for etf in etfs:
        count = db.query(ETFMembership).filter(ETFMembership.etf_code == etf.etf_code).count()
        etf_stats.append({
            "etf_code": etf.etf_code,
            "name": etf.name,
            "stock_count": count,
            "last_sync_at": etf.last_sync_at.isoformat() if etf.last_sync_at else None
        })

    # 聯集總檔數 (去重)
    union_tickers = db.query(ETFMembership.ticker).distinct().all()
    union_count = len(union_tickers)

    # 重疊數分佈統計
    overlap_query = db.query(
        ETFMembership.ticker,
        func.count(ETFMembership.etf_code).label("etf_count")
    ).group_by(ETFMembership.ticker).all()

    overlap_distribution = {1: 0, 2: 0, 3: 0, 4: 0}
    for row in overlap_query:
        c = row[1]
        if c in overlap_distribution:
            overlap_distribution[c] += 1

    return {
        "etfs": etf_stats,
        "union_total_stocks": union_count,
        "overlap_distribution": overlap_distribution
    }


def sync_all_etf_holdings(db: Session, snapshot_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    同步所有 4 檔 ETF (0050, 0056, 00881, 00891) 持股並產生快照與事件
    """
    from src.data.mock_fixtures import ETF_CONSTITUENTS
    events = []
    for etf_code, raw_list in ETF_CONSTITUENTS.items():
        res = sync_etf_holdings(db, etf_code=etf_code, raw_holdings=raw_list, snapshot_date=snapshot_date)
        events.extend(res.get("events", []))
    return events

