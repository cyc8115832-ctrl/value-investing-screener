"""整合測試僅使用 D 槽隔離示範資料庫，禁止覆寫正式資料。"""
import os
from pathlib import Path
import tempfile
import pytest

_workspace = Path(__file__).resolve().parent.parent
(_workspace / "data").mkdir(exist_ok=True)
_test_directory = tempfile.TemporaryDirectory(prefix="tests-", dir=_workspace / "data")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_test_directory.name) / "isolated.db")
os.environ["DEMO_MODE"] = "true"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = ""
os.environ["LINE_CHANNEL_SECRET"] = ""


@pytest.fixture(scope="session", autouse=True)
def isolated_market_database():
    from src.database.session import SessionLocal, init_db
    from src.data.mock_fixtures import seed_database_fixtures
    init_db()
    with SessionLocal() as db:
        seed_database_fixtures(db)
    yield
    from src.database.session import engine
    engine.dispose()
    _test_directory.cleanup()
