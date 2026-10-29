import json
from pathlib import Path

import pytest
import requests
from notify import notify,build_payload,raw_card_url

ROOT=Path(__file__).resolve().parents[1]


def latest(kind="event"):
    return json.loads((ROOT/f"tests/fixtures/latest_{kind}.json").read_text(encoding="utf-8"))


def forbidden(*args,**kwargs):
    raise AssertionError("Must not send")


def test_empty_events_no_send(tmp_path):
    assert notify(latest("regular"),tmp_path,{},forbidden)["status"]=="no-events"


@pytest.mark.parametrize("env",[{},{"GROK_WEBHOOK_URL":"https://test.invalid/hook"},
                                  {"GROK_WEBHOOK_KEY":"test-only"}])
def test_missing_environment_dry_run(tmp_path,env):
    result=notify(latest(),tmp_path,env,forbidden)
    assert result=={"status":"dry-run","attempts":0}
    assert "dry-run" in (tmp_path/"out/notify_log.csv").read_text()


def test_payload_is_exact_subset_no_prose():
    data=latest()
    payload=build_payload(data,"https://raw.githubusercontent.com/example/repo/commit/card.png")
    assert payload["events"]==data["events"]
    assert payload["summary"]==data["summary"]
    assert payload["sources"]==data["sources"]
    assert len(payload["stations"])==11
    for source,row in zip(data["stations"],payload["stations"]):
        assert row=={k:source[k] for k in ("name","level_m","level","delta_1h","status")}
    assert set(payload)=={"kind","generated_at","events","stations","summary","card_url","sources"}


def test_one_retry_success_and_idempotent_log(tmp_path):
    calls=[]
    class Response:
        def __init__(self,code): self.status_code=code
    def post(url,**kwargs):
        calls.append((url,kwargs))
        return Response(503 if len(calls)==1 else 204)
    env={"GROK_WEBHOOK_URL":"https://test.invalid/private-hook","GROK_WEBHOOK_KEY":"test-secret"}
    result=notify(latest(),tmp_path,env,post,card_url="https://raw.githubusercontent.com/x/y/rev/card.png")
    assert result=={"status":"sent","attempts":2}
    for _, request in calls:
        assert request["headers"]["Authorization"]=="Bearer test-secret"
        assert "X-Webhook-Key" not in request["headers"]
    assert calls[0][1]["allow_redirects"] is False
    assert notify(latest(),tmp_path,env,forbidden)["status"]=="already-sent"
    log=(tmp_path/"out/notify_log.csv").read_text()
    assert "test-secret" not in log and "private-hook" not in log


def test_timeout_retry_limit_and_no_secret_leak(tmp_path):
    calls=[]
    def post(*args,**kwargs):
        calls.append(1)
        raise requests.Timeout("https://test.invalid/secret-sensitive-url")
    env={"GROK_WEBHOOK_URL":"https://test.invalid/hook","GROK_WEBHOOK_KEY":"test-secret"}
    assert notify(latest(),tmp_path,env,post,card_url="public-card") == {"status":"failed","attempts":2}
    assert len(calls)==2
    assert "sensitive" not in (tmp_path/"out/notify_log.csv").read_text()


def test_real_send_requires_published_card(tmp_path):
    env={"GROK_WEBHOOK_URL":"https://test.invalid/hook","GROK_WEBHOOK_KEY":"test-secret"}
    assert notify(latest(),tmp_path,env,forbidden)["status"]=="failed"


def test_immutable_raw_url_from_manifest(tmp_path):
    data=latest()
    (tmp_path/"out/cards").mkdir(parents=True)
    card="out/cards/20261029-0404-event.png"
    (tmp_path/card).write_bytes(b"test")
    path=tmp_path/"out/card_manifest.json"
    path.write_text(json.dumps({"generated_at":data["generated_at"],"cards":{"event":card}}))
    env={"GITHUB_REPOSITORY":"example/repo","CARD_REVISION":"a"*40}
    assert raw_card_url(tmp_path,data,env)==f"https://raw.githubusercontent.com/example/repo/{'a'*40}/{card}"
    data["generated_at"]="different"
    with pytest.raises(ValueError): raw_card_url(tmp_path,data,env)
