# 價值投資選股 App（V1.7 實作版）

> **核心宗旨**：先選好公司，再等好價格。  
> 本系統依據《價值投資選股 App 技術規格書 V1.7》進行實作與驗收，涵蓋四檔主要台股 ETF（0050、0056、00881、00891）之聯集成分股與使用者自選股，建構好公司健檢引擎（六面向燈號）、EPS 滾動預估引擎、河流圖五段價位估值引擎（P/E、P/B、P/S）及領先訊號引擎，並提供深黑高對比 UI（炭黑帳本方案 B）、長輩友善模式與收盤後 LINE 每日精選推播。

---

## 🚀 快速啟動

專案依據磁碟隔離規範，所有套件與資料庫均建置於 D 槽本地虛擬環境：

```powershell
# 1. 啟動伺服器
.\.venv\Scripts\python.exe run.py

# 2. 開啟瀏覽器訪問
http://127.0.0.1:8000
```

### 執行單元測試與驗收測試
```powershell
.\.venv\Scripts\pytest.exe -v
```
*(目前 29 項測試全數通過，涵蓋規格書 6.2、6.2b、6.8b、6.8c、第 4、5、14 章等核心規則)*

---

## 📋 規格書 [TBD] 參數與預設值清單 (config/tbd_params.py)

依規格書第 0、21、22 章要求，所有待決項目皆已參數化配置於 `config/tbd_params.py`：

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
| **D-14** | `industry_concentration_limit` | `5` | 同產業入選超過幾檔時提醒分散風險 |
| **D-16** | `min_daily_volume_ntd` | `NT$ 10,000,000` | 每日精選流動性門檻（日成交金額 ≥ 1,000 萬） |
| **D-17** | `l1_revenue_accel_diff_pct` | `5.0%` | L1 訊號：近 3 月平均年增高於近 12 月之百分點差距 |
| **D-22** | `default_font_level` | `"large"` | 系統預設字級（標準 16px、大 18px、特大 21px、超大 24px） |
| **D-23** | `dividend_357_yields` | `(7%, 5%, 3%)` | 357 股利法比率（便宜 7%、合理 5%、昂貴 3%，基準取較低者） |
| **D-24** | `peg_targets` | `(0.75, 1.0, 1.5)` | PEG 保守估值目標倍數（G 設 25% 上限） |
| **D-25** | `macro_us10y_alert` | `5.0%` (接近 4.5%) | 美國 10 年期公債殖利率宏觀水位警示 |
| **D-26** | `extreme_pe_threshold` | `100.0` 倍 | 極端本益比警示門檻 |
| **D-27** | `brokerage_fee_rate` | `0.1425%` | 公定證券交易手續費率 |

---

## 🏗️ 核心架構與模組設計

```text
價值投資選股App/
├── config/
│   ├── settings.py           # 全域系統設定 (主題色碼、資料庫連線、LINE API)
│   └── tbd_params.py         # 規格書所有 [TBD] 參數配置
├── src/
│   ├── engines/              # 純函式獨立計算引擎 (通過 6.2 測試案例)
│   │   ├── valuation_river.py  # 河流圖估值、六錨點、線判定、PEG 6.8c、357法 6.8b
│   │   ├── eps_engine.py       # 六步驟滾動預估 EPS、景氣循環股防呆、業外收益防呆
│   │   ├── good_company.py     # 六面向燈號、三態判定 (good/watch/degraded)、規則化原因
│   │   └── leading_signals.py  # 八大領先訊號 (L1-L8)、轉強/轉弱狀態彙整
│   ├── database/
│   │   ├── schema.py           # SQLite/SQLAlchemy 2.0 ORM 資料模型 (第 9 章)
│   │   └── session.py          # Session 連線管理與自動初始化
│   ├── universe/
│   │   ├── cleaner.py          # ETF 持股清洗規則 (排除期貨、現金、債券、特別股，2.4)
│   │   ├── syncer.py           # 四檔 ETF 同步、快照比對與事件生成 (universe_event，2.3)
│   │   └── custom_stock.py     # 自選股加入、上限檢核、ETF 查重與自動回補 (2.5)
│   ├── data/
│   │   └── mock_fixtures.py    # 四檔 ETF 真實持股快照、近期財報與價格種子
│   ├── services/
│   │   ├── daily_screener.py   # 每日收盤後全股池計算、四象限分類、每日精選排序
│   │   ├── exit_checker.py     # 出場檢核五大情境與月營收/財報檢視提醒 (7.2, 7.3)
│   │   ├── line_push.py        # LINE 推播格式化 (標準版 vs 長輩大字版) 與心法庫輪替 (15, 16)
│   │   └── backtester.py       # Point-in-time 回測驗證引擎 (14.5)
│   └── web/
│       ├── app.py              # FastAPI 應用程式與生命週期管理
│       ├── api/routes.py       # RESTful API 端點
│       └── templates/index.html# 炭黑帳本方案 B 高對比 UI (深黑底、動態字級、SVG 河流圖)
└── tests/                      # 完整單元與整合測試套件 (29 項全部通過)
```

---

## 🎯 驗收成果指標

1. **6.2 測試案例**：台積電範例（PE 12.81～31.20，預估 EPS 135），A1～A6 價格錨點分別為 1729, 2226, 2722, 3219, 3715, 4212 元，誤差全數 ≤ 1 元。
2. **6.2b 價位區歸屬**：1700（特價）、2210（便宜）、2226（邊界便宜）、2500（合理）、3715（邊界昂貴）、4300（瘋狂）、漢唐 1450（至少昂貴），全數正確判定。
3. **循環股防呆**：長榮（2603）、陽明（2609）、中鋼（2002）等標記循環股時，預估 EPS 自動隱藏，系統推薦 P/B 河流圖。
4. **業外收益防呆**：單季業外 > 30% 淨利時標記 ⚠️，並自動計算扣除業外後之正常化 EPS。
5. **入選原因徽章**：`good`、`cheap`、`capex`、`contract`、`rev_up`、`eps_up` 規則化產出，零使用 LLM。
6. **合規與隱私**：全系統無任何真人姓名或他人商標，無任何買進/賣出指令文案。
