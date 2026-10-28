from judge import evaluate, summarize
from datetime import datetime


def test_summary(thresholds):
    now = datetime.fromisoformat("2026-10-29T10:00:00+09:00")
    rows = [{"id": i, "level_m": 2.0, "observed_at": now.isoformat(), "status": "ok"}
            for i in thresholds]
    rows, _, _ = evaluate(rows, thresholds, {"stations": {}}, now)
    result = summarize(rows, thresholds)
    assert result == {"with_threshold": 3, "all_below": True, "fetched": 11, "failed": 0, "stale": 0}
    rows[0]["status"] = "fetch_failed"  # No threshold: does not block threshold summary.
    assert summarize(rows, thresholds)["all_below"] is True
    next(r for r in rows if r["id"] == "kitainba")["status"] = "stale"
    assert summarize(rows, thresholds)["all_below"] is None
    next(r for r in rows if r["id"] == "kaburagi")["level"] = "caution"
    assert summarize(rows, thresholds)["all_below"] is False


def test_missing_target_is_not_below(thresholds):
    assert summarize([], thresholds)["all_below"] is None
