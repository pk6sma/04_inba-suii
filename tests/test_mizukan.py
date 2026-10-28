from bs4 import BeautifulSoup
from sources.mizukan import parse


def test_fixture(config, fixture_data):
    html, fetched_at, encoding = fixture_data("mizukan")
    result = parse(html, [s for s in config["stations"] if s["source"] == "mizukan"], fetched_at)
    assert encoding == "shift_jis"
    assert result["source"]["status"] == "ok"
    assert result["source"]["observed_at"] == "2026-10-29T03:40:00+09:00"
    assert [r["level_m"] for r in result["stations"]] == [0.91, 0.98, 2.15, 4.25, 0.32, 2.01, 2.00, 2.03]
    assert len(result["facilities"]) == 7
    assert all(f["state"] == "unknown" for f in result["facilities"])


def test_seven_values_fails_all(config, fixture_data):
    html, fetched_at, _ = fixture_data("mizukan")
    soup = BeautifulSoup(html, "html.parser")
    soup.select("div.data")[-1].decompose()
    result = parse(str(soup), [s for s in config["stations"] if s["source"] == "mizukan"], fetched_at)
    assert len(result["stations"]) == 8
    assert all(r["status"] == "fetch_failed" and r["level_m"] is None for r in result["stations"])


def test_bad_time_fails_all(config, fixture_data):
    html, fetched_at, _ = fixture_data("mizukan")
    result = parse(html.replace("2026年10月29日03時40分", "時刻不明"),
                   [s for s in config["stations"] if s["source"] == "mizukan"], fetched_at)
    assert all(r["status"] == "fetch_failed" for r in result["stations"])
