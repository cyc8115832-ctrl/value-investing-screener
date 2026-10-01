"""
測試 V3.0 AI 價值研究員與深度量化分析模組 (tests/test_v3_ai_analyst.py)
涵蓋：
1. 葛林布雷神奇公式計算引擎 (magic_formula.py)
   - 資本報酬率 (ROC) 與盈餘殖利率 (EY)
   - 金融股排除保護與異常數值防呆
2. 現金流品質與合約負債動能引擎 (cashflow_deep.py)
   - 自由現金流覆蓋率 (FCF/NI)
   - 合約負債 (客戶預收款) 季增率與在手訂單能見度
   - 資本支出營收比與擴產週期判定
3. AI 價值研究員深度個股分析引擎 (ai_analyst.py)
   - 結構化三大維度分析（亮點、拐點、風險與護城河防守）
   - 金融法規合規宣告與無指令性詞彙檢核
4. FastAPI RESTful 端點測試
   - GET /api/stocks/{ticker}/magic-formula
   - GET /api/stocks/{ticker}/cashflow-deep
   - GET /api/stocks/{ticker}/ai-analyst
   - GET /api/stocks/{ticker} 整合欄位驗證
"""

import pytest
from fastapi.testclient import TestClient

from src.engines.magic_formula import calculate_magic_formula_metrics
from src.engines.cashflow_deep import analyze_cashflow_quality_and_contract_liabilities
from src.engines.ai_analyst import generate_ai_research_report
from src.web.app import app

client = TestClient(app)


# ---------------- 1. 葛林布雷神奇公式測試 ----------------
def test_magic_formula_regular_stock():
    """驗證一般成長/製造業的神奇公式 ROC 與 EY 計算"""
    # 假設營益 EBIT 1200、市值 10000、流動資產 4000、流動負債 1500、固定資產 PPE 3500、總負債 1500
    # 投入資本 = (4000 - 1500) + 3500 = 6000
    # ROC = 1200 / 6000 = 20.0%
    # EV = 10000 + 1500 = 11500
    # EY = 1200 / 11500 = 10.43%
    res = calculate_magic_formula_metrics(
        operating_income=1200.0,
        market_cap=10000.0,
        current_assets=4000.0,
        current_liabilities=1500.0,
        net_ppe=3500.0,
        total_debt=1500.0,
        cash_and_equivalents=0.0,
        is_financial=False,
        is_cyclical=False
    )

    assert res["applicable"] is True
    assert res["roc_pct"] == 20.0
    assert res["ey_pct"] == 10.43
    assert 0 <= res["magic_score"] <= 100
    assert "雙優" in res["quality_tag"] or "穩健" in res["quality_tag"]
    assert "資本報酬率" in res["explanation"]


def test_magic_formula_financial_stock_exclusion():
    """驗證金融股排除原則：資本結構特殊不適用神奇公式"""
    res = calculate_magic_formula_metrics(
        operating_income=5000.0,
        market_cap=50000.0,
        current_assets=100000.0,
        current_liabilities=90000.0,
        net_ppe=5000.0,
        is_financial=True,
        is_cyclical=False
    )

    assert res["applicable"] is False
    assert "金融" in res["reason"]
    assert res["roc_pct"] is None
    assert res["ey_pct"] is None
    assert res["magic_score"] == 0.0


def test_magic_formula_edge_cases():
    """驗證負營業利益與異常資產之防呆機制"""
    # 虧損企業 (EBIT < 0)
    res_loss = calculate_magic_formula_metrics(
        operating_income=-500.0,
        market_cap=5000.0,
        current_assets=2000.0,
        current_liabilities=1000.0,
        net_ppe=2000.0,
        is_financial=False,
        is_cyclical=False
    )
    assert res_loss["applicable"] is True
    assert res_loss["roc_pct"] < 0
    assert res_loss["ey_pct"] < 0
    assert res_loss["magic_score"] == 0.0

    # 零投入資本且無總資產 (Invested Capital <= 0)
    res_zero_cap = calculate_magic_formula_metrics(
        operating_income=100.0,
        market_cap=1000.0,
        total_assets=0.0,
        current_assets=500.0,
        current_liabilities=1000.0,
        net_ppe=200.0,  # 500 - 1000 + 200 = -300
        is_financial=False,
        is_cyclical=False
    )
    assert res_zero_cap["applicable"] is True
    assert res_zero_cap["roc_pct"] is None


# ---------------- 2. 現金流品質與合約負債動能測試 ----------------
def test_cashflow_quality_and_contract_liabilities():
    """驗證自由現金流覆蓋率 (FCF/NI) 與合約負債 QoQ 趨勢分析"""
    cl_history = [
        {"quarter": "2025Q3", "contract_liabilities": 500.0},
        {"quarter": "2025Q4", "contract_liabilities": 600.0}
    ]
    # 淨利 1000，營業現金流 1500，資本支出 -400，自由現金流 1100，營收 5000
    # FCF/NI = 1100 / 1000 = 1.1x
    # CapEx/Rev = 400 / 5000 = 8.0%
    # 合約負債 QoQ = (600 - 500) / 500 = +20.0%
    res = analyze_cashflow_quality_and_contract_liabilities(
        net_income_ttm=1000.0,
        operating_cf_ttm=1500.0,
        capex_ttm=-400.0,
        fcf_ttm=1100.0,
        revenue_ttm=5000.0,
        contract_liabilities_history=cl_history,
        is_financial=False
    )

    assert res["applicable"] is True
    assert res["fcf_coverage"] == 1.1
    assert "現金轉化率" in res["fcf_quality_label"] or "真金白銀" in res["fcf_quality_label"]
    assert res["capex_ratio_pct"] == 8.0
    assert "常態維護" in res["capex_cycle_label"] or "穩健" in res["capex_cycle_label"]
    cl = res["contract_liabilities"]
    assert cl["has_data"] is True
    assert cl["qoq_growth_pct"] == 20.0
    assert "強勁" in cl["trend_label"] or "爆發成長" in cl["trend_label"]


def test_cashflow_deep_financial_stock():
    """驗證金融股排除現金流與合約負債分析"""
    res = analyze_cashflow_quality_and_contract_liabilities(
        net_income_ttm=2000.0,
        operating_cf_ttm=3000.0,
        capex_ttm=-100.0,
        fcf_ttm=2900.0,
        revenue_ttm=10000.0,
        contract_liabilities_history=[],
        is_financial=True
    )
    assert res["applicable"] is False
    assert "金融" in res["reason"]


def test_cashflow_deep_contract_liabilities_empty():
    """驗證無合約負債歷史資料時之容錯性"""
    res = analyze_cashflow_quality_and_contract_liabilities(
        net_income_ttm=1000.0,
        operating_cf_ttm=800.0,
        capex_ttm=-200.0,
        fcf_ttm=600.0,
        revenue_ttm=4000.0,
        contract_liabilities_history=None,
        is_financial=False
    )
    assert res["applicable"] is True
    assert res["fcf_coverage"] == 0.6
    assert res["contract_liabilities"]["has_data"] is False


# ---------------- 3. AI 價值研究員深度個股分析引擎測試 ----------------
def test_ai_research_report_generation_and_compliance():
    """驗證 AI 價值研究員之結構化三大維度、免責宣告與合規檢查"""
    stock_info = {
        "ticker": "2330",
        "company_name": "台積電",
        "industry": "半導體業",
        "is_cyclical": False,
        "sector_type": "semiconductor"
    }
    price_info = {"current_price": 950.0}
    good_company_info = {
        "overall": "good",
        "lights": {
            "revenue": "green",
            "eps": "green",
            "margin": "green",
            "efficiency": "green",
            "cashflow": "green",
            "growth": "green"
        },
        "reasons": ["近4季ROE達標", "毛利率逐季走高"],
        "composite_score": 92.5
    }
    eps_info = {
        "estimated_eps_base": 42.0,
        "actual_eps": 38.0,
        "cumulative_rev_yoy_g": 0.22
    }
    river_info = {
        "current_zone": "cheap",
        "zone_name_zh": "便宜價",
        "metric": "pe"
    }
    cashflow_info = {
        "applicable": True,
        "fcf_coverage": 1.15,
        "capex_ratio_pct": 38.5,
        "contract_liabilities": {
            "has_data": True,
            "qoq_growth_pct": 14.5,
            "trend_label": "穩健成長"
        }
    }

    report = generate_ai_research_report(
        stock_info=stock_info,
        price_info=price_info,
        good_company_info=good_company_info,
        eps_info=eps_info,
        river_info=river_info,
        cashflow_info=cashflow_info
    )

    # 驗證必要欄位
    assert report["ticker"] == "2330"
    assert report["company_name"] == "台積電"
    assert "generated_at" in report
    assert "compliance_disclaimer" in report
    assert "executive_summary" in report
    assert "report_sections" in report

    # 驗證三大結構面向
    sections = report["report_sections"]
    assert "core_investment_highlights" in sections
    assert "operational_inflection_points" in sections
    assert "downside_risks_and_moat_defense" in sections

    hlights = sections["core_investment_highlights"]
    assert len(hlights["items"]) >= 1
    assert "資料來源" in hlights or "data_source" in hlights

    inflection = sections["operational_inflection_points"]
    assert len(inflection["items"]) >= 1

    risks = sections["downside_risks_and_moat_defense"]
    assert len(risks["items"]) >= 1

    # 驗證金融合規：禁止出現誘導性、指令性買賣術語
    exec_text = report["executive_summary"]
    disclaimer = report["compliance_disclaimer"]
    assert "個人價值投資研究參考" in disclaimer or "不構成任何" in disclaimer
    for prohibited in ["保證獲利", "必買", "保證上漲", "無風險投資"]:
        assert prohibited not in exec_text
        assert prohibited not in disclaimer


# ---------------- 4. FastAPI RESTful API 端點測試 ----------------
def test_api_stock_detail_v3_fields():
    """驗證個股詳情 API 正確注入 magic_formula, cashflow_deep 與 ai_analyst 欄位"""
    res = client.get("/api/stocks/2330")
    assert res.status_code == 200
    data = res.json()

    assert "magic_formula" in data
    assert "cashflow_deep" in data
    assert "ai_analyst" in data

    # 驗證 magic_formula 欄位存在
    mf = data["magic_formula"]
    assert "applicable" in mf
    assert "roc_pct" in mf
    assert "ey_pct" in mf
    assert "magic_score" in mf

    # 驗證 cashflow_deep 欄位存在
    cd = data["cashflow_deep"]
    assert "applicable" in cd
    assert "fcf_coverage" in cd
    assert "contract_liabilities" in cd

    # 驗證 ai_analyst 欄位存在
    ai = data["ai_analyst"]
    assert "executive_summary" in ai
    assert "report_sections" in ai


def test_api_magic_formula_endpoint():
    """驗證獨立神奇公式 API 端點"""
    res = client.get("/api/stocks/2330/magic-formula")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "2330"
    assert data["applicable"] is True
    assert "roc_pct" in data
    assert "ey_pct" in data


def test_api_cashflow_deep_endpoint():
    """驗證獨立現金流深化分析 API 端點"""
    res = client.get("/api/stocks/2330/cashflow-deep")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "2330"
    assert "fcf_coverage" in data
    assert "contract_liabilities" in data


def test_api_ai_analyst_endpoint():
    """驗證獨立 AI 價值研究員報告 API 端點"""
    res = client.get("/api/stocks/2330/ai-analyst")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "2330"
    assert "executive_summary" in data
    assert "report_sections" in data


def test_api_financial_stock_magic_formula_and_cashflow():
    """驗證金融股 (如 2881) 神奇公式與現金流排除機制在 API 端運作正常"""
    res = client.get("/api/stocks/2881/magic-formula")
    assert res.status_code == 200
    data = res.json()
    assert data["applicable"] is False
    assert "金融" in data["reason"]
