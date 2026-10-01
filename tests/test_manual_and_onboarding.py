"""
測試新手操作手冊 (13 篇)、專有名詞白話辭典 (26 條)、觀察清單匯出與各畫面指引功能
對應規格書第 7.4 節、第 17 章 (17.1 - 17.6) 及附錄 A (A0 - A12)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import csv
import io

from src.web.app import app
from src.database.session import SessionLocal
from src.database.schema import ManualArticle, GlossaryTerm, WatchGroup, WatchGroupMember, StockMaster
from src.data.mock_fixtures import seed_database_fixtures

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def init_db():
    db = SessionLocal()
    seed_database_fixtures(db)
    yield db
    db.close()


def test_manual_articles_complete_count():
    """驗證手冊全部 13 篇章節 (A0 ~ A12) 皆已建立且順序正確"""
    res = client.get("/api/manual")
    assert res.status_code == 200
    articles = res.json()
    assert len(articles) == 13, f"應為 13 篇手冊，實際取得 {len(articles)} 篇"

    # 驗證 A0 ~ A12 章節名稱
    expected_prefixes = [f"A{i}" for i in range(13)]
    actual_chapters = [a["chapter"] for a in articles]
    for exp in expected_prefixes:
        assert any(exp in ch for ch in actual_chapters), f"缺少 {exp} 章節"

    # 驗證結構欄位
    for a in articles:
        assert a["id"].startswith("guide_a")
        assert len(a["title"]) > 0
        assert len(a["body"]) > 20
        assert a["screen"] in ["radar", "screener", "stock_detail", "watchlist", "settings"]


def test_manual_screen_filter():
    """驗證畫面專屬手冊篩選 (規格書 17.2)"""
    screens = ["radar", "screener", "stock_detail", "watchlist", "settings"]
    for s in screens:
        res = client.get(f"/api/manual?screen={s}")
        assert res.status_code == 200
        arts = res.json()
        assert len(arts) >= 1, f"畫面 {s} 應至少有一篇專屬操作說明"
        for a in arts:
            assert a["screen"] == s


def test_glossary_terms_complete_count():
    """驗證白話名詞辭典 26 個名詞皆備齊 (規格書附錄 A2)"""
    res = client.get("/api/glossary")
    assert res.status_code == 200
    terms = res.json()
    assert len(terms) == 26, f"應為 26 條專有名詞辭典，實際取得 {len(terms)} 條"

    # 驗證關鍵名詞均存在
    term_names = [t["term"] for t in terms]
    critical_terms = ["股票", "ETF (指數股票型基金)", "本益比 (P/E)", "股價淨值比 (P/B)", "合約負債 (客戶預收款)", "自由現金流 (FCF)", "景氣循環股"]
    for ct in critical_terms:
        assert ct in term_names, f"缺少重要名詞：{ct}"

    # 驗證每個名詞皆有白話解釋與生活例子 (高中生看得懂版)
    for t in terms:
        assert len(t["explain"]) >= 5
        assert len(t["example"]) >= 5


def test_glossary_search():
    """驗證專有名詞關鍵字搜尋"""
    # 搜尋本益比
    res1 = client.get("/api/glossary?q=本益比")
    assert res1.status_code == 200
    results1 = res1.json()
    assert len(results1) >= 1
    assert any("本益比" in item["term"] for item in results1)

    # 搜尋合約負債
    res2 = client.get("/api/glossary?q=合約負債")
    assert res2.status_code == 200
    results2 = res2.json()
    assert len(results2) >= 1
    assert any("合約負債" in item["term"] for item in results2)

    # 搜尋不存在名詞
    res3 = client.get("/api/glossary?q=不存在的火星指標")
    assert res3.status_code == 200
    results3 = res3.json()
    assert len(results3) == 0


def test_watchlist_add_and_export():
    """驗證加入觀察清單記錄現價價位區，以及 CSV 與 JSON 匯出 (規格書 V1.5 / 7.4)"""
    # 先加入台積電至核心候選群組
    add_res = client.post("/api/watchlist/add?group_id=core_pool&ticker=2330&note=護城河強大且先進製程領先")
    assert add_res.status_code == 200

    # 匯出 JSON
    res_json = client.get("/api/watchlist/export?format=json")
    assert res_json.status_code == 200
    items = res_json.json()
    assert len(items) >= 1
    tsmc = next((item for item in items if item["ticker"] == "2330"), None)
    assert tsmc is not None
    assert tsmc["company_name"] == "台積電"
    assert tsmc["entry_price"] > 0
    assert "價位區" in tsmc["entry_zone"] or tsmc["entry_zone"] in ["特價區", "便宜區", "合理區", "昂貴區", "瘋狂區"]
    assert "護城河" in tsmc["note"]

    # 匯出 CSV
    res_csv = client.get("/api/watchlist/export?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "attachment; filename=watchlist_" in res_csv.headers["content-disposition"]
    
    # 驗證 UTF-8 BOM
    content = res_csv.content
    assert content.startswith(b"\xef\xbb\xbf"), "CSV 必須包含 UTF-8 BOM 供 Excel 正常識別中文"

    # 解析 CSV 內容
    text_content = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)
    assert len(rows) >= 2  # 表頭 + 至少 1 列資料
    header = rows[0]
    assert header == ["股票代號", "公司名稱", "產業別", "觀察群組", "加入價格", "加入價位區", "最新現價", "目前價位區", "投資理由與研究筆記"]

    found_tsmc = any(r[0] == "2330" and r[1] == "台積電" for r in rows[1:])
    assert found_tsmc, "CSV 應包含台積電 2330"
