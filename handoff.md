# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》與《V3.0 深度架構規劃》，全系統二十三個里程碑已全數落地並驗收完畢，達成生產發布版、雲地自動化維運、資金風控與被動現金流複利試算全鏈路閉環：

1. **股息現金流複利滾雪球與長期被動收入試算引擎（階段二十三落地）**：
   - [`src/engines/dividend_snowball.py`](file:///d:/user/Documents/價值投資選股App/src/engines/dividend_snowball.py)：純函式股息滾雪球引擎：
     - 規格書 5.5 / 6.8b / 16.4 複利心法核心落實。
     - 支援初始本金、定期定額（DCA）、初始殖利率、股利年成長率、股價年化成長率、試算年數（5~30 年）與年化通膨率折現。
     - DRIP 股息再投入對比：量化展示「再投入買股 vs 現金領出」在 10~20 年後複利滾雪球的倍數級財富差距。
     - 持有成本殖利率（Yield on Cost, YoC）長期飆升分析與實質購買力折算。
     - 自動計算關鍵里程碑：資本回本年限（Payback Year）、年領 10 萬/50 萬/100 萬被動現金流達成年份。
   - [`src/web/api/routes.py`](file:///d:/user/Documents/價值投資選股App/src/web/api/routes.py)：新增 `POST /api/portfolio/dividend-snowball` RESTful 端點。
   - [`src/web/templates/index.html`](file:///d:/user/Documents/價值投資選股App/src/web/templates/index.html)：於「我的觀察（Tab 4）」新增純黑高對比雪球模擬器 UI，具備 4 大指標卡、里程碑標籤與年度軌跡表。
   - [`tests/test_dividend_snowball.py`](file:///d:/user/Documents/價值投資選股App/tests/test_dividend_snowball.py)：新增 6 項單元與整合測試，覆蓋率 100%。

2. **價值投資資金部位配置與動態再平衡引擎（階段二十二落地）**：
   - [`src/engines/portfolio_allocator.py`](file:///d:/user/Documents/價值投資選股App/src/engines/portfolio_allocator.py)：戰略現金儲備預留（20%）、單一持股風控上限（20% 封頂，溢額安全回流）、特價區 2.0x / 便宜區 1.0x 安全邊際加成、整張與零股試算。
   - API `POST /api/portfolio/calculate-allocation` 與前端純黑高對比資金試算卡片。

3. **GitHub Actions 雲端 CI/CD 自動化整合管線（階段二十一落地）**：
   - 建立 [`.github/workflows/ci.yml`](file:///d:/user/Documents/價值投資選股App/.github/workflows/ci.yml)，在每次 push / PR 自動於 GitHub runner 上執行全單元測試、端到端冒煙測試與 Docker 構建。

4. **端到端生產健康診斷引擎（階段十九落地）**：
   - `scripts/health_check.py`：端到端冒煙測試（Smoke Test）工具，綜合健康指數 100/100 滿分通過。

5. **全專案測試達到 114 項全數通過**：
   - 執行 `.\.venv\Scripts\pytest.exe`：**114 passed, 0 failed（100% 綠燈）**。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，造訪 `http://127.0.0.1:8000`。
  - 容器啟動：執行 `docker compose up -d` 即可在容器中常駐運行。
  - 資金與雪球試算：造訪網頁「我的觀察」分頁即可直接進行科學化資金部位分配與股息滾雪球長期被動收入模擬。
  - 實盤排程：執行 `powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduler.ps1 -Action Install` 即可註冊 Windows 全自動排程。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 114 passed（100% 通過）。
- **體檢狀態**：`.\.venv\Scripts\python.exe scripts/health_check.py` 100/100 HEALTHY。
- **合規性**：無任何投資買賣指令文字，維持客觀量化研究與複利試算定位。

## ➡️ 下一步（正式實盤運維建議）
1. **排程啟用**：在正式主機執行 `.\scripts\setup_scheduler.ps1 -Action Install` 啟用定時任務。
2. **LINE Webhook 上線**：在 LINE Developers 後台配置正式 HTTPS 域名指向 `/api/line/webhook`。
3. **長期實盤監控**：定期檢視 `data/backups/` 滾動備份與盤後 15:30 自動重算日誌。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- 備份路徑：預設存放在 `data/backups/`，透過滾動清理機制維持磁碟健康。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 18:55
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git status：✅ 階段二十三完成，待提交推送至遠端倉庫
