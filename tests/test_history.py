from datetime import datetime, timedelta
import pytest
from judge import delta_one_hour

NOW = datetime.fromisoformat("2026-10-29T10:00:00+09:00")


def entry(age, value, status="ok", station_id="kaburagi"):
    return {"id": station_id, "observed_at": (NOW - timedelta(minutes=age)).isoformat(),
            "level_m": value, "status": status}


@pytest.mark.parametrize("age,expected", [(54, None), (55, 0.1), (60, 0.1), (65, 0.1), (66, None)])
def test_window(age, expected):
    assert delta_one_hour(entry(0, 2.1), [{"stations": [entry(age, 2.0)]}]) == expected


def test_nearest_valid_observation_not_fetch_time():
    history = [{"stations": [entry(55, 2.5), entry(61, 2.0), entry(60, 9, "stale"),
                             entry(60, 8, station_id="other")]}]
    assert delta_one_hour(entry(0, 2.1), history) == 0.1
    assert delta_one_hour(entry(0, 2.1, "stale"), history) is None
