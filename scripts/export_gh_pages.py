"""匯出有證據的 Pages 快照；分檔載入、不冒充即時服務或模擬成功。"""
import json
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config.settings import SETTINGS
from fastapi.testclient import TestClient
from src.web.app import app
from src.database.session import SessionLocal
from src.database.schema import StockMaster

DOCS_DIR = PROJECT_ROOT / "docs"
STATIC_DIR = PROJECT_ROOT / "src" / "web" / "static"


def collect_static_database(client):
    endpoints = ["/api/radar", "/api/screener", "/api/evidence/status", "/api/data-quality/report"]
    routes = {}
    for endpoint in endpoints:
        response = client.get(endpoint)
        response.raise_for_status()
        routes[endpoint] = response.json()
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "routes": routes}


def generate_static_site(output_dir=DOCS_DIR):
    if SETTINGS.DEMO_MODE:
        raise RuntimeError("禁止將示範市場匯出為正式 Pages 資料")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(exist_ok=True)
    with TestClient(app) as client:
        database = collect_static_database(client)
        with SessionLocal() as db:
            tickers = [s.ticker for s in db.query(StockMaster).order_by(StockMaster.ticker).all()]
        for ticker in tickers:
            stock = {}
            for metric in ("auto", "pe", "pb", "ps"):
                response = client.get(f"/api/stocks/{ticker}", params={"metric": metric, "scenario": "base"})
                response.raise_for_status()
                stock[metric] = response.json()
            stock["history"] = {}
            for metric in ("auto", "pe", "pb", "ps"):
                response = client.get(f"/api/evidence/stocks/{ticker}/history", params={"metric": metric, "years": 3})
                response.raise_for_status()
                stock["history"][metric] = response.json()
            (data_dir / f"stock-{ticker}.json").write_text(json.dumps(stock, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # 私人觀察、筆記、LINE 綁定及權杖不進站點快照。
    (data_dir / "global.json").write_text(json.dumps(database, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for item in STATIC_DIR.iterdir():
        if item.is_file():
            shutil.copyfile(item, output_dir / item.name)
    manifest = json.loads((STATIC_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["start_url"] = "./index.html"
    for icon in manifest["icons"]:
        icon["src"] = "./icon.svg"
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    environment = Environment(loader=FileSystemLoader(PROJECT_ROOT / "src/web/templates"), autoescape=select_autoescape(["html"]))
    html = environment.get_template("index.html").render(app_name=SETTINGS.APP_NAME, version=SETTINGS.APP_VERSION, theme=SETTINGS.THEME_COLORS, demo_mode=False)
    html = html.replace('/static/', './')
    asset_version = quote(database["generated_at"], safe="")
    adapter = '<script>window.STATIC_BUILD_TIME=' + json.dumps(database["generated_at"]) + ';</script><script src="./static-adapter.js?snapshot=' + asset_version + '"></script>'
    for asset in ("value-ui.js", "value-ui.css"):
        html = html.replace('./' + asset + '"', './' + asset + '?snapshot=' + asset_version + '"')
    html = html.replace('<script>', adapter + '<script>', 1)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / "snapshot-manifest.json").write_text(json.dumps({"generated_at": database["generated_at"], "tickers": tickers, "mode": "verified", "private_data_exported": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    worker = (STATIC_DIR / "sw.js").read_text(encoding="utf-8").replace("'/static/", "'./").replace("'/'", "'./index.html'")
    worker = worker.replace("value-investing-evidence-v2", "value-investing-evidence-v2-" + database["generated_at"])
    (output_dir / "sw.js").write_text(worker, encoding="utf-8")
    print(f"正式快照：{len(tickers)} 檔；HTML {len(html.encode()) // 1024} KB；{output_dir}")
    return database


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    generate_static_site()
