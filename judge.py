"""Pure level/event/summary logic. No I/O or network."""
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal

RANK = {"normal": 0, "standby": 1, "caution": 2, "danger": 3, "design": 4}


def boundaries(config):
    return sorted([b for b in (config or {}).get("boundaries", []) if b["value"] is not None],
                  key=lambda b: (b["value"], RANK[b["level"]]))


def classify(value, config):
    limits = boundaries(config)
    if not limits:
        return "no_threshold"
    reached = [b["level"] for b in limits if Decimal(str(value)) >= Decimal(str(b["value"]))]
    return max(reached, key=RANK.get) if reached else "normal"


def evaluate(rows, thresholds, previous, now):
    state = deepcopy(previous)
    state.setdefault("stations", {})
    state["updated_at"] = now.isoformat()
    results, events = [], []
    for original in rows:
        row = dict(original)
        row.update(level=None, trend=None)
        if row["status"] != "ok":
            results.append(row)
            continue
        station_id = row["id"]
        old = state["stations"].get(station_id)
        current = classify(row["level_m"], thresholds.get(station_id))
        row["level"] = current
        if old and old.get("level_m") is not None:
            delta = Decimal(str(row["level_m"])) - Decimal(str(old["level_m"]))
            row["trend"] = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        last_events = deepcopy(old.get("last_events", {})) if old else {}
        old_level = old.get("level") if old else None
        if old_level in RANK and current in RANK and old_level != current:
            up = RANK[current] > RANK[old_level]
            low, high = sorted([RANK[current], RANK[old_level]])
            crossed = [b for b in boundaries(thresholds.get(station_id))
                       if low < RANK[b["level"]] <= high]
            eligible, suppressed = [], []
            for boundary in crossed:
                key = boundary["level"]
                last = last_events.get(key)
                cooling = last is not None and now - datetime.fromisoformat(last) <= timedelta(minutes=30)
                (suppressed if cooling else eligible).append(dict(boundary))
            if eligible:
                events.append({"station_id": station_id, "direction": "up" if up else "down",
                               "old_level": old_level, "new_level": current,
                               "crossed_thresholds": eligible, "suppressed_thresholds": suppressed,
                               "occurred_at": now.isoformat(), "observed_at": row["observed_at"]})
                for boundary in eligible:
                    last_events[boundary["level"]] = now.isoformat()
        state["stations"][station_id] = {
            "level": current, "level_m": row["level_m"], "observed_at": row["observed_at"],
            "last_events": last_events}
        results.append(row)
    return results, state, events


def summarize(rows, thresholds):
    target_ids = {station_id for station_id, config in thresholds.items() if boundaries(config)}
    available = {r["id"]: r for r in rows if r["status"] == "ok"}
    confirmed = [available[i] for i in target_ids if i in available]
    if any(r["level"] != "normal" for r in confirmed):
        all_below = False
    elif target_ids and len(confirmed) == len(target_ids):
        all_below = True
    else:
        all_below = None
    return {"with_threshold": len(target_ids), "all_below": all_below,
            "fetched": sum(r["status"] == "ok" for r in rows),
            "failed": sum(r["status"] != "ok" for r in rows),
            "stale": sum(r["status"] == "stale" for r in rows)}


def delta_one_hour(row, history):
    if row["status"] != "ok" or row.get("observed_at") is None:
        return None
    now = datetime.fromisoformat(row["observed_at"])
    candidates = []
    for snapshot in history:
        for old in snapshot["stations"]:
            if old["id"] != row["id"] or old["status"] != "ok":
                continue
            observed = datetime.fromisoformat(old["observed_at"])
            age = (now - observed).total_seconds()
            if 55 * 60 <= age <= 65 * 60:
                candidates.append((abs(age - 3600), -observed.timestamp(), old["level_m"]))
    if not candidates:
        return None
    old_value = min(candidates, key=lambda x: (x[0], x[1]))[2]
    return float(Decimal(str(row["level_m"])) - Decimal(str(old_value)))
