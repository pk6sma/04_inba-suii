import json
from copy import deepcopy
from pathlib import Path
import pytest
from PIL import Image
from render_card import render, regular_badge, sponsor_visible

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return json.loads((ROOT / "tests/fixtures/latest_regular.json").read_text(encoding="utf-8"))



@pytest.fixture
def approved_px(monkeypatch):
    # Simulate later human approval only in memory. Actual configuration stays candidate.
    import render_card
    original = render_card.read_json
    def read(path):
        value = original(path)
        key = {"stations.json":"stations","facilities.json":"facilities"}.get(Path(path).name)
        if key:
            value = deepcopy(value)
            for e in value[key]:
                if e.get("map_visible"):
                    e["px_status"] = "confirmed"
        return value
    monkeypatch.setattr(render_card,"read_json",read)

def test_regular_png_offline(tmp_path, approved_px):
    latest = fixture()
    result = render(latest, tmp_path / "regular.png")
    assert result["badge"] == "基準あり3地点 すべて基準未満"
    assert result["sponsor"] is True
    with Image.open(tmp_path / "regular.png") as image:
        assert image.size == (1200,675)
    assert sponsor_visible(latest, "event") is False


def test_null_summary_cannot_claim_below():
    latest = fixture()
    latest["summary"]["all_below"] = None
    assert sponsor_visible(latest,"regular") is False
    with pytest.raises(ValueError):
        regular_badge(latest)


def test_unconfirmed_coordinate_blocks_regular_card(monkeypatch,tmp_path):
    import render_card
    real = render_card.read_json
    def read(path):
        value = real(path)
        if Path(path).name == "stations.json":
            value = deepcopy(value)
            next(s for s in value["stations"] if s["map_visible"])["px_status"] = "candidate"
        return value
    monkeypatch.setattr(render_card,"read_json",read)
    with pytest.raises(ValueError,match="explicitly confirmed"):
        render(fixture(), tmp_path / "blocked.png")
    assert not (tmp_path / "blocked.png").exists()


def test_numbers_follow_display_order_and_average_has_no_marker(monkeypatch, tmp_path, approved_px):
    from PIL import ImageDraw
    captured = []
    original = ImageDraw.ImageDraw.text
    def record(self, xy, text, *args, **kwargs):
        if str(text) in {str(i) for i in range(1,10)}:
            captured.append(str(text))
        return original(self,xy,text,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,"text",record)
    render(fixture(),tmp_path/"numbered.png")
    assert captured[-9:] == [str(i) for i in range(1,10)]
    assert sorted(captured[:-9]) == ["1","2","3","5","6","7","8","9"]


def test_card_path_has_no_tile_or_latlon_dependencies():
    source = (ROOT/"render_card.py").read_text(encoding="utf-8")
    assert "basemap_schematic.png" in source
    for obsolete in ("basemap_simple.png", "basemap.json", "latlon_to_pixel", "地理院タイル"):
        assert obsolete not in source
