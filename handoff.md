# 交接檔（Handoff）— 價值投資選股App

> 開工必讀、收工必寫。任何 Agent、任何電腦接手請先讀此檔。

## 🟢 目前狀態：浮點數精度全面收斂！所有數值小數點上限嚴格限定 2 位、136 測試綠燈 PASS

- **最後更新者**：Antigravity @ DESKTOP-QISHBK7
- **最後更新時間**：2026-10-06 12:38
- **Git push 狀態**：✅ 準備推送至 origin/master
- **雲端 CI/CD 狀態**：✅ GitHub Actions 136 測試與 Pages 自動部署
- **GitHub Pages 網址**：📱 `https://cyc8115832-ctrl.github.io/value-investing-screener/` (狀態: Built 200 OK)

---

## 📦 本次里程碑與成果盤點（小數點精度優化）

### 🔧 工作流：浮點數精度健全化與小數點 2 位格式化（fmt2）

| 項目 | 檔案 | 說明 |
|------|------|------|
| 後端黑天鵝防守底線收斂 | `src/engines/valuation_stress_test.py` | 修復 `tangible_floor_price * 0.7` 比較後浮點數展開問題，以 `round(..., 2)` 徹底消除如 `55.71999999999999` 的無效浮點溢出 |
| 前端全域小數點 2 位格式化函式 | `src/web/templates/index.html`、`docs/index.html` | 新增 `fmt2(val)` 輔助工具（若有小數點最多取 2 位），應用於壓力測試樂觀/基準/悲觀情境價格與 EPS、極限底線、安全緩衝、風險報酬比、長期推估表與宏觀利率敏感度矩陣 |
| 自動化測試綠燈 | `tests/` | 136 項全自動化測試（包含估值壓力測試 `test_valuation_stress_test.py`）**100% 通過（136 passed）** |
| GitHub Pages 靜態發布包全量更新 | `docs/index.html` | 重新匯出 94 檔個股分析快照，Node.js 語法校驗 0 錯誤，手機端秒開 |

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
