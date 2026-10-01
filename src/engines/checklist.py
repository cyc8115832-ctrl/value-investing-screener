"""
價值投資選股 App - 五階段檢核表與下單前五問定義模組 (checklist.py)
嚴格落實技術規格書 V1.7 第 16.5 與 16.6 章：
- 16.5 下單前 5 問（App 內檢查清單，V1）
- 16.6 五階段檢核表（選股、估值、買進、持有、賣出，V1.5）
- 系統不代為判斷、不阻擋操作、不記錄使用者實際交易
"""

from typing import List, Dict, Any

# 16.5 下單前 5 問
PRE_ORDER_QUESTIONS: List[Dict[str, Any]] = [
    {
        "index": 0,
        "question": "這筆錢三年內會用到嗎？",
        "hint": "只用三年內用不到的閒錢投資，避免被迫在低點變現。",
        "type": "pre_order"
    },
    {
        "index": 1,
        "question": "這筆錢是借來的嗎？（若是，請停下）",
        "hint": "不借錢投資、不融資槓桿，你要的是睡得安穩。",
        "type": "pre_order"
    },
    {
        "index": 2,
        "question": "我買它的理由，寫下來了嗎？",
        "hint": "把買進理由記錄在備忘筆記中，未來出場重新檢視依據。",
        "type": "pre_order"
    },
    {
        "index": 3,
        "question": "現在的價格在便宜區、合理區，還是昂貴區？",
        "hint": "確認目前處於河流圖的安全邊際區間，不追高。",
        "type": "pre_order"
    },
    {
        "index": 4,
        "question": "如果明天跌 20%，我還睡得著嗎？",
        "hint": "做好最壞心理準備與資金分批配置規劃。",
        "type": "pre_order"
    },
]

# 16.6 五階段檢核表
FIVE_STAGE_QUESTIONS: List[Dict[str, Any]] = [
    {
        "stage": "selection",
        "stage_name": "選股",
        "index": 0,
        "question": "這家公司的獲利是否逐年成長？它所在的產業，是不是「過去沒有、現在開始有、未來會很多」的趨勢？",
        "note_placeholder": "寫下你對產業趨勢與公司護城河的觀察...",
        "is_subjective": True,
    },
    {
        "stage": "valuation",
        "stage_name": "估值",
        "index": 0,
        "question": "這檔股票適合用哪種評價法？現在價格在河流圖的哪一區？",
        "note_placeholder": "確認評價法（本益比河流圖 / 淨值比河流圖 / 357股利法）與當前價位區間...",
        "is_subjective": False,
    },
    {
        "stage": "buying",
        "stage_name": "買進",
        "index": 0,
        "question": "價格在便宜或特價區嗎？我留了足夠的現金可以分批進場嗎？",
        "note_placeholder": "規劃預計進場梯次、資金分配與安全防護比例...",
        "is_subjective": False,
    },
    {
        "stage": "holding",
        "stage_name": "持有",
        "index": 0,
        "question": "每月營收與每季財報如預期嗎？獲利上修時，我有同步檢視目標價嗎？",
        "note_placeholder": "記錄最近月營收 YoY 與季報毛利率、預估 EPS 追蹤情況...",
        "is_subjective": False,
    },
    {
        "stage": "selling",
        "stage_name": "賣出",
        "index": 0,
        "question": "是否到達目標價？當初看好的理由還在嗎？有沒有更好的選擇？",
        "note_placeholder": "賣出的理由只有三個：到達目標價、買進理由消失、有更好的選擇。心情不好不是理由...",
        "is_subjective": False,
    },
]


def get_checklist_template() -> Dict[str, Any]:
    """取得預設檢核表模板與問題定義"""
    return {
        "pre_order": PRE_ORDER_QUESTIONS,
        "five_stages": FIVE_STAGE_QUESTIONS,
        "disclaimer": "清單與筆記由使用者自主勾選，僅供投資決策自我提醒，系統不代為判斷、不阻擋操作、不記錄實際交易。"
    }
