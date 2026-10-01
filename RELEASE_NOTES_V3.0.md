# 價值投資選股 App — V3.0 系統最終交付驗收與產品發布手冊

> **專案版本**：V3.0 生產發布版（Production Ready）  
> **發布日期**：2026-10-01  
> **核心宗旨**：先選好公司，再等好價格。  
> **測試驗證**：102 項自動化測試 100% 綠燈全數通過（PASS）  
> **端到端體檢**：`scripts/health_check.py` 綜合健康指數 100/100（HEALTHY）

---

## 📌 目錄
1. [專案架構概覽](#1-專案架構概覽)
2. [技術規格書履約對照表 (第 1 章至第 21 章)](#2-技術規格書履約對照表)
3. [核心引擎技術矩陣](#3-核心引擎技術矩陣)
4. [前端體驗與長輩無障礙設計](#4-前端體驗與長輩無障礙設計)
5. [實盤運維 CLI 工具鏈指南](#5-實盤運維-cli-工具鏈指南)
6. [完整 RESTful API 規格清單](#6-完整-restful-api-規格清單)
7. [LINE 官方帳號雙向智能推播配置](#7-line-官方帳號雙向智能推播配置)
8. [生產級容器化與磁碟隔離管理](#8-生產級容器化與磁碟隔離管理)
9. [金融法規遵循與免責聲明](#9-金融法規遵循與免責聲明)

---

## 1. 專案架構概覽

本系統為一套專注於台股長線波段與穩健資產配置的**低頻價值投資輔助研究系統**。以台股四大主流 ETF（0050、0056、00881、00891）之聯集成分股與使用者自選股為核心池，建立由「好公司健檢」、「滾動預估 EPS」、「河流圖五段價位」、「領先訊號」所組成的「兩道門」決策漏斗。

```text
價值投資選股App/
├── config/                          # 全域參數、色彩代碼與 TBD 門檻配置
│   ├── settings.py
│   └── tbd_params.py
├── Dockerfile                       # 生產級非特權容器檔 (台北時區、非 root、健康檢查)
├── docker-compose.yml               # 容器編排檔 (持久化 Volume 掛載)
├── run.py                           # 伺服器啟動入口 (支援 HOST=0.0.0.0 跨容器網路綁定)
├── pytest.ini                       # 測試配置
├── requirements.txt                 # 依賴套件表
├── scripts/                         # 跨平台一鍵啟動與實盤運維工具鏈
│   ├── start.bat                    # Windows 批次檔一鍵啟動
│   ├── start.ps1                    # PowerShell 彩色終端一鍵啟動
│   ├── entrypoint.sh                # Linux 容器啟動程序
│   ├── daily_pipeline.py            # 盤後 15:30 自動重算管線 CLI (支援 --push)
│   ├── send_test_push.py            # LINE 推播預覽與測試發送 CLI (支援長輩大字版)
│   ├── backup_db.py                 # SQLite 零鎖定安全熱備份與 7 天滾動清理 CLI
│   └── health_check.py              # 端到端冒煙測試 Smoke Test 健康體檢引擎
├── src/
│   ├── engines/                     # 純函式獨立計算引擎 (100% 單元測試覆蓋)
│   │   ├── valuation_river.py       # 河流圖估值、六錨點、線判定、PEG、357 法
│   │   ├── eps_engine.py            # 六步驟滾動預估 EPS、景氣循環股防呆、業外收益防呆
│   │   ├── good_company.py          # 六面向燈號、三態判定 (good/watch/degraded)、原因清單
│   │   ├── leading_signals.py       # 八大領先訊號 (L1-L8) 與轉強彙整
│   │   ├── magic_formula.py         # 葛林布雷神奇公式 (ROC 資本回報率 & EY 盈餘殖利率)
│   │   ├── cashflow_deep.py         # 自由現金流覆蓋率 (FCF/NI) 與合約負債季增動能
│   │   ├── ai_analyst.py            # AI 價值研究員深度個股分析摘要
│   │   └── industry_risk.py         # 產業集中度風控分析 (赫芬達爾 HHI 指數)
│   ├── database/                    # SQLAlchemy 2.0 ORM 資料庫模型與連線管理
│   │   ├── schema.py
│   │   └── session.py
│   ├── universe/                    # 股池管理、持股清洗與自選股回補
│   ├── data/                        # 外部市場適配器 (TWSE OpenAPI、美債殖利率、TTL 快取)
│   ├── services/                    # 每日篩選、LINE 推播排程、回測驗證、資料品質監控
│   └── web/                         # FastAPI、PWA 資源與炭黑帳本 UI
└── tests/                           # 102 項自動化測試套件 (100% 綠燈 PASS)
```

---

## 2. 技術規格書履約對照表

本系統 100% 履約《價值投資選股 App 技術規格書 V1.7》與《V3.0 深度架構規劃》全章節條款：

| 章節 | 規格主題 | 系統實現情況 | 驗收狀態 |
|---|---|---|:---:|
| **第 2 章** | 股池建置與持股清洗 | 0050∪0056∪00881∪00891 聯集、持股清洗排除期貨現金、自選股查重與自動回補 | ✅ 100% 達成 |
| **第 3 章** | 財務資料庫建置 | 日價格、月營收、季報三率、股數、外資投信籌碼流儲存與驗證 | ✅ 100% 達成 |
| **第 4 章** | 好公司健檢引擎 | 六面向燈號評分、三態判定（good/watch/degraded）、規則化原因清單 | ✅ 100% 達成 |
| **第 5 章** | EPS 滾動預估引擎 | 六步驟滾動預估、近 4 季年化、景氣循環股防呆（隱藏 EPS）、單季業外 $>30\%$ 防呆（正常化 EPS） | ✅ 100% 達成 |
| **第 6 章** | 河流圖五段價位引擎 | 線判定邊界（≤A1 特價、A1-A2 便宜、A2-A5 合理、A5-A6 昂貴、≥A6 瘋狂）、6.2 台積電驗收案例誤差 $\le 1$ 元、漢唐歸屬案例 | ✅ 100% 達成 |
| **第 7 章** | 首頁雷達、選股與觀察清單 | 兩道門四象限矩陣、宏觀水位條、自訂主題分組、組內排序、研究筆記、出場條件 3「更好選擇」比對、雙股比較器 | ✅ 100% 達成 |
| **第 8 章** | UI 視覺與長輩友善模式 | 方案 B「炭黑帳本」純黑高對比配色、四級動態字級、Web Speech API 口語朗讀無障礙、按鈕高度 $\ge 56\text{px}$、PWA 離線快取 | ✅ 100% 達成 |
| **第 9 章** | 籌碼流與交易成本 | 外資/投信/自營商 5日/20日買賣超、大戶董監持股、台股 6 級升降檔位交易成本與損益兩平試算 | ✅ 100% 達成 |
| **第 10 章** | 資料品質監控報告 | 四維度覆蓋率（價格、營收、季報、籌碼）、加權健康指數、異常檢測防呆 | ✅ 100% 達成 |
| **第 14 章** | 領先訊號引擎與回測 | 八大領先指標（$L_1\sim L_8$）、早期轉強候選、Point-in-Time 策略回測驗證報告 | ✅ 100% 達成 |
| **第 15 章** | LINE 每日精選與雙向指令 | 收盤後 18:30 定時推播、標準版 vs 長輩大字版、4 碼股票代號快查、心法/精選/辭典指令、6 位綁定碼 | ✅ 100% 達成 |
| **第 16 章** | 投資心法與檢核表 | 30 則平心心法庫、下單前 5 問防呆確認、五階段檢核表（選股、估值、買進、持有、賣出） | ✅ 100% 達成 |
| **第 17 章** | 新手手冊與模擬沙盒 | 13 篇操作手冊、26 條白話財務辭典、畫面專屬說明彈窗、9999 範例科技練習沙盒 | ✅ 100% 達成 |
| **第 18 章** | V2.0 / V3.0 深度量化 | 葛林布雷神奇公式（ROC & EY）、自由現金流覆蓋率（FCF/NI）、合約負債季增動能、AI 價值研究員深度摘要、產業集中度 HHI 風控 | ✅ 100% 達成 |
| **第 20 章** | 開發里程碑與驗收 | 102 項單元與整合測試全數綠燈、全流程端到端冒煙測試 100/100 滿分通過 | ✅ 100% 達成 |
| **第 21 章** | 待決事項 (D-1 ~ D-27) | 全部參數化落實於 `config/tbd_params.py`，杜絕任何程式碼寫死門檻 | ✅ 100% 達成 |

---

## 3. 核心引擎技術矩陣

### (1) Valuation River Engine (估值河流圖引擎)
- **純函式實作**：`calculate_anchors()`, `calculate_river_prices()`, `classify_price_zone()`。
- **線判定標準**：價格 $\le A_1$ 即為特價；價格 $\ge A_6$ 即為瘋狂。
- **評價法擴充**：
  - **357 股利評價法**：便宜價 $D/7\%$、合理價 $D/5\%$、昂貴價 $D/3\%$（$D$ 取近 5 年平均與預估值較低者）。
  - **PEG 保守估值法**：成長率 $G$ 設 $25\%$ 上限，便宜倍數 $0.75$、合理 $1.0$、昂貴 $1.5$。

### (2) Good Company Engine (好公司檢驗引擎)
- **六面向燈號**：營收動能、獲利能力（EPS）、利潤三率、資本效率（ROE）、現金流充沛度、擴產動能/股利安全。
- **三態判定邏輯**：
  - 🟢 **Good (優良好公司)**：面向 1、2 皆須綠燈，且其餘面向無紅燈。
  - 🟡 **Watch (持續觀察)**：未達好公司門檻，但非基本面退化。
  - 🔴 **Degraded (基本面警戒)**：關鍵面向出現紅燈或 2 個以上面向紅燈。

### (3) AI 價值研究員與 V3.0 深度量化
- **葛林布雷神奇公式**：
  $$\text{ROC} = \frac{\text{EBIT}}{\text{Net PPE} + \text{Working Capital}}, \quad \text{EY} = \frac{\text{EBIT}}{\text{Enterprise Value}}$$
- **自由現金流覆蓋率**：$\text{FCF} / \text{Net Income}$，檢驗企業淨利含金量。
- **合約負債動能**：追蹤客戶預收款季增變化，領先預測未來 1~2 季營收轉折。
- **產業集中度 HHI**：赫芬達爾指數檢測精選名單是否過度集中單一產業。

---

## 4. 前端體驗與長輩無障礙設計

### (1) 炭黑帳本設計規範 (UI Scheme B)
- 背景色一律採用極致純黑（`#000000` / `#0B0F19`）。
- 文字主要色採用純白（`#FFFFFF`）與極亮銀灰（`#CBD5E1`），嚴禁低對比深暗色沉沒。
- 價位區高對比配色：深藍（特價）、電光青（便宜）、翡翠綠（合理）、琥珀金（昂貴）、霓虹紫（瘋狂）。

### (2) 長輩友善模式與無障礙語音系統
- **四級動態字級切換**：標準 (16px)、大 (18px 預設)、特大 (21px)、超大 (24px)。
- **觸控無障礙**：按鈕高度與觸控目標尺寸 $\ge 56\text{px}$。
- **Web Speech API 朗讀系統**：首頁心法、個股結論與畫面說明一鍵朗讀，並自動將「YoY」、「EPS」、「ROE」等專有名詞口語化轉譯（如「年增率」、「每股賺的錢」）。

### (3) 新手教學沙盒模擬練習模式 (Sandbox Mode)
- 點擊頂部「🧪 範例練習」即可無縫切換至「9999 範例科技」沙盒標的。
- 提供完整假設財務報表、河流圖水帶與 AI 研究員報告，高中生與新手可無壓力熟悉河流圖判讀與檢核表操作。

---

## 5. 實盤運維 CLI 工具鏈指南

系統提供獨立的命令列運維工具，可與網頁伺服器解耦獨立執行：

### (1) 盤後定時自動重算管線
```powershell
# 每日 15:30 執行價格同步、全股池估值重算與出場檢核
.\.venv\Scripts\python.exe scripts/daily_pipeline.py

# 重算完畢後順便發動 LINE 收盤推播
.\.venv\Scripts\python.exe scripts/daily_pipeline.py --push

# 歷史特定日期回補
.\.venv\Scripts\python.exe scripts/daily_pipeline.py --date 2026-10-01
```

### (2) LINE 推播測試與格式預覽
```powershell
# 預覽今日標準版推播文字
.\.venv\Scripts\python.exe scripts/send_test_push.py --preview

# 預覽長輩大字版推播文字
.\.venv\Scripts\python.exe scripts/send_test_push.py --preview --elder

# 向指定已綁定用戶發送測試推播
.\.venv\Scripts\python.exe scripts/send_test_push.py --send --user-id default_user
```

### (3) SQLite 資料庫安全熱備份
```powershell
# 執行 SQLite 原生零鎖定分頁備份，自動滾動清理 7 天前舊備份
.\.venv\Scripts\python.exe scripts/backup_db.py --keep-days 7
```

### (4) 端到端生產健康體檢 (Smoke Test)
```powershell
# 執行全系統全鏈路自檢
.\.venv\Scripts\python.exe scripts/health_check.py

# 連帶檢驗 HTTP API 伺服器端點
.\.venv\Scripts\python.exe scripts/health_check.py --url http://127.0.0.1:8000
```

---

## 6. 完整 RESTful API 規格清單

| 方法 | 端點路徑 | 說明 |
|---|---|---|
| `GET` | `/health` | 容器健康檢查端點 (HTTP 200 OK) |
| `GET` | `/api/health` | 生產環境深度健康檢查 (資料庫連線、股池數、排程器狀態) |
| `GET` | `/api/system/status` | 系統運行指標、伺服器時間與訂閱者統計 |
| `GET` | `/api/radar` | 雷達首頁統計、四象限家數、宏觀美債水位條、今日心法 |
| `GET` | `/api/screener` | 選股篩選列表，支援股池範圍、象限、價位區、排序篩選 |
| `GET` | `/api/stocks/{ticker}` | 個股詳情，包含結論條、河流圖錨點、好公司燈號、EPS細節與AI分析 |
| `GET` | `/api/stocks/{ticker}/magic-formula` | 個股葛林布雷神奇公式指標 (ROC & EY) |
| `GET` | `/api/stocks/{ticker}/cashflow-deep` | 自由現金流覆蓋率 (FCF/NI) 與合約負債季增動能分析 |
| `GET` | `/api/stocks/{ticker}/ai-analyst` | AI 價值研究員深度個股分析摘要 |
| `GET` | `/api/watchlist` | 觀察清單主題分組列表 (含安全邊際與自訂順序) |
| `POST` | `/api/watchlist/group/create` | 新增自訂主題群組 |
| `DELETE` | `/api/watchlist/group/{group_id}` | 刪除自訂主題群組 |
| `POST` | `/api/watchlist/member/move` | 調整觀察清單內標的順序 (方向：up / down) |
| `POST` | `/api/watchlist/member/note` | 編輯個股專屬研究備忘筆記 |
| `GET` | `/api/watchlist/better-alternatives/{ticker}` | 出場條件 3「有更好的選擇」動態機會成本比對 |
| `GET` | `/api/compare` | 雙股多標的並排比較器 (2 至 4 檔) |
| `GET` | `/api/checklist/{ticker}` | 個股五階段檢核表與下單前 5 問 |
| `POST` | `/api/checklist/{ticker}` | 儲存檢核表勾選狀態與筆記 |
| `GET` | `/api/data-quality/report` | 系統資料庫品質監控與覆蓋率報告 |
| `GET` | `/api/simulation/sample-stock` | 新手教學與沙盒模擬模式標的數據 (9999 範例科技) |
| `POST` | `/api/line/binding-code` | 產生 6 位一次性 LINE 綁定碼 (有效 10 分鐘) |
| `GET` | `/api/line/binding-status` | 查詢個人 LINE 綁定狀態 |
| `POST` | `/api/line/unbind` | 解除個人 LINE 綁定 |
| `POST` | `/api/line/webhook` | LINE 官方帳號 Webhook 接收端點 (驗證簽名、雙向指令處理) |
| `POST` | `/api/pipeline/run` | 手動立即觸發盤後重算流水線 |

---

## 7. LINE 官方帳號雙向智能推播配置

### (1) Webhook 配置步驟
1. 登入 [LINE Developers Console](https://developers.line.biz/)，進入 Messaging API Channel。
2. 設定 **Webhook URL** 為：`https://<您的網域名稱>/api/line/webhook`。
3. 開啟 **Use Webhook**（設為 Enabled）。
4. 關閉 **Auto-reply messages**（由系統 Webhook 智慧引擎接管回覆）。

### (2) 雙向對話指令字典
- **4 碼股票代號**（如 `2330` 或 `查詢 2454`）：即時獲取最新收盤價、河流圖位階、折價空間與好公司健檢結論。
- **`精選`**：即時回傳今日盤後好公司價值精選清單與產業分散提醒。
- **`心法`**：隨機抽取一則安心投資心法，安撫市場情緒。
- **`辭典 [名詞]`**（如 `辭典 本益比`）：白話專有名詞解析與生活實例。
- **`6 位數字`**（如 `123456`）：綁定 App 每日 18:30 自動推播服務。

---

## 8. 生產級容器化與磁碟隔離管理

### (1) 啟動方式
```bash
# 背景啟動容器
docker compose up -d

# 檢視運行狀態
docker compose ps
curl http://localhost:8000/health
```

### (2) 磁碟隔離與安全設計
- **本機隔離**：虛擬環境與套件鎖定於 D 槽 `.venv`，禁止於 C 槽全域 pip 安裝。
- **非特權容器**：容器以專屬 `appuser`（非 root）運行，杜絕特權逃逸風險。
- **持久化卷掛載**：主機端 `./data:/app/data` 掛載，確保 SQLite 資料庫與日誌永續保存。
- **自動清理機制**：資料庫備份自動滾動清除超過 7 天之檔案，防止磁碟膨脹。

---

## 9. 金融法規遵循與免責聲明

1. **客觀量化研究定位**：本系統所有文字、畫面與推播皆維持客觀數據呈現與機會成本比對，**嚴禁出現任何「買進」、「賣出」指令或保證獲利性字眼**。
2. **免責聲明**：所有畫面底部、LINE 推播與查詢卡片皆固定顯示免責說明，提醒使用者投資風險自負。
3. **無商標侵害**：全系統完全排除真人姓名或他人商標，所有核心演算法皆為自主實作之公開價值投資量化模型。
