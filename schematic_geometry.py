"""Schematic coordinates are image pixels, independent of lat/lon."""
import math


def schematic_pixel(entry, image_size, require_confirmed=True):
    if require_confirmed and entry.get("px_status") != "confirmed":
        raise ValueError("Schematic pixel coordinates must be explicitly confirmed")
    px = entry.get("px")
    if not isinstance(px, list) or len(px) != 2:
        raise ValueError("Missing schematic px: [x,y]")
    x,y = px
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in px):
        raise ValueError("Invalid schematic pixels")
    if not (0 <= x < image_size[0] and 0 <= y < image_size[1]):
        raise ValueError("Schematic pixels are outside background")
    return x,y
