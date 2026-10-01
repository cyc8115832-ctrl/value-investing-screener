@echo off
chcp 65001 >nul
echo ========================================================
echo  價值投資選股 App (Value Investing Screener)
echo  版本: V3.0 (炭黑帳本深黑高對比 UI / AI 價值研究員)
echo ========================================================
echo.

cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo [警告] 找不到本機虛擬環境 .venv！
    echo 請先在專案目錄執行: python -m venv .venv 並安裝依賴。
    pause
    exit /b 1
)

echo [啟動中] 正在以 D 槽本地虛擬環境啟動伺服器...
echo 開啟瀏覽器訪問: http://127.0.0.1:8000
echo.
".venv\Scripts\python.exe" run.py
pause
