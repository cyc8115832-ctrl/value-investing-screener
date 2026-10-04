# 交接檔（Handoff）— 價值投資選股App

> 開工必讀、收工必寫。任何 Agent、任何電腦接手請先讀此檔。

## 🟢 目前狀態：GitHub Pages 手機操作體驗全修復！全 22 檔個股與河流圖順暢秒開、136 測試綠燈 PASS

- **最後更新者**：Antigravity @ DESKTOP-QISHBK7
- **最後更新時間**：2026-10-04 23:16
- **Git push 狀態**：✅ 已推送至 origin/master
- **雲端 CI/CD 狀態**：✅ GitHub Actions 136 測試與 Pages 發布全數成功 PASS
- **GitHub Pages 網址**：📱 `https://cyc8115832-ctrl.github.io/value-investing-screener/` (狀態: Built 200 OK)

---

## 📦 本次里程碑與成果盤點（階段二十九）

### 🔧 工作流：GitHub Pages 100% 靜態站點上線與手機觸控交互健全化

| 項目 | 檔案 | 說明 |
|------|------|------|
| 移除導覽遮罩攔截 | `src/web/templates/index.html` | 移除 `window.onload` 自動彈出新手導覽彈窗，徹底消除覆蓋在手機螢幕上方的 `z-index: 1000` 遮罩層，改為設定頁手動點選觸發 |
| 健壯化分頁與個股跳轉 | `src/web/templates/index.html` | `switchTab` 淘汰脆弱的 `event.target` 改用屬性選擇器；`viewStock` 新增平滑向上滾動與子圖表 `try-catch` 容錯 |
| 篩選器欄位名稱對齊 | `scripts/export_gh_pages.py`、`docs/index.html` | 修正靜態適配層篩選比對邏輯，支援 `state_tag`（象限）與 `current_zone`（價位區），修復「估值警戒」下查無股票之異常 |
| 離線資料庫與正則降級 | `scripts/export_gh_pages.py`、`docs/index.html` | 嵌入包含全 22 檔個股深度分析（464 端點）的完整 `STATIC_DB`，個股動態 query 具備正則降級匹配 |
| 部署與雲端測試 | GitHub Actions / GitHub Pages | 136 項測試全數 PASS，GitHub Pages 即時構建並部署成功 |

---

## 🔮 下一步建議步驟

1. **實盤體驗覆盤**：在手機上使用已部署的 GitHub Pages 站點進行日常選股、河流圖五段價位確認與長輩模式試聽。
2. **生產運維排程**：若有需要，可在本機運行盤後每日選股推播腳本（`scripts/setup_scheduler.ps1`）。

---

## ⚠️ 注意事項

- 本機開發環境鎖定在 D 槽本地虛擬環境（`.\.venv\`），禁止全域安裝至 C 槽。
- 前端色彩遵循暗黑高對比規範（底色 `#0B0F19`，字體白/青/綠/琥珀/珊瑚紅）。
- `send_line_push_with_retry` 保持雙參數相容，不可刪除 `message_text` 參數以維護 CLI 穩定性。

---

## 🗂️ 核心路徑與環境

| 項目 | 路徑 |
|------|------|
| 專案目錄 | `d:\user\Documents\價值投資選股App` |
| 技術規格書 | `價值投資選股App 技術規格書 V1_7.md` |
| 虛擬環境 Python | `d:\user\Documents\價值投資選股App\.venv\Scripts\python.exe` |
| Pytest | `d:\user\Documents\價值投資選股App\.venv\Scripts\pytest.exe` |
| 遠端 GitHub Repo | `https://github.com/cyc8115832-ctrl/value-investing-screener` (私有) |
