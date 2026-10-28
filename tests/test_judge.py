from datetime import datetime, timedelta
from copy import deepcopy

import pytest
from judge import classify, evaluate

NOW = datetime.fromisoformat("2026-10-29T10:00:00+09:00")


def row(value, status="ok", station_id="kaburagi"):
    return {"id": station_id, "level_m": value, "status": status, "observed_at": NOW.isoformat()}


def initial(value, thresholds):
    return evaluate([row(value)], thresholds, {"stations": {}}, NOW)[1]


@pytest.mark.parametrize("value,expected", [(3.49, "normal"), (3.50, "standby"),
    (3.99, "standby"), (4.00, "caution"), (4.01, "caution"), (4.80, "design")])
def test_boundaries(thresholds, value, expected):
    assert classify(value, thresholds["kaburagi"]) == expected


def test_up_down_and_first_sample(thresholds):
    assert evaluate([row(4.01)], thresholds, {"stations": {}}, NOW)[2] == []
    previous = initial(3.99, thresholds)
    rows, state, events = evaluate([row(4.00)], thresholds, previous, NOW + timedelta(minutes=1))
    assert events[0]["direction"] == "up"
    assert events[0]["old_level"] == "standby"
    assert events[0]["new_level"] == "caution"
    assert events[0]["crossed_thresholds"][0]["value"] == 4.0
    assert rows[0]["trend"] == "up"
    rows, _, events = evaluate([row(3.99)], thresholds, state, NOW + timedelta(minutes=32))
    assert events[0]["direction"] == "down"
    assert rows[0]["trend"] == "down"


def test_cooldown_updates_level_but_not_event_clock(thresholds):
    previous = initial(3.99, thresholds)
    _, state, first = evaluate([row(4.01)], thresholds, previous, NOW)
    assert len(first) == 1
    _, state, events = evaluate([row(3.99)], thresholds, state, NOW + timedelta(minutes=10))
    assert events == []
    assert state["stations"]["kaburagi"]["level"] == "standby"
    _, state, events = evaluate([row(4.01)], thresholds, state, NOW + timedelta(minutes=30))
    assert events == []
    _, _, events = evaluate([row(3.99)], thresholds, state, NOW + timedelta(minutes=31))
    assert len(events) == 1


@pytest.mark.parametrize("status", ["fetch_failed", "stale"])
def test_unavailable_retains_previous(thresholds, status):
    previous = initial(4.01, thresholds)
    untouched = deepcopy(previous)
    rows, state, events = evaluate([row(None, status)], thresholds, previous, NOW + timedelta(minutes=10))
    assert state["stations"] == previous["stations"]
    assert previous == untouched
    assert events == []
    assert rows[0]["level"] is None and rows[0]["trend"] is None


def test_equal_thresholds_and_multiple_boundaries_one_event(thresholds):
    previous = initial(3.49, thresholds)
    _, _, events = evaluate([row(4.80)], thresholds, previous, NOW)
    assert len(events) == 1
    assert [b["level"] for b in events[0]["crossed_thresholds"]] == ["standby", "caution", "danger", "design"]


def test_guidance_and_reference_not_used(thresholds):
    assert classify(2.65, thresholds["kitainba"]) == "normal"
    assert classify(2.80, thresholds["kitainba"]) == "standby"
    assert classify(4.25, thresholds["kitainba"]) == "design"
    assert classify(9, thresholds["inba_average"]) == "no_threshold"
    assert classify(9, None) == "no_threshold"
