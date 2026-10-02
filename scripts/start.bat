@echo off
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo [Error] Cannot find virtualenv .venv
    pause
    exit /b 1
)

echo ========================================================
echo   Value Investing Screener V3.0 Server Starting...
echo   Open browser at: http://127.0.0.1:8000
echo ========================================================
echo.
".venv\Scripts\python.exe" run.py
pause
