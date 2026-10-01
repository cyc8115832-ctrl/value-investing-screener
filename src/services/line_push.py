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
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session

from src.database.schema import (
    DailyPickRecord, StockMaster, MindsetTip, MindsetShown, PushLog, PriceDaily, LineBinding
)
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
# LINE 帳號綁定流程 (規格書 15.3)
# =========================================================================

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


def send_reply_message(reply_token: str, text: str) -> bool:
    """發送 LINE Webhook 快速回覆訊息"""
    token = SETTINGS.LINE_CHANNEL_ACCESS_TOKEN
    if not token or not reply_token:
        logger.info(f"[Dry Run Reply] {text}")
        return True

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
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

                # 比對 6 位代碼
                if text.isdigit() and len(text) == 6:
                    now = datetime.utcnow()
                    target_binding = db.query(LineBinding)\
                        .filter(LineBinding.binding_code == text, LineBinding.code_expires_at >= now)\
                        .first()

                    if target_binding:
                        target_binding.line_user_id = line_uid
                        target_binding.status = "bound"
                        target_binding.consent_at = now
                        target_binding.bound_at = now
                        target_binding.binding_code = None  # 一次性使用後註銷
                        target_binding.code_expires_at = None
                        db.commit()

                        success_msg = (
                            "🎉【綁定成功】\n"
                            "已成功綁定您的價值投資選股 App！\n\n"
                            "📌 推播時間：每個交易日 18:30\n"
                            "📌 推播內容：好公司每日價值精選、早期轉強候選與投資心法\n"
                            "📌 解除方式：可隨時於 App 設定頁點擊「解除綁定」或封鎖本帳號\n\n"
                            "※ 本系統僅供量化價值研究，非任何投資買賣指令。"
                        )
                        if reply_token:
                            send_reply_message(reply_token, success_msg)
                    else:
                        fail_msg = "❌ 驗證碼無效或已過期（有效時限 10 分鐘）。\n請至 App 設定頁重新產生 6 位綁定碼後再試。"
                        if reply_token:
                            send_reply_message(reply_token, fail_msg)
                else:
                    help_msg = (
                        "💡 若欲綁定 App 推播，請在此輸入 App 產生的 6 位數字驗證碼。\n"
                        "本帳號為自動推播機器人，暫不支援真人即時問答。"
                    )
                    if reply_token:
                        send_reply_message(reply_token, help_msg)
                processed += 1

    return {"status": "success", "processed_events": processed}


# =========================================================================
# LINE 訊息發送與 3 次重試防呆 (規格書 15.4, 15.5)
# =========================================================================

def send_line_push_with_retry(
    db: Session,
    message_text: str,
    user_id: str = "default_user",
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    發送 LINE 訊息，支援定向推送與全域廣播。
    具備 3 次指數退避重試與 push_log 記錄 (規格書 15.5)。
    """
    token = SETTINGS.LINE_CHANNEL_ACCESS_TOKEN
    binding = db.query(LineBinding).filter(LineBinding.user_id == user_id).first()
    target_line_uid = binding.line_user_id if binding and binding.status == "bound" else None

    # 若未提供 Token，回傳 Dry Run 結果
    if not token:
        logger.info(f"[LINE Dry-Run Push] Message:\n{message_text}")
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
            "preview": message_text[:200]
        }

    # 決定發送端點：已綁定個別使用者用 push，否則用 broadcast
    if target_line_uid:
        url = "https://api.line.me/v2/bot/message/push"
        payload = {
            "to": target_line_uid,
            "messages": [{"type": "text", "text": message_text}]
        }
    else:
        url = "https://api.line.me/v2/bot/message/broadcast"
        payload = {
            "messages": [{"type": "text", "text": message_text}]
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


def send_line_broadcast(db: Session, pick_date: Optional[date] = None, elder_mode: bool = False) -> Dict[str, Any]:
    """同步供排程器或 API 呼叫之日推播入口函式"""
    msg = format_daily_line_message(db, pick_date=pick_date, elder_mode=elder_mode)
    return send_line_push_with_retry(db, message_text=msg)
