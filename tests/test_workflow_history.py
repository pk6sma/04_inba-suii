import json
from pathlib import Path
from inba_watch import compact_history,read_history

ROOT=Path(__file__).resolve().parents[1]


def test_legacy_daily_history_migrates_without_losing_source(tmp_path):
    folder=tmp_path/"out/history"
    folder.mkdir(parents=True)
    first={"generated_at":"2026-10-29T03:40:00+09:00","stations":[]}
    second={"generated_at":"2026-10-29T03:50:00+09:00","stations":[]}
    daily=folder/"2026-10-29.jsonl"
    original=json.dumps(first)+"\n"+json.dumps(second)+"\n"
    daily.write_text(original,encoding="utf-8")
    (folder/"2026-10.jsonl").write_text(json.dumps(first)+"\n",encoding="utf-8")
    compact_history(folder)
    assert sorted(p.name for p in folder.iterdir())==["2026-10.jsonl"]
    assert read_history(folder)==[first,second]
    assert (tmp_path/"out/history_archive/2026-10-29.jsonl").read_text(encoding="utf-8")==original
    compact_history(folder)
    assert read_history(folder)==[first,second]


def test_workflow_keeps_runtime_outputs_and_secrets_scoped():
    text=(ROOT/".github/workflows/watch.yml").read_text()
    assert "*/10 * * * *" in text
    assert "group: watch" in text and "cancel-in-progress: false" in text
    assert "TZ: Asia/Tokyo" in text
    assert text.index("Publish output before notifying")<text.index("Notify event webhook")<text.index("Save notification log")
    assert 'code" -ne 2' in text
    assert "git add -f -- out/" in text
    assert "secrets.GROK_WEBHOOK_URL" in text and "secrets.GROK_WEBHOOK_KEY" in text
    assert "CARD_REVISION:" in text
    assert "contents: write" in text
