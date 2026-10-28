"""Static water-level diagram; station document order comes only from JSON."""
import re
from datetime import datetime, timedelta
from pathlib import PurePosixPath

from bs4 import BeautifulSoup

from sources.common import JST, failed, freshness, station_row

WATER_ICON = re.compile(r"ico_010121_suii_(\d+)_(\d+)\.gif")
FACILITY_ICON = re.compile(r"ico_010121_kijou_\d+_\d+\.gif")
NUMBER = re.compile(r"[+-]?\d+(?:\.\d+)?")


def parse(html, stations, fetched_at, facility_codes=None):
    stations = sorted(stations, key=lambda s: s["order"])
    soup = BeautifulSoup(html, "html.parser")
    try:
        nodes = soup.select("div.node")
        values = soup.select("div.node div.data")
        if len(stations) != 8 or len(nodes) != 8 or len(values) != 8:
            raise ValueError("Expected exactly eight station nodes and eight values")
        time_nodes = soup.select(".obs-time")
        if len(time_nodes) != 1:
            raise ValueError("Expected exactly one observation time")
        stamp = time_nodes[0].get_text(strip=True)
        if not re.fullmatch(r"\d{4}年\d{2}月\d{2}日\d{2}時\d{2}分", stamp):
            raise ValueError("Unreadable observation time")
        observed = datetime.strptime(stamp, "%Y年%m月%d日%H時%M分").replace(tzinfo=JST)
        if observed > fetched_at + timedelta(minutes=5):
            raise ValueError("Observation time is more than five minutes in the future")
        rows = []
        for station, node in zip(stations, nodes):
            data = node.select("div.data")
            icons = [PurePosixPath(img.get("src", "")).name for img in node.find_all("img")]
            if len(data) != 1 or len(icons) != 1 or not WATER_ICON.fullmatch(icons[0]):
                raise ValueError("Unexpected water node layout")
            text = data[0].get_text(strip=True)
            if not NUMBER.fullmatch(text):
                raise ValueError("Non-numeric water level")
            match = WATER_ICON.fullmatch(icons[0])
            rows.append(station_row(station) | {
                "level_m": float(text), "status": freshness(observed, fetched_at),
                "observed_at": observed.isoformat(), "water_icon": icons[0],
                "water_icon_code": f"{match[1]}_{match[2]}"})
        facility_icons = [PurePosixPath(img.get("src", "")).name for img in soup.find_all("img")
                          if "ico_010121_kijou_" in img.get("src", "")]
        if len(facility_icons) != 7 or not all(FACILITY_ICON.fullmatch(i) for i in facility_icons):
            raise ValueError("Expected exactly seven facility icons")
        facilities = [{"id": f"facility_{i}", "name": f"施設{i}（文書順）", "order": i,
                       "icon": icon, "state": (facility_codes or {}).get(icon, "unknown")}
                      for i, icon in enumerate(facility_icons, 1)]
        return {"source": {"observed_at": observed.isoformat(), "fetched_at": fetched_at.isoformat(),
                           "status": freshness(observed, fetched_at)},
                "stations": rows, "facilities": facilities}
    except ValueError as exc:
        return failed(stations, fetched_at, exc)
