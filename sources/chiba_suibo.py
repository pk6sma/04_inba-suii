"""County mobile page: each station is an anchor followed by a time/value row."""
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup, Tag

from sources.common import JST, freshness, station_row


def infer_observed_at(hhmm, fetched_at):
    fetched_at = fetched_at.astimezone(JST)
    hour, minute = map(int, hhmm.split(":"))
    observed = fetched_at.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if observed > fetched_at + timedelta(minutes=5):
        observed -= timedelta(days=1)
    return observed


def parse(html, stations, fetched_at):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for station in sorted(stations, key=lambda s: s["order"]):
        row = station_row(station) | {
            "observed_date_inferred": True, "fetched_at": fetched_at.isoformat()}
        try:
            anchors = [a for a in soup.find_all("a") if a.get_text(strip=True) == station["match_name"]]
            if len(anchors) != 1:
                raise ValueError("Expected exactly one station anchor: " + station["match_name"])
            parts, breaks = [], 0
            for sibling in anchors[0].next_siblings:
                if isinstance(sibling, Tag) and sibling.name == "br":
                    breaks += 1
                    if breaks == 2:
                        break
                parts.append(sibling.get_text(" ", strip=True) if isinstance(sibling, Tag) else str(sibling))
            match = re.fullmatch(r"\s*\)\s*└(\d{2}:\d{2})\s*[↑↓→]\s*([+-]?\d+(?:\.\d+)?)\s*",
                                 " ".join(parts))
            if not match:
                raise ValueError("Unreadable station time/value: " + station["match_name"])
            observed = infer_observed_at(match[1], fetched_at)
            row.update(level_m=float(match[2]), observed_at=observed.isoformat(),
                       status=freshness(observed, fetched_at))
        except ValueError as exc:
            row["error"] = str(exc)
        rows.append(row)
    times = {row["observed_at"] for row in rows}
    statuses = {row["status"] for row in rows}
    status = "fetch_failed" if "fetch_failed" in statuses else ("stale" if "stale" in statuses else "ok")
    return {"source": {"observed_at": next(iter(times)) if len(times) == 1 else None,
                       "observed_date_inferred": True, "fetched_at": fetched_at.isoformat(),
                       "status": status},
            "stations": rows, "facilities": []}
