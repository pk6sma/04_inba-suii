"""Offline regular/event cards from latest.json and approved schematic pixels."""
import argparse
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from schematic_geometry import schematic_pixel
from sources.common import JST
from judge import RANK

ROOT = Path(__file__).resolve().parent
NAVY, BLUE, LIGHT, GRAY = "#0B2545", "#1F5FBF", "#63B3ED", "#718096"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def font(size, bold=False, root=ROOT):
    name = "NotoSansJP-Bold.otf" if bold else "NotoSansJP-Regular.otf"
    return ImageFont.truetype(str(root / "assets/fonts" / name), size)


def fit(draw, text, size, width, bold=False, root=ROOT):
    while size >= 9:
        f = font(size, bold, root)
        if draw.textlength(text, font=f) <= width:
            return f
        size -= 1
    raise ValueError("Text does not fit allotted card area")


def level_style(level):
    if level in ("danger","design"):
        return "#C53030","#FFF5F5"
    if level in ("standby","caution"):
        return "#B7791F","#FFF8E1"
    return BLUE,"#F2F8FF"


def badge_info(latest, display, thresholds):
    by_id={s["id"]:s for s in latest["stations"]}
    rows=[by_id.get(d["id"], {"id":d["id"],"status":"fetch_failed","level":None}) for d in display]
    missing=sum(r["status"] != "ok" for r in rows)
    alerts=[r for r in rows if r["status"]=="ok" and RANK.get(r.get("level"),0)>0]
    if alerts:
        highest=max(alerts,key=lambda r:RANK[r["level"]])
        definition=next(d for d in display if d["id"]==highest["id"])
        threshold=next(b["name"] for b in thresholds[highest["id"]]["boundaries"] if b["level"]==highest["level"])
        detail=f"{threshold}を超過"
        if len(alerts)>1: detail+=f" ほか{len(alerts)-1}地点"
        if missing: detail+=f"／未取得{missing}地点"
        color,bg=level_style(highest["level"])
        return {"text":definition["name"]+" "+detail,"lines":[definition["name"],detail],
                "color":color,"background":bg,"available":len(rows)-missing,"missing":missing}
    if missing or latest["summary"]["all_below"] is not True:
        label=f"確認済み{len(rows)-missing}地点／未取得{missing}地点"
        return {"text":label,"lines":[label],"color":GRAY,"background":"#F7FAFC",
                "available":len(rows)-missing,"missing":missing}
    label=f'基準あり{latest["summary"]["with_threshold"]}地点 すべて基準未満'
    return {"text":label,"lines":[label],"color":BLUE,"background":"#F2F8FF",
            "available":len(rows),"missing":0}


def regular_badge(latest):
    config=read_json(ROOT/"data/stations.json")["stations"]
    display=[s for s in config if s.get("display_order") is not None]
    return badge_info(latest,display,read_json(ROOT/"data/thresholds.json"))["text"]


def sponsor_visible(latest, kind):
    return (kind == "regular" and not latest["events"]
            and latest["summary"]["all_below"] is True
            and latest["summary"]["failed"] == 0 and latest["summary"].get("stale", 0) == 0
            and all(s["status"] == "ok" and s["level"] in ("normal", "no_threshold")
                    for s in latest["stations"]))


def render(latest, output, kind="regular", root=ROOT):
    root, output = Path(root), Path(output)
    if kind not in ("regular","event"):
        raise ValueError("Unknown card kind")
    definitions = read_json(root / "data/stations.json")["stations"]
    display = sorted([s for s in definitions if s.get("display_order") is not None],
                     key=lambda s: s["display_order"])
    if len(display) != 9:
        raise ValueError("Expected nine display rows")
    badge=badge_info(latest,display,read_json(root/"data/thresholds.json"))
    event_ids={e["station_id"] for e in latest["events"]} if kind=="event" else set()
    by_id = {s["id"]: s for s in latest["stations"]}
    for s in display:
        by_id.setdefault(s["id"], {"id":s["id"],"status":"fetch_failed","level_m":None,"level":None,"delta_1h":None})
    facilities = read_json(root / "data/facilities.json")["facilities"]
    mapped = [s for s in display if s.get("map_visible")]
    with Image.open(root / "assets/basemap_schematic.png") as im:
        native = im.convert("RGB")
    positions = {}
    for e in mapped + facilities:
        x,y = schematic_pixel(e,native.size,require_confirmed=True)
        positions[e["id"]] = (x*700/native.width,y*560/native.height)
    basemap = native.resize((700,560),Image.Resampling.LANCZOS)
    card = Image.new("RGB", (1200, 675), "white")
    draw = ImageDraw.Draw(card)
    def text(x, y, content, size, color=NAVY, bold=False, max_width=None, anchor="lt"):
        f = fit(draw, content, size, max_width, bold, root) if max_width else font(size, bold, root)
        draw.text((x,y),content,font=f,fill=color,anchor=anchor)

    # Header: title, municipality context, status, generated time.
    text(12, 8, "印旛沼の水位情報", 44, bold=True, max_width=440)
    text(465, 13, "佐倉・印西・成田・八千代・栄・", 12)
    text(465, 34, "千葉市花見川区", 12)
    draw.rounded_rectangle((726,7,1028,59),radius=8,fill=badge["background"],outline=badge["color"],width=1)
    for i,line in enumerate(badge["lines"]):
        text(737,12+i*23 if len(badge["lines"])>1 else 15,line,17 if len(badge["lines"])>1 else 18,
             badge["color"],True,max_width=281)
    if len(badge["lines"])>1:
        text(706,49,"9地点観測中",10,BLUE,anchor="rt")
    else:
        text(1017,43,"9地点観測中",11,BLUE,anchor="rt")
    stamp = datetime.fromisoformat(latest["generated_at"])
    weekday = "月火水木金土日"[stamp.weekday()]
    text(1190,7,f"{stamp:%Y/%m/%d}（{weekday}）",13,bold=True,anchor="rt")
    text(1190,24,f"{stamp:%H:%M}",23,bold=True,anchor="rt")
    text(1190,50,"※表示の水位は速報値です",9,anchor="rt")

    # Schematic background; scale only image-native pixels, never lat/lon.
    map_x, map_y = 12, 65
    card.paste(basemap, (map_x,map_y))
    for facility in facilities:
        px,py = positions[facility["id"]]
        x,y = map_x+px,map_y+py
        # Match only an explicit stable ID. Never guess a source icon order.
        state=next((f["state"] for f in latest["facilities"] if f["id"]==facility.get("source_id",facility["id"])),"unknown")
        facility_color={"排水中":"#C53030","停止":"#2F855A","揚水中":"#B7791F",
                        "故障":"#718096","欠測":"#718096","故障・欠測":"#718096"}.get(state,GRAY)
        if "機場" in facility["name"]:
            draw.polygon([(x-5,y-6),(x+5,y-6),(x+8,y+6),(x-8,y+6)],fill=facility_color,outline="white")
        else:
            draw.rectangle((x-6,y-6,x+6,y+6),fill=facility_color,outline="white")
    for station in mapped:
        px,py = positions[station["id"]]
        dx,dy = station.get("label_offset_px",[0,0])
        row=by_id[station["id"]]
        active=row["status"]=="ok" and (RANK.get(row.get("level"),0)>0 or station["id"] in event_ids)
        radius=22 if active else 17
        color=level_style(row.get("level"))[0] if row["status"]=="ok" else GRAY
        x,y = map_x+px+dx,map_y+py+dy
        if not (radius <= px+dx < 700-radius and radius <= py+dy < 539-radius):
            raise ValueError("Explicit marker offset puts marker outside map area")
        if max(abs(dx),abs(dy))>17:
            draw.line((map_x+px,map_y+py,x,y),fill=color,width=1)
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=color,outline="white",width=2)
        text(x,y,str(station["display_order"]),21,"white",True,anchor="mm")
    # Facility legend and schematic notice. No GSI attribution for this background.
    draw.rectangle((map_x,map_y+539,map_x+699,map_y+559),fill="white")
    text(map_x+6,map_y+543,"■水門  ▲排水機場",12,GRAY)
    text(map_x+691,map_y+543,"位置関係模式図",12,GRAY,anchor="rt")

    # Nine rows, source-specific north/south values from the county records.
    for index, definition in enumerate(display):
        row = by_id[definition["id"]]
        y = 71 + index*53
        missing=row["status"]!="ok"
        warning=not missing and RANK.get(row.get("level"),0)>0
        active=warning or (not missing and row["id"] in event_ids)
        color,bg=level_style(row.get("level"))
        if missing: color,bg=GRAY,"#F7FAFC"
        draw.rounded_rectangle((726,y,1188,y+50),radius=8,outline=color if active else "#D7E6F5",
                               width=2 if active else 1,fill=bg if active or missing else "#FBFDFF")
        number = str(definition["display_order"])
        draw.ellipse((737,y+8,771,y+42),fill=color)
        text(754,y+25,number,21,"white",True,anchor="mm")
        delta=row.get("delta_1h") if warning else None
        text(785,y+15,definition["name"],21,bold=True,max_width=160 if delta is not None else 225)
        if missing:
            text(1176,y+15,"未取得",22,GRAY,True,anchor="rt")
        elif delta is not None:
            text(1035,y+14,f'{row["level_m"]:.2f}m',25,color,True,anchor="rt")
            text(1045,y+20,f'{delta:+.2f}m（1時間前比）',11,color,max_width=132)
        else:
            text(1146,y+8,f'{row["level_m"]:.2f}',33,color,True,anchor="rt")
            text(1176,y+25,"m",17,color,True,anchor="rt")

    # Source times and regular-only sponsor.
    sources = latest["sources"]
    for index, (source,label) in enumerate((("mizukan","印旛沼水位情報"),("chiba_suibo","千葉県 雨量・水位情報"))):
        value=sources.get(source,{}).get("observed_at")
        observed=datetime.fromisoformat(value).strftime("%m/%d %H:%M") if value else "未取得"
        text(735,555+index*17,f"{label}  観測 {observed}",11,GRAY)
    show_sponsor = sponsor_visible(latest, kind)
    if show_sponsor:
        config = read_json(root / "config.json")["sponsor"]
        text(1176,598,config["text"],16,bold=True,anchor="rt")
        logo_path = root / config["logo_path"]
        if logo_path.exists():
            with Image.open(logo_path) as logo:
                logo = logo.convert("RGBA")
                logo.thumbnail((90,40), Image.Resampling.LANCZOS)
                card.paste(logo,(1035-logo.width,582),logo)

    # Three sections, specified statements only.
    draw.rectangle((0,625,1200,674),fill=NAVY)
    for x in (305,735):
        draw.line((x,635,x,664),fill=LIGHT,width=1)
    text(12,639,"表示は各観測所の表示基準による速報値です",12,"white",max_width=282)
    text(319,634,"避難判断は各市の防災情報・気象庁の発表で",12,"white")
    text(319,652,"確認してください",12,"white")
    text(749,634,"出典：印旛沼水位情報（mizukan.sakura.ne.jp/suii/）／",11,"white")
    text(749,652,"千葉県 雨量・水位情報",11,"white")
    output.parent.mkdir(parents=True,exist_ok=True)
    card.save(output)
    return {"output":str(output),"size":card.size,"badge":badge["text"],"sponsor":show_sponsor}



def cleanup_cards(folder, now):
    """Delete only timestamp-named generated cards older than seven days."""
    folder=Path(folder).resolve()
    removed=[]
    if not folder.exists(): return removed
    for path in folder.iterdir():
        match=re.fullmatch(r"(\d{8}-\d{4})-(regular|event)\.png",path.name)
        if not match or path.is_symlink() or not path.is_file(): continue
        stamp=datetime.strptime(match[1],"%Y%m%d-%H%M").replace(tzinfo=JST)
        if now.astimezone(JST)-stamp>timedelta(days=7):
            if path.resolve().parent != folder: raise ValueError("Unsafe cleanup path")
            path.unlink()
            removed.append(path.name)
    return removed


def scheduled_regular(now, previous):
    local=now.astimezone(JST)
    minute=local.hour*60+local.minute
    slot=("morning" if 6*60+50<=minute<7*60+20 else
          "evening" if 18*60+50<=minute<19*60+20 else None)
    if slot is None: return None
    key=f"{local:%Y-%m-%d}-{slot}"
    return key if previous.get(slot)!=key else None


def render_outputs(latest,root=ROOT):
    root=Path(root)
    now=datetime.fromisoformat(latest["generated_at"]).astimezone(JST)
    out=root/"out"
    folder=out/"cards"
    folder.mkdir(parents=True,exist_ok=True)
    schedule_path=out/"card_schedule.json"
    schedule=read_json(schedule_path) if schedule_path.exists() else {}
    slot=scheduled_regular(now,schedule)
    fixed=folder/"latest_regular.png"
    render(latest,fixed,"regular",root)
    cards={"regular":fixed.relative_to(root).as_posix()}
    if slot:
        history=folder/f"{now:%Y%m%d-%H%M}-regular.png"
        shutil.copyfile(fixed,history)
        cards["regular"]=history.relative_to(root).as_posix()
        schedule[slot.rsplit("-",1)[1]]=slot
    if latest["events"]:
        path=folder/f"{now:%Y%m%d-%H%M}-event.png"
        render(latest,path,"event",root)
        cards["event"]=path.relative_to(root).as_posix()
    from inba_watch import write_json
    if slot: write_json(schedule_path,schedule)
    cleanup_cards(folder,now)
    manifest={"generated_at":latest["generated_at"],"cards":cards}
    write_json(out/"card_manifest.json",manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest",type=Path,default=ROOT/"out/latest.json")
    parser.add_argument("--kind",choices=["regular","event"])
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    latest=read_json(args.latest)
    if args.kind or args.output:
        kind=args.kind or "regular"
        stamp=datetime.fromisoformat(latest["generated_at"])
        output=args.output or ROOT/"out/cards"/f"{stamp:%Y%m%d-%H%M}-{kind}.png"
        result=render(latest,output,kind)
    else:
        result=render_outputs(latest)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
