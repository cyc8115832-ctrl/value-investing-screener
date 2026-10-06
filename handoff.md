# 交接檔（Handoff）— 價值投資選股App

> 開工必讀、收工必寫。任何 Agent、任何電腦接手請先讀此檔。

## 🟢 目前狀態：個股比較器財務乘數與河流圖價位補齊完成！136 測試綠燈 PASS

- **最後更新者**：Antigravity @ DESKTOP-QISHBK7
- **最後更新時間**：2026-10-06 16:30
- **Git push 狀態**：✅ 已推送至 origin/master (commit `8ef8fee`)
- **雲端 CI/CD 狀態**：✅ GitHub Actions 136 測試與 Pages 自動部署中
- **GitHub Pages 網址**：📱 `https://cyc8115832-ctrl.github.io/value-investing-screener/` (狀態: Built 200 OK)

---

## 📦 本次里程碑與成果盤點（個股比較器資料補齊）

### 🔧 工作流：個股比較器（Compare Modal）財務指標與河流圖價位映射修復

| 項目 | 檔案 | 說明 |
|------|------|------|
| 後端個股詳情端點補齊比率 | `src/web/api/routes.py` | 在 `/api/stocks/{ticker}` 補上頂層 `pe`, `pb`, `ps`, `revenue_yoy`, `gross_margin`, `roe`，確保比較器可以直接從個股詳細資料提取各項估值乘數與獲利能力指標 |
| 靜態離線適配層資料提取映射 | `scripts/export_gh_pages.py` | 修正 `/api/stocks/compare` 靜態攔截邏輯，不再從無比率欄位的 screener 抓取，改由 `stData` 完整提取真實比率；同時將河流圖價位帶鍵名對齊至 `stData.river.prices`，徹底消除 `--` 與預設 80/100/140 價位防呆值 |
| 靜態發布包重編 | `docs/index.html` | 重新匯出 94 檔成分股的靜態離線資料庫，比較器在 GitHub Pages 上即可秒開兩檔個股完整真實財務數據 |
| 自動化測試綠燈 | `tests/` | 136 項全自動化測試**100% 通過（136 passed in 49.27s）** |

---

## 🔮 下一步建議步驟

1. **實盤體驗覆盤**：在手機開啟已更新的 GitHub Pages 站點，點擊 5871 中租-KY 或其他個股，確認黑天鵝防守底線與文字敘述中不再出現長串小數（已整潔顯示為 `NT$ 55.72`）。
2. **生產運維排程**：可在本機運行盤後每日選股推播腳本（`scripts/setup_scheduler.ps1`）。

---

## ⚠️ 注意事項

- 本機開發環境鎖定在 D 槽本地虛擬環境（`.\.venv\`），禁止全域安裝至 C 槽。
- 前端色彩遵循暗黑高對比規範（底色 `#0B0F19`，字體白/青/綠/琥珀/珊瑚紅）。

---

## 🗂️ 核心路徑與環境

| 項目 | 路徑 |
|------|------|
| 專案目錄 | `d:\user\Documents\價值投資選股App` |
| 技術規格書 | `價值投資選股App 技術規格書 V1_7.md` |
| 虛擬環境 Python | `d:\user\Documents\價值投資選股App\.venv\Scripts\python.exe` |
| Pytest | `d:\user\Documents\價值投資選股App\.venv\Scripts\pytest.exe` |
| 遠端 GitHub Repo | `https://github.com/cyc8115832-ctrl/value-investing-screener` (私有) |
