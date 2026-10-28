"""Run once: acquire two sources, judge levels, and write local output only."""
import argparse
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from judge import delta_one_hour, evaluate, summarize
from sources import chiba_suibo, mizukan
from sources.common import JST, load_source

ROOT = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))



def compact_history(folder):
    """Migrate daily files to monthly JSONL, retaining original files in an archive."""
    import re
    folder=Path(folder)
    if not folder.exists(): return
    groups={}
    for path in sorted(folder.glob("*.jsonl")):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.jsonl",path.name):
            datetime.strptime(path.stem,"%Y-%m-%d")
            groups.setdefault(path.name[:7],[]).append(path)
    archive=folder.parent/"history_archive"
    for month,paths in groups.items():
        target=folder/f"{month}.jsonl"
        records=[]
        seen=set()
        for path in ([target] if target.exists() else [])+paths:
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip(): continue
                    value=json.loads(line)
                    if not isinstance(value,dict) or "stations" not in value:
                        raise ValueError("Invalid history record")
                    identity=json.dumps(value,sort_keys=True,ensure_ascii=False)
                    if identity not in seen:
                        records.append(value)
                        seen.add(identity)
        archive.mkdir(exist_ok=True)
        for path in paths:
            if (archive/path.name).exists():
                raise ValueError("History archive already exists; refusing overwrite")
        temporary=target.with_suffix(".jsonl.tmp")
        with temporary.open("w",encoding="utf-8",newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+"\n")
        temporary.replace(target)
        for path in paths:
            path.rename(archive/path.name)


def read_history(folder):
    result = []
    if folder.exists():
        for path in sorted(folder.glob("*.jsonl")):
            with path.open(encoding="utf-8") as stream:
                result.extend(json.loads(line) for line in stream if line.strip())
    return result


def append_json_line(path, value):
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def write_json(path, value):
    # One-shot single-process writer. Completed JSON serialization precedes replacement.
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    temporary.replace(path)


def add_source_comparisons(results):
    diagram_time = results["mizukan"]["source"].get("observed_at")
    county = results["chiba_suibo"]
    suspect_rows = []
    for row in county["stations"]:
        row["stale_suspect"] = False
        if diagram_time and row.get("observed_at"):
            seconds = abs((datetime.fromisoformat(row["observed_at"]) -
                           datetime.fromisoformat(diagram_time)).total_seconds())
            row["stale_suspect"] = seconds > 30 * 60
            if row["stale_suspect"]:
                suspect_rows.append({"station_id": row["id"], "county_observed_at": row["observed_at"],
                                     "mizukan_observed_at": diagram_time, "difference_minutes": seconds / 60})
    county["source"]["stale_suspect"] = bool(suspect_rows)
    return suspect_rows


def mismatches(rows, pairs):
    by_id = {row["id"]: row for row in rows}
    records = []
    for pair in pairs:
        primary, auxiliary = by_id[pair["primary"]], by_id[pair["auxiliary"]]
        if primary["status"] != "ok" or auxiliary["status"] != "ok":
            continue
        difference = Decimal(str(primary["level_m"])) - Decimal(str(auxiliary["level_m"]))
        if abs(difference) > Decimal("0.05"):
            records.append({"primary": primary["id"], "auxiliary": auxiliary["id"],
                            "primary_value": primary["level_m"], "auxiliary_value": auxiliary["level_m"],
                            "difference_m": float(difference),
                            "primary_observed_at": primary["observed_at"],
                            "auxiliary_observed_at": auxiliary["observed_at"]})
    return records


def run_once(root=ROOT, loader=load_source, now=None):
    config = read_json(root / "data/stations.json")
    thresholds = read_json(root / "data/thresholds.json")
    facility_codes = read_json(root / "data/facility_codes.json")
    out = root / "out"
    # Read/validate previous output before doing any network I/O. Never silently reset bad JSON.
    previous = read_json(out / "state.json") if (out / "state.json").exists() else {"stations": {}}
    if not isinstance(previous, dict) or not isinstance(previous.get("stations"), dict):
        raise ValueError("Invalid state.json")
    compact_history(out / "history")
    history = read_history(out / "history")
    results = {}
    for source, parser in (("mizukan", mizukan.parse), ("chiba_suibo", chiba_suibo.parse)):
        stations = [s for s in config["stations"] if s["source"] == source]
        urls = {s["source_url"] for s in stations}
        if len(urls) != 1:
            raise ValueError("Expected one URL per source")
        kwargs = {"facility_codes": facility_codes} if source == "mizukan" else {}
        results[source] = loader(next(iter(urls)), parser, stations, **kwargs)
    now = now or datetime.now(JST)
    suspects = add_source_comparisons(results)
    rows = [row for source in results.values() for row in source["stations"]]
    rows, state, events = evaluate(rows, thresholds, previous, now)
    for row in rows:
        row["delta_1h"] = delta_one_hour(row, history)
    latest = {"generated_at": now.isoformat(), "sources": {k: v["source"] for k, v in results.items()},
              "stations": rows, "facilities": results["mizukan"]["facilities"],
              "summary": summarize(rows, thresholds), "events": events}
    out.mkdir(exist_ok=True)
    (out / "history").mkdir(exist_ok=True)
    facility_path = out / "facility_log.csv"
    if latest["facilities"]:
        needs_header = not facility_path.exists() or facility_path.stat().st_size == 0
        with facility_path.open("a", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            if needs_header:
                writer.writerow(["observed_at", "order", "filename"])
            for facility in latest["facilities"]:
                writer.writerow([results["mizukan"]["source"]["observed_at"],
                                 facility["order"], facility["icon"]])
    for record in mismatches(rows, config["mismatch_pairs"]):
        append_json_line(out / "mismatch.log", {"generated_at": now.isoformat(), **record})
    for record in suspects:
        append_json_line(out / "stale_suspect.log", {"generated_at": now.isoformat(), **record})
    append_json_line(out / "history" / f"{now.astimezone(JST):%Y-%m}.jsonl",
                     {"generated_at": now.isoformat(), "stations": rows})
    write_json(out / "latest.json", latest)
    write_json(out / "state.json", state)
    return latest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", required=True)
    parser.parse_args()
    try:
        latest = run_once()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"inba-suii-bot: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(latest, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if latest["summary"]["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
