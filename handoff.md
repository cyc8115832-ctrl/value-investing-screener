# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》與後續擴充規劃，已全面完成「階段十一：生產環境容器化部署與外部市場資料適配器」之研發、整合與驗證：

1. **生產級 Docker 容器化套件**：
   - `Dockerfile`：基於 Python 3.12-slim，配置台北時區 (`Asia/Taipei`)、非特權安全用戶 (`appuser`)、健康檢查指令 (`curl -f http://localhost:8000/health`) 與持久化儲存卷 (`/app/data`)。
   - `docker-compose.yml`：配置服務編排、端口映射、環境變數 (`DATABASE_URL`, `TZ`, `LINE_CHANNEL_ACCESS_TOKEN`, `FINMIND_API_TOKEN`) 與本地 `./data:/app/data` Volume 持久化掛載。
   - `.dockerignore`：排除虛擬環境、測試快取、日誌與暫存檔。

2. **雙層健康檢查與系統維運狀態端點**：
   - `GET /health`：根級極速心跳檢查，專為 Docker/K8s Liveness Probe 設計（<1ms）。
   - `GET /api/health`：API 層級詳細健康診斷，測試資料庫連線、統計股池標的數、檢驗最新報價日期與背景排程器存活狀態。
   - `GET /api/system/status`：系統環境與維運報表，提供主機 OS、UTC/本地時間、股池總檔數、自選股數、觀察清單筆數、有效 LINE 訂閱用戶數與市場資料源狀態。

3. **外部台股市場資料適配器（`src/data/external_market_source.py`）**：
   - 支援外掛式實盤 API（如 FinMind / RESTful JSON），可拉取日 K 線與三大法人日買賣超。
   - 內建 5 分鐘 TTL 記憶體快取，防止重複高頻調用觸發速率限制。
   - 具備連線超時防呆與「自動優雅降級（Fallback to TWSE OpenAPI / Local DB）」，嚴格保證 0 崩潰（Zero Crash Guarantee）。

4. **跨平台一鍵啟動與運維腳本**：
   - `scripts/start.bat`：Windows Command Prompt 一鍵雙擊啟動。
   - `scripts/start.ps1`：Windows PowerShell 一鍵彩色輸出啟動。
   - `scripts/entrypoint.sh`：Linux / Docker 容器自動化啟動腳本。

5. **測試與品質保證（100% 全數 PASS）**：
   - 新增 `tests/test_deployment_and_adapters.py`（7 項新增測試）。
   - 專案總測試增至 **75 項全數通過**（100% 綠燈無任何報錯）。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：直接執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，瀏覽器存取 `http://127.0.0.1:8000`。
  - Docker 啟動：執行 `docker compose up -d` 即可在容器中常駐運行並自動健檢。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 75 passed（100% 通過）。
- **合規性**：全 App、手冊、推播與 AI 報告無真人姓名或他人商標，無任何買賣指令式文字。

## ➡️ 下一步（後續擴充規劃）
1. **上線發行與實盤監控**：配置正式生產網址與 SSL 憑證。
2. **LINE 官方帳號上線**：在 LINE Developers 後台設定 Webhook URL 指向 `/api/line/webhook` 並填入正式 Token。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- Docker 持久化：使用 Docker 部署時，確保主機端 `./data` 目錄具備讀寫權限，防止資料庫寫入被拒。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 15:45
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git push：✅ 待本次提交後推至 `cyc8115832-ctrl/value-investing-screener`
