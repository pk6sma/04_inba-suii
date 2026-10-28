from datetime import datetime, timedelta
import pytest

from sources.chiba_suibo import parse, infer_observed_at


def test_fixture(config, fixture_data):
    html, fetched_at, encoding = fixture_data("chiba_suibo")
    result = parse(html, [s for s in config["stations"] if s["source"] == "chiba_suibo"], fetched_at)
    assert encoding == "shift_jis"
    assert result["source"]["observed_date_inferred"] is True
    assert result["source"]["fetched_at"] == fetched_at.isoformat()
    assert [r["level_m"] for r in result["stations"]] == [2.21, 2.00, 2.03]
    assert all(r["observed_at"] == "2026-10-29T03:40:00+09:00" for r in result["stations"])
    assert all(r["status"] == "ok" for r in result["stations"])


@pytest.mark.parametrize("hhmm,expected", [("23:50", "2026-10-28T23:50:00+09:00"),
                                          ("00:07", "2026-10-29T00:07:00+09:00"),
                                          ("00:08", "2026-10-28T00:08:00+09:00")])
def test_midnight(hhmm, expected):
    fetched = datetime.fromisoformat("2026-10-29T00:02:00+09:00")
    assert infer_observed_at(hhmm, fetched).isoformat() == expected


@pytest.mark.parametrize("minutes,status", [(89, "ok"), (90, "stale"), (91, "stale")])
def test_freshness(config, fixture_data, minutes, status):
    html, _, _ = fixture_data("chiba_suibo")
    fetched = datetime.fromisoformat("2026-10-29T03:40:00+09:00") + timedelta(minutes=minutes)
    result = parse(html, [s for s in config["stations"] if s["source"] == "chiba_suibo"], fetched)
    assert all(r["status"] == status for r in result["stations"])


def test_one_station_missing_does_not_borrow_other_values(config, fixture_data):
    html, fetched, _ = fixture_data("chiba_suibo")
    result = parse(html.replace(">鏑木橋<", ">別の橋<"),
                   [s for s in config["stations"] if s["source"] == "chiba_suibo"], fetched)
    assert result["stations"][0]["status"] == "fetch_failed"
    assert all(r["status"] == "ok" for r in result["stations"][1:])
