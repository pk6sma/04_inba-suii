"""Shared strict decoding and one-shot retrieval (no retries or redirects)."""
import codecs
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))
USER_AGENT = "inba-suii-bot (contact: TBD)"


def decode_html(raw, headers):
    content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    header_match = re.search(r"charset\s*=\s*[\"']?([\w-]+)", content_type, re.I)
    soup = BeautifulSoup(raw.decode("ascii", errors="ignore"), "html.parser")
    declared = []
    if header_match:
        declared.append(header_match[1])
    for tag in soup.find_all("meta"):
        if tag.get("charset"):
            declared.append(tag["charset"])
        match = re.search(r"charset\s*=\s*([\w-]+)", tag.get("content", ""), re.I)
        if match:
            declared.append(match[1])
    if not declared:
        raise ValueError("No declared charset; refusing to guess")
    encodings = {codecs.lookup(name).name for name in declared}
    if len(encodings) != 1:
        raise ValueError("Conflicting charset declarations")
    encoding = encodings.pop()
    return raw.decode(encoding, errors="strict"), encoding


def retrieve(url):
    # requests defaults to zero adapter retries. Reject redirects, including HTTP->HTTPS.
    response = requests.get(url, headers={"User-Agent": USER_AGENT},
                            timeout=(10, 30), allow_redirects=False)
    fetched_at = datetime.now(JST)
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}; no redirect/retry attempted")
    html, encoding = decode_html(response.content, response.headers)
    return html, fetched_at, {"encoding": encoding, "response_bytes": len(response.content),
                             "http_status": response.status_code}


def station_row(station):
    return {key: station[key] for key in ("id", "name", "source")} | {
        "level_m": None, "status": "fetch_failed", "observed_at": None}


def freshness(observed_at, fetched_at):
    return "stale" if fetched_at - observed_at >= timedelta(minutes=90) else "ok"


def failed(stations, fetched_at, error):
    return {"source": {"observed_at": None, "fetched_at": fetched_at.isoformat(),
                       "status": "fetch_failed", "error": str(error)},
            "stations": [station_row(s) for s in stations], "facilities": []}


def load_source(url, parser, stations, **kwargs):
    fetched_at = datetime.now(JST)
    try:
        html, fetched_at, metadata = retrieve(url)
        result = parser(html, stations, fetched_at, **kwargs)
        result["source"].update(metadata)
        return result
    except (requests.RequestException, ValueError, LookupError) as exc:
        return failed(stations, fetched_at, exc)
