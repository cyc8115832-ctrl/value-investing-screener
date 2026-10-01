"""
價值投資選股 App - 資料模型 Schema (schema.py)
嚴格落實技術規格書 V1.7 第 9 章資料模型：
- stock_master, etf_master, etf_membership, custom_stock
- etf_holdings_snapshot, universe_event
- price_daily, revenue_monthly, financials_quarterly, shares_outstanding
- eps, good_company_result, valuation_metric_daily, valuation_bands
- chip_data, watchlist, watch_group, watch_group_member
- leading_signal_daily, leading_summary, daily_pick, strategy_hit
- line_binding, push_log, mindset_tip, mindset_shown, manual_article, glossary_term
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date,
    Text, ForeignKey, PrimaryKeyConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class StockMaster(Base):
    __tablename__ = "stock_master"

    ticker = Column(String(10), primary_key=True)                      # 股票代號 (如 "2330")
    company_name = Column(String(50), nullable=False)                 # 公司名稱
    industry = Column(String(50), nullable=False)                     # 產業分類 (如 "半導體業")
    sector_type = Column(String(20), default="general")               # general | financial | cyclical
    is_cyclical = Column(Boolean, default=False)                      # 是否為景氣循環股
    pool_status = Column(String(20), default="etf")                   # etf | custom | both | former
    created_at = Column(DateTime, default=datetime.utcnow)

    # 關聯
    etf_memberships = relationship("ETFMembership", back_populates="stock")
    daily_prices = relationship("PriceDaily", back_populates="stock")


class ETFMaster(Base):
    __tablename__ = "etf_master"

    etf_code = Column(String(10), primary_key=True)                   # 0050, 0056, 00881, 00891
    name = Column(String(50), nullable=False)
    issuer = Column(String(50), nullable=False)                       # 元大, 國泰, 中信
    tracking_index = Column(String(100), nullable=False)
    source_url = Column(String(255), nullable=True)
    last_sync_at = Column(DateTime, nullable=True)

    memberships = relationship("ETFMembership", back_populates="etf")


class ETFMembership(Base):
    __tablename__ = "etf_membership"

    etf_code = Column(String(10), ForeignKey("etf_master.etf_code"), primary_key=True)
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), primary_key=True)
    weight = Column(Float, nullable=False, default=0.0)                # 持股權重 (%)
    effective_date = Column(Date, default=date.today)
    removed_date = Column(Date, nullable=True)

    etf = relationship("ETFMaster", back_populates="memberships")
    stock = relationship("StockMaster", back_populates="etf_memberships")


class CustomStock(Base):
    __tablename__ = "custom_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, default="default_user")
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    backfill_status = Column(String(20), default="pending")            # pending | running | done | failed
    backfill_done_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_custom_stock_user_ticker", "user_id", "ticker", unique=True),
    )


class ETFHoldingsSnapshot(Base):
    __tablename__ = "etf_holdings_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    etf_code = Column(String(10), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    ticker = Column(String(10), nullable=False)
    weight = Column(Float, nullable=False)

    __table_args__ = (
        Index("idx_etf_snapshot", "etf_code", "snapshot_date", "ticker", unique=True),
    )


class UniverseEvent(Base):
    __tablename__ = "universe_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(Date, default=date.today)
    ticker = Column(String(10), nullable=False)
    etf_code = Column(String(10), nullable=False)
    event_type = Column(String(20), nullable=False)                    # add | remove | weight_change
    detail = Column(Text, nullable=True)


class PriceDaily(Base):
    __tablename__ = "price_daily"

    ticker = Column(String(10), ForeignKey("stock_master.ticker"), primary_key=True)
    date = Column(Date, primary_key=True)
    close = Column(Float, nullable=False)                              # 收盤價
    volume = Column(Float, nullable=False, default=0.0)                # 成交量
    pe = Column(Float, nullable=True)
    pb = Column(Float, nullable=True)
    ps = Column(Float, nullable=True)

    stock = relationship("StockMaster", back_populates="daily_prices")


class RevenueMonthly(Base):
    __tablename__ = "revenue_monthly"

    ticker = Column(String(10), ForeignKey("stock_master.ticker"), primary_key=True)
    month = Column(String(7), primary_key=True)                        # "2026-08"
    revenue = Column(Float, nullable=False)                            # 當月營收 (千元/百萬元)
    yoy = Column(Float, nullable=False)                                # 當月 YoY (%)
    cumulative_revenue = Column(Float, nullable=False)                 # 累計營收
    cumulative_yoy = Column(Float, nullable=False)                    # 累計 YoY (%)


class FinancialsQuarterly(Base):
    __tablename__ = "financials_quarterly"

    ticker = Column(String(10), ForeignKey("stock_master.ticker"), primary_key=True)
    quarter = Column(String(8), primary_key=True)                      # "2026-Q2"
    revenue = Column(Float, nullable=False)
    gross_profit = Column(Float, nullable=False)
    operating_income = Column(Float, nullable=False)
    net_income = Column(Float, nullable=False)
    non_operating_income = Column(Float, default=0.0)
    gross_margin = Column(Float, nullable=False)
    operating_margin = Column(Float, nullable=False)
    net_margin = Column(Float, nullable=False)
    roe = Column(Float, nullable=False)
    roic = Column(Float, default=0.0)
    operating_cf = Column(Float, default=0.0)
    capex = Column(Float, default=0.0)
    fcf = Column(Float, default=0.0)
    contract_liabilities = Column(Float, default=0.0)
    ppe = Column(Float, default=0.0)
    inventory = Column(Float, default=0.0)
    receivables = Column(Float, default=0.0)


class SharesOutstanding(Base):
    __tablename__ = "shares_outstanding"

    ticker = Column(String(10), ForeignKey("stock_master.ticker"), primary_key=True)
    date = Column(Date, primary_key=True)
    shares = Column(Float, nullable=False)                             # 流通在外股數 (千股/百萬股)


class EPSRecord(Base):
    __tablename__ = "eps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    period = Column(String(20), nullable=False)                        # "2026"
    actual_eps = Column(Float, nullable=True)
    ttm_eps = Column(Float, nullable=True)
    estimated_eps = Column(Float, nullable=True)
    estimate_year = Column(Integer, nullable=False)
    estimate_method = Column(String(50), nullable=False)
    confidence_flag = Column(String(30), nullable=False)
    calc_detail_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GoodCompanyRecord(Base):
    __tablename__ = "good_company_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    date = Column(Date, default=date.today)
    revenue_light = Column(String(10), nullable=False)
    eps_light = Column(String(10), nullable=False)
    margin_light = Column(String(10), nullable=False)
    efficiency_light = Column(String(10), nullable=False)
    cashflow_light = Column(String(10), nullable=False)
    growth_light = Column(String(10), nullable=False)
    overall = Column(String(20), nullable=False)                       # good | watch | degraded | insufficient
    reasons_json = Column(Text, nullable=True)
    badges_json = Column(Text, nullable=True)


class ValuationBandsRecord(Base):
    __tablename__ = "valuation_bands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    date = Column(Date, default=date.today)
    metric = Column(String(10), nullable=False)                        # pe | pb | ps
    variant = Column(String(20), default="fixed")                      # fixed | rolling | forecast
    estimate_year = Column(Integer, nullable=False)
    v_min = Column(Float, nullable=False)
    v_max = Column(Float, nullable=False)
    delta = Column(Float, nullable=False)
    a1 = Column(Float, nullable=False)
    a2 = Column(Float, nullable=False)
    a3 = Column(Float, nullable=False)
    a4 = Column(Float, nullable=False)
    a5 = Column(Float, nullable=False)
    a6 = Column(Float, nullable=False)
    p1 = Column(Float, nullable=False)
    p2 = Column(Float, nullable=False)
    p3 = Column(Float, nullable=False)
    p4 = Column(Float, nullable=False)
    p5 = Column(Float, nullable=False)
    p6 = Column(Float, nullable=False)
    current_zone = Column(String(20), nullable=False)
    zone_rule_version = Column(String(20), default="v1.5_line")


class ChipData(Base):
    __tablename__ = "chip_data"

    ticker = Column(String(10), ForeignKey("stock_master.ticker"), primary_key=True)
    date = Column(Date, primary_key=True)
    foreign_net = Column(Float, default=0.0)
    trust_net = Column(Float, default=0.0)
    dealer_net = Column(Float, default=0.0)
    insider_holding_pct = Column(Float, default=0.0)
    big_holder_pct = Column(Float, default=0.0)


class LeadingSummaryRecord(Base):
    __tablename__ = "leading_summary"

    ticker = Column(String(10), ForeignKey("stock_master.ticker"), primary_key=True)
    date = Column(Date, primary_key=True)
    status = Column(String(20), nullable=False)                        # strengthening | neutral | weakening | insufficient
    green_count = Column(Integer, default=0)
    yellow_count = Column(Integer, default=0)
    red_count = Column(Integer, default=0)
    gray_count = Column(Integer, default=0)
    signals_json = Column(Text, nullable=True)


class DailyPickRecord(Base):
    __tablename__ = "daily_pick"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pick_date = Column(Date, default=date.today)
    user_scope = Column(String(20), default="etf")                     # etf | custom | all
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    list_type = Column(String(20), nullable=False)                     # pick (每日精選) | early (早期轉強)
    rank = Column(Integer, default=1)
    margin_pct = Column(Float, default=0.0)                            # 折價空間安全邊際 (%)
    reasons_json = Column(Text, nullable=True)
    consecutive_days = Column(Integer, default=1)


class StrategyHit(Base):
    __tablename__ = "strategy_hit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    date = Column(Date, default=date.today)
    strategy_id = Column(String(50), nullable=False)
    badge_code = Column(String(20), nullable=False)                    # good, cheap, capex, etc.
    detail_json = Column(Text, nullable=True)


class WatchGroup(Base):
    __tablename__ = "watch_group"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), default="default_user")
    group_id = Column(String(50), nullable=False)
    name = Column(String(50), nullable=False)
    sort_order = Column(Integer, default=0)
    group_type = Column(String(20), default="custom")                  # system | custom


class WatchGroupMember(Base):
    __tablename__ = "watch_group_member"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), default="default_user")
    group_id = Column(String(50), nullable=False)
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    sort_order = Column(Integer, default=0)
    entry_price = Column(Float, nullable=True)
    entry_zone = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class ChecklistRecord(Base):
    """五階段檢核表與下單前 5 問記錄 (規格書 16.5, 16.6)"""
    __tablename__ = "checklist_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), default="default_user")
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    stage = Column(String(20), nullable=False)  # selection | valuation | buying | holding | selling | pre_order
    item_index = Column(Integer, nullable=False, default=0)
    checked = Column(Boolean, default=False)
    note = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_checklist_user_ticker_stage_item", "user_id", "ticker", "stage", "item_index", unique=True),
    )


class UserSettingRecord(Base):
    __tablename__ = "user_setting"

    user_id = Column(String(50), primary_key=True, default="default_user")
    settings_json = Column(Text, nullable=False)                       # 字級、長輩模式、推播偏好等
    updated_at = Column(DateTime, default=datetime.utcnow)


class MindsetTip(Base):
    __tablename__ = "mindset_tip"

    tip_id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False)                      # 槓桿資金, 操作心態, 估值本質
    text = Column(Text, nullable=False)
    trigger_rule = Column(String(50), default="always")
    active = Column(Boolean, default=True)
    last_reviewed_at = Column(Date, nullable=True)


class MindsetShown(Base):
    __tablename__ = "mindset_shown"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    tip_id = Column(Integer, nullable=False)
    shown_at = Column(DateTime, default=datetime.utcnow)


class PushLog(Base):
    __tablename__ = "push_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    channel = Column(String(20), default="line")
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="success")
    message_type = Column(String(50), nullable=True)
    error = Column(Text, nullable=True)


class ManualArticle(Base):
    __tablename__ = "manual_article"

    article_id = Column(String(50), primary_key=True)
    chapter = Column(String(50), nullable=False)
    title = Column(String(100), nullable=False)
    body_md = Column(Text, nullable=False)
    related_screen = Column(String(50), nullable=True)
    version = Column(String(20), default="1.0")
    updated_at = Column(DateTime, default=datetime.utcnow)


class GlossaryTerm(Base):
    __tablename__ = "glossary_term"

    term_id = Column(String(50), primary_key=True)
    term = Column(String(50), nullable=False)
    plain_explain = Column(Text, nullable=False)
    example = Column(Text, nullable=True)
    related_article_id = Column(String(50), nullable=True)


class LineBinding(Base):
    """LINE 帳號綁定記錄 (規格書 15.3)"""
    __tablename__ = "line_binding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), default="default_user", unique=True)
    line_user_id = Column(String(100), nullable=True)
    binding_code = Column(String(10), nullable=True)
    code_expires_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")  # pending | bound | blocked
    consent_at = Column(DateTime, nullable=True)
    bound_at = Column(DateTime, nullable=True)
    unbound_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MacroDaily(Base):
    """宏觀水位：美債 10 年期殖利率 (規格書 14.6)"""
    __tablename__ = "macro_daily"

    date = Column(Date, primary_key=True)
    us_10y_yield = Column(Float, nullable=False)
    warning_flag = Column(String(20), default="normal")  # normal | warning_4_5 | alert_5_0
    updated_at = Column(DateTime, default=datetime.utcnow)


class DividendHistory(Base):
    """除息日與股利發放記錄 (規格書 5.5)"""
    __tablename__ = "dividend_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), ForeignKey("stock_master.ticker"), nullable=False)
    year = Column(Integer, nullable=False)
    ex_date = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=True)
    cash_dividend = Column(Float, default=0.0)
    stock_dividend = Column(Float, default=0.0)

