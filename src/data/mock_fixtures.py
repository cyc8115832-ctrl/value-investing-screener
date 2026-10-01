"""
價值投資選股 App - 財務資料與 ETF 初始數據種子 (mock_fixtures.py)
提供四檔 ETF (0050, 0056, 00881, 00891) 真實持股代表名單、
歷史財務報表、日價格、月營收、籌碼數據、投資心法庫 (第16章) 與新手手冊 (附錄A)。
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from src.database.schema import (
    StockMaster, ETFMaster, ETFMembership, ETFHoldingsSnapshot, PriceDaily,
    RevenueMonthly, FinancialsQuarterly, SharesOutstanding, ChipData,
    MindsetTip, ManualArticle, GlossaryTerm, WatchGroup
)
from src.universe.syncer import init_etf_master

# 四檔 ETF 成分股持股真實權重與代表名單 (去重聯集)
ETF_CONSTITUENTS = {
    "0050": [
        {"ticker": "2330", "name": "台積電", "weight": 52.1},
        {"ticker": "2454", "name": "聯發科", "weight": 4.9},
        {"ticker": "2317", "name": "鴻海", "weight": 4.5},
        {"ticker": "2382", "name": "廣達", "weight": 2.8},
        {"ticker": "2881", "name": "富邦金", "weight": 2.2},
        {"ticker": "2882", "name": "國泰金", "weight": 1.9},
        {"ticker": "2308", "name": "台達電", "weight": 1.8},
        {"ticker": "2603", "name": "長榮", "weight": 1.2},
        {"ticker": "2002", "name": "中鋼", "weight": 0.9},
        {"ticker": "1301", "name": "台塑", "weight": 0.8},
    ],
    "0056": [
        {"ticker": "2603", "name": "長榮", "weight": 3.8},
        {"ticker": "2382", "name": "廣達", "weight": 3.5},
        {"ticker": "2357", "name": "華碩", "weight": 3.2},
        {"ticker": "2379", "name": "瑞昱", "weight": 3.0},
        {"ticker": "3034", "name": "聯詠", "weight": 2.9},
        {"ticker": "2881", "name": "富邦金", "weight": 2.7},
        {"ticker": "2882", "name": "國泰金", "weight": 2.5},
        {"ticker": "2609", "name": "陽明", "weight": 2.2},
        {"ticker": "2409", "name": "友達", "weight": 1.8},
        {"ticker": "2303", "name": "聯電", "weight": 2.0},
    ],
    "00881": [
        {"ticker": "2330", "name": "台積電", "weight": 29.5},
        {"ticker": "2454", "name": "聯發科", "weight": 12.0},
        {"ticker": "2317", "name": "鴻海", "weight": 10.5},
        {"ticker": "2382", "name": "廣達", "weight": 7.2},
        {"ticker": "2308", "name": "台達電", "weight": 5.8},
        {"ticker": "3711", "name": "日月光投控", "weight": 4.5},
        {"ticker": "6669", "name": "緯穎", "weight": 3.8},
        {"ticker": "3008", "name": "大立光", "weight": 3.2},
    ],
    "00891": [
        {"ticker": "2330", "name": "台積電", "weight": 20.2},
        {"ticker": "2454", "name": "聯發科", "weight": 18.5},
        {"ticker": "3711", "name": "日月光投控", "weight": 9.2},
        {"ticker": "2379", "name": "瑞昱", "weight": 7.5},
        {"ticker": "3034", "name": "聯詠", "weight": 6.8},
        {"ticker": "6488", "name": "環球晶", "weight": 4.2},
        {"ticker": "3443", "name": "創意", "weight": 3.9},
        {"ticker": "3661", "name": "世芯-KY", "weight": 3.5},
    ]
}

# 個股屬性設定
STOCKS_METADATA = {
    "2330": {"name": "台積電", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 12.81, "pe_max": 31.20, "price": 980.0, "eps_est": 45.0},
    "2454": {"name": "聯發科", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 12.0, "pe_max": 25.0, "price": 1280.0, "eps_est": 68.0},
    "2317": {"name": "鴻海", "industry": "其他電子業", "sector": "general", "cyclical": False, "pe_min": 9.5, "pe_max": 18.0, "price": 190.0, "eps_est": 12.5},
    "2382": {"name": "廣達", "industry": "電腦及週邊", "sector": "general", "cyclical": False, "pe_min": 11.0, "pe_max": 24.0, "price": 280.0, "eps_est": 15.2},
    "2881": {"name": "富邦金", "industry": "金融保險業", "sector": "financial", "cyclical": False, "pe_min": 7.5, "pe_max": 13.5, "price": 88.0, "eps_est": 8.5},
    "2882": {"name": "國泰金", "industry": "金融保險業", "sector": "financial", "cyclical": False, "pe_min": 8.0, "pe_max": 14.0, "price": 65.0, "eps_est": 6.2},
    "2308": {"name": "台達電", "industry": "電子零組件", "sector": "general", "cyclical": False, "pe_min": 16.0, "pe_max": 28.0, "price": 385.0, "eps_est": 16.0},
    "2603": {"name": "長榮", "industry": "航運業", "sector": "cyclical", "cyclical": True, "pe_min": 3.0, "pe_max": 10.0, "price": 195.0, "eps_est": 25.0},
    "2609": {"name": "陽明", "industry": "航運業", "sector": "cyclical", "cyclical": True, "pe_min": 2.5, "pe_max": 9.0, "price": 68.0, "eps_est": 8.0},
    "2002": {"name": "中鋼", "industry": "鋼鐵工業", "sector": "cyclical", "cyclical": True, "pe_min": 14.0, "pe_max": 28.0, "price": 22.5, "eps_est": 0.8},
    "1301": {"name": "台塑", "industry": "塑膠工業", "sector": "cyclical", "cyclical": True, "pe_min": 12.0, "pe_max": 26.0, "price": 48.0, "eps_est": 1.2},
    "2357": {"name": "華碩", "industry": "電腦及週邊", "sector": "general", "cyclical": False, "pe_min": 9.0, "pe_max": 16.0, "price": 540.0, "eps_est": 42.0},
    "2379": {"name": "瑞昱", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 13.0, "pe_max": 26.0, "price": 490.0, "eps_est": 28.5},
    "3034": {"name": "聯詠", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 10.0, "pe_max": 20.0, "price": 510.0, "eps_est": 38.0},
    "2409": {"name": "友達", "industry": "光電業", "sector": "cyclical", "cyclical": True, "pe_min": 8.0, "pe_max": 18.0, "price": 16.5, "eps_est": 0.5},
    "2303": {"name": "聯電", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 8.5, "pe_max": 18.0, "price": 51.0, "eps_est": 4.5},
    "3711": {"name": "日月光投控", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 10.5, "pe_max": 19.5, "price": 155.0, "eps_est": 10.2},
    "6669": {"name": "緯穎", "industry": "電腦及週邊", "sector": "general", "cyclical": False, "pe_min": 14.0, "pe_max": 26.0, "price": 2150.0, "eps_est": 115.0},
    "3008": {"name": "大立光", "industry": "光電業", "sector": "general", "cyclical": False, "pe_min": 12.0, "pe_max": 22.0, "price": 2500.0, "eps_est": 165.0},
    "6488": {"name": "環球晶", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 11.0, "pe_max": 22.0, "price": 460.0, "eps_est": 32.0},
    "3443": {"name": "創意", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 25.0, "pe_max": 65.0, "price": 1220.0, "eps_est": 30.0},
    "3661": {"name": "世芯-KY", "industry": "半導體業", "sector": "general", "cyclical": False, "pe_min": 28.0, "pe_max": 75.0, "price": 2180.0, "eps_est": 55.0},
}

MINDSET_TIPS_DATA = [
    {"category": "槓桿資金", "text": "【平心心法】切勿擴大融資槓桿！價值投資是數年尺度的耐力賽，借錢投資會讓時間從盟友變成逼你斷頭的敵人。"},
    {"category": "槓桿資金", "text": "【資金紀律】永遠預留 6 個月以上的生活預備金。只有在即使股市休市三年也不影響生活的狀態下，才能心平氣和等待好價格。"},
    {"category": "操作心態", "text": "【估值心法】昂貴區是『風險偏高』的警示，而非放空或預測行情的最高點；便宜區是『相對特價』，不是明天立即飆漲的保證。"},
    {"category": "操作心態", "text": "【抗焦慮】台股證交稅千分之三加上手續費，頻繁當沖只會把獲利送給政府與券商。好公司值得用低頻節奏長相廝守。"},
    {"category": "操作心態", "text": "【好公司本質】先選好公司，再等好價格。獲利持續衰退的公司，就算跌到特價區也只是價值陷阱，碰不得！"},
    {"category": "操作心態", "text": "【逆向思維】巴菲特：『在別人貪婪時恐懼，在別人恐懼時貪婪。』當河流圖沉入特價藍海時，正是靜心研究的核心良機。"},
    {"category": "操作心態", "text": "【耐心持有】種下一棵果樹需要四季更迭，買進優秀企業也要給予產能釋放與業績發酵的時間。"},
    {"category": "槓桿資金", "text": "【避免重押】單一標的持股比重不宜超過總資金的 25%~30%，分散產業配置能有效避開不可抗力的黑天鵝。"},
    {"category": "估值本質", "text": "【獲利上修】通道帶是跟著獲利走，不是跟著股價跑。公司獲利持續上修時，原本的昂貴價在未來也會變成便宜價。"},
    {"category": "操作心態", "text": "【下單前 5 問】1. 這筆錢何時要用？ 2. 我了解它的獲利來源嗎？ 3. 跌 20% 我能睡得著嗎？ 4. 它是循環股嗎？ 5. 現價在哪個區帶？"},
    {"category": "操作心態", "text": "【循環股警惕】循環股絕不能用單月爆發的 EPS 乘上 12 個月去盲目推估！在獲利最高峰時往往是本益比最低的週期頂部。"},
    {"category": "估值本質", "text": "【領先訊號】財報是過去的成績單，訂金與月營收加速度才是明天的天氣預報。兩者呼應，勝算更高。"},
    {"category": "操作心態", "text": "【市場先生】股市短期是投票機，長期是稱重機。不要被每日跳動的紅綠價格牽動情緒，專注於公司真實重量。"},
    {"category": "槓桿資金", "text": "【杜絕質押】股票質押看似保留了股票，但在急速修正中常因維持率不足被強迫變賣在阿呆谷。"},
    {"category": "操作心態", "text": "【出場紀律】好公司若因市場恐慌被錯殺，是加碼良機；但若好公司基本面連續兩季轉弱退化，則應冷靜檢視出場。"},
    {"category": "估值本質", "text": "【安全邊際】便宜價就是為我們不可預知的意外保留的安全防撞氣囊。買得夠便宜，犯錯的代價就極小。"}
]

MANUAL_ARTICLES_DATA = [
    {
        "article_id": "guide_01",
        "chapter": "第一章",
        "title": "先選好公司，再等好價格：價值投資核心觀念",
        "related_screen": "radar",
        "body_md": "### 什麼是價值投資？\n\n很多人買股票像在買彩券，看今天誰漲就追誰。但價值投資的觀念完全不同：**買股票就是成為這家公司的合夥股東**。\n\n我們的核心策略只有兩句話：\n1. **先選好公司**：這家公司獲利穩健成長、每年越賺越多、現金流充沛。\n2. **再等好價格**：再好的公司買貴了也是壞投資，我們耐心等待市場恐慌或合理特價時才出手。\n\n本 App 每日為您追蹤 0050、0056、00881、00891 四檔主要 ETF 的優質成分股，透過兩道門模型把關，幫助您安心波段投資。"
    },
    {
        "article_id": "guide_02",
        "chapter": "第二章",
        "title": "如何看懂估值河流圖與五段價位",
        "related_screen": "stock_detail",
        "body_md": "### 河流圖五段價位線怎麼看？\n\n本 App 依據過去 5 年的歷史倍數（如本益比），透過專屬演算法畫出五條彩帶：\n- 🔵 **特價區**（深藍）：價格低於特價線，歷史難得一見的超值研究區。\n- 🩵 **便宜區**（淺藍）：價格位於特價線與便宜線之間，安全邊際充沛。\n- 🟢 **合理區**（翡翠綠）：企業價值與市場預期相當，穩健持有區間。\n- 🟠 **昂貴區**（琥珀橘）：價格來到相對高檔，留意估值膨脹風險。\n- 🔴 **瘋狂區**（紫色標記）：市場情緒極度過熱，切勿追高盲目進場！"
    },
    {
        "article_id": "guide_03",
        "chapter": "第三章",
        "title": "長輩友善與大字模式設定指南",
        "related_screen": "settings",
        "body_md": "### 把字放大，看得輕鬆自在\n\n我們深知長時間盯盤與閱讀小字對眼睛的負擔，因此全系統提供專屬字級調整：\n1. 前往「設定」頁面。\n2. 在字級大小中可自由切換：**標準、大（預設）、特大、超大** 四種字級。\n3. 您也可以一鍵開啟「**長輩友善模式**」，系統會自動啟用高對比配色、放大操作按鈕並簡化圖表。"
    }
]

GLOSSARY_DATA = [
    {"term_id": "g_pe", "term": "本益比 (P/E)", "plain_explain": "買進這檔股票回本需要的年數。例如股價 100 元，每年賺 10 元，本益比就是 10 倍。", "example": "台積電現在股價 980 元，預估今年賺 45 元，本益比約 21.8 倍。"},
    {"term_id": "g_pb", "term": "股價淨值比 (P/B)", "plain_explain": "股價相對於公司資產淨值的倍數。適合用來衡量景氣循環股與金融股。", "example": "航運股與鋼鐵股在虧損或低谷時，看淨值比比看本益比更能抓住低點。"},
    {"term_id": "g_yoy", "term": "年增率 (YoY)", "plain_explain": "跟去年同一個月份相比增加的百分比。能排除單月旺季淡季的干擾。", "example": "今年 8 月營收比去年 8 月成長 20%，YoY 就是 +20%。"},
    {"term_id": "g_fcf", "term": "自由現金流 (FCF)", "plain_explain": "公司賺來的真金白銀扣掉擴廠投資後，真正能自由支配、分給股東的現金。", "example": "光有營收帳面數字不夠，自由現金流為正才代表公司真的有現金進帳。"}
]


def seed_database_fixtures(db: Session):
    """
    填充資料庫基礎種子數據
    """
    init_etf_master(db)
    today_dt = date.today()

    # 1. 先寫入 StockMaster (獨立去重)
    for ticker, meta in STOCKS_METADATA.items():
        stock = db.query(StockMaster).filter(StockMaster.ticker == ticker).first()
        if not stock:
            stock = StockMaster(
                ticker=ticker,
                company_name=meta["name"],
                industry=meta["industry"],
                sector_type=meta["sector"],
                is_cyclical=meta["cyclical"],
                pool_status="etf"
            )
            db.add(stock)
    db.commit()

    # 2. 寫入 ETF 成分與持股快照
    for etf_code, holdings in ETF_CONSTITUENTS.items():
        for item in holdings:
            t = item["ticker"]
            w = item["weight"]

            # ETFMembership
            mem = db.query(ETFMembership).filter(ETFMembership.etf_code == etf_code, ETFMembership.ticker == t).first()
            if not mem:
                mem = ETFMembership(
                    etf_code=etf_code,
                    ticker=t,
                    weight=w,
                    effective_date=today_dt
                )
                db.add(mem)

            # ETFHoldingsSnapshot
            snap = db.query(ETFHoldingsSnapshot).filter(
                ETFHoldingsSnapshot.etf_code == etf_code,
                ETFHoldingsSnapshot.snapshot_date == today_dt,
                ETFHoldingsSnapshot.ticker == t
            ).first()
            if not snap:
                snap = ETFHoldingsSnapshot(
                    etf_code=etf_code,
                    snapshot_date=today_dt,
                    ticker=t,
                    weight=w
                )
                db.add(snap)
    db.commit()

    # 3. 寫入每檔股票的近期行情、營收與季報資料
    all_stocks = db.query(StockMaster).all()
    for s in all_stocks:
        t = s.ticker
        meta = STOCKS_METADATA.get(t, {"pe_min": 12.0, "pe_max": 25.0, "price": 100.0, "eps_est": 5.0})
        cur_price = meta.get("price", 100.0)

        # 價格記錄 (最近 5 天)
        for i in range(5):
            d = today_dt - timedelta(days=i)
            existing_p = db.query(PriceDaily).filter(PriceDaily.ticker == t, PriceDaily.date == d).first()
            if not existing_p:
                p_record = PriceDaily(
                    ticker=t,
                    date=d,
                    close=cur_price * (1.0 - i * 0.005),
                    volume=15000000.0,
                    pe=cur_price / meta.get("eps_est", 5.0),
                    pb=cur_price / (cur_price * 0.4),
                    ps=cur_price / (cur_price * 0.8)
                )
                db.add(p_record)

        # 月營收 (最近 12 個月)
        for m in range(1, 13):
            month_str = f"2026-{m:02d}" if m <= 9 else f"2025-{m:02d}"
            existing_rev = db.query(RevenueMonthly).filter(RevenueMonthly.ticker == t, RevenueMonthly.month == month_str).first()
            if not existing_rev:
                base_rev = 150.0 if t == "2330" else 20.0
                growth = 0.18 if not s.is_cyclical else 0.05
                rev = RevenueMonthly(
                    ticker=t,
                    month=month_str,
                    revenue=base_rev * (1.0 + m * 0.02),
                    yoy=growth + (m % 3) * 0.02,
                    cumulative_revenue=base_rev * m * 1.05,
                    cumulative_yoy=growth
                )
                db.add(rev)

        # 季報 (最近 4 季)
        for q_idx, q_name in enumerate(["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"]):
            existing_q = db.query(FinancialsQuarterly).filter(FinancialsQuarterly.ticker == t, FinancialsQuarterly.quarter == q_name).first()
            if not existing_q:
                q_rev = 500.0 if t == "2330" else 80.0
                fq = FinancialsQuarterly(
                    ticker=t,
                    quarter=q_name,
                    revenue=q_rev,
                    gross_profit=q_rev * 0.52,
                    operating_income=q_rev * 0.42,
                    net_income=q_rev * 0.38,
                    non_operating_income=q_rev * 0.02,
                    gross_margin=0.52,
                    operating_margin=0.42,
                    net_margin=0.38,
                    roe=24.5,
                    roic=21.0,
                    operating_cf=q_rev * 0.40,
                    capex=q_rev * 0.15,
                    fcf=q_rev * 0.25,
                    contract_liabilities=q_rev * 0.10,
                    ppe=q_rev * 2.0,
                    inventory=q_rev * 0.08,
                    receivables=q_rev * 0.06
                )
                db.add(fq)

        # 流通股數
        existing_sh = db.query(SharesOutstanding).filter(SharesOutstanding.ticker == t, SharesOutstanding.date == today_dt).first()
        if not existing_sh:
            db.add(SharesOutstanding(ticker=t, date=today_dt, shares=25930.0 if t == "2330" else 1500.0))

        # 籌碼資料
        existing_chip = db.query(ChipData).filter(ChipData.ticker == t, ChipData.date == today_dt).first()
        if not existing_chip:
            db.add(ChipData(
                ticker=t,
                date=today_dt,
                foreign_net=3500.0,
                trust_net=1200.0,
                dealer_net=400.0,
                insider_holding_pct=28.5,
                big_holder_pct=76.2
            ))

    # 4. 填入心法庫
    for tip in MINDSET_TIPS_DATA:
        existing_tip = db.query(MindsetTip).filter(MindsetTip.text == tip["text"]).first()
        if not existing_tip:
            db.add(MindsetTip(category=tip["category"], text=tip["text"], active=True))

    # 5. 填入新手手冊
    for art in MANUAL_ARTICLES_DATA:
        existing_art = db.query(ManualArticle).filter(ManualArticle.article_id == art["article_id"]).first()
        if not existing_art:
            db.add(ManualArticle(
                article_id=art["article_id"],
                chapter=art["chapter"],
                title=art["title"],
                body_md=art["body_md"],
                related_screen=art["related_screen"]
            ))

    # 6. 填入詞典
    for g in GLOSSARY_DATA:
        existing_g = db.query(GlossaryTerm).filter(GlossaryTerm.term_id == g["term_id"]).first()
        if not existing_g:
            db.add(GlossaryTerm(
                term_id=g["term_id"],
                term=g["term"],
                plain_explain=g["plain_explain"],
                example=g["example"]
            ))

    # 7. 初始化預設觀察清單群組 (規格書 7.1)
    default_groups = [
        {"id": "core_pool", "name": "核心候選", "order": 1, "type": "system"},
        {"id": "watch_cheap", "name": "便宜等催化", "order": 2, "type": "system"},
        {"id": "cyclical_tracking", "name": "循環轉折", "order": 3, "type": "system"},
        {"id": "warn_list", "name": "警戒待檢視", "order": 4, "type": "system"}
    ]
    for g in default_groups:
        existing_grp = db.query(WatchGroup).filter(WatchGroup.group_id == g["id"]).first()
        if not existing_grp:
            db.add(WatchGroup(group_id=g["id"], name=g["name"], sort_order=g["order"], group_type=g["type"]))

    db.commit()
    print("Database fixture seeding completed.")
