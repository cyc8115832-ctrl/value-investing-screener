# 交接檔（Handoff）— 價值投資選股App

> 開工必讀、收工必寫。任何 Agent、任何電腦接手請先讀此檔。

## 🟢 目前狀態：階段二十五（工作流一：LINE Flex Message 大字版美化）圓滿完成，系統穩定

- **最後更新者**：Antigravity @ DESKTOP-QISHBK7
- **最後更新時間**：2026-10-02 14:10
- **Git push 狀態**：✅ 準備 commit & push

---

## 📦 本次里程碑與成果盤點（階段二十五）

### 🔧 工作流一：LINE Flex Message 大字版美化與雙向個股卡片

| 項目 | 檔案 | 說明 |
|------|------|------|
| Flex 建構器 | `src/services/line_push.py` | `build_daily_line_flex_message` (每日盤後精選泡泡卡片、支援長輩大字版 giga 尺寸、炭黑高對比配色、安全邊際醒目化、產業集中警示區塊)；`build_single_stock_flex_message` (個股即時查詢快訊卡片) |
| 推播向下相容 | `src/services/line_push.py` | 擴充 `send_reply_message` 與 `send_line_push_with_retry`，同時相容 `message_text` 與 `message_payload`（dict Flex 物件），具備 3 次指數退避重試 |
| API 端點升級 | `src/web/api/routes.py` | 升級 `POST /api/push/preview` 支援 `use_flex` 參數並回傳 `flex_payload`；新增 `GET /api/stocks/{ticker}/line-flex` 個股卡片端點 |
| 前端擬真預覽 | `src/web/templates/index.html` | 設定頁提供「LINE 擬真手機泡泡預覽卡片」與「純文字版」即時切換開關，免推播即可直觀驗證視覺效果 |
| 單元測試套件 | `tests/test_line_and_simulation.py` | 新增 3 項 Flex Message 測試用例，全數通過 |
| 全套測試驗證 | `tests/` | **123 項測試全數通過（123 passed）** |
| 技術小教室筆記 | `D:\user\Documents\00_Inbox\[技術小教室] 價值投資選股App_LINE_Flex_Message大字版技術解析.md` | 已完稿存入 `00_Inbox` |

---

## 🗺️ 剩餘工作流盤點（依序進行中）

1. [x] **工作流一：LINE 官方帳號 Flex Message 大字版美化（階段二十五已完成 ✅）**
2. [ ] **工作流二：EPS 長期複合成長率 (CAGR) 與歷史預估偏差校準儀表板（規格書 §5.4、§6.8）**
   - 滾動追蹤過去預估 EPS 與實際公告季報之誤差率，提供預估信心指數微調與長期成長軌跡圖。
3. [ ] **工作流三：宏觀市場水位與美債殖利率聯動儀表板（規格書 §10、§14）**
   - 強化 10 年期美債殖利率（4.5% / 5.0% 警戒線）對全股池估值位階動態折現之視覺化面板與敏感度試算。
4. [ ] **工作流四：長輩實測回饋微調與體驗優化（規格書 §8.10.8、待決事項 D-19）**
   - 依據實際操作反饋進行字級層次、按鈕間距、語音朗讀語速的細節調優。

---

## 🔮 下一步建議步驟

- 依序推進 **「工作流二：EPS 長期複合成長率 (CAGR) 與歷史預估偏差校準儀表板」**。

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
