"""One-time acquisition of a fixed GSI pale basemap. Never used by render_check.py."""
import io
import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests
from PIL import Image, ImageDraw, ImageFont
from map_geometry import world_pixel, pixel_latlon
from sources.common import USER_AGENT

WIDTH, HEIGHT = 700, 560
REQUESTED = {"north": 35.84, "south": 35.62, "west": 140.03, "east": 140.34}


def main():
    assets = ROOT / "assets"
    cache = assets / "tile_sources"
    assets.mkdir(exist_ok=True)
    # The directory itself is a one-shot lock. A failure requires explicit manual review.
    cache.mkdir(exist_ok=False)
    if (assets / "basemap.png").exists() or (assets / "basemap.json").exists():
        raise SystemExit("Basemap exists; refusing replacement or download")
    for z in range(18, -1, -1):
        left, top = world_pixel(REQUESTED["north"], REQUESTED["west"], z)
        right, bottom = world_pixel(REQUESTED["south"], REQUESTED["east"], z)
        if right - left <= WIDTH and bottom - top <= HEIGHT:
            break
    origin_x = math.floor((left + right - WIDTH) / 2)
    origin_y = math.floor((top + bottom - HEIGHT) / 2)
    x0, x1 = origin_x // 256, (origin_x + WIDTH - 1) // 256
    y0, y1 = origin_y // 256, (origin_y + HEIGHT - 1) // 256
    mosaic = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    records = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            url = f"https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png"
            stamp = datetime.now(timezone(timedelta(hours=9))).isoformat()
            response = requests.get(url, headers={"User-Agent": USER_AGENT},
                                    timeout=(10, 30), allow_redirects=False)
            record = {"url": url, "fetched_at": stamp, "status": response.status_code,
                      "bytes": len(response.content), "x": x, "y": y}
            (cache / f"{z}_{x}_{y}.meta.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            if response.status_code != 200:
                raise SystemExit(f"Tile failed ({response.status_code}); no retry: {url}")
            tile = Image.open(io.BytesIO(response.content))
            if tile.size != (256, 256) or tile.format != "PNG":
                raise SystemExit("Unexpected tile image; stopped")
            (cache / f"{z}_{x}_{y}.png").write_bytes(response.content)
            mosaic.paste(tile.convert("RGB"), ((x - x0) * 256, (y - y0) * 256))
            records.append(record)
    crop_x, crop_y = origin_x - x0 * 256, origin_y - y0 * 256
    image = mosaic.crop((crop_x, crop_y, crop_x + WIDTH, crop_y + HEIGHT))
    font = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 12)
    draw = ImageDraw.Draw(image)
    # Required credit only. No recoloring, geographic label edits, or river emphasis.
    draw.rectangle((0, HEIGHT - 21, WIDTH, HEIGHT), fill="white")
    draw.text((6, HEIGHT - 20), "出典：地理院タイル", font=font, fill="black")
    image.save(assets / "basemap.png")
    corners = {}
    for name, px, py in (("top_left", 0, 0), ("top_right", WIDTH, 0),
                        ("bottom_left", 0, HEIGHT), ("bottom_right", WIDTH, HEIGHT)):
        lat, lon = pixel_latlon(origin_x + px, origin_y + py, z)
        corners[name] = {"lat": lat, "lon": lon}
    metadata = {"projection": "EPSG:3857", "tile_size": 256, "zoom": z,
                "width": WIDTH, "height": HEIGHT, "world_pixel_origin": {"x": origin_x, "y": origin_y},
                "top_left": corners["top_left"], "corners": corners,
                "corner_convention": "outer pixel edges; bottom_right is (width,height)",
                "requested_bounds": REQUESTED,
                "source": "地理院タイル（淡色地図）",
                "source_url": "https://maps.gsi.go.jp/development/ichiran.html#pale",
                "tile_template": "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
                "attribution": "出典：地理院タイル", "credit_strip_height": 21,
                "resampled": False, "tiles": records}
    (assets / "basemap.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(json.dumps({"zoom": z, "size": image.size, "corners": corners,
                      "tile_count": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
