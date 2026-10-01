# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》待決事項 D-14、第 10 章與第 20.1 節，已全面完成「產業集中度風控分析」與「系統資料庫品質監控報告」之研發、整合與驗證：

1. **產業集中度分析與風控警示模組（規格書 13.10 & 待決事項 D-14）**：
   - 建立純函式模組 [`src/engines/industry_concentration.py`](file:///d:/user/Documents/價值投資選股App/src/engines/industry_concentration.py)：`analyze_industry_concentration(stocks, threshold=3)`。
   - 計算各產業入選檔數與佔比，引入權威赫芬達爾-赫希曼指數（HHI），量化計算投資組合產業分散度分數（0 ~ 100 分）。
   - 區分三態警示等級：🟢 產業配置分散（HHI ≤ 1500，分數 85~100 分）、🟡 產業輕度集中（1500 < HHI ≤ 2500，分數 70~84 分）、🔴 產業高度集中（HHI > 2500，分數 < 70 分）。
   - 當單一產業（如科技半導體）入選達門檻（預設 3 檔）時，自動生成溫和風險提示文案，叮嚀適度分散至傳產或金融防禦配置。

2. **資料品質監控與異常檢查服務（規格書第 10 章 & 20.1 節）**：
   - 建立後端服務 [`src/services/data_quality.py`](file:///d:/user/Documents/價值投資選股App/src/services/data_quality.py)：`get_data_quality_report(db)`。
   - 盤後全自動評估四大指標加權健康指數：日價格覆蓋率 (30%)、月營收連續性 (30%)、季報三率完整度 (25%)、籌碼大戶覆蓋率 (15%)。
   - 產出健康等級評等（A+ / A / B / C）與狀態標籤（healthy / good / warning / danger）。
   - 數值異常值防呆健檢：負營收檢查與極端本益比（P/E > 150 或 P/E < 0）異常檢測。

3. **後端 API 路由與 LINE 每日推播深化**：
   - `GET /api/radar`：注入 `industry_concentration` 結構化資料（HHI、分散度評分、警示清單、產業佔比 Breakdown）。
   - `GET /api/data-quality/report`：新增資料品質監控端點，回傳四大覆蓋率指標、異常檢測結果與綜合健康評等。
   - `src/services/line_push.py`：在 `format_daily_line_message` 中注入精選名單產業集中度防呆；若單一產業 ≥ 2 檔時，自動於標準版與長輩版附加產業分散提醒。

4. **深色高對比前端 UI 渲染（`src/web/templates/index.html`）**：
   - 雷達首頁：更新 `#radarIndustryCard`，動態渲染 HHI 集中度指數、分散度評分、風控警示盒與各產業彩色進度條。
   - 系統設定頁：新增「🛡️ 系統資料庫品質監控與覆蓋率報告 (規格書第 10 章)」卡片，以高對比四宮格儀表板展示四大覆蓋率百分比與異常檢測結果。
   - 實作 `loadDataQualityReport()` 函式並於切換至設定頁時自動載入。

5. **測試與品質保證（100% 全數 PASS）**：
   - 新增 [`tests/test_industry_and_quality.py`](file:///d:/user/Documents/價值投資選股App/tests/test_industry_and_quality.py)（7 項新增單元與整合測試，包含純函式、服務、API、LINE 推播）。
   - 專案總測試增至 **87 項全數通過**（100% 綠燈，無任何失敗）。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：直接執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，瀏覽器存取 `http://127.0.0.1:8000`。
  - Docker 啟動：執行 `docker compose up -d` 即可在容器中常駐運行並自動健檢。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 87 passed（100% 通過）。
- **合規性**：維持客觀量化研究與風控提示定位，無真人姓名或他人商標，無任何買賣指令式文字。

## ➡️ 下一步（後續擴充規劃）
1. **上線發行與實盤監控**：配置正式生產網址與 SSL 憑證。
2. **LINE 官方帳號上線**：在 LINE Developers 後台設定 Webhook URL 指向 `/api/line/webhook` 並填入正式 Token。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- Docker 持久化：使用 Docker 部署時，確保主機端 `./data` 目錄具備讀寫權限，防止資料庫寫入被拒。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 16:25
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git push：✅ 待本次提交後推至 `cyc8115832-ctrl/value-investing-screener`
