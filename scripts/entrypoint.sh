#!/bin/bash
set -e

echo "=========================================================="
echo " 價值投資選股 App - Docker 容器化啟動程序"
echo " 運作環境: $(uname -s) / $(python -V)"
echo " 時區: ${TZ:-Asia/Taipei}"
echo "=========================================================="

# 確保資料目錄存在
mkdir -p /app/data

# 啟動應用程式
exec python run.py
