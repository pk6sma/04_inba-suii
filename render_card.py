"""Offline card rendering. Stage 3 step 1: regular preview only, pending approval."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from schematic_geometry import schematic_pixel

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


def regular_badge(latest):
    # Other conditions deliberately stop until the regular design is approved.
    summary = latest["summary"]
    if (summary["all_below"] is not True or summary["failed"] or summary.get("stale", 0)
            or any(s["status"] != "ok" or s["level"] not in ("normal", "no_threshold")
                   for s in latest["stations"])):
        raise ValueError("Only fully available normal regular preview is implemented at this approval stage")
    return f'基準あり{summary["with_threshold"]}地点 すべて基準未満'


def sponsor_visible(latest, kind):
    return (kind == "regular" and not latest["events"]
            and latest["summary"]["all_below"] is True
            and latest["summary"]["failed"] == 0 and latest["summary"].get("stale", 0) == 0
            and all(s["status"] == "ok" and s["level"] in ("normal", "no_threshold")
                    for s in latest["stations"]))


def render(latest, output, kind="regular", root=ROOT):
    root, output = Path(root), Path(output)
    if kind != "regular":
        raise ValueError("Event layout awaits regular-card approval")
    badge = regular_badge(latest)
    definitions = read_json(root / "data/stations.json")["stations"]
    display = sorted([s for s in definitions if s.get("display_order") is not None],
                     key=lambda s: s["display_order"])
    if len(display) != 9:
        raise ValueError("Expected nine display rows")
    by_id = {s["id"]: s for s in latest["stations"]}
    if any(s["id"] not in by_id for s in display):
        raise ValueError("Required display station is missing")
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
    draw.rounded_rectangle((726,7,1028,59),radius=8,fill="#F2F8FF",outline=BLUE,width=1)
    text(737,15,badge,18,BLUE,True,max_width=281)
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
        if "機場" in facility["name"]:
            draw.polygon([(x-5,y-6),(x+5,y-6),(x+8,y+6),(x-8,y+6)],fill=GRAY,outline="white")
        else:
            draw.rectangle((x-6,y-6,x+6,y+6),fill=GRAY,outline="white")
    for station in mapped:
        px,py = positions[station["id"]]
        dx,dy = (0,0)  # px is the complete approved schematic marker position
        x,y = map_x+px+dx,map_y+py+dy
        if not (17 <= px+dx < 683 and 17 <= py+dy < 539):
            raise ValueError("Explicit marker offset puts marker outside map area")
        if dx or dy:
            draw.line((map_x+px,map_y+py,x,y),fill=BLUE,width=1)
        draw.ellipse((x-17,y-17,x+17,y+17),fill=BLUE,outline="white",width=2)
        text(x,y,str(station["display_order"]),21,"white",True,anchor="mm")
    # Facility legend and schematic notice. No GSI attribution for this background.
    draw.rectangle((map_x,map_y+539,map_x+699,map_y+559),fill="white")
    text(map_x+6,map_y+543,"■水門  ▲排水機場",12,GRAY)
    text(map_x+691,map_y+543,"位置関係模式図",12,GRAY,anchor="rt")

    # Nine rows, source-specific north/south values from the county records.
    for index, definition in enumerate(display):
        row = by_id[definition["id"]]
        y = 71 + index*53
        draw.rounded_rectangle((726,y,1188,y+50),radius=8,outline="#D7E6F5",width=1,fill="#FBFDFF")
        number = str(definition["display_order"])
        draw.ellipse((737,y+8,771,y+42),fill=BLUE)
        text(754,y+25,number,21,"white",True,anchor="mm")
        text(785,y+15,definition["name"],21,bold=True,max_width=225)
        text(1146,y+8,f'{row["level_m"]:.2f}',33,BLUE,True,anchor="rt")
        text(1176,y+25,"m",17,BLUE,True,anchor="rt")

    # Source times and regular-only sponsor.
    sources = latest["sources"]
    for index, (source,label) in enumerate((("mizukan","印旛沼水位情報"),("chiba_suibo","千葉県 雨量・水位情報"))):
        observed = datetime.fromisoformat(sources[source]["observed_at"])
        text(735,555+index*17,f"{label}  観測 {observed:%m/%d %H:%M}",11,GRAY)
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
    text(749,634,"出典：印旛沼水位情報（mizukan.sakura.ne.jp）／",11,"white")
    text(749,652,"千葉県 雨量・水位情報",11,"white")
    output.parent.mkdir(parents=True,exist_ok=True)
    card.save(output)
    return {"output":str(output),"size":card.size,"badge":badge,"sponsor":show_sponsor}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest",type=Path,default=ROOT/"out/latest.json")
    parser.add_argument("--kind",choices=["regular"],default="regular")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    latest=read_json(args.latest)
    stamp=datetime.fromisoformat(latest["generated_at"])
    output=args.output or ROOT/"out/cards"/f"{stamp:%Y%m%d-%H%M}-{args.kind}.png"
    print(json.dumps(render(latest,output,args.kind),ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
