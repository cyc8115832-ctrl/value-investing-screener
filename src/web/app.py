"""
價值投資選股 App - FastAPI 主應用程式 (app.py)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.web.api.routes import api_router
from src.database.session import init_db, SessionLocal
from src.data.mock_fixtures import seed_database_fixtures
from config.settings import SETTINGS

from src.services.scheduler import GLOBAL_SCHEDULER

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式啟動與關閉生命週期管理"""
    init_db()
    if SETTINGS.DEMO_MODE:
        db = SessionLocal()
        try:
            from src.database.schema import StockMaster
            if db.query(StockMaster).count() == 0:
                seed_database_fixtures(db)
        finally:
            db.close()
    
    # 啟動 15:30 盤後重算流水線與 18:30 LINE 定時推播背景排程
    if SETTINGS.ENABLE_SCHEDULER and not SETTINGS.DEMO_MODE:
        GLOBAL_SCHEDULER.start()
    yield
    if SETTINGS.ENABLE_SCHEDULER and not SETTINGS.DEMO_MODE:
        GLOBAL_SCHEDULER.stop()


app = FastAPI(
    title=SETTINGS.APP_NAME,
    version=SETTINGS.APP_VERSION,
    description="台股價值投資選股系統 - 炭黑帳本高對比 UI",
    lifespan=lifespan
)

# 掛載 API 路由
from src.web.api.verified_routes import verified_router, enforce_evidence_boundary
app.middleware("http")(enforce_evidence_boundary)
if not SETTINGS.DEMO_MODE:
    app.include_router(verified_router, prefix="/api")
app.include_router(api_router, prefix="/api")

# 設定模板與靜態檔案目錄
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    """主介面單頁應用程式 (Single-Page Application)"""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": SETTINGS.APP_NAME,
            "version": SETTINGS.APP_VERSION,
            "demo_mode": SETTINGS.DEMO_MODE,
            "theme": SETTINGS.THEME_COLORS
        }
    )


@app.get("/health")
def root_health():
    """容器快速健康檢查端點 (Container Healthcheck)"""
    return {
        "status": "ok",
        "app": SETTINGS.APP_NAME,
        "version": SETTINGS.APP_VERSION
    }

