"""
價值投資選股 App - 本地伺服器啟動腳本 (run.py)
執行：.\.venv\Scripts\python.exe run.py
預設監聽：http://127.0.0.1:8000
"""

import uvicorn
from config.settings import SETTINGS

if __name__ == "__main__":
    print(f"啟動 {SETTINGS.APP_NAME} v{SETTINGS.APP_VERSION} 伺服器...")
    print("瀏覽器請開啟：http://127.0.0.1:8000")
    uvicorn.run("src.web.app:app", host="127.0.0.1", port=8000, reload=False)
