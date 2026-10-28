import csv
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from inba_watch import run_once, add_source_comparisons, mismatches
from sources.common import failed, load_source
from sources import mizukan, chiba_suibo

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp_path):
    (tmp_path / "data").mkdir()
    for filename in ("stations.json", "thresholds.json", "facility_codes.json"):
        (tmp_path / "data" / filename).write_bytes((ROOT / "data" / filename).read_bytes())


def fixture_loader(fixture_data, county_failed=False):
    def load(url, parser, stations, **kwargs):
        source = stations[0]["source"]
        html, fetched, _ = fixture_data(source)
        if county_failed and source == "chiba_suibo":
            return failed(stations, fetched, "offline test failure")
        return parser(html, stations, fetched, **kwargs)
    return load


def test_run_twice_and_failure_preserves_state(tmp_path, fixture_data):
    prepare(tmp_path)
    now = datetime.fromisoformat("2026-10-29T03:53:00+09:00")
    first = run_once(tmp_path, loader=fixture_loader(fixture_data), now=now)
    assert first["summary"]["fetched"] == 11
    assert first["summary"]["with_threshold"] == 3
    assert first["summary"]["all_below"] is True
    assert first["events"] == []
    assert all(s["trend"] is None and s["delta_1h"] is None for s in first["stations"])
    assert not (tmp_path / "out/mismatch.log").exists()
    state = json.loads((tmp_path / "out/state.json").read_text(encoding="utf-8"))
    second = run_once(tmp_path, loader=fixture_loader(fixture_data, True), now=now + timedelta(minutes=1))
    after = json.loads((tmp_path / "out/state.json").read_text(encoding="utf-8"))
    for station_id in ("kaburagi", "kitainba", "nishiinba"):
        assert state["stations"][station_id] == after["stations"][station_id]
    assert second["summary"]["all_below"] is None
    assert second["summary"]["failed"] == 3
    with (tmp_path / "out/facility_log.csv").open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.reader(stream))) == 15  # header + 7 + 7
    assert len((tmp_path / "out/history/2026-10.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    assert json.loads((tmp_path / "out/latest.json").read_text(encoding="utf-8")) == second


def test_comparison_flags_do_not_change_status(config, fixture_data):
    results = {}
    for source, parser in (("mizukan", mizukan.parse), ("chiba_suibo", chiba_suibo.parse)):
        html, fetched, _ = fixture_data(source)
        results[source] = parser(html, [s for s in config["stations"] if s["source"] == source], fetched)
    row = results["chiba_suibo"]["stations"][0]
    row["observed_at"] = "2026-10-29T03:10:00+09:00"
    assert add_source_comparisons(results) == []
    row["observed_at"] = "2026-10-29T03:09:00+09:00"
    assert len(add_source_comparisons(results)) == 1
    assert row["status"] == "ok" and row["stale_suspect"] is True


def test_mismatch_strictly_greater_than_point_zero_five():
    rows = [{"id": "a", "level_m": 2.05, "status": "ok", "observed_at": "time"},
            {"id": "b", "level_m": 2, "status": "ok", "observed_at": "time"}]
    pairs = [{"primary": "a", "auxiliary": "b"}]
    assert mismatches(rows, pairs) == []
    rows[0]["level_m"] = 2.06
    assert mismatches(rows, pairs)[0]["difference_m"] == 0.06
    rows[0]["status"] = "stale"
    assert mismatches(rows, pairs) == []


def test_corrupt_state_stops_before_network(tmp_path):
    prepare(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out/state.json").write_text("broken", encoding="utf-8")
    def unexpected(*args, **kwargs):
        raise AssertionError("Must not fetch")
    with pytest.raises(ValueError):
        run_once(tmp_path, loader=unexpected)


def test_request_no_retry_no_redirect(monkeypatch, config):
    import requests
    calls = []
    class Response:
        status_code = 302
    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()
    monkeypatch.setattr(requests, "get", get)
    stations = [s for s in config["stations"] if s["source"] == "chiba_suibo"]
    result = load_source(stations[0]["source_url"], chiba_suibo.parse, stations)
    assert len(calls) == 1
    assert calls[0][0][0].startswith("http://")
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["headers"]["User-Agent"] == "inba-suii-bot (contact: TBD)"
    assert all(r["status"] == "fetch_failed" for r in result["stations"])
