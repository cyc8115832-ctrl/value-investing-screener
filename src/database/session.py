"""
價值投資選股 App - 資料庫 Session 與連線管理 (session.py)
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import SETTINGS
from src.database.schema import Base

engine = create_engine(
    SETTINGS.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SETTINGS.DATABASE_URL else {},
    echo=SETTINGS.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """建立所有定義之資料表"""
    Base.metadata.create_all(bind=engine)

# 確保資料表自動建立
init_db()

def get_db():
    """FastAPI 依賴注入 Session 產生器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
