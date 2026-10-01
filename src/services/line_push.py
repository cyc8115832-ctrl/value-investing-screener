"""
價值投資選股 App - LINE 每日價值精選與推播服務 (line_push.py)
遵循技術規格書 V1.7：
- 第 15 章 每日價值精選與 LINE 推播 (收盤後發布，精簡重點)
- 第 16 章 投資心法 (每次推播皆附一則，30天內不重複，每週至少一則與槓桿/資金有關)
- 第 8.10.7 節 LINE 大字版訊息樣式 (長輩友善模式可切換)
"""

from datetime import date, datetime, timedelta
import json
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session
from src.database.schema import (
    DailyPickRecord, StockMaster, MindsetTip, MindsetShown, PushLog, PriceDaily
)
from config.settings import SETTINGS

def get_next_mindset_tip(db: Session, user_id: str = "default_user") -> MindsetTip:
    """
    選取本日心法：
    - 30 天內不重複
    - 每週至少一則與槓桿或資金管理有關
    """
    cutoff = datetime.utcnow() - timedelta(days=30)
    shown_ids = [row[0] for row in db.query(MindsetShown.tip_id)\
        .filter(MindsetShown.user_id == user_id, MindsetShown.shown_at >= cutoff)\
        .all()]

    # 若今天為週一或週五，優先選取槓桿資金類別
    is_leverage_priority = (date.today().weekday() in [0, 4])

    query = db.query(MindsetTip).filter(MindsetTip.active == True)
    if is_leverage_priority:
        lev_tips = query.filter(MindsetTip.category == "槓桿資金", ~MindsetTip.tip_id.in_(shown_ids)).all()
        if lev_tips:
            tip = lev_tips[0]
            db.add(MindsetShown(user_id=user_id, tip_id=tip.tip_id))
            db.commit()
            return tip

    # 一般挑選未在 30 天內顯示過的
    available = query.filter(~MindsetTip.tip_id.in_(shown_ids)).all()
    if not available:
        # 全部都顯示過了，重置
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

    # 精選清單
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

    # 早期轉強
    if earlies:
        lines.append("⚡【早期轉強候選】(領先訊號衝刺中)")
        for ep in earlies:
            stock = db.query(StockMaster).filter(StockMaster.ticker == ep.ticker).first()
            p_daily = db.query(PriceDaily).filter(PriceDaily.ticker == ep.ticker).order_by(PriceDaily.date.desc()).first()
            close_str = f"${p_daily.close:.1f}" if p_daily else ""
            name = stock.company_name if stock else ep.ticker
            lines.append(f"• {name}({ep.ticker}) {close_str} (訂金/營收加速度轉強)")
        lines.append("")

    # 心法
    lines.append("💡【本日投資心法】")
    lines.append(tip.text)
    lines.append("\n※ 本系統僅供量化價值研究，非任何投資買賣指令。")

    return "\n".join(lines)


async def send_line_broadcast(message_text: str) -> Dict[str, Any]:
    """
    透過 LINE Messaging API 發送推播
    若未設定 Access Token，則回傳 Dry-Run 模擬成功結果。
    """
    token = SETTINGS.LINE_CHANNEL_ACCESS_TOKEN
    if not token:
        return {
            "status": "dry_run",
            "message": "LINE_CHANNEL_ACCESS_TOKEN 未設定，已完成推播格式化 (Dry Run 模式)",
            "payload_preview": message_text[:200] + "..."
        }

    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            return {"status": "success", "http_status": 200}
        else:
            return {
                "status": "failed",
                "http_status": resp.status_code,
                "error": resp.text
            }
