# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》與《V3.0 深度架構規劃》，全系統二十一個里程碑已全數落地並驗收完畢，達成生產發布版與雲地雙重自動化維運閉環：

1. **GitHub Actions 雲端 CI/CD 自動化整合管線（階段二十一落地）**：
   - 建立 [`.github/workflows/ci.yml`](file:///d:/user/Documents/價值投資選股App/.github/workflows/ci.yml)，在每次 push / PR 自動於 GitHub Ubuntu runner 上執行：
     - Python 3.12 環境與依賴套件安裝
     - 102 項全單元測試（pytest -v）
     - 端到端冒煙測試（`health_check.py`）
     - Docker 容器鏡像建置驗證（`docker build`）

2. **Windows 實盤排程一鍵配置器（階段二十一落地）**：
   - [`scripts/setup_scheduler.ps1`](file:///d:/user/Documents/價值投資選股App/scripts/setup_scheduler.ps1)：在 Windows Task Scheduler 一鍵註冊/檢視/卸載/測試三大實盤定時維運工作：
     - `ValueInvesting_DailyPipeline_1530`：每週一至週五 15:30 盤後重算與 LINE 每日精選推播
     - `ValueInvesting_DatabaseBackup_0300`：每日凌晨 03:00 SQLite 零鎖定安全熱備份
     - `ValueInvesting_MorningHealth_0830`：每週一至週五 08:30 開盤前端到端健康體檢

3. **完整系統文檔與發布手冊（階段二十落地）**：
   - 旗艦級發布手冊 [`RELEASE_NOTES_V3.0.md`](file:///d:/user/Documents/價值投資選股App/RELEASE_NOTES_V3.0.md)，詳細記錄 100% 規格履約、24 條 RESTful API、CLI 指南與合規原則。
   - `README.md` 頂部配置 CI Passing、102 Tests、100/100 Health 狀態徽章。

4. **端到端生產健康診斷引擎（階段十九落地）**：
   - `scripts/health_check.py`：端到端冒煙測試（Smoke Test）工具，綜合健康指數 100/100 滿分通過。

5. **全專案測試達到 102 項全數通過**：
   - 執行 `.\.venv\Scripts\pytest.exe -v`：**102 passed, 0 failed（100% 綠燈）**。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，造訪 `http://127.0.0.1:8000`。
  - 容器啟動：執行 `docker compose up -d` 即可在容器中常駐運行。
  - 實盤排程安裝：執行 `powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduler.ps1 -Action Install` 即可註冊 Windows 全自動排程。
  - 實盤排程測試：執行 `powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduler.ps1 -Action TestRun`。
  - 雲端 CI/CD：已推送到 GitHub 私有倉庫，自動觸發 Actions 工作流。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 102 passed（100% 通過）。
- **合規性**：無任何投資買賣指令文字，維持客觀量化研究定位。

## ➡️ 下一步（正式實盤運維建議）
1. **排程啟用**：在正式主機執行 `.\scripts\setup_scheduler.ps1 -Action Install` 啟用定時任務。
2. **LINE Webhook 上線**：在 LINE Developers 後台配置正式 HTTPS 域名指向 `/api/line/webhook`。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- 備份路徑：預設存放在 `data/backups/`，透過滾動清理機制維持磁碟健康。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 18:20
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git status：✅ 本次修改已備妥，待提交推送
