import json
from copy import deepcopy
from datetime import datetime,timedelta
from pathlib import Path

import pytest
from PIL import Image
from render_card import render, regular_badge, sponsor_visible, cleanup_cards, scheduled_regular, render_outputs

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT/f"tests/fixtures/latest_{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name,kind,expected",[
    ("regular","regular","基準あり3地点 すべて基準未満"),
    ("event","event","高崎川｜鏑木橋 はん濫注意水位を超過"),
    ("missing","regular","確認済み7地点／未取得2地点")])
def test_cards(name,kind,expected,tmp_path,monkeypatch):
    from PIL import ImageDraw
    source_boxes=[]
    original=ImageDraw.ImageDraw.text
    def record(self,xy,text,*args,**kwargs):
        if str(text).startswith("出典："):
            assert text=="出典：印旛沼水位情報（mizukan.sakura.ne.jp/suii/）／"
            source_boxes.append(self.textbbox(xy,text,font=kwargs["font"],anchor=kwargs.get("anchor")))
        return original(self,xy,text,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,"text",record)
    result=render(load(name),tmp_path/f"{name}.png",kind)
    assert len(source_boxes)==1
    left,top,right,bottom=source_boxes[0]
    assert 735<=left<right<=1200 and 625<=top<bottom<=675
    assert result["badge"]==expected
    assert result["sponsor"]==(name=="regular")
    with Image.open(result["output"]) as im: assert im.size==(1200,675)


def test_missing_values_are_not_printed(monkeypatch,tmp_path):
    from PIL import ImageDraw
    printed=[]
    original=ImageDraw.ImageDraw.text
    def spy(self,xy,text,*args,**kwargs):
        printed.append(str(text))
        return original(self,xy,text,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,"text",spy)
    render(load("missing"),tmp_path/"missing.png")
    assert printed.count("未取得")==2
    assert "2.00" not in printed
    assert "すべて基準未満" not in " ".join(printed)
    assert "提供：" not in " ".join(printed)


@pytest.mark.parametrize("level,threshold",[
    ("standby","水防団待機水位"),("danger","はん濫危険水位"),("design","計画高水位")])
def test_other_alert_levels(level,threshold,tmp_path):
    latest=load("event")
    next(s for s in latest["stations"] if s["id"]=="kaburagi")["level"]=level
    assert threshold in render(latest,tmp_path/"alert.png","event")["badge"]


def test_multiple_alerts_highest_not_hidden_by_missing():
    latest=load("missing")
    row=next(s for s in latest["stations"] if s["id"]=="kaburagi")
    row.update(status="ok",level="danger",level_m=4.8)
    row=next(s for s in latest["stations"] if s["id"]=="nishiinba")
    row.update(status="ok",level="caution",level_m=3.5)
    badge=regular_badge(latest)
    assert "はん濫危険水位" in badge and "ほか1地点" in badge and "未取得1地点" in badge


def test_no_sponsor_for_event_even_after_recovery(tmp_path):
    latest=load("regular")
    assert render(latest,tmp_path/"event.png","event")["sponsor"] is False
    latest["events"]=[{"station_id":"kaburagi"}]
    assert sponsor_visible(latest,"regular") is False


@pytest.mark.parametrize("stamp,previous,expected",[
    ("2026-10-29T06:49:00+09:00",{},None),
    ("2026-10-29T06:50:00+09:00",{},"2026-10-29-morning"),
    ("2026-10-29T07:00:00+09:00",{"morning":"2026-10-29-morning"},"2026-10-29-morning"),
    ("2026-10-29T07:10:00+09:00",{},"2026-10-29-morning"),
    ("2026-10-29T07:10:00+09:00",{"morning":"2026-10-29-morning"},None),
    ("2026-10-29T18:50:00+09:00",{},"2026-10-29-evening"),
    ("2026-10-29T19:00:00+09:00",{},"2026-10-29-evening"),
    ("2026-10-29T10:00:00+00:00",{},"2026-10-29-evening")])
def test_regular_schedule(stamp,previous,expected):
    assert scheduled_regular(datetime.fromisoformat(stamp),previous)==expected


def test_cleanup_keeps_fixed_samples_and_exact_seven_days(tmp_path):
    now=datetime.fromisoformat("2026-10-29T07:00:00+09:00")
    names=["20261022-0659-event.png","20261022-0700-regular.png","latest_regular.png","sample_event.png","user.png"]
    for name in names: (tmp_path/name).write_bytes(b"generated-test-output")
    assert cleanup_cards(tmp_path,now)==["20261022-0659-event.png"]
    assert all((tmp_path/name).exists() for name in names[1:])


def test_auto_outputs_regular_and_event_and_fixed_alias(tmp_path):
    import shutil
    for folder in ("data","assets"):
        shutil.copytree(ROOT/folder,tmp_path/folder)
    shutil.copyfile(ROOT/"config.json",tmp_path/"config.json")
    latest=load("event")
    latest["generated_at"]="2026-10-29T06:50:00+09:00"
    manifest=render_outputs(latest,tmp_path)
    assert set(manifest["cards"])=={"regular","event"}
    assert (tmp_path/"out/cards/latest_regular.png").read_bytes()==(tmp_path/manifest["cards"]["regular"]).read_bytes()
    latest["generated_at"]="2026-10-29T07:10:00+09:00"
    latest["events"]=[]
    assert render_outputs(latest,tmp_path)["cards"]=={}


def test_facility_state_uses_saved_source_id(tmp_path):
    latest=load("regular")
    latest["facilities"][0]["state"]="排水中"  # fixture order 1 = 印旛機場
    result=render(latest,tmp_path/"facility.png")
    with Image.open(result["output"]) as im:
        assert im.getcolors(maxcolors=1000000) is not None
        assert any(color == (197,48,48) for _,color in im.getcolors(maxcolors=1000000))
