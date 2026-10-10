# 交接檔 — 價值投資選股App

最後更新：2026-10-09T11:32:39.745634+00:00，Codex @ DESKTOP-QISHBK7。
狀態：使用者已核准44檔來源換行修正，9f7badd已提交推送，113份來源blob hash一致且遠端0/0。最新CI及Pages已啟動，尚未結束。

## 目前做到哪

- 官方行情94檔共91,089筆，最新2026-10-07；93檔49月份、6526為37月份。12檔279個參考日差集仍待公司事件核實。
- 最新94檔2026-Q2累計損益＋94檔資產負債188筆仍與10個官方來源一致。
- 本輪新增五類代表2330／2881／5876／2207／3105的2025-Q2損益及資產負債10筆，既有五筆現金流保留10/8版本。另新增2330之2024-Q2、2317之2025-Q2各三表6筆。合計7組報告期間有三表；不是全94檔歷年完成。
- 7份電子書原PDF、Big5索引、上傳時間及hash已保存；91個本期核心科目與MOPS表一致，2330跨年比較欄14科目一致。僅核對列明核心範圍，未逐一核對所有附註、原檔科目及更正鏈。
- 損益依兩層表頭／金額百分比／colspan取官方直接單季基本EPS，不相減累計EPS；母公司淨利依歸屬段落避開綜合損益。BS本期及比較期均勾稽，股本不換股數。目前損益契約僅核對Q2，其他季度停止。
- 新16筆可得日保守2026-10-09，10/8不可見；原現金流10/8各一筆仍可見。電子書上傳時間保留但不回填可得日，原公告日null／原始版本驗證false。TTM、預估EPS、自由現金流及真實策略仍未知。
- 全套217項D槽隔離測試通過（470個既有棄用警告，99.9秒）；SQLite完整性ok，最新91,392及修訂91,693，共183,085筆hash失敗0，行情91,089筆一致；188筆最新財報來源一致。最後表頭rowspan防護調整後29項歷史兩表模組回歸通過；compileall及git diff --check通過。
- 94檔靜態已重新匯出；756個API／靜態端點與273,264列歷史資料一致，禁止私人欄位0、版本時間／資產檔查核通過。本機雷達已載入並維持停止排名；未作本輪雲端發布或實機驗收。

## 下一步

1. 核實7組報告最早申報及歷次更正鏈，分開電子書上傳、董事會通過、重大訊息與實際觀察時間。即使目錄更補正欄為「無」，也不能自行判定原始版本；2330之7月單季EPS公告索引不能作半年現金流公告日。
2. 取樣Q1／Q3／Q4真實表頭並擴充契約及單季EPS；優先補五類代表連續四季三表，不以目前Q2直接套用其他型態。
3. 依明確hash批次分批擴大94檔歷年資料。先整批預檢、備份、單一交易匯入，再資料庫／截止日／API靜態查核。script預設只驗證，--apply才寫正式DB。

## 注意事項與工具

全94檔歷年財報、公告更正、股數／股利、歷史股池與公司事件仍缺。正式排名、LINE買進精選與真實策略維持未驗收，事後重建不是當時預估；不得使用舊100%勝率及+16.71%。官方403／428／429或防護文字立即停止，不反覆試探。

主要新工具：src/data/historical_statements.py；scripts/backfill_verified_statements.py、capture_statement_books.py、verify_statement_books.py。沿用historical_cash_flow、共用匯入備份交易、verified_earnings直接官方EPS防護。只使用D槽.venv，新增pypdf[crypto]==6.19.0於requirements，pip快取D:/pip_cache，無C槽全域安裝。

詳細來源、批次hash與匯入結果在reports/2026-10-09/財報來源/；成果為歷史三表與電子書第一批成果.md，查核為電子書三表核心核對.json、台積電跨年比較欄核對.json、歷史三表測試結果.json、歷史三表後資料庫查核.json、財報證據查核.json、歷史三表時間點查核.json。未重跑701月／972日行情來源快照，原證據保留。開工前完整交接已保存本輪開工前交接.md；10/8提交hash清單與草稿保持原版本。

## Git與預覽

開工HEAD 6ca888856b4b30eb0a95a78b5678edc1ffc2ba15，master與origin/master 0/0，工作區乾淨。6ca8888之CI及Pages已成功；85900ba之CI成功，其Pages被後續成功部署取代。

- CI：https://github.com/cyc8115832-ctrl/value-investing-screener/actions/runs/37794963842
- Pages：https://github.com/cyc8115832-ctrl/value-investing-screener/actions/runs/37794963073

本輪236檔已核准提交／推送（0083e0b，實際236檔且清單外0）；正式DB／備份／.venv／金鑰排除Git；Obsidian未啟用。SQLite一致備份在data/收工備份/歷史三表-20261009-020319/，完整性ok、三個公開資料表全部欄位與運行中DB一致。DB及公開變更ZIP／hash見本輪保存結果.json；新的繁中提交草稿與逐檔hash範圍已鎖定（歷史三表提交草稿.md／歷史三表提交檔案清單.json），使用者已明確核准本輪236檔，草稿及清單保持核准時版本。

8767舊正式預覽程序已停止，已於本輪用D槽.venv重啟127.0.0.1:8767，DEMO_MODE=false、ENABLE_SCHEDULER=false；啟動父PID19892、實際服務PID14888。靜態8768也已重啟，實際PID11952。舊PID不沿用，下次先核對連接埠。

備份行情表另有846筆既有列（94檔、2026-04-03至2026-10-04）未對應已核實行情證據；不計入91,089筆官方覆蓋，本輪未刪除或改寫，正式顯示採MarketEvidence。

## 本輪推送結果與下一批取樣

主要提交0083e0bd3dd3c70b4db6e34f68d77c6b65cdc209，推送後0/0，逐檔hash及暫存內容核對失敗0，實際提交236檔、清單外0。核准範圍與結果見reports/2026-10-09/歷史三表Git同步結果.json；此結果及agents/handoff另以文件提交同步。

- CI/CD Pipeline：https://github.com/cyc8115832-ctrl/value-investing-screener/actions/runs/37917955908（in_progress／未結束）
- pages build and deployment：https://github.com/cyc8115832-ctrl/value-investing-screener/actions/runs/37917954933（in_progress／未結束）

下一批2330／2881／5876／2207／3105之2025-Q1／Q3／Q4損益15份，40組母公司＋非控制＝總淨利核對一致。Q1雙期間、Q3單季／累計四期間、Q4年度雙期間；正式解析器仍對15份停止，未匯入DB。原表與季度取樣查核.json／下一批交接.md位於data/收工備份/歷史三表-20261009-020319/下一批季度取樣/（私人備份，不納入本輪236檔）。下一步擴充季度契約，補BS／CF／電子書及整批匯入；Q4無官方直接單季EPS，不相減累計EPS，保持未知。

## 最新CI查核與修正待核准

主要236檔0083e0b及交接9a76c92已推送，遠端0/0；兩次Pages均成功，但兩次CI均215通過／2項來源hash失敗。根因為Git core.autocrlf將原始CRLF轉LF。新增財報來源-text規則、按原核准位元組復原後，113份hash全部一致，乾淨取出29項相關測試通過；新修正草稿／逐檔清單等待明確核准，尚未stage／commit／push。原236檔草稿及清單不改。

詳見reports/2026-10-09/來源位元組保存修正驗證.json、來源位元組保存修正提交草稿.md與來源位元組保存修正提交檔案清單.json。CI 37918084775 failure，Pages 37918084173 success；驗證目錄與測試輸出保存在私人備份。下一步核准修正後只stage新清單指定檔案；來源需git add --renormalize以原始位元組入Git，再重新確認113份來源blob的SHA256及整個暫存範圍。

## 最新換行修正推送結果（優先於上述歷史狀態）

使用者已核准44檔換行修正，9f7badd已提交並推送至origin/master，實際44檔、清單外0，113份來源Git blob與原核准位元組hash全部一致，推送後0/0。原236檔及修正44檔草稿／hash清單保留核准時版本；私人DB及備份排除Git。修正後CI／Pages已觸發，記錄時尚未結束，後續須以本提交或最新文件提交的工作流判定。

- CI/CD Pipeline：https://github.com/cyc8115832-ctrl/value-investing-screener/actions/runs/37924312148（in_progress／未結束）
- pages build and deployment：https://github.com/cyc8115832-ctrl/value-investing-screener/actions/runs/37924311398（in_progress／未結束）

同步結果見reports/2026-10-09/來源位元組保存修正Git結果.json；本節及agents與結果JSON另以文件提交同步。即時最終CI／Pages結果另外保存在data/收工備份/歷史三表-20261009-020319/換行修正最終遠端驗證.json。下一步仍為核實公告更正鏈、擴充Q1／Q3／Q4契約與連續四季三表；15份取樣尚未匯入。
