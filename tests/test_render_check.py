import hashlib
import json
from pathlib import Path

from PIL import Image
from render_check import render

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preview_uses_saved_basemap_and_never_changes_inputs(tmp_path, monkeypatch):
    import requests
    import urllib.request
    import socket
    def fail(*args, **kwargs):
        raise AssertionError("Preview attempted network access")
    monkeypatch.setattr(requests, "get", fail)
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    inputs = [ROOT / name for name in ("assets/basemap.png", "assets/basemap.json",
                                       "data/stations.json", "data/facilities.json")]
    before = [digest(path) for path in inputs]
    target = tmp_path / "check.png"
    result = render(ROOT, target)
    with Image.open(target) as image:
        assert image.size == (1240, 940)
        assert image.format == "PNG"
    assert result["offmap"] == []
    assert sum(result["counts"].values()) == 15
    assert before == [digest(path) for path in inputs]


def test_candidates_preserve_api_points_and_do_not_infer_auxiliary_positions():
    config = json.loads((ROOT / "data/stations.json").read_text(encoding="utf-8"))
    facilities = json.loads((ROOT / "data/facilities.json").read_text(encoding="utf-8"))["facilities"]
    for entry in config["stations"] + facilities:
        if entry["coord_status"] == "candidate":
            raw = json.loads((ROOT / entry["coord_source"]).read_text(encoding="utf-8"))
            assert len(raw["response"]) == 1
            assert [entry["lon"], entry["lat"]] == raw["response"][0]["geometry"]["coordinates"]
        if entry["id"] in ("inba_average", "yoshitaka_aux", "usui_aux"):
            assert entry["lat"] is None and entry["lon"] is None
            assert entry["map_visible"] is False
    assert sorted(s["map_number"] for s in config["stations"] if s["map_visible"]) == list(range(1, 9))

def test_confirmed_locations_follow_user_approval_and_pass_card_guard():
    from map_geometry import confirmed_card_pixel
    config = json.loads((ROOT / "data/stations.json").read_text(encoding="utf-8"))
    facilities = json.loads((ROOT / "data/facilities.json").read_text(encoding="utf-8"))["facilities"]
    approval = json.loads((ROOT / "data/coordinate_approval.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "assets/basemap.json").read_text(encoding="utf-8"))
    locations = [e for e in config["stations"] + facilities if e.get("map_visible")]
    assert len(locations) == 15
    for entry in locations:
        assert entry["coord_status"] == "confirmed"
        confirmed_card_pixel(entry, meta)
        label = str(entry.get("map_number", entry.get("check_label")))
        if label in approval["corrections"]:
            assert [entry["lat"], entry["lon"]] == approval["corrections"][label]
        else:
            raw = json.loads((ROOT / entry["coord_source"]).read_text(encoding="utf-8"))
            assert [entry["lon"], entry["lat"]] == raw["response"][0]["geometry"]["coordinates"]
