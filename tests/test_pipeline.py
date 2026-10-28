from datetime import datetime,timedelta
from pathlib import Path
import json
import shutil

from inba_watch import run_once
from render_card import render_outputs
from notify import notify

ROOT=Path(__file__).resolve().parents[1]


def test_offline_end_to_end_fetch_judge_render_and_dry_run(tmp_path,fixture_data):
    for folder in ("data","assets"):
        shutil.copytree(ROOT/folder,tmp_path/folder)
    shutil.copyfile(ROOT/"config.json",tmp_path/"config.json")
    def loader_at(hhmm,high=False):
        def loader(url,parser,stations,**kwargs):
            html,_,_=fixture_data(stations[0]["source"])
            if stations[0]["source"]=="mizukan":
                html=html.replace("03時40分",hhmm[:2]+"時"+hhmm[3:]+"分")
            else:
                html=html.replace("03:40",hhmm)
                if high: html=html.replace("2.21","4.05")
            fetched=datetime.fromisoformat(f"2026-10-29T{hhmm}:00+09:00")+timedelta(minutes=2)
            return parser(html,stations,fetched,**kwargs)
        return loader
    first=run_once(tmp_path,loader_at("06:40"),datetime.fromisoformat("2026-10-29T06:42:00+09:00"))
    assert first["events"]==[]
    latest=run_once(tmp_path,loader_at("06:50",True),datetime.fromisoformat("2026-10-29T06:52:00+09:00"))
    assert len(latest["events"])==1
    assert latest["events"][0]["new_level"]=="caution"
    manifest=render_outputs(latest,tmp_path)
    assert set(manifest["cards"])=={"event","regular"}
    assert notify(latest,tmp_path,environ={})=={"status":"dry-run","attempts":0}
    assert (tmp_path/"out/cards/latest_regular.png").exists()
    assert len((tmp_path/"out/history/2026-10.jsonl").read_text(encoding="utf-8").splitlines())==2
    state=json.loads((tmp_path/"out/state.json").read_text(encoding="utf-8"))
    assert state["stations"]["kaburagi"]["level"]=="caution"
