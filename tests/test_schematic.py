import json
import hashlib
from pathlib import Path
import pytest
from PIL import Image
from schematic_geometry import schematic_pixel
from render_check_schematic import render

ROOT=Path(__file__).resolve().parents[1]


def test_pixel_geometry_does_not_use_latlon():
    record={"px":[123,456],"px_status":"confirmed","lat":None,"lon":None}
    assert schematic_pixel(record,(1400,1120)) == (123,456)
    record.update(lat=-80,lon=-100,coord_status="missing")
    assert schematic_pixel(record,(1400,1120)) == (123,456)


def test_unapproved_px_rejected_even_if_latlon_confirmed():
    with pytest.raises(ValueError,match="explicitly confirmed"):
        schematic_pixel({"px":[123,456],"px_status":"candidate","coord_status":"confirmed"},(1400,1120))


def test_preview_offline_preserves_background_and_positions(tmp_path):
    paths=[ROOT/p for p in ("assets/basemap_schematic.png","data/stations.json","data/facilities.json")]
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    result=render(ROOT,tmp_path/"check.png")
    assert result["stations"]==8 and result["facilities"]==7
    with Image.open(tmp_path/"check.png") as output, Image.open(paths[0]) as background:
        assert output.size==background.size
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]

def test_approved_schematic_locations_are_usable():
    stations=json.loads((ROOT/"data/stations.json").read_text(encoding="utf-8"))["stations"]
    facilities=json.loads((ROOT/"data/facilities.json").read_text(encoding="utf-8"))["facilities"]
    locations=[s for s in stations if s.get("map_visible")]+facilities
    assert len(locations)==15
    for e in locations:
        assert e["px_status"]=="confirmed"
        schematic_pixel(e,(1402,1122))
    by_label={e["check_label"]:e for e in facilities}
    assert by_label["F3"]["px"]==[1150,350]
    assert by_label["F4"]["px"]==[1175,372]
