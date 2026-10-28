import json
from pathlib import Path
import pytest

from map_geometry import latlon_to_pixel, confirmed_card_pixel

ROOT = Path(__file__).resolve().parents[1]


def metadata():
    return json.loads((ROOT / "assets/basemap.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name,expected", [
    ("top_left", (0, 0)), ("top_right", (700, 0)),
    ("bottom_left", (0, 560)), ("bottom_right", (700, 560)),
])
def test_saved_map_corners(name, expected):
    meta = metadata()
    corner = meta["corners"][name]
    assert latlon_to_pixel(corner["lat"], corner["lon"], meta) == pytest.approx(expected, abs=1e-7)


@pytest.mark.parametrize("status", ["candidate", "missing", None, "rejected"])
def test_card_rejects_unconfirmed(status):
    with pytest.raises(ValueError, match="explicitly confirmed"):
        confirmed_card_pixel({"lat": 35.73, "lon": 140.18, "coord_status": status}, metadata())


def test_card_accepts_only_valid_confirmed_inside_map():
    assert len(confirmed_card_pixel({"lat": 35.73, "lon": 140.18, "coord_status": "confirmed"}, metadata())) == 2
    for lat, lon in [(None, 140.18), (35.73, None), (float("nan"), 140.18), (0, 0)]:
        with pytest.raises(ValueError):
            confirmed_card_pixel({"lat": lat, "lon": lon, "coord_status": "confirmed"}, metadata())
