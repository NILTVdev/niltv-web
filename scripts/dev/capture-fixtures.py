# -*- coding: utf-8 -*-
"""Snapshot the dev API into <private data>/fixtures/api/ so the site runs
locally with ZERO AWS access (scripts/dev/serve.py answers /v1/* from it).

    python scripts/dev/capture-fixtures.py

The snapshot is private data and is never committed: every contributor
captures their own (the dev API is public-readable). The target folder is
NILTV_PRIVATE_DATA if set, else ../private-data/niltv-web next to the repo
(created on first run) - see DEVELOPING.md.
"""
import io, json, os, sys, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "builders"))
from private_data import private_path

API = "https://d1nm1d2txb83wa.cloudfront.net"
OUT = private_path("fixtures", "api", create=True)
UA = {"User-Agent": "niltv-fixture-capture"}

def get(path):
    req = urllib.request.Request(API + path, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def save(name, obj):
    path = os.path.join(OUT, name + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(obj, indent=1))
    return path

def main():
    home = get("/v1/home")
    save("home", home)
    channels = get("/v1/channels")
    save("channels", channels)
    save("events", get("/v1/events"))

    detail_ids = set()
    def walk(o):
        if isinstance(o, dict):
            cid = o.get("id")
            if isinstance(cid, str) and ("-" in cid) and not cid.startswith("ch-") and not cid.startswith("ev"):
                detail_ids.add(cid)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(home)

    ch_rows = channels.get("items") or channels.get("channels") or []
    for ch in ch_rows:
        cid = ch.get("id")
        if not cid:
            continue
        page = get("/v1/content?channelId=" + cid + "&limit=48")
        save("content/" + cid, page)
        for it in (page.get("items") or [])[:12]:
            detail_ids.add(it["id"])

    n = 0
    for did in sorted(detail_ids):
        try:
            save("detail/" + did, get("/v1/content/" + did))
            n += 1
        except Exception as e:
            print("  detail skip", did, e)
    print("fixtures: home, channels, events, %d channel pages, %d details -> %s"
          % (len(ch_rows), n, OUT))

if __name__ == "__main__":
    main()
