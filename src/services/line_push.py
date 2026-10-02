"""
價值投資選股 App - LINE 每日價值精選、推播與 Webhook 綁定服務 (line_push.py)
嚴格落實技術規格書 V1.7：
- 第 15 章 每日價值精選與 LINE 推播 (收盤後發布，精簡重點)
- 第 15.3 節 LINE 帳號綁定流程 (6 位一次性驗證碼、Webhook、隱私 consent、解綁與封鎖)
- 第 15.5 節 失敗處理 (3 次重試、push_log 記錄)
- 第 16 章 投資心法 (每次推播皆附一則，30天內不重複，每週至少一則與槓桿/資金有關)
- 第 8.10.7 節 LINE 大字版訊息樣式 (長輩友善模式可切換)
"""

import base64
import hashlib
import hmac
import json
import logging
import random
import time
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import httpx
from sqlalchemy.orm import Session

from src.database.schema import (
    DailyPickRecord, StockMaster, MindsetTip, MindsetShown, PushLog, PriceDaily, LineBinding,
    GoodCompanyRecord, ValuationBandsRecord, GlossaryTerm
)
from src.engines.industry_concentration import analyze_industry_concentration
from config.settings import SETTINGS

logger = logging.getLogger("line_push")


def get_next_mindset_tip(db: Session, user_id: str = "default_user") -> MindsetTip:
    """
    選取本日心法：
    - 30 天內不重複
    - 每週至少一則與槓桿或資金管理有關 (週一或週五優先)
    """
    cutoff = datetime.utcnow() - timedelta(days=30)
    shown_ids = [row[0] for row in db.query(MindsetShown.tip_id)\
        .filter(MindsetShown.user_id == user_id, MindsetShown.shown_at >= cutoff)\
        .all()]

    is_leverage_priority = (date.today().weekday() in [0, 4])

    query = db.query(MindsetTip).filter(MindsetTip.active == True)
    if is_leverage_priority:
        lev_tips = query.filter(MindsetTip.category == "槓桿資金", ~MindsetTip.tip_id.in_(shown_ids)).all()
        if lev_tips:
            tip = lev_tips[0]
            db.add(MindsetShown(user_id=user_id, tip_id=tip.tip_id))
            db.commit()
            return tip

    available = query.filter(~MindsetTip.tip_id.in_(shown_ids)).all()
    if not available:
        available = query.all()

    tip = available[0] if available else MindsetTip(category="操作心態", text="先選好公司，再等好價格。安心投資，靜待花開。")
    db.add(MindsetShown(user_id=user_id, tip_id=tip.tip_id))
    db.commit()
    return tip


def format_daily_line_message(
    db: Session,
    pick_date: Optional[date] = None,
    elder_mode: bool = False,
    user_id: str = "default_user"
) -> str:
    """
    格式化 LINE 每日精選推播訊息 (標準版與大字版)
    """
    target_date = pick_date or date.today()
    picks = db.query(DailyPickRecord)\
        .filter(DailyPickRecord.pick_date == target_date, DailyPickRecord.list_type == "pick")\
        .order_by(DailyPickRecord.rank.asc())\
        .limit(5)\
        .all()

    earlies = db.query(DailyPickRecord)\
        .filter(DailyPickRecord.pick_date == target_date, DailyPickRecord.list_type == "early")\
        .order_by(DailyPickRecord.rank.asc())\
        .limit(3)\
        .all()

    tip = get_next_mindset_tip(db, user_id=user_id)

    # 產業集中度風險分析 (規格書 13.10 & D-14)
    pick_stocks_meta = []
    for p in picks:
        stk = db.query(StockMaster).filter(StockMaster.ticker == p.ticker).first()
        if stk:
            pick_stocks_meta.append({"ticker": stk.ticker, "company_name": stk.company_name, "industry": stk.industry})
    conc_analysis = analyze_industry_concentration(pick_stocks_meta, threshold=2)

    # 1. 大字版 / 長輩友善樣式 (規格書 8.10.7)
    if elder_mode:
        lines = [
            f"🔔【價值投資選股】每日精選 ({target_date})",
            "----------------------------",
            "【今日好公司特惠名單】"
        ]
        if not picks:
            lines.append("今日股池無完全符合『特價/便宜區』之好公司標的，請耐心等待好價格。")
        else:
            for p in picks:
                stock = db.query(StockMaster).filter(StockMaster.ticker == p.ticker).first()
                p_daily = db.query(PriceDaily).filter(PriceDaily.ticker == p.ticker).order_by(PriceDaily.date.desc()).first()
                close_str = f"{p_daily.close:.1f}元" if p_daily else "-"
                name = stock.company_name if stock else p.ticker
                lines.append(f"\n● {name} ({p.ticker})")
                lines.append(f"  現價：{close_str} | 折價空間：+{p.margin_pct:.1f}%")
                reasons = json.loads(p.reasons_json or "[]")
                if reasons:
                    lines.append(f"  特色：{reasons[0]}")
            
            if conc_analysis.get("has_concentration_risk") and conc_analysis.get("top_industries"):
                top_ind = conc_analysis["top_industries"][0]
                lines.append(f"\n⚠️ 提醒：今日名單中「{top_ind['industry']}」佔 {top_ind['count']} 檔，請留意產業分散，避免資金過度集中。")

        lines.extend([
            "\n----------------------------",
            "【今日投資心法】",
            f"{tip.text}",
            "----------------------------",
            "點擊進入 App 查看完整河流圖與安全邊際。"
        ])
        return "\n".join(lines)

    # 2. 標準版樣式 (規格書 15.2)
    lines = [
        f"📊【價值投資選股】盤後精選 ({target_date})",
        "先選好公司，再等好價格。\n"
    ]

    lines.append("🟢【核心研究區・特價/便宜好公司】")
    if not picks:
        lines.append("  今日無符合標的（好公司皆位於合理或偏高區間，持有者平心續抱，觀望者耐心等候）\n")
    else:
        for p in picks:
            stock = db.query(StockMaster).filter(StockMaster.ticker == p.ticker).first()
            p_daily = db.query(PriceDaily).filter(PriceDaily.ticker == p.ticker).order_by(PriceDaily.date.desc()).first()
            close_str = f"${p_daily.close:.1f}" if p_daily else ""
            name = stock.company_name if stock else p.ticker
            reasons = json.loads(p.reasons_json or "[]")
            r_summary = "、".join([r.replace("✓ ", "") for r in reasons[:2]])
            lines.append(f"• {name}({p.ticker}) {close_str} | 安全邊際 {p.margin_pct:+.1f}%")
            lines.append(f"  入選原因: {r_summary}")
        lines.append("")

        if conc_analysis.get("has_concentration_risk") and conc_analysis.get("top_industries"):
            top_ind = conc_analysis["top_industries"][0]
            lines.append(f"⚠️【產業分散提醒】精選中有 {top_ind['count']} 檔標的集中於「{top_ind['industry']}」，四檔 ETF 偏科技，配置時請留意產業分散。\n")

    if earlies:
        lines.append("⚡【早期轉強候選】(領先訊號衝刺中)")
        for ep in earlies:
            stock = db.query(StockMaster).filter(StockMaster.ticker == ep.ticker).first()
            p_daily = db.query(PriceDaily).filter(PriceDaily.ticker == ep.ticker).order_by(PriceDaily.date.desc()).first()
            close_str = f"${p_daily.close:.1f}" if p_daily else ""
            name = stock.company_name if stock else ep.ticker
            lines.append(f"• {name}({ep.ticker}) {close_str} (訂金/營收加速度轉強)")
        lines.append("")

    lines.append("💡【本日投資心法】")
    lines.append(tip.text)
    lines.append("\n※ 本系統僅供量化價值研究，非任何投資買賣指令。")

    return "\n".join(lines)


# =========================================================================
# LINE Flex Message 視覺化卡片建構器 (規格書 8.10.7 & 待決事項 D-21)
# =========================================================================

def build_daily_line_flex_message(
    db: Session,
    pick_date: Optional[date] = None,
    elder_mode: bool = False,
    user_id: str = "default_user",
    app_base_url: str = "https://value-invest.app"
) -> Dict[str, Any]:
    """
    建構符合 LINE 官方規範之 Flex Message (Bubble 或 Carousel)
    符合炭黑帳本高對比配色與長輩大字版規格 (規格書 8.10.7 & 待決事項 D-21)
    """
    target_date = pick_date or date.today()
    picks = db.query(DailyPickRecord)\
        .filter(DailyPickRecord.pick_date == target_date, DailyPickRecord.list_type == "pick")\
        .order_by(DailyPickRecord.rank.asc())\
        .limit(3 if elder_mode else 5)\
        .all()

    earlies = db.query(DailyPickRecord)\
        .filter(DailyPickRecord.pick_date == target_date, DailyPickRecord.list_type == "early")\
        .order_by(DailyPickRecord.rank.asc())\
        .limit(3)\
        .all()

    tip = get_next_mindset_tip(db, user_id=user_id)

    # 產業集中度風險分析
    pick_stocks_meta = []
    for p in picks:
        stk = db.query(StockMaster).filter(StockMaster.ticker == p.ticker).first()
        if stk:
            pick_stocks_meta.append({"ticker": stk.ticker, "company_name": stk.company_name, "industry": stk.industry})
    conc_analysis = analyze_industry_concentration(pick_stocks_meta, threshold=2)

    # 視覺尺寸設定 (長輩模式放大字級)
    title_size = "xl" if elder_mode else "lg"
    body_size = "md" if elder_mode else "sm"
    badge_size = "sm" if elder_mode else "xs"

    # Header 區塊
    header_box = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#0B0F19",
        "paddingTop": "16px",
        "paddingBottom": "14px",
        "paddingStart": "16px",
        "paddingEnd": "16px",
        "contents": [
            {
                "type": "text",
                "text": f"💎 價值投資選股・每日精選" if not elder_mode else "🔔 價值投資選股・長輩大字精選",
                "weight": "bold",
                "color": "#00F59B",
                "size": title_size
            },
            {
                "type": "text",
                "text": f"交易基準日：{target_date} ｜ 盤後量化估值",
                "color": "#94A3B8",
                "size": "xs",
                "margin": "xs"
            }
        ]
    }

    body_contents = []

    # 1. 核心精選個股區塊
    body_contents.append({
        "type": "text",
        "text": "🟢【好公司特惠名單】" if elder_mode else "🟢【核心精選・特價與便宜好公司】",
        "weight": "bold",
        "color": "#FFFFFF",
        "size": body_size,
        "margin": "md"
    })

    if not picks:
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#141D2E",
            "cornerRadius": "6px",
            "paddingAll": "12px",
            "margin": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "今日股池無完全符合「特價/便宜區」之標的。",
                    "color": "#CBD5E1",
                    "size": body_size,
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": "🛡️ 好公司皆位於合理或偏高區間，請耐心等待好價格出現。",
                    "color": "#94A3B8",
                    "size": "xs",
                    "wrap": True,
                    "margin": "xs"
                }
            ]
        })
    else:
        for p in picks:
            stock = db.query(StockMaster).filter(StockMaster.ticker == p.ticker).first()
            p_daily = db.query(PriceDaily).filter(PriceDaily.ticker == p.ticker).order_by(PriceDaily.date.desc()).first()
            close_str = f"NT$ {p_daily.close:.1f}" if p_daily else "-"
            name = stock.company_name if stock else p.ticker
            reasons = json.loads(p.reasons_json or "[]")
            first_reason = reasons[0].replace("✓ ", "") if reasons else "基本面指標評級優異"

            body_contents.append({
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#141D2E",
                "cornerRadius": "8px",
                "paddingAll": "12px",
                "margin": "md",
                "borderColor": "#1E293B",
                "borderWidth": "1px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{name} ({p.ticker})",
                                "weight": "bold",
                                "color": "#FFFFFF",
                                "size": "md" if elder_mode else "sm",
                                "flex": 4
                            },
                            {
                                "type": "text",
                                "text": f"+{p.margin_pct:.1f}%",
                                "weight": "bold",
                                "color": "#00F59B",
                                "size": "sm",
                                "align": "end",
                                "flex": 2
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "xs",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"現價：{close_str}",
                                "color": "#38BDF8",
                                "size": "xs",
                                "flex": 3
                            },
                            {
                                "type": "text",
                                "text": "安全邊際空間",
                                "color": "#94A3B8",
                                "size": "xxs",
                                "align": "end",
                                "flex": 3
                            }
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"💡 {first_reason}",
                        "color": "#CBD5E1",
                        "size": "xs",
                        "wrap": True,
                        "margin": "sm"
                    }
                ]
            })

    # 產業集中度提醒
    if conc_analysis.get("has_concentration_risk") and conc_analysis.get("top_industries"):
        top_ind = conc_analysis["top_industries"][0]
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "rgba(251, 191, 36, 0.12)",
            "cornerRadius": "6px",
            "paddingAll": "10px",
            "margin": "md",
            "borderColor": "#FBBF24",
            "borderWidth": "1px",
            "contents": [
                {
                    "type": "text",
                    "text": f"⚠️ 產業集中警示：今日名單中「{top_ind['industry']}」佔 {top_ind['count']} 檔，四檔 ETF 偏科技，配置請注意分散。",
                    "color": "#FBBF24",
                    "size": "xs",
                    "wrap": True
                }
            ]
        })

    # 2. 早期轉強候選 (標準模式展示)
    if earlies and not elder_mode:
        body_contents.append({
            "type": "text",
            "text": "⚡【早期轉強候選・動能衝刺中】",
            "weight": "bold",
            "color": "#38BDF8",
            "size": "sm",
            "margin": "lg"
        })
        early_items = []
        for ep in earlies:
            stock = db.query(StockMaster).filter(StockMaster.ticker == ep.ticker).first()
            p_daily = db.query(PriceDaily).filter(PriceDaily.ticker == ep.ticker).order_by(PriceDaily.date.desc()).first()
            close_str = f"${p_daily.close:.1f}" if p_daily else ""
            name = stock.company_name if stock else ep.ticker
            early_items.append(f"• {name}({ep.ticker}) {close_str}")

        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#141D2E",
            "cornerRadius": "6px",
            "paddingAll": "10px",
            "margin": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "、".join(early_items),
                    "color": "#CBD5E1",
                    "size": "xs",
                    "wrap": True
                }
            ]
        })

    # 3. 今日心法區塊
    body_contents.append({
        "type": "separator",
        "margin": "lg",
        "color": "#1E293B"
    })
    body_contents.append({
        "type": "text",
        "text": "🧘【本日安心心法】",
        "weight": "bold",
        "color": "#FBBF24",
        "size": body_size,
        "margin": "md"
    })
    body_contents.append({
        "type": "text",
        "text": f"「{tip.text}」",
        "color": "#FFFFFF",
        "size": "sm",
        "wrap": True,
        "margin": "xs"
    })

    body_box = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#0B0F19",
        "paddingStart": "16px",
        "paddingEnd": "16px",
        "paddingBottom": "16px",
        "contents": body_contents
    }

    # Footer 區塊 (免責聲明與前往 App 按鈕)
    footer_box = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": "#0E1524",
        "paddingAll": "14px",
        "contents": [
            {
                "type": "button",
                "action": {
                    "type": "uri",
                    "label": "📲 開啟 App 查看完整河流圖" if not elder_mode else "📲 開啟 App 看完整分析",
                    "uri": f"{app_base_url}/"
                },
                "style": "primary",
                "color": "#2563EB",
                "height": "sm"
            },
            {
                "type": "text",
                "text": "※ 本訊息僅供客觀數據分析，非投資買賣指令。",
                "color": "#64748B",
                "size": "xxs",
                "align": "center",
                "margin": "sm"
            }
        ]
    }

    return {
        "type": "flex",
        "altText": f"📊【價值投資選股】盤後精選 ({target_date})",
        "contents": {
            "type": "bubble",
            "size": "giga" if elder_mode else "mega",
            "header": header_box,
            "body": body_box,
            "footer": footer_box
        }
    }


def build_single_stock_flex_message(
    db: Session,
    ticker: str,
    app_base_url: str = "https://value-invest.app"
) -> Dict[str, Any]:
    """
    建構單一股票即時查詢的 LINE Flex Message 視覺化卡片
    """
    stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
    if not stock:
        return {}

    p_row = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.desc()).first()
    v_row = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == ticker).order_by(ValuationBandsRecord.date.desc()).first()
    g_row = db.query(GoodCompanyRecord).filter(GoodCompanyRecord.ticker == ticker).order_by(GoodCompanyRecord.date.desc()).first()

    cur_price = f"${p_row.close:.1f} 元" if p_row else "暫無報價"
    zone_color_map = {
        "special": ("特價區", "#2563EB"),
        "cheap": ("便宜區", "#38BDF8"),
        "fair": ("合理區", "#00F59B"),
        "expensive": ("昂貴區", "#FBBF24"),
        "crazy": ("瘋狂區", "#A855F7")
    }
    zone_label, zone_color = zone_color_map.get(v_row.current_zone if v_row else "fair", ("合理區", "#00F59B"))

    margin_str = ""
    if v_row and p_row and v_row.p2 > 0:
        m_pct = round((v_row.p2 - p_row.close) / v_row.p2 * 100.0, 1)
        margin_str = f"折價空間 {m_pct:+.1f}%"

    lights_summary = "良好"
    if g_row:
        lights_summary = "優良 (全數符合)" if g_row.overall == "good" else ("觀察 (部分達標)" if g_row.overall == "watch" else "警戒 (需留意風險)")

    return {
        "type": "flex",
        "altText": f"📊【{stock.company_name} ({ticker})】價值分析快報",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0B0F19",
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{stock.company_name} ({ticker})",
                        "weight": "bold",
                        "color": "#FFFFFF",
                        "size": "xl"
                    },
                    {
                        "type": "text",
                        "text": f"所屬產業：{stock.industry or '綜合'} ｜ 價值估值快報",
                        "color": "#94A3B8",
                        "size": "xs",
                        "margin": "xs"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0B0F19",
                "paddingStart": "16px",
                "paddingEnd": "16px",
                "paddingBottom": "16px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "backgroundColor": "#141D2E",
                        "cornerRadius": "6px",
                        "paddingAll": "12px",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "flex": 1,
                                "contents": [
                                    {"type": "text", "text": "最新收盤價", "color": "#94A3B8", "size": "xxs"},
                                    {"type": "text", "text": cur_price, "weight": "bold", "color": "#FFFFFF", "size": "md", "margin": "xs"}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "flex": 1,
                                "contents": [
                                    {"type": "text", "text": "河流圖位階", "color": "#94A3B8", "size": "xxs"},
                                    {"type": "text", "text": zone_label, "weight": "bold", "color": zone_color, "size": "md", "margin": "xs"}
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"● 安全邊際：{margin_str or '無折價空間'}",
                                "color": "#00F59B" if "+" in margin_str else "#CBD5E1",
                                "size": "sm"
                            },
                            {
                                "type": "text",
                                "text": f"● 好公司體質健檢：{lights_summary}",
                                "color": "#CBD5E1",
                                "size": "sm",
                                "margin": "xs"
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0E1524",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "📈 查看完整河流圖與體質評分",
                            "uri": f"{app_base_url}/#detail?ticker={ticker}"
                        },
                        "style": "primary",
                        "color": "#2563EB",
                        "height": "sm"
                    }
                ]
            }
        }
    }

def generate_binding_code(db: Session, user_id: str = "default_user") -> Dict[str, Any]:
    """
    產生 6 位一次性綁定驗證碼 (10 分鐘內有效)
    """
    code = f"{random.randint(100000, 999999)}"
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=10)

    binding = db.query(LineBinding).filter(LineBinding.user_id == user_id).first()
    if not binding:
        binding = LineBinding(
            user_id=user_id,
            binding_code=code,
            code_expires_at=expires_at,
            status="pending"
        )
        db.add(binding)
    else:
        binding.binding_code = code
        binding.code_expires_at = expires_at
        if binding.status != "bound":
            binding.status = "pending"

    db.commit()
    db.refresh(binding)

    return {
        "user_id": user_id,
        "binding_code": code,
        "expires_at": expires_at.isoformat(),
        "seconds_valid": 600,
        "status": binding.status
    }


def get_binding_status(db: Session, user_id: str = "default_user") -> Dict[str, Any]:
    """取得當前使用者之 LINE 綁定狀態"""
    binding = db.query(LineBinding).filter(LineBinding.user_id == user_id).first()
    if not binding:
        return {
            "user_id": user_id,
            "status": "not_bound",
            "is_bound": False,
            "line_user_id": None
        }

    is_bound = (binding.status == "bound" and binding.line_user_id is not None)
    masked_id = (binding.line_user_id[:6] + "..." + binding.line_user_id[-4:]) if binding.line_user_id else None

    return {
        "user_id": user_id,
        "status": binding.status,
        "is_bound": is_bound,
        "line_user_id_masked": masked_id,
        "bound_at": binding.bound_at.isoformat() if binding.bound_at else None,
        "consent_at": binding.consent_at.isoformat() if binding.consent_at else None
    }


def unbind_line_account(db: Session, user_id: str = "default_user") -> Dict[str, Any]:
    """解除使用者 LINE 帳號綁定"""
    binding = db.query(LineBinding).filter(LineBinding.user_id == user_id).first()
    if not binding:
        return {"status": "not_found", "message": "無綁定紀錄"}

    binding.status = "pending"
    binding.line_user_id = None
    binding.binding_code = None
    binding.code_expires_at = None
    binding.unbound_at = datetime.utcnow()
    db.commit()

    return {"status": "success", "message": "已成功解除 LINE 帳號綁定"}


def verify_line_signature(body_bytes: bytes, signature: str, secret: Optional[str] = None) -> bool:
    """驗證 LINE Webhook X-Line-Signature 簽名"""
    sec = secret or SETTINGS.LINE_CHANNEL_SECRET
    if not sec:
        # 若未設定 Channel Secret，在開發環境中放行
        return True
    hash_val = hmac.new(sec.encode("utf-8"), body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(hash_val).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def send_reply_message(reply_token: str, message: Union[str, Dict[str, Any]]) -> bool:
    """發送 LINE Webhook 快速回覆訊息 (支援純文字或 Flex Message 物件)"""
    token = SETTINGS.LINE_CHANNEL_ACCESS_TOKEN
    msg_obj = {"type": "text", "text": message} if isinstance(message, str) else message

    if not token or not reply_token:
        logger.info(f"[Dry Run Reply] {msg_obj.get('text') or msg_obj.get('altText') or 'Flex Message'}")
        return True

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [msg_obj]
    }
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=5.0)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"發送 LINE 回覆訊息失敗: {e}")
        return False


def handle_line_webhook(db: Session, body_bytes: bytes, signature: str) -> Dict[str, Any]:
    """
    處理來自 LINE 官方帳號的 Webhook 事件
    """
    if not verify_line_signature(body_bytes, signature):
        return {"status": "invalid_signature", "processed_events": 0}

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {"status": "bad_json", "processed_events": 0}

    events = data.get("events", [])
    processed = 0

    for ev in events:
        ev_type = ev.get("type")
        source = ev.get("source", {})
        line_uid = source.get("userId")
        reply_token = ev.get("replyToken")

        # 1. 好友追蹤事件 (follow)
        if ev_type == "follow":
            reply_msg = (
                "👋 歡迎加入【價值投資選股】官方帳號！\n\n"
                "請在 App 內點選「設定」→「綁定 LINE」，取得 6 位一次性驗證碼後在此直接回覆該 6 位代碼完成綁定。\n\n"
                "綁定後將於每個交易日 18:30 為您推播盤後好公司精選與安心心法！"
            )
            if reply_token:
                send_reply_message(reply_token, reply_msg)
            processed += 1

        # 2. 封鎖或取消追蹤 (unfollow)
        elif ev_type == "unfollow" and line_uid:
            binding = db.query(LineBinding).filter(LineBinding.line_user_id == line_uid).first()
            if binding:
                binding.status = "blocked"
                db.commit()
                logger.info(f"使用者封鎖官方帳號，已標記 blocked: {line_uid}")
            processed += 1

        # 3. 訊息事件 (message)
        elif ev_type == "message":
            msg_obj = ev.get("message", {})
            if msg_obj.get("type") == "text":
                text = msg_obj.get("text", "").strip()
                reply_text = process_line_incoming_text(db, text=text, line_uid=line_uid)
                if reply_token and reply_text:
                    send_reply_message(reply_token, reply_text)
                processed += 1

    return {"status": "success", "processed_events": processed}


def process_line_incoming_text(db: Session, text: str, line_uid: Optional[str] = None) -> str:
    """
    處理 LINE 使用者文字訊息，支援 6 位綁定碼、4 碼個股快查、精選名單、投資心法與白話辭典 (規格書 15.3, 15.4)
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    # 1. 6 位數字綁定碼
    if cleaned.isdigit() and len(cleaned) == 6:
        now = datetime.utcnow()
        target_binding = db.query(LineBinding)\
            .filter(LineBinding.binding_code == cleaned, LineBinding.code_expires_at >= now)\
            .first()

        if target_binding:
            target_binding.line_user_id = line_uid
            target_binding.status = "bound"
            target_binding.consent_at = now
            target_binding.bound_at = now
            target_binding.binding_code = None  # 一次性使用後註銷
            target_binding.code_expires_at = None
            db.commit()

            return (
                "🎉【綁定成功】\n"
                "已成功綁定您的價值投資選股 App！\n\n"
                "📌 推播時間：每個交易日 18:30\n"
                "📌 推播內容：好公司每日價值精選、早期轉強候選與投資心法\n"
                "📌 解除方式：可隨時於 App 設定頁點擊「解除綁定」或封鎖本帳號\n\n"
                "※ 本系統僅供量化價值研究，非任何投資買賣指令。"
            )
        else:
            return "❌ 驗證碼無效或已過期（有效時限 10 分鐘）。\n請至 App 設定頁重新產生 6 位綁定碼後再試。"

    # 2. 4 碼股票代號查詢 (例如 "2330" 或 "查 2330" 或 "查詢 2330")
    import re
    match = re.search(r'(?:查|查詢|股價|估值)?\s*([0-9]{4})', cleaned)
    if match and len(cleaned) <= 10:
        ticker = match.group(1)
        stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
        if not stock:
            return (
                f"🔍 股池中暫無股票代號【{ticker}】。\n\n"
                "💡 本系統核心股池為 0050、0056、00881、00891 聯集成分股與自選股。\n"
                "若欲追蹤此標的，請開啟 App 至「設定」→「新增自選股」，系統將自動為您回補近 5 年數據！"
            )

        p_row = db.query(PriceDaily).filter(PriceDaily.ticker == ticker).order_by(PriceDaily.date.desc()).first()
        v_row = db.query(ValuationBandsRecord).filter(ValuationBandsRecord.ticker == ticker).order_by(ValuationBandsRecord.date.desc()).first()
        g_row = db.query(GoodCompanyRecord).filter(GoodCompanyRecord.ticker == ticker).order_by(GoodCompanyRecord.date.desc()).first()

        cur_price = f"${p_row.close:.1f} 元" if p_row else "暫無報價"
        zone_map = {
            "special": "🔵 特價區",
            "cheap": "🟢 便宜區",
            "fair": "🟢 合理區",
            "expensive": "🟠 昂貴區",
            "crazy": "🟣 瘋狂區"
        }
        zone_str = zone_map.get(v_row.current_zone if v_row else "fair", "合理區")
        margin_str = ""
        if v_row and p_row and v_row.p2 > 0:
            m_pct = round((v_row.p2 - p_row.close) / v_row.p2 * 100.0, 1)
            margin_str = f" (折價空間 {m_pct:+.1f}%)"

        lights_summary = "良好 (5燈全亮)"
        if g_row:
            lights_summary = f"{'🟢 優良' if g_row.overall == 'good' else ('🟡 觀察' if g_row.overall == 'watch' else '🔴 警戒')}"

        return (
            f"📊【{stock.company_name} ({ticker}) 價值分析快報】\n"
            f"----------------------------\n"
            f"● 最新收盤價：{cur_price}\n"
            f"● 河流圖位階：{zone_str}{margin_str}\n"
            f"● 好公司健檢：{lights_summary}\n"
            f"● 所屬產業別：{stock.industry or '未分類'}\n"
            f"----------------------------\n"
            f"💡 先選好公司，再等好價格。\n"
            f"開啟 App 可查看完整五段河流圖、漲跌拆解與 AI 深度研究報告！\n"
            f"※ 本訊息僅供客觀數據分析，非投資買賣指令。"
        )

    # 3. 查詢心法
    if cleaned in ["心法", "今日心法", "投資心法", "心理", "心態"]:
        tip = get_next_mindset_tip(db)
        return (
            "🧘【安心投資心法】\n\n"
            f"「{tip.text}」\n\n"
            "※ 平心專注於公司長線獲利能力，勿被每日市場雜音干擾情緒。"
        )

    # 4. 查詢精選名單
    if cleaned in ["精選", "今日精選", "盤後精選", "選股"]:
        return format_daily_line_message(db, elder_mode=False)

    # 5. 查詢專有名詞白話辭典 (例如 "辭典 本益比" 或 "辭典" 或 "字典")
    if cleaned.startswith("辭典") or cleaned.startswith("字典") or cleaned.startswith("名詞"):
        kw = cleaned.replace("辭典", "").replace("字典", "").replace("名詞", "").strip()
        if not kw:
            return (
                "📚【白話財務小辭典】\n\n"
                "常用查詢範例：\n"
                "• 輸入「辭典 本益比」\n"
                "• 輸入「辭典 河流圖」\n"
                "• 輸入「辭典 自由現金流」\n"
                "• 輸入「辭典 安全邊際」\n"
                "• 輸入「辭典 合約負債」\n\n"
                "請在「辭典」後面加上您想查詢的名詞！"
            )
        term_row = db.query(GlossaryTerm).filter(GlossaryTerm.term.contains(kw)).first()
        if term_row:
            return (
                f"📚【{term_row.term}】白話解析：\n\n"
                f"📌 白話解釋：\n{term_row.plain_explain}\n\n"
                f"💡 生活實例：\n{term_row.example or '無實例'}"
            )
        else:
            return f"查無與「{kw}」相符的專有名詞。建議輸入常見詞彙如：本益比、河流圖、自由現金流、安全邊際。"

    # 6. 預設幫助指引選單
    return (
        "💡【價值投資選股 智能助理指令指南】\n"
        "----------------------------\n"
        "• 輸入【4 碼股票代號】(如 2330)：即時查現價、河流圖價位區與好公司健檢\n"
        "• 輸入【精選】：查看今日盤後好公司價值精選名單\n"
        "• 輸入【心法】：隨機抽取一則安心價值投資心法\n"
        "• 輸入【辭典 名詞】(如「辭典 本益比」)：白話財務名詞速查\n"
        "• 輸入【6 位數字代碼】：綁定 App 每日 18:30 自動推播\n"
        "----------------------------\n"
        "※ 本官方帳號由選股引擎自動驅動，僅供客觀數據研究。"
    )


# =========================================================================
# LINE 訊息發送與 3 次重試防呆 (規格書 15.4, 15.5)
# =========================================================================

def send_line_push_with_retry(
    db: Session,
    message_payload: Optional[Union[str, Dict[str, Any]]] = None,
    user_id: str = "default_user",
    max_retries: int = 3,
    message_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    發送 LINE 訊息，支援純文字與 Flex Message 格式，支援定向推送與全域廣播。
    具備 3 次指數退避重試與 push_log 記錄 (規格書 15.5)。
    支援 message_payload 或相容 message_text 具名參數。
    """
    token = SETTINGS.LINE_CHANNEL_ACCESS_TOKEN
    binding = db.query(LineBinding).filter(LineBinding.user_id == user_id).first()
    target_line_uid = binding.line_user_id if binding and binding.status == "bound" else None

    actual_payload = message_payload if message_payload is not None else message_text
    if actual_payload is None:
        actual_payload = ""

    # 標準化 LINE messages 陣列
    if isinstance(actual_payload, str):
        msg_obj = {"type": "text", "text": actual_payload}
        preview_text = actual_payload[:200]
    else:
        msg_obj = actual_payload
        preview_text = msg_obj.get("altText", "[Flex Message]")

    # 若未提供 Token，回傳 Dry Run 結果
    if not token:
        logger.info(f"[LINE Dry-Run Push] Message:\n{preview_text}")
        log = PushLog(
            user_id=user_id,
            channel="line",
            status="dry_run",
            message_type="daily_pick",
            error=None
        )
        db.add(log)
        db.commit()
        return {
            "status": "dry_run",
            "message": "LINE_CHANNEL_ACCESS_TOKEN 未設定，已完成推播模擬 (Dry Run)",
            "preview": preview_text
        }

    # 決定發送端點：已綁定個別使用者用 push，否則用 broadcast
    if target_line_uid:
        url = "https://api.line.me/v2/bot/message/push"
        payload = {
            "to": target_line_uid,
            "messages": [msg_obj]
        }
    else:
        url = "https://api.line.me/v2/bot/message/broadcast"
        payload = {
            "messages": [msg_obj]
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=8.0)
            if resp.status_code == 200:
                log = PushLog(
                    user_id=user_id,
                    channel="line",
                    status="success",
                    message_type="daily_pick",
                    error=None
                )
                db.add(log)
                db.commit()
                return {"status": "success", "attempts": attempt}
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text}"
                logger.warning(f"LINE 推播第 {attempt} 次發送失敗: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"LINE 推播第 {attempt} 次請求異常: {last_error}")

        if attempt < max_retries:
            time.sleep(attempt * 1.5)  # 漸進重試退避

    # 3 次皆失敗，寫入 push_log
    log = PushLog(
        user_id=user_id,
        channel="line",
        status="failed",
        message_type="daily_pick",
        error=last_error
    )
    db.add(log)
    db.commit()

    return {"status": "failed", "attempts": max_retries, "error": last_error}


def send_line_broadcast(
    db: Session,
    pick_date: Optional[date] = None,
    elder_mode: bool = False,
    use_flex: bool = False
) -> Dict[str, Any]:
    """同步供排程器或 API 呼叫之日推播入口函式 (支援純文字或 Flex 格式)"""
    if use_flex:
        msg = build_daily_line_flex_message(db, pick_date=pick_date, elder_mode=elder_mode)
    else:
        msg = format_daily_line_message(db, pick_date=pick_date, elder_mode=elder_mode)
    return send_line_push_with_retry(db, message_payload=msg)
