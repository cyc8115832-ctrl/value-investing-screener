"""
價值投資選股 App - ETF 持股清洗模組 (cleaner.py)
遵循技術規格書 V1.7 第 2.4 節持股清洗規則：
- 台股期貨、指數期貨：排除（非個股）
- 現金、應收付款、保證金：排除
- 海外標的、ETF 本身、債券：排除，V1 僅收台股上市櫃普通股
- 特別股、存託憑證：預設排除 (D-12)
- 代號對照：以股票代號為主鍵，標準化公司名稱
"""

from typing import List, Dict, Any, Tuple
import re

# 非股票關鍵字排除列表
NON_STOCK_KEYWORDS = [
    "期貨", "TX", "TF", "MTX", "現金", "存款", "保證金", "應收", "應付",
    "債券", "債", "美債", "國債", "公債", "公司債", "REPO", "附買回",
    "基金", "ETF", "託管", "權證", "認購", "認售", "牛證", "熊證"
]

def is_valid_tw_stock_ticker(ticker: str) -> bool:
    """
    台股上市櫃普通股代號驗證：
    一般為 4 位數字 (如 2330, 2454) 或部分特殊 4 碼。
    排除 5 碼特別股 (如 2881A)、6 碼權證、或含英文字母非普通股標的。
    """
    if not ticker:
        return False
    # 嚴格 4 碼純數字，代表一般普通股
    return bool(re.match(r"^\d{4}$", ticker.strip()))


def clean_etf_holdings(raw_holdings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    清洗原始 ETF 持股清單。
    輸入格式為 list of dict，每個元素含 'ticker', 'name', 'weight' 等。
    輸出：(有效持股清單, 被過濾排除清單)
    """
    valid_holdings = []
    excluded_items = []

    for item in raw_holdings:
        ticker = str(item.get("ticker", "")).strip()
        name = str(item.get("name", "")).strip()
        weight = float(item.get("weight", 0.0))

        # 1. 檢查是否包含非股票關鍵字
        hit_keyword = next((kw for kw in NON_STOCK_KEYWORDS if kw in name), None)
        if hit_keyword:
            excluded_items.append({
                "ticker": ticker,
                "name": name,
                "weight": weight,
                "reason": f"包含非股票關鍵字: {hit_keyword}"
            })
            continue

        # 2. 檢查代號格式 (排除特別股、權證等)
        if not is_valid_tw_stock_ticker(ticker):
            excluded_items.append({
                "ticker": ticker,
                "name": name,
                "weight": weight,
                "reason": f"代號非台股 4 碼普通股: {ticker}"
            })
            continue

        # 3. 權重合理性驗證 (必須大於 0)
        if weight <= 0:
            excluded_items.append({
                "ticker": ticker,
                "name": name,
                "weight": weight,
                "reason": "權重小於等於 0"
            })
            continue

        valid_holdings.append({
            "ticker": ticker,
            "name": name,
            "weight": weight
        })

    return valid_holdings, excluded_items
