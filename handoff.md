# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據《價值投資選股App 技術規格書 V1.7》第 7 章（7.1 觀察清單主題分組、排序與研究筆記）與第 7.2 節（出場條件 3：有更好的選擇動態比對），已全面完成「觀察清單進階管理與出場換股決策模組」之研發、整合與驗證：

1. **自訂觀察群組與管理體系（規格書 7.1 / V1.5）**：
   - 建立自訂群組建立端點 `POST /api/watchlist/group/create` 與刪除端點 `DELETE /api/watchlist/group/{group_id}`。
   - 實作防重複同名檢查與「系統預設群組保護（不可刪除）」機制。
   - 刪除自訂群組時同步級聯清理組內成員，確保資料庫零殘留。

2. **組內標的排序與欄位排序（規格書 7.1）**：
   - 實作順序對調端點 `POST /api/watchlist/member/move?direction=up|down`，手機與長輩端點擊「⬆️ / ⬇️」按鈕即可調換順序，無需手勢長按。
   - 前端提供即時排序下拉選單：預設順序、安全邊際（深至淺便宜優先）、現價（高至低 / 低至高）、股票代號順序。

3. **個人研究筆記與買進理由紀錄（規格書 7.1）**：
   - 實作筆記編輯儲存端點 `POST /api/watchlist/member/note`。
   - 點擊「📝 筆記」彈出專屬編輯小卡片，輸入買進理由或目標觀察價後即時存檔，並在列表下方以標籤亮顯提示。

4. **出場條件 3：有更好的選擇動態比對（規格書 7.2）**：
   - 模組位置：[`src/services/exit_checker.py`](file:///d:/user/Documents/價值投資選股App/src/services/exit_checker.py) 中的 `find_better_alternatives(db, ticker)`。
   - 當觀察或持股標的回到合理以上（合理、昂貴或瘋狂區）時，自動在列表點亮「🔄 更好選擇」按鈕。
   - 點擊彈出模態卡片，自動在全股池中搜尋同產業優先、五燈全亮且跌入「特價/便宜區」之替代候選標的，並排顯示現價、便宜價、折價空間與好公司燈號，回歸冷靜的機會成本衡量。

5. **測試與品質保證（100% 全數 PASS）**：
   - 新增 [`tests/test_watchlist_advanced.py`](file:///d:/user/Documents/價值投資選股App/tests/test_watchlist_advanced.py)（5 項新增單元與整合測試）。
   - 專案總測試增至 **92 項全數通過**（100% 綠燈，無任何失敗）。

## 🚦 目前狀態
- **可運行**：
  - 本機啟動：直接執行 `scripts/start.bat` 或 `.\.venv\Scripts\python.exe run.py`，瀏覽器存取 `http://127.0.0.1:8000`。
  - Docker 啟動：執行 `docker compose up -d` 即可在容器中常駐運行並自動健檢。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 92 passed（100% 通過）。
- **合規性**：維持客觀量化研究與機會成本比對，無真人姓名或他人商標，無任何買賣指令式文字。

## ➡️ 下一步（後續擴充規劃）
1. **上線發行與實盤監控**：配置正式生產網址與 SSL 憑證。
2. **LINE 官方帳號上線**：在 LINE Developers 後台設定 Webhook URL 指向 `/api/line/webhook` 並填入正式 Token。

## ⚠️ 注意事項
- 磁碟管理：本機虛擬環境與資料庫鎖定在 D 槽本機 `.venv`，禁止於 C 槽進行全域 pip 安裝。
- Docker 持久化：使用 Docker 部署時，確保主機端 `./data` 目錄具備讀寫權限，防止資料庫寫入被拒。
- 時區一致性：系統排程與時間戳記嚴格綁定 `Asia/Taipei`（UTC+8）。

## 🕐 最後更新
- 時間：2026-10-01 16:35
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git push：✅ 待本次提交後推至 `cyc8115832-ctrl/value-investing-screener`
