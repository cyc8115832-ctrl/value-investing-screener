"""
價值投資選股 App - 全域環境與系統設定 (settings.py)
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from config.tbd_params import TBD_CONFIG, TBDParameters

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class AppSettings(BaseModel):
    APP_NAME: str = "價值投資選股 App"
    APP_VERSION: str = "1.7.0"
    DEBUG: bool = False

    # 資料庫設定 (儲存於專案 D 槽目錄下)
    DATABASE_URL: str = Field(default_factory=lambda: f"sqlite:///{DATA_DIR / 'value_investing.db'}")

    # LINE Messaging API 設定 (預設空字串，透過環境變數或設定頁填入)
    LINE_CHANNEL_ACCESS_TOKEN: str = Field(default_factory=lambda: os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""))
    LINE_CHANNEL_SECRET: str = Field(default_factory=lambda: os.getenv("LINE_CHANNEL_SECRET", ""))

    # TBD 參數
    tbd: TBDParameters = TBD_CONFIG

    # UI 主題方案：炭黑帳本 (Scheme B)
    THEME_COLORS: dict = {
        "bg_primary": "#0B0F19",       # 主背景：深黑
        "bg_card": "#131B2E",          # 卡片背景：深藍黑
        "bg_card_secondary": "#1E293B",# 次要卡片
        "border": "#2D3748",           # 邊框微光
        "text_primary": "#FFFFFF",     # 主要文字：純白
        "text_secondary": "#CBD5E1",   # 次要文字：淺銀灰
        "text_muted": "#94A3B8",       # 弱化文字：中灰
        
        # 五段價位專屬色
        "zone_special": "#2563EB",     # 特價：深藍
        "zone_cheap": "#38BDF8",       # 便宜：淺天藍
        "zone_fair": "#10B981",        # 合理：翡翠綠
        "zone_expensive": "#F59E0B",   # 昂貴：琥珀橘
        "zone_crazy": "#A855F7",       # 瘋狂：紫色
        "zone_crazy_text": "#1E1B4B",  # 瘋狂文字：深紫確保對比度
        
        # 狀態燈號
        "light_green": "#00F59B",      # 綠燈改善
        "light_yellow": "#FBBF24",     # 黃燈持平/警示
        "light_red": "#FF5252",        # 紅燈惡化
        "light_gray": "#64748B",       # 灰燈無資料
    }

SETTINGS = AppSettings()
