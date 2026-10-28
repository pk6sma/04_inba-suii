"""Web Mercator pixel geometry; no network and no automatic coordinate correction."""
import math


def world_pixel(lat, lon, zoom):
    if not (-85.05112878 <= lat <= 85.05112878 and -180 <= lon <= 180):
        raise ValueError("Coordinate outside Web Mercator bounds")
    scale = 256 * 2 ** zoom
    return ((lon + 180) / 360 * scale,
            (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * scale)


def pixel_latlon(x, y, zoom):
    scale = 256 * 2 ** zoom
    return (math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / scale)))),
            x / scale * 360 - 180)


def latlon_to_pixel(lat, lon, metadata):
    x, y = world_pixel(lat, lon, metadata["zoom"])
    return x - metadata["world_pixel_origin"]["x"], y - metadata["world_pixel_origin"]["y"]


def confirmed_card_pixel(location, metadata):
    """The future card must use this guard, never the unchecked preview conversion."""
    if location.get("coord_status") != "confirmed":
        raise ValueError("Card coordinates must be explicitly confirmed by the user")
    lat, lon = location.get("lat"), location.get("lon")
    if lat is None or lon is None or not math.isfinite(lat) or not math.isfinite(lon):
        raise ValueError("Confirmed coordinate is missing or invalid")
    x, y = latlon_to_pixel(lat, lon, metadata)
    if not (0 <= x < metadata["width"] and 0 <= y < metadata["height"]):
        raise ValueError("Confirmed coordinate is outside the saved basemap")
    return x, y
