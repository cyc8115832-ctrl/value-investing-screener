import pytest
from src.data.historical_statements import balance_values


def test_balance_sheet_shares_outstanding_strictly_none():
    """
    T05 鐵律測試：
    資產負債表解析嚴格禁止由股本（capital_amount）推算股數（shares_outstanding）。
    shares_outstanding 必須維持 None，未經驗證官方每股資料前不可自行衍生。
    """
    mock_table = [
        ["期別", "2025年6月30日", "2024年12月31日", "2024年6月30日"],
        ["代號", "金額", "金額", "金額"],
        ["資產總計", "1,000", "1,000", "1,000"],
        ["負債總計", "400", "400", "400"],
        ["權益總計", "600", "600", "600"],
        ["歸屬於母公司業主之權益合計", "600", "600", "600"],
        ["股本合計", "200", "200", "200"],
        ["流動資產合計", "300", "300", "300"],
        ["流動負債合計", "150", "150", "150"],
    ]
    vals = balance_values(mock_table, 1)
    assert vals["capital_amount"] == 200
    assert vals["shares_outstanding"] is None
    assert vals["identity_residual"] == 0
