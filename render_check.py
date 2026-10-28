"""Offline coordinate review PNG. Uses only the saved basemap and local JSON."""
import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from map_geometry import latlon_to_pixel

ROOT = Path(__file__).resolve().parent
BLUE = "#155fa5"
GRAY = "#555b64"
INK = "#26313d"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def font(size):
    for name in ("C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/YuGothM.ttc"):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    raise RuntimeError("Japanese font not found; specify/install a font only after user approval")


def render(root=ROOT, output=None):
    """No downloads, geocoding, or JSON writes; candidate positions are never moved."""
    root = Path(root)
    output = Path(output) if output is not None else root / "out/check_map.png"
    meta = read_json(root / "assets/basemap.json")
    stations = sorted([s for s in read_json(root / "data/stations.json")["stations"]
                       if s.get("map_visible")], key=lambda s: s["map_number"])
    facilities = read_json(root / "data/facilities.json")["facilities"]
    visible = stations + facilities
    all_confirmed = all(e["coord_status"] == "confirmed" for e in visible)
    with Image.open(root / "assets/basemap.png") as saved:
        basemap = saved.convert("RGB")
    if basemap.size != (meta["width"], meta["height"]):
        raise ValueError("Saved basemap size does not match metadata")
    canvas = Image.new("RGB", (1240, 940), "#f6f7f8")
    draw = ImageDraw.Draw(canvas)
    title_font, text_font, small_font = font(25), font(16), font(13)
    draw.text((24, 16), "印旛沼水位bot｜座標確認用", font=title_font, fill=INK)
    draw.text((24, 52), ("全15件をユーザー承認により確定。2・4・6・F1・F2は指定座標へ修正済み。"
               if all_confirmed else "住所検索の候補を含みます。未承認の座標はカードには使用できません。"),
              font=small_font, fill=INK)
    map_x, map_y = 24, 95
    canvas.paste(basemap, (map_x, map_y))
    draw.rectangle((map_x-1, map_y-1, map_x+meta["width"], map_y+meta["height"]), outline="#a5abb1")
    draw.text((map_x, 73), "青丸：観測地点（1〜8）　グレー四角：施設（F1〜F7）", font=small_font, fill=INK)

    facility_keys = {(f["lat"], f["lon"]) for f in facilities if f["lat"] is not None}
    offmap = []
    for station in stations:
        if station["lat"] is None or station["lon"] is None:
            continue
        px, py = latlon_to_pixel(station["lat"], station["lon"], meta)
        if not (0 <= px < meta["width"] and 0 <= py < meta["height"]):
            offmap.append(station)
            continue
        x, y = map_x + px, map_y + py
        shared = (station["lat"], station["lon"]) in facility_keys
        draw.ellipse((x-12, y-12, x+12, y+12), fill=None if shared else BLUE, outline=BLUE, width=3)
        if shared:
            pass  # Number drawn after facility labels
        else:
            draw.text((x, y), str(station["map_number"]), font=font(14), fill="white", anchor="mm")

    # Label-only offsets. Leaders start at the exact candidate coordinates.
    offsets = {"F1":(-170,-46), "F2":(-170,-17), "F3":(34,-10), "F4":(34,19),
               "F5":(-95,-32), "F6":(30,28), "F7":(-100,-34)}
    for facility in facilities:
        if facility["lat"] is None or facility["lon"] is None:
            continue
        px, py = latlon_to_pixel(facility["lat"], facility["lon"], meta)
        if not (0 <= px < meta["width"] and 0 <= py < meta["height"]):
            offmap.append(facility)
            continue
        x, y = map_x+px, map_y+py
        draw.rectangle((x-5,y-5,x+5,y+5), fill=GRAY, outline="white")
        dx, dy = offsets.get(facility["check_label"], (16, -20))
        label = facility["check_label"] + " " + facility["short_name"]
        box = draw.textbbox((x+dx,y+dy),label,font=small_font)
        draw.line((x,y,box[2] if dx<0 else box[0],(box[1]+box[3])/2),fill=GRAY,width=1)
        draw.rectangle((box[0]-2,box[1]-1,box[2]+2,box[3]+1),fill="white")
        draw.text((x+dx,y+dy),label,font=small_font,fill=GRAY)

    # Draw shared-station numbers last so facility labels cannot obscure them.
    for station in stations:
        if (station["lat"], station["lon"]) in facility_keys:
            px, py = latlon_to_pixel(station["lat"], station["lon"], meta)
            draw.text((map_x+px+15, map_y+py-24), str(station["map_number"]),
                      font=text_font, fill=BLUE, stroke_width=1, stroke_fill="white")

    right_x, cursor = 762, 91
    draw.text((right_x,cursor), "観測地点：番号／緯度・経度",font=text_font,fill=INK)
    cursor += 32
    for station in stations:
        label = f'{station["map_number"]}  {station["name"]}'
        draw.text((right_x,cursor),label,font=text_font,fill=BLUE)
        coord = ("未取得" if station["coord_status"] == "missing" else
                 f'{station["lat"]:.6f}, {station["lon"]:.6f}  [{station["coord_status"]}]')
        draw.text((right_x+18,cursor+21),coord,font=small_font,fill=INK)
        cursor += 45
    draw.text((right_x,cursor+3),"施設：同一座標は重ねて表示しています",font=small_font,fill=INK)
    cursor += 32
    for facility in facilities:
        draw.text((right_x,cursor),f'{facility["check_label"]}  {facility["name"]}',font=text_font,fill=GRAY)
        coord = ("未取得" if facility["coord_status"] == "missing" else
                 f'{facility["lat"]:.6f}, {facility["lon"]:.6f}  [{facility["coord_status"]}]')
        draw.text((right_x+18,cursor+21),coord,font=small_font,fill=INK)
        cursor += 44

    missing = [s for s in visible if s["coord_status"] == "missing"]
    draw.text((24,678),"未取得・範囲外",font=text_font,fill=INK)
    for i, entry in enumerate(missing + offmap):
        key = entry.get("map_number", entry.get("check_label"))
        status = "未取得" if entry in missing else "地図範囲外"
        draw.text((24,710+i*24),f'{key}  {entry["name"]}：{status}',font=text_font,fill=INK)
    if not missing and not offmap:
        draw.text((24,710),"なし",font=text_font,fill=INK)
    draw.text((24,765),("6 長門川：ユーザー指定の緯度経度で確定済み。" if all_confirmed
                       else "未取得の座標はnullのままです。自動で推定・補正しません。"),font=small_font,fill=INK)
    draw.text((24,791),"印旛沼平均は地点ではないため非表示。北・西の補助値も別点にしません。",font=small_font,fill=INK)
    counts = Counter(entry["coord_status"] for entry in visible)
    draw.text((24,835),f'地図対象15件：confirmed {counts["confirmed"]} / candidate {counts["candidate"]} / missing {counts["missing"]}',
              font=text_font,fill=INK)
    draw.text((24,864),"修正は「番号・F番号：正しい緯度経度」または「方向・距離」で指定してください。",font=small_font,fill=INK)
    draw.text((24,889),("ユーザーの全件確定指示を反映済み。背景地図：出典 地理院タイル" if all_confirmed
               else "OKが出た地点だけconfirmedに更新します。背景地図：出典 地理院タイル"),font=small_font,fill=INK)
    output.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(output)
    return {"output": str(output), "size": canvas.size, "counts": dict(counts),
            "offmap": [s["id"] for s in offmap]}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(render(),ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
