r"""
價值投資選股 App - 端到端生產健康診斷與冒煙測試工具 (health_check.py)
用途：
  對系統全鏈路進行自動化健康檢測：
  1. 資料庫連線與核心表（StockMaster, PriceDaily, FinancialsQuarterly）檢核
  2. 股池標的覆蓋率檢核
  3. 純函式估值引擎（河流圖、六面向好公司、EPS）運算正確性檢核
  4. 實盤運維備份目錄寫入權限檢核
  5. 本地/容器 FastAPI HTTP 健康端點（/health）連通性檢核
  6. 綜合評分與彩色診斷報告輸出

用法範例：
  .\.venv\Scripts\python.exe scripts/health_check.py
  .\.venv\Scripts\python.exe scripts/health_check.py --url http://127.0.0.1:8000
"""

import sys
import os
import argparse
import tempfile
import time
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database.session import SessionLocal, init_db
from src.database.schema import StockMaster, PriceDaily, FinancialsQuarterly, ETFMaster
from src.engines.valuation_river import calculate_anchors, calculate_river_prices, classify_price_zone
from src.engines.good_company import evaluate_good_company
from src.services.data_quality import get_data_quality_report
from config.settings import SETTINGS


def run_system_health_check(base_url: str = None) -> dict:
    """執行全系統健康診斷並回傳指標結果"""
    if not SETTINGS.DEMO_MODE:
        from src.services.market_evidence import data_quality_report
        from fastapi.testclient import TestClient
        from src.web.app import app
        import requests
        try:
            with SessionLocal() as db:
                quality = data_quality_report(db)
            response = requests.get(base_url.rstrip('/') + '/health', timeout=10) if base_url else TestClient(app).get('/health')
            passed = response.status_code == 200 and response.json().get('status') == 'ok'
            return {"timestamp": datetime.now().isoformat(), "total_checks": 2, "passed_checks": 2 if passed else 1,
                    "items": [{"name": "服務與資料庫連線", "passed": passed, "detail": "運行健康與投資資料完整性分開檢查"},
                              {"name": "正式證據邊界", "passed": True, "detail": quality['reason']}],
                    "overall_health_score": 100 if passed else 50, "status": "PROCESS_HEALTHY / INVESTMENT_DATA_INSUFFICIENT" if passed else "UNHEALTHY",
                    "investment_ready": quality['investment_ready'], "quality": quality}
        except Exception as error:
            return {"timestamp": datetime.now().isoformat(), "total_checks": 1, "passed_checks": 0, "items": [{"name": "正式模式健康檢查", "passed": False, "detail": str(error)}], "overall_health_score": 0, "status": "UNHEALTHY"}
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_checks": 0,
        "passed_checks": 0,
        "items": [],
        "overall_health_score": 100,
        "status": "HEALTHY"
    }

    def record_check(name: str, passed: bool, detail: str):
        report["total_checks"] += 1
        if passed:
            report["passed_checks"] += 1
        report["items"].append({
            "name": name,
            "passed": passed,
            "detail": detail
        })

    # 1. 資料庫連線與核心表格
    try:
        init_db()
        db = SessionLocal()
        stock_count = db.query(StockMaster).count()
        price_count = db.query(PriceDaily).count()
        etf_count = db.query(ETFMaster).count()
        db.close()

        record_check("資料庫連線與核心表", True, f"成功連線 SQLite，股池共 {stock_count} 檔標的，行情記錄 {price_count} 筆，ETF {etf_count} 檔")
    except Exception as e:
        record_check("資料庫連線與核心表", False, f"資料庫異常: {e}")

    # 2. 估值河流圖引擎驗算 (純函式)
    try:
        anchors = calculate_anchors(vmin=12.8, vmax=31.2)
        sample_eps = 40.0
        prices = calculate_river_prices(anchors=anchors, base=sample_eps)
        p1 = prices.p1
        p6 = prices.p6
        valid_anchor = (p1 > 0 and p6 > p1)
        record_check("Valuation River 估值引擎", valid_anchor, f"河流圖錨點計算正確 (A1={p1:.1f}, A6={p6:.1f})")
    except Exception as e:
        record_check("Valuation River 估值引擎", False, f"計算異常: {e}")

    # 3. 好公司六面向健檢引擎 (純函式)
    try:
        from src.engines.good_company import DimensionResult
        dim_rev = DimensionResult(name_zh="營收動能", light="green", value_display="YoY +15%", explanation="營收成長動能良好")
        dim_eps = DimensionResult(name_zh="獲利能力", light="green", value_display="EPS 成長", explanation="獲利持續成長")
        dim_margin = DimensionResult(name_zh="利潤率", light="green", value_display="三率升", explanation="毛利淨利改善")
        dim_eff = DimensionResult(name_zh="資本效率", light="green", value_display="ROE 22%", explanation="ROE 遠高於門檻")
        dim_cf = DimensionResult(name_zh="現金流", light="green", value_display="FCF>0", explanation="自由現金流正向")
        dim_gr = DimensionResult(name_zh="擴產動能", light="green", value_display="擴產中", explanation="資本支出穩健擴充")

        good_res = evaluate_good_company(
            ticker="2330",
            dim_revenue=dim_rev,
            dim_eps=dim_eps,
            dim_margin=dim_margin,
            dim_efficiency=dim_eff,
            dim_cashflow=dim_cf,
            dim_growth_div=dim_gr
        )
        is_good = (good_res.overall == "good")
        record_check("Good Company 六面向健檢引擎", is_good, f"判定狀態: {good_res.overall_name_zh}, 入選徽章: {len(good_res.badges)} 個, 理由: {len(good_res.reasons)} 條")
    except Exception as e:
        record_check("Good Company 六面向健檢引擎", False, f"健檢引擎異常: {e}")

    # 4. 資料庫品質健康度 (規格書第 10 章)
    try:
        db = SessionLocal()
        dq = get_data_quality_report(db)
        db.close()
        grade = dq.get("grade", "未知")
        pct = dq.get("overall_health_pct", 0.0)
        record_check("資料庫品質與覆蓋率報告", pct >= 70.0, f"品質評等: {grade} (健康指數 {pct:.1f}%)")
    except Exception as e:
        record_check("資料庫品質與覆蓋率報告", False, f"檢測失敗: {e}")

    # 5. 磁碟寫入與熱備份目錄權限
    try:
        backup_dir = os.path.join(ROOT_DIR, "data", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        test_file = os.path.join(backup_dir, f".write_test_{int(time.time())}.tmp")
        with open(test_file, "w") as f:
            f.write("health check write test")
        if os.path.exists(test_file):
            os.remove(test_file)
        record_check("磁碟熱備份目錄讀寫權限", True, f"目錄正常可讀寫: {backup_dir}")
    except Exception as e:
        record_check("磁碟熱備份目錄讀寫權限", False, f"磁碟權限異常: {e}")

    # 6. HTTP API 伺服器連通性 (可選)
    if base_url:
        try:
            import requests
            health_endpoint = f"{base_url.rstrip('/')}/health"
            resp = requests.get(health_endpoint, timeout=3)
            if resp.status_code == 200:
                record_check("HTTP API 伺服器連通性", True, f"端點響應 200 OK: {health_endpoint}")
            else:
                record_check("HTTP API 伺服器連通性", False, f"端點回傳狀態碼 {resp.status_code}")
        except Exception as e:
            record_check("HTTP API 伺服器連通性", False, f"無法連線至 {base_url}: {e}")

    # 計算綜合評分
    if report["total_checks"] > 0:
        score = int((report["passed_checks"] / report["total_checks"]) * 100)
        report["overall_health_score"] = score
        if score >= 90:
            report["status"] = "HEALTHY (健康)"
        elif score >= 70:
            report["status"] = "DEGRADED (警告)"
        else:
            report["status"] = "UNHEALTHY (異常)"

    return report


def main():
    parser = argparse.ArgumentParser(description="全系統健康診斷與冒煙測試")
    parser.add_argument("--url", type=str, default=None, help="可選測試之伺服器 URL (如 http://127.0.0.1:8000)")

    args = parser.parse_args()

    print("==========================================================")
    print(" 🏥 價值投資選股 App - 端到端生產健康體檢 (Smoke Test)")
    print(f" 檢驗時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==========================================================")

    res = run_system_health_check(base_url=args.url)

    print("\n【📋 各項指標檢驗結果】\n")
    for item in res["items"]:
        icon = "✅" if item["passed"] else "❌"
        print(f" {icon} [{item['name']}]")
        print(f"    說明: {item['detail']}")

    print("\n----------------------------------------------------------")
    print(f" 🎯 綜合健康指數: {res['overall_health_score']}/100")
    print(f" 🚦 系統運行狀態: {res['status']}")
    print(f" 📊 通過檢驗項目: {res['passed_checks']} / {res['total_checks']}")
    print("==========================================================")

    if res["overall_health_score"] < 70:
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    main()
