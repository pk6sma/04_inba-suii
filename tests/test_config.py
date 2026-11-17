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
    from PIL import Image
    from collections import Counter
    codes = json.loads((ROOT / "data/facility_codes.json").read_text(encoding="utf-8"))
    colors = {(217,217,217): "故障・欠測", (112,173,71): "停止", (255,0,0): "排水中"}
    icons = list((ROOT / "assets/icons").glob("*.gif"))
    assert set(codes) == {p.name for p in icons}
    for p in icons:
        with Image.open(p) as image:
            pixels = Counter(rgb[:3] for rgb in image.convert("RGBA").getdata() if rgb[3])
        assert codes[p.name] == colors[pixels.most_common(1)[0][0]]
