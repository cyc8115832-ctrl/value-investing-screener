# 交接檔（Handoff）— 價值投資選股App

> 開工必讀、收工必寫。任何 Agent、任何電腦接手請先讀此檔。

## 🟢 目前狀態：階段二十六（工作流二：EPS 長期複合成長率 (CAGR) 與歷史預估偏差校準儀表板）圓滿完成，系統穩定

- **最後更新者**：Antigravity @ DESKTOP-QISHBK7
- **最後更新時間**：2026-10-03 18:35
- **Git push 狀態**：✅ 準備 commit & push

---

## 📦 本次里程碑與成果盤點（階段二十六）

### 🔧 工作流二：EPS 長期複合成長率 (CAGR) 與歷史預估偏差校準儀表板 (規格書 §5.4、§6.8c)

| 項目 | 檔案 | 說明 |
|------|------|------|
| 計算引擎 | `src/engines/eps_cagr_calibration.py` | 純函式實作 `calculate_eps_cagr`（3Y/5Y CAGR、負值/虧損防呆、穩健度判定、25%成長上限鉗制）；`evaluate_forecast_calibration`（歷年預估 vs 實際公告比對、MAPE 計算、可信度評分與評級、樂觀/保守偏差傾向分析）；`project_multi_year_eps_scenarios`（未來 3 年與 5 年保守/基準/樂觀長期獲利與目標價推估） |
| REST API 端點 | `src/web/api/routes.py` | 新增 `GET /api/stocks/{ticker}/eps-cagr-calibration` 端點，聚合歷史季報淨利與流通在外股數，結合 EPS 預估紀錄與本益比估值錨點，輸出完整校準分析 |
| 前端儀表板 UI | `src/web/templates/index.html` | 在個股頁「預估 EPS 與拆解」分頁新增專屬儀表板卡片：3Y/5Y CAGR、有效成長率、模型偏差 MAPE、可信度評分、歷年預估偏差明細表格、未來 3~5 年情境推估對比表格 |
| 前端資料動態載入 | `src/web/templates/index.html` | 新增 `loadEpsCagrCalibration(ticker)` 非同步函式，於進入個股河流圖頁時自動掛載觸發，數據動態即時渲染 |
| 單元與整合測試 | `tests/test_eps_cagr_calibration.py` | 涵蓋 CAGR 計算、25%上限鉗制、虧損防呆、MAPE 偏差比對、未來情境推估、FastAPI 端點整合測試，新增 7 項測試全數通過 |
| 全套測試驗證 | `tests/` | **130 項測試全數通過（130 passed）**，零回歸 |

---

## 🗺️ 剩餘工作流盤點（依序進行中）

1. [x] **工作流一：LINE 官方帳號 Flex Message 大字版美化（階段二十五已完成 ✅）**
2. [x] **工作流二：EPS 長期複合成長率 (CAGR) 與歷史預估偏差校準儀表板（階段二十六已完成 ✅）**
3. [ ] **工作流三：宏觀市場水位與美債殖利率聯動儀表板（規格書 §10、§14）**
   - 強化 10 年期美債殖利率（4.5% / 5.0% 警戒線）對全股池估值位階動態折現之視覺化面板與敏感度試算。
4. [ ] **工作流四：長輩實測回饋微調與體驗優化（規格書 §8.10.8、待決事項 D-19）**
   - 依據實際操作反饋進行字級層次、按鈕間距、語音朗讀語速的細節調優。

---

## 🔮 下一步建議步驟

- 依序推進 **「工作流三：宏觀市場水位與美債殖利率聯動儀表板」**。

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
