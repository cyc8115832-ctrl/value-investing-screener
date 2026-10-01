"""
價值投資選股 App - 現金流品質與合約負債動能引擎 (cashflow_deep.py)
依據技術規格書 V1.7 第 18 章（V2.0 擴充）：
- 自由現金流覆蓋率 (FCF / 稅後淨利)：檢視帳面獲利轉化為真實現金的能力
- 自由現金流佔營收比重 (FCF Margin)：檢驗企業造血體質
- 合約負債（預收貨款）動能：季增率 (QoQ)、年增率 (YoY) 與未來訂單能見度分析
- 資本支出 (CapEx) 週期分析：維護型支出 vs 擴張型支出 (CapEx / 營收比重)
"""

from typing import Dict, Any, List, Optional


def analyze_cashflow_quality_and_contract_liabilities(
    net_income_ttm: float,
    operating_cf_ttm: float,
    capex_ttm: float,
    fcf_ttm: float,
    revenue_ttm: float,
    contract_liabilities_history: Optional[List[Dict[str, Any]]] = None,
    is_financial: bool = False
) -> Dict[str, Any]:
    """
    純函式分析個股現金流品質與合約負債動能
    """
    if is_financial:
        return {
            "applicable": False,
            "quality_tag": "金融股不適用",
            "reason": "金融保險業不具備一般製造業之營業現金流、自由現金流與合約負債指標定義。"
        }

    # 1. 自由現金流覆蓋率 FCF / Net Income
    fcf_coverage = None
    if net_income_ttm > 0:
        fcf_coverage = round(fcf_ttm / net_income_ttm, 2)
        if fcf_coverage >= 1.0:
            fcf_quality_label = "💎 超高現金轉化率 (真金白銀)"
            fcf_status = "excellent"
        elif fcf_coverage >= 0.7:
            fcf_quality_label = "🟢 現金轉化良好"
            fcf_status = "good"
        elif fcf_coverage >= 0.3:
            fcf_quality_label = "🟡 部分盈餘未轉為現金"
            fcf_status = "neutral"
        elif fcf_coverage >= 0.0:
            fcf_quality_label = "🟠 現金覆蓋偏低 (帳款或存貨積累)"
            fcf_status = "warning"
        else:
            fcf_quality_label = "🔴 自由現金流為負 (高度吃緊)"
            fcf_status = "danger"
    else:
        fcf_quality_label = "⚪ 公司處於虧損或持平"
        fcf_status = "neutral"

    # 2. 自由現金流佔營收比 (FCF Margin)
    fcf_margin_pct = round((fcf_ttm / revenue_ttm) * 100.0, 2) if revenue_ttm > 0 else 0.0

    # 3. 資本支出強度 (CapEx / Revenue)
    capex_ratio_pct = round((abs(capex_ttm) / revenue_ttm) * 100.0, 2) if revenue_ttm > 0 else 0.0
    if capex_ratio_pct >= 25.0:
        capex_cycle_label = "🚀 大規模擴產週期 (重資本擴張)"
    elif capex_ratio_pct >= 12.0:
        capex_cycle_label = "⚙️ 積極研發與擴產中"
    elif capex_ratio_pct >= 4.0:
        capex_cycle_label = "🛠️ 常態維護性資本支出"
    else:
        capex_cycle_label = "💡 輕資產營運模式"

    # 4. 合約負債（預收訂金）動能分析
    contract_analysis = {
        "has_data": False,
        "latest_value": 0.0,
        "qoq_growth_pct": None,
        "trend_label": "無合約負債資料",
        "description": "該產業或標的財報無顯著合約負債科目。"
    }

    if contract_liabilities_history and len(contract_liabilities_history) >= 2:
        # 按季度排序
        sorted_cl = sorted(contract_liabilities_history, key=lambda x: str(x.get("quarter", "")))
        latest_cl = float(sorted_cl[-1].get("contract_liabilities", 0.0) or 0.0)
        prev_cl = float(sorted_cl[-2].get("contract_liabilities", 0.0) or 0.0)

        if prev_cl > 0:
            qoq_pct = round(((latest_cl - prev_cl) / prev_cl) * 100.0, 1)
        else:
            qoq_pct = 0.0

        if qoq_pct >= 15.0:
            cl_label = "🔥 預收訂單爆發成長 (強勁訂單在手)"
            cl_status = "strong_growth"
        elif qoq_pct > 0.0:
            cl_label = "🟢 預收訂單溫和墊高"
            cl_status = "mild_growth"
        elif qoq_pct >= -10.0:
            cl_label = "🟡 訂單儲備持平消化"
            cl_status = "flat"
        else:
            cl_label = "🟠 在手訂單加速出貨消耗或縮減"
            cl_status = "contracting"

        contract_analysis = {
            "has_data": True,
            "latest_quarter": sorted_cl[-1].get("quarter", ""),
            "latest_value": latest_cl,
            "previous_quarter": sorted_cl[-2].get("quarter", ""),
            "previous_value": prev_cl,
            "qoq_growth_pct": qoq_pct,
            "trend_label": cl_label,
            "status": cl_status,
            "description": f"最新合約負債 {latest_cl:.1f} 億元，季增 {qoq_pct:+.1f}%，顯示在手訂單與預收客戶款項動能。"
        }
    elif contract_liabilities_history and len(contract_liabilities_history) == 1:
        val = float(contract_liabilities_history[0].get("contract_liabilities", 0.0) or 0.0)
        contract_analysis = {
            "has_data": True,
            "latest_quarter": contract_liabilities_history[0].get("quarter", ""),
            "latest_value": val,
            "qoq_growth_pct": None,
            "trend_label": "合約負債資料單期",
            "description": f"最新合約負債 {val:.1f} 億元。"
        }

    return {
        "applicable": True,
        "fcf_ttm": round(fcf_ttm, 1),
        "operating_cf_ttm": round(operating_cf_ttm, 1),
        "capex_ttm": round(capex_ttm, 1),
        "fcf_coverage": fcf_coverage,
        "fcf_quality_label": fcf_quality_label,
        "fcf_status": fcf_status,
        "fcf_margin_pct": fcf_margin_pct,
        "capex_ratio_pct": capex_ratio_pct,
        "capex_cycle_label": capex_cycle_label,
        "contract_liabilities": contract_analysis,
        "summary": f"{fcf_quality_label}｜{capex_cycle_label}｜{contract_analysis['trend_label']}"
    }
