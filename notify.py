"""Event-only webhook delivery. Secrets are read only from environment variables."""
import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import requests

from sources.common import USER_AGENT

ROOT=Path(__file__).resolve().parent
FIELDS=["generated_at","event_key","status","attempt","http_status","error_type"]


def event_key(latest):
    raw=json.dumps({"generated_at":latest["generated_at"],"events":latest["events"]},
                   sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def log_result(root,latest,key,status,attempt=0,http_status="",error_type=""):
    path=Path(root)/"out/notify_log.csv"
    path.parent.mkdir(parents=True,exist_ok=True)
    header=not path.exists() or path.stat().st_size==0
    with path.open("a",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS)
        if header: writer.writeheader()
        writer.writerow(dict(generated_at=latest["generated_at"],event_key=key,status=status,
                             attempt=attempt,http_status=http_status,error_type=error_type))


def already_sent(root,key):
    path=Path(root)/"out/notify_log.csv"
    if not path.exists(): return False
    with path.open(encoding="utf-8",newline="") as stream:
        return any(row["event_key"]==key and row["status"]=="sent" for row in csv.DictReader(stream))


def raw_card_url(root,latest,environ):
    manifest_path=Path(root)/"out/card_manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["generated_at"]!=latest["generated_at"]:
        raise ValueError("Card manifest does not match latest")
    relative=manifest["cards"].get("event")
    if not relative or not re.fullmatch(r"out/cards/\d{8}-\d{4}-event\.png",relative):
        raise ValueError("Event card is not in manifest")
    if not (Path(root)/relative).is_file():
        raise ValueError("Event card file is missing")
    repository=environ.get("GITHUB_REPOSITORY","")
    revision=environ.get("CARD_REVISION","")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+",repository) or not re.fullmatch(r"[0-9a-fA-F]{40,64}",revision):
        raise ValueError("Published repository and commit revision are required")
    return f"https://raw.githubusercontent.com/{repository}/{revision}/{quote(relative,safe='/')}"


def build_payload(latest,card_url):
    return {"kind":"event","generated_at":latest["generated_at"],"events":latest["events"],
            "stations":[{k:s.get(k) for k in ("name","level_m","level","delta_1h","status")}
                        for s in latest["stations"]],
            "summary":latest["summary"],"card_url":card_url,"sources":latest["sources"]}


def notify(latest,root=ROOT,environ=None,poster=None,card_url=None):
    environ=os.environ if environ is None else environ
    root=Path(root)
    if not latest["events"]:
        return {"status":"no-events","attempts":0}
    key=event_key(latest)
    if already_sent(root,key):
        return {"status":"already-sent","attempts":0}
    url=environ.get("GROK_WEBHOOK_URL")
    secret=environ.get("GROK_WEBHOOK_KEY")
    if not url or not secret:
        log_result(root,latest,key,"dry-run")
        return {"status":"dry-run","attempts":0}
    try:
        resolved_url=card_url or raw_card_url(root,latest,environ)
    except (OSError,ValueError,KeyError,TypeError):
        log_result(root,latest,key,"failed",error_type="card-not-ready")
        return {"status":"failed","attempts":0}
    config_path=root/"config.json"
    config=json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    header=config.get("webhook",{}).get("header_name","X-Webhook-Key")
    if not re.fullmatch(r"[A-Za-z0-9-]+",header) or header.lower() in ("host","content-length","user-agent","content-type"):
        log_result(root,latest,key,"failed",error_type="invalid-header-name")
        return {"status":"failed","attempts":0}
    payload=build_payload(latest,resolved_url)
    post=poster or requests.post
    for attempt in (1,2):  # initial attempt plus at most ONE retry
        status_code=""
        error_type=""
        try:
            response=post(url,json=payload,headers={header:secret,"User-Agent":USER_AGENT},
                          timeout=(10,30),allow_redirects=False)
            status_code=response.status_code
            success=200<=status_code<300
        except requests.RequestException as exc:
            success=False
            # Never log exception strings: they may contain URL, credentials or response bodies.
            error_type=type(exc).__name__
        log_result(root,latest,key,"sent" if success else "failed",attempt,status_code,error_type)
        if success: return {"status":"sent","attempts":attempt}
    return {"status":"failed","attempts":2}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest",type=Path,default=ROOT/"out/latest.json")
    parser.add_argument("--card-url",help="Already-published public raw card URL (never a webhook URL)")
    args=parser.parse_args()
    latest=json.loads(args.latest.read_text(encoding="utf-8"))
    result=notify(latest,card_url=args.card_url)
    print(json.dumps(result))
    return 1 if result["status"]=="failed" else 0


if __name__=="__main__":
    raise SystemExit(main())
