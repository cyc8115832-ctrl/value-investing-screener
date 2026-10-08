# 價值投資選股 App（Value Investing Screener）— 證據查核修訂版

[![CI Pipeline](https://github.com/cyc8115832-ctrl/value-investing-screener/actions/workflows/ci.yml/badge.svg)](https://github.com/cyc8115832-ctrl/value-investing-screener/actions)
![Tests](https://img.shields.io/badge/local_tests-156%20passed-86EFAC)
![Data](https://img.shields.io/badge/investment_data-incomplete-F59E0B)
![License](https://img.shields.io/badge/license-MIT-FBBF24)

> **核心宗旨**：先選好公司，再等好價格。  
> 本系統依據《價值投資選股 App 技術規格書 V1.7》與《V3.0 深度架構規劃》全功能落地建構。以台股四檔主要 ETF（0050、0056、00881、00891）之聯集成分股與使用者自選股為核心股池，建構好公司健檢引擎（六面向燈號）、EPS 滾動預估引擎、河流圖五段價位估值引擎（P/E、P/B、P/S）、領先訊號引擎、AI 價值研究員深度個股分析、產業集中度風控（HHI 指數）、LINE 官方帳號雙向互動推播、新手教學沙盒練習模式、資金部位配置與動態再平衡試算器、股息現金流複利滾雪球與長期被動收入模擬器、多情境估值敏感度與黑天鵝壓力測試引擎、**LINE 官方帳號 Flex Message 大字版美化與雙向個股卡片**及炭黑帳本高對比 UI。


## 2026-10-08 正式資料邊界

本機已完成 CEO 稽核後的第一批可信度與手機介面修正。下方 V3.0 功能列表是既有架構記錄，並不表示市場資料全部真實或實盤功能通過驗收。正式模式預設 `DEMO_MODE=false`、`ENABLE_SCHEDULER=false`，不在啟動時寫入模擬種子。缺來源的分析、買進精選、LINE 發送及策略回測保留待核實；原「100% 勝率、+16.71%」不能作為真實策略績效。

- 已核實：94 檔最近官方行情均至 2026-10-07、94 檔 2026-08 營收、71 檔一般上市公司 2026-Q2 累計損益。日期以每筆來源為準。
- 歷史研究範圍：94 檔共 91,089 筆官方行情，93 檔涵蓋 49 個月份，6526 涵蓋 37 個月份；截止 2026-10-07。參考交易日差集保存在查核報告，尚未核對掛牌、停牌及公司事件，不能稱四年逐日完全無缺漏。此為真實歷史的事後重建，不是當時已留存預估。
- 手機底部五入口、六個個股子頁重複收盤價、緊湊股票總表、歷史表與時間變動河流圖；色彩區分成長、風險、價位與缺資料。
- 河流圖採可設定 240 日分位數研究模型，非孫慶龍未公開的原公式。完整財報、股數、現金流、股利、ETF 歷史名單、籌碼及美債仍有來源缺口。
- 靜態匯出分檔、標示真實產生時間；私人筆記、觀察及 LINE 身分不匯出。Pages 的觀察與筆記只寫入該裝置，跨裝置同步需登入後端。

設計與平台說明：[時間序列介面與資料儲存設計](reports/2026-10-07/時間序列介面與資料儲存設計.md)。現用 SQLite；多人與跨裝置需求明確後再規劃 PostgreSQL。

更新命令（先備份，保留官方原始回應）：

```powershell
.venv\Scripts\python.exe scripts/refresh_verified_data.py
.venv\Scripts\python.exe scripts/backfill_verified_history.py --tickers 2330,2317,2454 --months 48
.venv\Scripts\python.exe scripts/verify_history_evidence.py --check-snapshots
.venv\Scripts\python.exe scripts/export_gh_pages.py
.venv\Scripts\python.exe scripts/verify_static_snapshot.py
.venv\Scripts\python.exe -m pytest -q
```

測試使用獨立資料庫，156 項本機測試通過。來源查核核對 182,738 筆最新／修訂版雜湊、701 個月快照與 972 個日快照，失敗 0；詳見 [本輪報告](reports/2026-10-08/開工接續與歷史回補.md)。服務可正常運行與投資資料足夠是兩種不同驗收；本次未部署雲端或發送 LINE。

---

## 🚀 快速啟動指引

### 方式一：本地一鍵啟動 (Windows 優先)

專案依據磁碟隔離規範，依賴套件與資料庫均建置於 D 槽本地虛擬環境：

```powershell
# 1. 雙擊執行或在命令列執行一鍵腳本
.\scripts\start.bat
# 或使用 PowerShell
.\scripts\start.ps1

# 2. 開啟瀏覽器訪問
http://127.0.0.1:8000
```

### 方式二：Docker 容器化部署 (跨平台 / 生產環境)

專案已配備生產級非 root 容器配置、自動台北時區（Asia/Taipei）與健康檢查：

```bash
# 1. 背景啟動容器
docker compose up -d

# 2. 檢視運行狀態與健康指標
docker compose ps
curl http://localhost:8000/health

### 方式三：實盤運維 CLI 工具鏈 (排程與自動化)

系統提供獨立命令列運維腳本，適合搭配 Windows 工作排程器 (Task Scheduler) 或 Linux crontab：

```powershell
# 1. 執行盤後 15:30 自動重算管線 (價格同步、全股池估值、出場檢核)
.\.venv\Scripts\python.exe scripts/daily_pipeline.py

# 2. 盤後重算後立即發動 LINE 推播
.\.venv\Scripts\python.exe scripts/daily_pipeline.py --push

# 3. 測試與預覽 LINE 今日精選推播文案 (支援長輩版與真實發送)
.\.venv\Scripts\python.exe scripts/send_test_push.py --preview
.\.venv\Scripts\python.exe scripts/send_test_push.py --preview --elder

# 4. SQLite 資料庫零鎖定安全熱備份 (自動滾動保留 7 天，防磁碟膨脹)
.\.venv\Scripts\python.exe scripts/backup_db.py --keep-days 7

# 5. 端到端系統健康診斷與冒煙測試 (Smoke Test 全鏈路驗收)
.\.venv\Scripts\python.exe scripts/health_check.py

# 6. Windows 工作排程器一鍵自動註冊 (實盤全自動無人值守)
powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduler.ps1 -Action Install
# 檢視排程狀態: powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduler.ps1 -Action Status
```

---

## 🧪 自動化測試與品質保證

本系統具備嚴格的測試覆蓋，執行全專案單元與整合測試：

```powershell
.\.venv\Scripts\pytest.exe -v
```

> **測試結果**：**114 項測試 100% 綠燈全數通過**（PASS）。  
> 涵蓋：
> - 階段二十三 股息現金流複利滾雪球與被動收入試算（DRIP 股息再投入、成本殖利率 YoC 成長、實質通膨折現、里程碑預估）
> - 階段二十二 資金部位配置與動態再平衡（特價 2.0x 加權、安全邊際加成、單一持股 20% 風控上限封頂、整張/零股支援）
> - 運維 CLI 工具鏈（端到端健康診斷、SQLite 安全熱備份、滾動清理、推播預覽與盤後管線）
> - 規格書 6.2 台積電基準錨點誤差 ≤ 1 元驗證
> - 規格書 6.2b 價位線判定與漢唐邊界歸屬案例
> - 規格書 6.7 歷史觸及與反彈統計
> - 規格書 6.8b 357 股利評價法（7%、5%、3%）
> - 規格書 6.8c PEG 保守估值法（G 上限 25%）
> - 規格書 7.1 & 7.2 觀察清單主題分組、排序、研究筆記與「更好選擇」機會成本比對
> - 規格書 7.4 雙股並排多維度比較器
> - 規格書 8.10 長輩友善模式與 Web Speech API 語音朗讀無障礙系統
> - 規格書 10 & 20.1 系統資料庫品質監控報告與異常檢測防呆
> - 規格書 14.5 Point-in-Time 策略回測報告
> - 規格書 15.3 & 15.4 LINE 雙向智能指令引擎（股票代號查詢、精選、心法、詞典、綁定）
> - 規格書 16.5 & 16.6 下單前 5 問與五階段檢核表
> - 規格書 17.2 新手教學沙盒模擬練習模式（Sandbox Simulation Mode）
> - 規格書 18 & V3.0 AI 價值研究員、葛林布雷神奇公式（ROC & EY）、自由現金流覆蓋率（FCF/NI）與合約負債季增動能分析

---

## 📱 LINE 官方帳號雙向互動與每日推播

本系統整合 LINE Messaging API，具備收盤後定時推播與即時雙向智能查詢功能：

### 1. Webhook 與連線配置
在 LINE Developers Console 後台設定：
- **Webhook URL**：`https://<您的正式域名>/api/line/webhook`（需具備 SSL/TLS HTTPS 憑證）
- **Use Webhook**：開啟（Enabled）
- **Auto-reply messages**：關閉（Disabled，由本系統智能接管）

在環境變數或 `.env` 配置金鑰：
```env
LINE_CHANNEL_ACCESS_TOKEN=您的_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET=您的_CHANNEL_SECRET
```

### 2. 支援雙向對話指令
| 指令範例 | 說明 |
|---|---|
| `2330` 或 `查詢 2454` | 4 碼股票代號快查：即時回傳收盤價、河流圖位階、折價空間與好公司健檢結論 |
| `精選` | 即時獲取今日盤後好公司價值精選名單與產業分散提醒 |
| `心法` | 隨機抽取一則安心價值投資心法，避免情緒化操作 |
| `辭典 本益比` | 查詢財務名詞之白話解釋與生活實例 |
| `123456`（6 位數字） | 於 App 設定頁生成一次性驗證碼後在此回覆，綁定個人帳號 |

---

## 📋 規格書 [TBD] 參數與預設值配置 (config/tbd_params.py)

依規格書要求，所有門檻與權重皆參數化，杜絕寫死：

| 編號 | 參數名稱 | 暫定預設值 | 說明 |
|---|---|---|---|
| **D-1** | `zone_rule_version` | `"v1.5_line"` | 五段價位區邊界判定規則（採線判定：≤A1 特價、A1-A2 便宜、A2-A5 合理、A5-A6 昂貴、≥A6 瘋狂） |
| **D-2** | `revenue_cagr_years` | `3` | 營收 CAGR 計算年數 |
| **D-2** | `revenue_positive_quarters_needed` | `3` | 近 4 季營收 YoY 至少需幾季為正 |
| **D-2** | `margin_decline_consecutive_quarters` | `2` | 三率連續幾季下滑視為黃燈警戒 |
| **D-2** | `roe_good_threshold` | `10.0%` (金融股 8.0%) | 資本效率 ROE 良好標準 |
| **D-2** | `dividend_payout_max_safe` | `100.0%` | 股利配發率安全上限（防高股息陷阱） |
| **D-2** | `dividend_consecutive_years` | `3` | 連續配息年數門檻 |
| **D-2** | `capex_growth_threshold_pct` | `20.0%` | 資本支出大幅擴產季增門檻 |
| **D-2** | `non_operating_income_warn_ratio` | `30.0%` | 單季業外收益佔淨利警示比例（提供扣除業外之正常化 EPS） |
| **D-3** | `outlier_method` | `"iqr"` (1.5×IQR) | 河流圖歷史倍數離群值剔除方法 |
| **D-3** | `valuation_history_years` | `5` | 河流圖歷史資料區間（年） |
| **D-5** | `cyclical_industries` | `["記憶體", "DRAM", "面板", "航運", "鋼鐵", "塑化", "被動元件"]` | 景氣循環股產業防呆清單（隱藏預估 EPS，改推 P/B） |
| **D-11** | `custom_stock_limit` | `50` | 每位使用者自選股上限檔數 |
| **D-12** | `include_preferred_stocks` | `False` | 是否納入特別股與存託憑證（V1 預設排除） |
| **D-13** | `radar_default_scope` | `"etf"` | 雷達首頁預設股池範圍 |
| **D-14** | `industry_concentration_limit` | `5` | 同產業入選超過幾檔時提醒分散風險 (HHI 計算) |
| **D-16** | `min_daily_volume_ntd` | `NT$ 10,000,000` | 每日精選流動性門檻（日成交金額 ≥ 1,000 萬） |
| **D-17** | `l1_revenue_accel_diff_pct` | `5.0%` | L1 訊號：近 3 月平均年增高於近 12 月之百分點差距 |
| **D-22** | `default_font_level` | `"large"` | 系統預設字級（標準 16px、大 18px、特大 21px、超大 24px） |
| **D-23** | `dividend_357_yields` | `(7%, 5%, 3%)` | 357 股利法比率（便宜 7%、合理 5%、昂貴 3%） |
| **D-24** | `peg_targets` | `(0.75, 1.0, 1.5)` | PEG 保守估值目標倍數（成長率取較低者並設 25% 上限） |
| **D-25** | `macro_us10y_alert` | `5.0%` (接近 4.5%) | 美國 10 年期公債殖利率宏觀水位警示 |
| **D-26** | `extreme_pe_threshold` | `100.0` 倍 | 極端本益比警示門檻 |
| **D-27** | `brokerage_fee_rate` | `0.1425%` | 公定證券交易手續費率 |

---

## 🏗️ 核心架構與目錄結構

```text
價值投資選股App/
├── config/
│   ├── settings.py           # 全域系統設定 (主題色碼、資料庫連線、LINE API、外部市場設定)
│   └── tbd_params.py         # 規格書所有 [TBD] 參數配置
├── Dockerfile                # 生產級非特權容器建置檔 (含台北時區與健康檢查)
├── docker-compose.yml        # 容器編排檔 (支援持久化資料目錄掛載)
├── run.py                    # 跨平台伺服器啟動入口 (支援 HOST=0.0.0.0 綁定)
├── scripts/
│   ├── start.bat             # Windows 批次檔一鍵啟動
│   ├── start.ps1             # PowerShell 彩色終端一鍵啟動
│   └── entrypoint.sh         # Linux/Docker 容器入口執行檔
├── src/
│   ├── engines/              # 純函式獨立計算引擎
│   │   ├── valuation_river.py   # 河流圖估值、六錨點、線判定、PEG、357 股利法
│   │   ├── eps_engine.py        # 六步驟滾動預估 EPS、景氣循環股與業外收益防呆
│   │   ├── good_company.py      # 六面向燈號、三態判定 (good/watch/degraded)、規則化原因清單
│   │   ├── leading_signals.py   # 八大領先訊號 (L1-L8) 與轉強狀態
│   │   ├── magic_formula.py     # 葛林布雷神奇公式 (ROC 資本報酬率 & EY 盈餘殖利率)
│   │   ├── cashflow_deep.py     # 自由現金流覆蓋率 (FCF/NI) 與合約負債季增動能分析
│   │   ├── ai_analyst.py        # AI 價值研究員深度個股分析摘要
│   │   └── industry_risk.py     # 產業集中度風控分析 (赫芬達爾 HHI 指數)
│   ├── database/
│   │   ├── schema.py            # SQLite/SQLAlchemy 2.0 ORM 資料模型 (全章節結構)
│   │   └── session.py           # 連線池與自動初始化
│   ├── universe/
│   │   ├── cleaner.py           # ETF 持股清洗規則 (排除期貨、現金、債券、特別股)
│   │   ├── syncer.py            # 四檔 ETF 同步、快照比對與事件生成 (universe_event)
│   │   └── custom_stock.py      # 自選股加入、上限檢核、查重與歷史回補
│   ├── data/
│   │   ├── mock_fixtures.py     # 初始真實持股快照、財報與價格種子
│   │   ├── twse_adapter.py      # 證交所公開市場資料適配器
│   │   ├── macro_adapter.py     # 美國財政部美債殖利率宏觀適配器
│   │   └── market_adapter.py    # 外部市場資料適配器 (具備 TTL 記憶體快取與降級回退)
│   ├── services/
│   │   ├── daily_screener.py    # 每日收盤後全股池重算與四象限分類
│   │   ├── exit_checker.py      # 出場檢核五大情境與「更好選擇」機會成本比對
│   │   ├── line_push.py         # LINE 推播排程、雙向指令處理與心法庫輪替
│   │   ├── backtester.py        # Point-in-time 歷史回測驗證服務
│   │   └── data_quality.py      # 四維度資料庫健康度檢核與加權評分
│   └── web/
│       ├── app.py               # FastAPI 應用程式主檔與生命週期
│       ├── api/routes.py        # 完整 RESTful API 路由
│       └── templates/index.html # 炭黑帳本 UI、SVG 河流圖、長輩模式、新手沙盒與模態互動
└── tests/                       # 98 項單元與整合測試套件 (100% 綠燈 PASS)
```

---

## ⚖️ 金融法規與合規遵循

1. **客觀量化研究**：本系統所有文字、畫面與推播皆維持客觀數據呈現與機會成本比對，**嚴禁出現任何「買進」、「賣出」指令或保證獲利性字眼**。
2. **免責聲明**：所有畫面底部、LINE 推播與查詢卡片皆固定顯示免責說明，提醒使用者投資風險自負。
3. **無商標侵害**：全系統完全排除真人姓名或他人商標，所有核心演算法皆為自主實作之公開價值投資量化模型。
