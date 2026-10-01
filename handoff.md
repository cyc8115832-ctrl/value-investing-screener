# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》與《V3.0 深度架構規劃》，全系統十八個里程碑已全數落地並驗收完畢，達成生產發布版與完整實盤運維閉環：

1. **實盤運維 CLI 工具鏈（階段十八落地）**：
   - [`scripts/daily_pipeline.py`](file:///d:/user/Documents/價值投資選股App/scripts/daily_pipeline.py)：盤後定時自動重算管線 CLI 腳本，支援 `--push` 自動發送推播與 `--date` 歷史回補，可由 Windows 工作排程器或 Linux cron 自動呼叫。
   - [`scripts/send_test_push.py`](file:///d:/user/Documents/價值投資選股App/scripts/send_test_push.py)：LINE 推播文字格式預覽與手動發送工具，支援標準版與長輩大字版樣式切換。
   - [`scripts/backup_db.py`](file:///d:/user/Documents/價值投資選股App/scripts/backup_db.py)：SQLite 零鎖定安全熱備份工具，使用原生 `Connection.backup()` 避免並發損壞，自動儲存至 `data/backups/` 並滾動清理超過 7 天之舊備份，杜絕磁碟膨脹。
   - [`tests/test_cli_and_ops.py`](file:///d:/user/Documents/價值投資選股App/tests/test_cli_and_ops.py)：新增 3 項針對熱備份、過期清理與 CLI 流程的單元測試。

2. **全專案測試達到 101 項全數通過**：
   - 執行 `.\.venv\Scripts\pytest.exe -v`：**101 passed, 0 failed（100% 綠燈）**。

3. **生產發布與文檔完善**：
   - `README.md` 更新「實盤運維 CLI 工具鏈」完整操作指引與 101 項測試指標。
   - `AGENTS.md` 路線圖已將階段十八標記為完成。
   - 收工技術小教室筆記已存入 `D:\user\Documents\00_Inbox`。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，造訪 `http://127.0.0.1:8000`。
  - 容器啟動：執行 `docker compose up -d` 即可在容器中常駐運行。
  - 排程執行：執行 `.\.venv\Scripts\python.exe scripts/daily_pipeline.py --push` 每日定時自動重算。
  - 資料庫備份：執行 `.\.venv\Scripts\python.exe scripts/backup_db.py` 定期熱備份。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 101 passed（100% 通過）。
- **合規性**：無任何投資買賣指令文字，維持客觀量化研究定位。

## ➡️ 下一步（正式實盤運維建議）
1. **排程掛載**：在伺服器（Windows 工作排程器或 Linux crontab）掛載兩項定時工作：
   - 每日 15:30 執行 `scripts/daily_pipeline.py --push`
   - 每日 03:00 執行 `scripts/backup_db.py --keep-days 14`
2. **LINE Webhook 上線**：在 LINE Developers 後台配置正式 HTTPS 域名指向 `/api/line/webhook`。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- 備份路徑：預設存放在 `data/backups/`，透過滾動清理機制維持磁碟健康。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 17:40
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git status：✅ 本次修改已備妥，待提交推送
