# 交接檔（handoff.md）

> 任何 Agent、任何電腦接手前**必讀**；收工時**必更新**。本檔只放交接必需的精簡資訊，詳細脈絡放 Obsidian（若有 L3）。

## ⏯️ 目前做到哪
依據規格書與 Roadmap 規劃，已全面完成「方向二：自動化資料排程與真實管線」以及「方向三：V2.0 定期定額試算機與漲跌貢獻拆解」之研發、整合與驗證：

1. **自動化資料排程與真實管線（規格書 10, 11, 15）**：
   - `src/data/twse_adapter.py`：實作證交所 TWSE OpenAPI（`STOCK_DAY_ALL` 與 `BWIBBU_ALL`）收盤價、成交量、PE、PB 爬取與離線 Fallback 防呆機制。
   - `src/services/scheduler.py`：以背景守護執行緒實作 `MarketDataScheduler`，支援交易日 15:30 盤後重算管線（價格更新 → ETF 持股清洗比對 → 全股池重算 → 出場提醒檢查）與 18:30 LINE 自動推播。
   - `src/services/line_push.py`：實作 6 位一次性 LINE 綁定碼生成（10 分鐘時效）、`X-Line-Signature` HMAC-SHA256 簽名校驗、Webhook 好友追蹤/封鎖/驗證碼接收處理、3 次指數退避重試與 `push_log` 記錄。
   - `src/web/app.py`：FastAPI lifespan 正確掛載排程器啟動與停止。
   - `POST /api/pipeline/run`：提供手動立即執行盤後重算流水線端點。

2. **V2.0 定期定額回測試算機（規格書 5.5）**：
   - `src/engines/dca_backtest.py`：純函式模擬定期定額扣款，同時並排比較「不再投入（現金股利領回）」與「股息再投入（複利滾動）」，計算總投入、最新市值、累積股息、總損益、總報酬率、年化報酬率與最大帳面回落（MDD）。
   - 提供公定手續費 0.1425% 與折扣設定、零股最低手續費、休市順延與小樣本平滑補齊機制。
   - `GET /api/stocks/{ticker}/dca-backtest` 端點與個股頁雙方案並排對比卡片。

3. **漲跌貢獻拆解與估值極端旗標（規格書 6.9 & D-26）**：
   - `src/engines/decomposition.py`：嚴格實現公式 `ln(P1/P0) = ln(EPS1/EPS0) + ln(PE1/PE0)`，精準拆解獲利成長貢獻 % 與估值倍數擴張/收縮 %；EPS ≤ 0 時依規格不予拆解。
   - 估值極端旗標判定（PE > 100 或 > 3x 同業中位數，或 EPS <= 0 且處於 52 週前 20% 高檔），排除循環股與金融股，僅提示「⚠️ 獲利尚未支撐股價」而不改變價位區。
   - `GET /api/stocks/{ticker}/decomposition` 端點與個股頁視覺化貢獻進度條。

4. **宏觀水位美債 10 年期殖利率（規格書 14.6）**：
   - `src/data/macro_adapter.py`：支援遠端抓取與本地快取，自動判定 ≥5.0% 警戒線與 ≥4.5% 接近提示，無縫整合至雷達首頁與個股詳情。

5. **測試與品質保證**：
   - 新增 `tests/test_v2_and_pipeline.py`，全套 41 項測試全數 PASS（100% 綠燈）。

## 🚦 目前狀態
- **可運行**：執行 `.\.venv\Scripts\python.exe run.py` 即可在 `http://127.0.0.1:8000` 完整體驗全套功能。
- **測試狀態**：`.\.venv\Scripts\pytest.exe` 41 passed（100% 通過）。
- **合規性**：全 App、手冊與推播無真人姓名或他人商標，無任何買賣指令式文字。

## ➡️ 下一步（後續擴充規劃）
1. **V2.0 宏觀水位進階指標**：評估加入加權指數本益比水位與殖利率曲線倒掛指標。
2. **V3.0 AI 輔助模組**：依技術規格書規劃，導入財報重點萃取與新聞摘要分析。
3. **佈署準備**：依雲端環境撰寫 Dockerfile 與本機生產環境啟動腳本。

## ⚠️ 注意事項
- 磁碟管理：專案虛擬環境與資料庫均置於 D 槽，請勿於 C 槽進行全域 pip 安裝。
- 排程器啟動：排程器由 FastAPI lifespan 在應用程式啟動時自動常駐，單元測試中使用獨立 Mock 實例避免常駐干擾。
- 路由匹配順序：具體路由必須在動態萬用路由之前註冊。

## 🕐 最後更新
- 時間：2026-10-01 10:05
- 更新者：Antigravity @ DESKTOP-QISHBK7
- Git push：✅ 待本次提交後推至 `cyc8115832-ctrl/value-investing-screener`
