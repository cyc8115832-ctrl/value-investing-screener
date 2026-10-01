"""
測試生產部署、健康檢查端點與外部市場資料適配器 (tests/test_deployment_and_adapters.py)
涵蓋：
1. 容器健康檢查端點 (GET /health 與 GET /api/health)
2. 系統運維狀態端點 (GET /api/system/status)
3. 外部台股市場資料適配器 (ExternalMarketAdapter) 之快取與降級機制
4. 生產環境部署設定檔 (Dockerfile, docker-compose.yml) 完整性驗證
"""

import os
import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.web.app import app
from src.data.external_market_source import ExternalMarketAdapter

client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------- 1. 容器健康檢查與狀態端點測試 ----------------
def test_root_health_check_endpoint():
    """驗證 Docker 快速健康檢查端點 /health"""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "app" in data


def test_api_health_check_detailed():
    """驗證 API 層級詳細健檢報告 /api/health"""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "healthy"
    assert "database" in data
    assert data["database"]["status"] == "connected"
    assert data["database"]["total_stocks"] > 0
    assert "latest_price_date" in data["database"]
    assert "scheduler" in data
    assert "market_adapter" in data


def test_api_system_status_endpoint():
    """驗證系統環境與各項統計指標報告 /api/system/status"""
    res = client.get("/api/system/status")
    assert res.status_code == 200
    data = res.json()

    assert "system" in data
    assert "statistics" in data
    assert "market_source" in data

    stats = data["statistics"]
    assert "universe_total_stocks" in stats
    assert "custom_stocks_count" in stats
    assert "watchlist_items_count" in stats
    assert "active_line_subscribers" in stats


# ---------------- 2. 外部台股市場資料適配器測試 ----------------
def test_external_market_adapter_cache_mechanism():
    """驗證適配器本地 TTL 快取寫入、命中與過期"""
    adapter = ExternalMarketAdapter(cache_ttl_seconds=1)
    
    # 測試寫入與讀取快取
    adapter._set_to_cache("test_key", {"val": 1234})
    cached = adapter._get_from_cache("test_key")
    assert cached is not None
    assert cached["val"] == 1234

    # 模擬逾時過期
    time.sleep(1.1)
    expired = adapter._get_from_cache("test_key")
    assert expired is None


def test_external_market_adapter_fallback():
    """驗證無 Token 或外部請求失敗時之自動降級安全機制"""
    # 指定無效 URL 測試例外捕獲與優雅降級
    adapter = ExternalMarketAdapter(api_token="", timeout_seconds=1)
    adapter.base_url = "https://invalid-host-for-testing.local/api"

    # 呼叫時絕不崩潰 (Zero Crash Guarantee)
    res = adapter.fetch_daily_price("2330")
    assert isinstance(res, list)

    inst_res = adapter.fetch_institutional_investors("2330")
    assert isinstance(inst_res, list)


def test_external_market_adapter_health():
    """驗證適配器健康狀態報告"""
    adapter = ExternalMarketAdapter(api_token="test_token_123")
    h = adapter.get_market_health()
    assert h["status"] == "ready"
    assert h["api_token_configured"] is True
    assert "cache_ttl_seconds" in h


# ---------------- 3. 生產環境部署設定檔完整性測試 ----------------
def test_dockerfile_and_compose_exist_and_valid():
    """驗證 Dockerfile 與 docker-compose.yml 符合生產規範"""
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    dockerignore_path = PROJECT_ROOT / ".dockerignore"
    start_bat_path = PROJECT_ROOT / "scripts" / "start.bat"
    start_ps1_path = PROJECT_ROOT / "scripts" / "start.ps1"

    assert dockerfile_path.exists(), "Dockerfile 必須存在"
    assert compose_path.exists(), "docker-compose.yml 必須存在"
    assert dockerignore_path.exists(), ".dockerignore 必須存在"
    assert start_bat_path.exists(), "scripts/start.bat 必須存在"
    assert start_ps1_path.exists(), "scripts/start.ps1 必須存在"

    df_content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in df_content
    assert "HEALTHCHECK" in df_content
    assert "appuser" in df_content  # 非 root 安全要求

    compose_content = compose_path.read_text(encoding="utf-8")
    assert "value_investing_app" in compose_content
    assert "healthcheck" in compose_content
    assert "./data:/app/data" in compose_content  # 持久化 Volume
