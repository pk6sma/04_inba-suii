import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_config():
    stations = json.loads((ROOT / "data/stations.json").read_text(encoding="utf-8"))["stations"]
    thresholds = json.loads((ROOT / "data/thresholds.json").read_text(encoding="utf-8"))
    assert len(stations) == 11
    assert len({s["id"] for s in stations}) == 11
    assert [s["order"] for s in stations if s["source"] == "mizukan"] == list(range(1, 9))
    assert sum(bool(t and any(b["value"] is not None for b in t.get("boundaries", []))) for t in thresholds.values()) == 3
    assert thresholds["kitainba"]["evac_guide"]["level4"] == 2.65
    assert json.loads((ROOT / "data/facility_codes.json").read_text()) == {}
