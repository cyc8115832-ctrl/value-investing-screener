"""
測試觀察清單進階功能（自訂群組、順序調整、研究筆記）與三大出場條件（有更好的選擇動態比對）
對應規格書第 7.1 節、第 7.2 節與第 7.4 節
"""

import pytest
from fastapi.testclient import TestClient
from src.web.app import app
from src.database.session import SessionLocal
from src.database.schema import WatchGroup, WatchGroupMember, StockMaster
from src.data.mock_fixtures import seed_database_fixtures
from src.services.exit_checker import find_better_alternatives

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def init_db():
    db = SessionLocal()
    seed_database_fixtures(db)
    yield db
    db.close()


def test_watchlist_structure_with_sorting_and_margins():
    """驗證 GET /api/watchlist 回傳的分組資料結構包含折價空間與排序欄位"""
    res = client.get("/api/watchlist")
    assert res.status_code == 200
    groups = res.json()
    assert len(groups) >= 1
    
    first_g = groups[0]
    assert "group_id" in first_g
    assert "name" in first_g
    assert "is_custom" in first_g
    assert "stocks" in first_g

    if len(first_g["stocks"]) > 0:
        s = first_g["stocks"][0]
        assert "ticker" in s
        assert "company_name" in s
        assert "current_price" in s
        assert "zone" in s
        assert "margin_pct" in s
        assert "sort_order" in s
        assert "note" in s


def test_custom_watchgroup_lifecycle():
    """驗證自訂觀察群組的生命週期（建立、防重名、加入標的、刪除與系統群組保護）"""
    # 1. 建立自訂群組
    g_name = "AI伺服器專用測試群組"
    res = client.post(f"/api/watchlist/group/create?name={g_name}")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    group_id = data["group_id"]

    # 2. 防重名檢查
    res_dup = client.post(f"/api/watchlist/group/create?name={g_name}")
    assert res_dup.status_code == 200
    assert res_dup.json()["success"] is False
    assert "已有相同名稱" in res_dup.json()["message"]

    # 3. 加入成員
    res_add = client.post(f"/api/watchlist/add?group_id={group_id}&ticker=2382&note=AI主力代工廠")
    assert res_add.status_code == 200
    assert res_add.json()["success"] is True

    # 4. 驗證群組內有該成員
    res_list = client.get("/api/watchlist")
    target_g = next((g for g in res_list.json() if g["group_id"] == group_id), None)
    assert target_g is not None
    assert target_g["is_custom"] is True
    assert len(target_g["stocks"]) == 1
    assert target_g["stocks"][0]["ticker"] == "2382"
    assert target_g["stocks"][0]["note"] == "AI主力代工廠"

    # 5. 系統預設群組保護（不可刪除）
    res_del_sys = client.delete("/api/watchlist/group/core_pool")
    assert res_del_sys.status_code == 200
    assert res_del_sys.json()["success"] is False
    assert "系統預設群組不可刪除" in res_del_sys.json()["message"]

    # 6. 刪除自訂群組
    res_del = client.delete(f"/api/watchlist/group/{group_id}")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 7. 驗證已移除
    res_after = client.get("/api/watchlist")
    assert not any(g["group_id"] == group_id for g in res_after.json())


def test_watchlist_member_move_and_reorder():
    """驗證觀察清單組內順序調整（上移/下移與邊界防呆）"""
    # 建立臨時測試群組並加入兩檔標的
    res = client.post("/api/watchlist/group/create?name=順序測試群組")
    group_id = res.json()["group_id"]

    try:
        client.post(f"/api/watchlist/add?group_id={group_id}&ticker=2330")
        client.post(f"/api/watchlist/add?group_id={group_id}&ticker=2454")

        # 頂端標的無法再上移
        res_up_edge = client.post(f"/api/watchlist/member/move?group_id={group_id}&ticker=2330&direction=up")
        assert res_up_edge.json()["success"] is False

        # 下移 2330 (與 2454 交換)
        res_down = client.post(f"/api/watchlist/member/move?group_id={group_id}&ticker=2330&direction=down")
        assert res_down.json()["success"] is True

        # 驗證順序已互換
        res_list = client.get("/api/watchlist")
        target_g = next((g for g in res_list.json() if g["group_id"] == group_id), None)
        assert target_g["stocks"][0]["ticker"] == "2454"
        assert target_g["stocks"][1]["ticker"] == "2330"
    finally:
        client.delete(f"/api/watchlist/group/{group_id}")


def test_watchlist_member_note_and_remove():
    """驗證個股研究筆記更新與移出功能"""
    res = client.post("/api/watchlist/group/create?name=筆記測試群組")
    group_id = res.json()["group_id"]

    try:
        client.post(f"/api/watchlist/add?group_id={group_id}&ticker=2881")
        
        # 更新筆記
        res_note = client.post(
            f"/api/watchlist/member/note?group_id={group_id}&ticker=2881",
            json={"note": "金融獲利龍頭，殖利率穩定"}
        )
        assert res_note.status_code == 200
        assert res_note.json()["success"] is True

        # 驗證筆記更新生效
        res_list = client.get("/api/watchlist")
        target_g = next((g for g in res_list.json() if g["group_id"] == group_id), None)
        assert len(target_g["stocks"]) >= 1
        assert target_g["stocks"][0]["note"] == "金融獲利龍頭，殖利率穩定"

        # 移出標的
        res_rem = client.post(f"/api/watchlist/member/remove?group_id={group_id}&ticker=2881")
        assert res_rem.status_code == 200
        assert res_rem.json()["success"] is True

        res_check = client.get("/api/watchlist")
        target_g_empty = next((g for g in res_check.json() if g["group_id"] == group_id), None)
        assert len(target_g_empty["stocks"]) == 0
    finally:
        client.delete(f"/api/watchlist/group/{group_id}")


def test_better_alternatives_service_and_api(init_db):
    """驗證規格書 7.2 出場條件 3：有更好的選擇比對服務與端點"""
    db = init_db
    # 測試服務函式
    result = find_better_alternatives(db, ticker="2330")
    assert result["success"] is True
    assert "target_stock" in result
    assert "has_better_choices" in result
    assert "advice" in result
    assert "better_candidates" in result

    # 測試 API 端點
    res = client.get("/api/watchlist/better-alternatives?ticker=2330")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["target_stock"]["ticker"] == "2330"
    assert "current_price" in data["target_stock"]
    assert "zone_name_zh" in data["target_stock"]

    if data["has_better_choices"]:
        cand = data["better_candidates"][0]
        assert "ticker" in cand
        assert "company_name" in cand
        assert "cheap_price" in cand
        assert "margin_pct" in cand
        assert "lights" in cand
