import json
import sys
from pathlib import Path
from datetime import datetime

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in tests")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


@pytest.fixture
def config():
    return json.loads((ROOT / "data/stations.json").read_text(encoding="utf-8"))


@pytest.fixture
def thresholds():
    return json.loads((ROOT / "data/thresholds.json").read_text(encoding="utf-8"))


@pytest.fixture
def fixture_data():
    from sources.common import decode_html
    def read(name):
        path = ROOT / "tests/fixtures"
        meta = json.loads((path / f"{name}.meta.json").read_text(encoding="utf-8"))
        html, encoding = decode_html((path / f"{name}.html").read_bytes(), meta["headers"])
        return html, datetime.fromisoformat(meta["saved_at"]), encoding
    return read
