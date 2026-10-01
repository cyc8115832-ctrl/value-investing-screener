# ========================================================
# 價值投資選股 App - PowerShell 一鍵啟動腳本
# ========================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSScriptRootDirectory = Split-Path -Parent $PSScriptRoot

Set-Location $PSScriptRootDirectory

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " 價值投資選股 App (Value Investing Screener) " -ForegroundColor Cyan
Write-Host " 版本: V3.0 (炭黑帳本高對比 UI / AI 價值研究員)" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $PSScriptRootDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[錯誤] 找不到本地虛擬環境: $VenvPython" -ForegroundColor Red
    Write-Host "請在專案目錄下執行: python -m venv .venv 進行環境初始化。" -ForegroundColor Yellow
    exit 1
}

Write-Host "[啟動中] 正在以本地虛擬環境啟動伺服器..." -ForegroundColor Green
Write-Host "🌐 瀏覽器請造訪: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "💡 按 Ctrl+C 可停止伺服器" -ForegroundColor Gray
Write-Host ""

& $VenvPython run.py
