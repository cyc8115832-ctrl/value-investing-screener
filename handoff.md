# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》第 15 章（15.3, 15.4 LINE 雙向指令互動）與第 17 章（17.2 新手沙盒模擬練習模式 Sandbox Mode），已全面完成「LINE 官方帳號雙向智能指令引擎」與「新手沙盒模擬練習模式」之研發、整合與驗證：

1. **LINE 官方帳號雙向智能指令引擎（規格書 15.3, 15.4）**：
   - 建立指令處理器 [`src/services/line_push.py`](file:///d:/user/Documents/價值投資選股App/src/services/line_push.py) 中的 `process_line_incoming_text(db, text, line_uid)`。
   - 支援 4 碼股票代號即時查詢（如 `2330` 或 `查詢 2454`）：自動抓取最新收盤價、河流圖位階（特價/便宜/合理/昂貴/瘋狂）、折價空間與好公司燈號結論，即時回覆高可讀性文字卡片。
   - 支援關鍵字指令：輸入「心法」抽取一則安心投資心法；輸入「精選」產生今日盤後精選名單；輸入「辭典 [名詞]」（如 `辭典 本益比`）查詢白話名詞解析與生活實例。
   - 支援 6 位一次性驗證碼綁定與預設指令指南引導。

2. **新手沙盒模擬練習模式（規格書 17.2 Sandbox Mode）**：
   - 後端新增模擬標的數據端點 `GET /api/simulation/sample-stock`，提供「9999 範例科技 (練習沙盒)」完整假設財務數據、五段河流圖錨點、好公司五燈評等與 AI 研究員摘要。
   - 前端頂部 Header 配置「🧪 範例練習」開關按鈕。
   - 開啟沙盒模式時，頁面頂部浮現琥珀金醒目橫幅 `🧪【新手練習沙盒進行中】`，個股頁自動載入模擬標的，讓新手無壓力練習河流圖判定、五階段檢核與下單前 5 問。
   - 點擊「✕ 退出範例模式」隨時無縫返回真實股池。

3. **測試與品質保證（100% 全數 PASS）**：
   - 新增 [`tests/test_line_and_simulation.py`](file:///d:/user/Documents/價值投資選股App/tests/test_line_and_simulation.py)（6 項新增單元與整合測試）。
   - 專案總測試增至 **98 項全數通過**（100% 綠燈，無任何失敗）。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：直接執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，瀏覽器存取 `http://127.0.0.1:8000`。
  - Docker 啟動：執行 `docker compose up -d` 即可在容器中常駐運行並自動健檢。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 98 passed（100% 通過）。
- **合規性**：LINE 查詢與沙盒模式全數加註免責說明，維持客觀量化研究與教學定位，無任何買賣指令式文字。

## ➡️ 下一步（後續擴充規劃）
1. **上線發行與實盤監控**：配置正式生產網址與 SSL 憑證。
2. **LINE 官方帳號上線**：在 LINE Developers 後台設定 Webhook URL 指向 `/api/line/webhook` 並填入正式 Token。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- Docker 持久化：使用 Docker 部署時，確保主機端 `./data` 目錄具備讀寫權限，防止資料庫寫入被拒。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 17:00
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git push：✅ 待本次提交後推至 `cyc8115832-ctrl/value-investing-screener`
