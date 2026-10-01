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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式啟動與關閉生命週期管理"""
    init_db()
    db = SessionLocal()
    try:
        seed_database_fixtures(db)
    finally:
        db.close()
    yield

app = FastAPI(
    title=SETTINGS.APP_NAME,
    version=SETTINGS.APP_VERSION,
    description="台股價值投資選股系統 - 炭黑帳本高對比 UI",
    lifespan=lifespan
)

# 掛載 API 路由
app.include_router(api_router, prefix="/api")

# 設定模板目錄
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
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
            "theme": SETTINGS.THEME_COLORS
        }
    )
