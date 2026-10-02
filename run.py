r"""
價值投資選股 App - 本地伺服器啟動腳本 (run.py)
執行：.\.venv\Scripts\python.exe run.py
預設監聽：http://127.0.0.1:8000
"""

import os
import uvicorn
from config.settings import SETTINGS

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"啟動 {SETTINGS.APP_NAME} v{SETTINGS.APP_VERSION} 伺服器...")
    print(f"監聽位址：http://{host}:{port} (本機造訪: http://127.0.0.1:{port})")
    uvicorn.run("src.web.app:app", host=host, port=port, reload=False)
