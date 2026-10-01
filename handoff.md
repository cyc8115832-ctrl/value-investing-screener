# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》與《V3.0 深度架構規劃》，全系統二十個開發與運維里程碑已全數落地並驗收完畢，達成生產發布版與完整實盤運維閉環：

1. **全系統最終交付驗收與產品發布手冊（階段二十落地）**：
   - 產出完整旗艦級文件 [`RELEASE_NOTES_V3.0.md`](file:///d:/user/Documents/價值投資選股App/RELEASE_NOTES_V3.0.md)，涵蓋：
     - 規格書第 1 章至第 21 章與全部 D-1 ~ D-27 待決事項之 100% 履約對照表。
     - 估值河流圖、好公司健檢、EPS、領先訊號、神奇公式、現金流品質、AI 研究員與 HHI 風控核心技術矩陣。
     - 炭黑帳本 UI、長輩友善模式、語音朗讀、新手沙盒與 13 篇手冊/26 條辭典說明。
     - 實盤運維 CLI 工具鏈（daily_pipeline, send_test_push, backup_db, health_check）。
     - 24 條 RESTful API 完整端點清單。
     - LINE Webhook 官方帳號上線指南與生產容器化配置。

2. **端到端生產健康診斷引擎（階段十九落地）**：
   - [`scripts/health_check.py`](file:///d:/user/Documents/價值投資選股App/scripts/health_check.py)：端到端冒煙測試（Smoke Test）工具，實測綜合健康指數 100/100 滿分通過。
   - Win32 終端編碼（UTF-8 wrapper）與 pytest capture 完全隔離。

3. **實盤運維 CLI 工具鏈（階段十八落地）**：
   - `scripts/daily_pipeline.py`、`scripts/send_test_push.py`、`scripts/backup_db.py`。

4. **全專案測試達到 102 項全數通過**：
   - 執行 `.\.venv\Scripts\pytest.exe -v`：**102 passed, 0 failed（100% 綠燈）**。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，造訪 `http://127.0.0.1:8000`。
  - 容器啟動：執行 `docker compose up -d` 即可在容器中常駐運行並自動健檢。
  - 健康體檢：執行 `.\.venv\Scripts\python.exe scripts/health_check.py` 即時獲取 100/100 滿分報告。
  - 排程執行：執行 `.\.venv\Scripts\python.exe scripts/daily_pipeline.py --push` 每日定時自動重算。
  - 資料庫備份：執行 `.\.venv\Scripts\python.exe scripts/backup_db.py` 定期零鎖定熱備份。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 102 passed（100% 通過）。
- **合規性**：無任何投資買賣指令文字，維持客觀量化研究定位。

## ➡️ 下一步（正式實盤運維建議）
1. **排程掛載**：在伺服器（Windows 工作排程器或 Linux crontab）掛載兩項定時工作：
   - 每日 15:30 執行 `scripts/daily_pipeline.py --push`
   - 每日 03:00 執行 `scripts/backup_db.py --keep-days 14`
2. **開盤前巡檢**：設定每日 08:30 開盤前執行 `scripts/health_check.py` 進行系統自檢。
3. **LINE Webhook 上線**：在 LINE Developers 後台配置正式 HTTPS 域名指向 `/api/line/webhook`。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- 備份路徑：預設存放在 `data/backups/`，透過滾動清理機制維持磁碟健康。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 18:15
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git status：✅ 本次修改已備妥，待提交推送
