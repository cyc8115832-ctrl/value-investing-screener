"""用實際靜態適配器驗證查詢與儲存，不重寫其演算法。"""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_static_transport_contract():
    node=shutil.which('node')
    if node is None:
        pytest.skip('環境未提供 Node；CI 另設 Node 執行此契約')
    result=subprocess.run([node,'tests/static_adapter_contract.cjs'],cwd=Path(__file__).resolve().parent.parent,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode == 0, result.stderr
