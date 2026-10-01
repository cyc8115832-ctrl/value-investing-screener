# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》與《V3.0 深度架構規劃》，全系統二十二個里程碑已全數落地並驗收完畢，達成生產發布版、雲地自動化維運與科學化資金管理閉環：

1. **價值投資資金部位配置與動態再平衡引擎（階段二十二落地）**：
   - [`src/engines/portfolio_allocator.py`](file:///d:/user/Documents/價值投資選股App/src/engines/portfolio_allocator.py)：實作純函式科學化資金管理引擎：
     - 堅守價值投資防守紀律：戰略現金儲備預留（預設 20%）、單一持股風控上限（預設 20% 封頂，溢額安全回流現金池）。
     - 河流圖動態加權：特價區 2.0x 基礎權重、便宜區 1.0x 基礎權重，並按安全邊際（margin %）線性加乘；合理/昂貴/瘋狂區與劣質公司不予配置。
     - 台股交易單位適配：支援整張（1,000 股向下取整）與零股計算。
     - 守株待兔防守機制：當無符合標的時，100% 資金保留於現金池等待好價格。
   - [`src/web/api/routes.py`](file:///d:/user/Documents/價值投資選股App/src/web/api/routes.py)：掛載 `POST /api/portfolio/calculate-allocation`，支援自選候選名單或全股池自動抓取特價好公司。
   - [`src/web/templates/index.html`](file:///d:/user/Documents/價值投資選股App/src/web/templates/index.html)：於「我的觀察（Tab 4）」新增純黑高對比資金部位試算器 UI，支援即時試算、3 大指標卡、明細表格與風控封頂提醒。
   - [`tests/test_portfolio_allocator.py`](file:///d:/user/Documents/價值投資選股App/tests/test_portfolio_allocator.py)：新增 6 項單元與整合測試，覆蓋率 100%。

2. **GitHub Actions 雲端 CI/CD 自動化整合管線（階段二十一落地）**：
   - 建立 [`.github/workflows/ci.yml`](file:///d:/user/Documents/價值投資選股App/.github/workflows/ci.yml)，在每次 push / PR 自動於 GitHub Ubuntu runner 上執行單元測試、端到端冒煙測試與 Docker 構建。

3. **Windows 實盤排程一鍵配置器（階段二十一落地）**：
   - [`scripts/setup_scheduler.ps1`](file:///d:/user/Documents/價值投資選股App/scripts/setup_scheduler.ps1)：在 Windows Task Scheduler 一鍵註冊/檢視/卸載/測試三大實盤定時維運工作。

4. **端到端生產健康診斷引擎（階段十九落地）**：
   - `scripts/health_check.py`：端到端冒煙測試（Smoke Test）工具，綜合健康指數 100/100 滿分通過。

5. **全專案測試達到 108 項全數通過**：
   - 執行 `.\.venv\Scripts\pytest.exe`：**108 passed, 0 failed（100% 綠燈）**。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，造訪 `http://127.0.0.1:8000`。
  - 容器啟動：執行 `docker compose up -d` 即可在容器中常駐運行。
  - 資金試算：造訪網頁「我的觀察」分頁即可直接進行科學化資金部位分配與動態試算。
  - 實盤排程：執行 `powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduler.ps1 -Action Install` 即可註冊 Windows 全自動排程。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 108 passed（100% 通過）。
- **體檢狀態**：`.\.venv\Scripts\python.exe scripts/health_check.py` 100/100 HEALTHY。
- **合規性**：無任何投資買賣指令文字，維持客觀量化研究與資金控管定位。

## ➡️ 下一步（正式實盤運維建議）
1. **排程啟用**：在正式主機執行 `.\scripts\setup_scheduler.ps1 -Action Install` 啟用定時任務。
2. **LINE Webhook 上線**：在 LINE Developers 後台配置正式 HTTPS 域名指向 `/api/line/webhook`。
3. **長期實盤監控**：定期檢視 `data/backups/` 滾動備份與盤後 15:30 自動重算日誌。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- 備份路徑：預設存放在 `data/backups/`，透過滾動清理機制維持磁碟健康。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 18:28
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git status：✅ 階段二十二完成，待提交推送至遠端倉庫
