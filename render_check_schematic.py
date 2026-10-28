"""Local-only pixel-position preview; no real-map coordinate conversions."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from schematic_geometry import schematic_pixel

ROOT=Path(__file__).resolve().parent


def render(root=ROOT, output=None):
    root=Path(root)
    output=Path(output) if output else root/"out/check_schematic.png"
    stations=json.loads((root/"data/stations.json").read_text(encoding="utf-8"))["stations"]
    facilities=json.loads((root/"data/facilities.json").read_text(encoding="utf-8"))["facilities"]
    with Image.open(root/"assets/basemap_schematic.png") as image:
        canvas=image.convert("RGB")
    draw=ImageDraw.Draw(canvas)
    def font(size):
        return ImageFont.truetype(str(root/"assets/fonts/NotoSansJP-Bold.otf"),size)
    for e in facilities:
        x,y=schematic_pixel(e,canvas.size,require_confirmed=False)
        if "機場" in e["name"]:
            draw.polygon([(x-14,y-18),(x+14,y-18),(x+21,y+18),(x-21,y+18)],fill="#718096",outline="white")
        else:
            draw.rectangle((x-19,y-19,x+19,y+19),fill="#718096",outline="white",width=2)
        draw.text((x,y),e["check_label"],font=font(16),fill="white",anchor="mm")
    for e in stations:
        if not e.get("map_visible"):
            continue
        x,y=schematic_pixel(e,canvas.size,require_confirmed=False)
        draw.ellipse((x-32,y-32,x+32,y+32),fill="#1F5FBF",outline="white",width=3)
        draw.text((x,y),str(e["display_order"]),font=font(34),fill="white",anchor="mm")
    text="位置関係模式図"
    f=font(18)
    x,y=canvas.width-14,canvas.height-14
    box=draw.textbbox((x,y),text,font=f,anchor="rb")
    draw.rectangle((box[0]-5,box[1]-3,box[2]+5,box[3]+3),fill="white")
    draw.text((x,y),text,font=f,fill="#718096",anchor="rb")
    output.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(output)
    return {"output":str(output),"size":canvas.size,"px_status":("confirmed" if all(e.get("px_status") == "confirmed" for e in facilities + [s for s in stations if s.get("map_visible")]) else "candidate"),
            "stations":sum(bool(e.get("map_visible")) for e in stations),"facilities":len(facilities)}


if __name__=="__main__":
    print(json.dumps(render(),ensure_ascii=False,indent=2))
