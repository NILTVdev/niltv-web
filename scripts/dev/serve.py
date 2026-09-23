# -*- coding: utf-8 -*-
"""Local NIL TV in one command - no AWS account, no keys, no build step.

    python scripts/dev/serve.py          # -> http://localhost:8787

Serves the committed site straight from the repo and answers the /v1/* API
from the fixture snapshots in the private data folder (<private>/fixtures/api/,
see capture-fixtures.py and DEVELOPING.md). Video and poster files stream
from the public dev CDN, so playback works locally too.

Notes for contributors:
  - /watch/* deep-link pages are generated at deploy time and are not in the
    repo; the in-page theater player covers video playback locally.
  - Sign-in is stubbed out locally (guest browsing is the full experience).
  - Newsletter signups return ok without writing anywhere.
"""
import io, json, os, re, sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "builders"))
from private_data import private_path, HOWTO

FIX = private_path("fixtures", "api")
PORT = 8787

LOCAL_CONFIG = """// local dev config (served by scripts/dev/serve.py)
window.NILTV_CONFIG = {
  apiBase: "",            // same-origin /v1/* answered from fixtures
  payoutsApi: "",
  cognito: { userPoolId: "", clientId: "" },  // sign-in stubbed locally
};
"""

def fixture(*parts):
    if not FIX:
        return None
    path = os.path.join(FIX, *parts) + ".json"
    if os.path.exists(path):
        return io.open(path, encoding="utf-8").read()
    return None

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        pass  # keep the console clean for beginners

    def send_json(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path.startswith("/v1/newsletter"):
            return self.send_json('{"status":"ok"}')
        return self.send_json('{"error":"NOT_AVAILABLE_LOCALLY"}', 501)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/config.js":
            data = LOCAL_CONFIG.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/v1/"):
            if path == "/v1/home":
                return self.send_json(fixture("home") or "{}")
            if path == "/v1/channels":
                return self.send_json(fixture("channels") or "{}")
            if path == "/v1/events":
                return self.send_json(fixture("events") or '{"events":[]}')
            m = re.match(r"^/v1/content/([^/]+)$", path)
            if m:
                body = fixture("detail", m.group(1))
                if body:
                    return self.send_json(body)
                # uncaptured id: synthesize the detail from pipeline conventions
                cid = m.group(1)
                return self.send_json(json.dumps({
                    "id": cid, "title": cid, "creator": "", "channelId": "",
                    "channelName": "", "likes": 0, "duration": 0, "provider": "fixture",
                    "description": "", "related": [],
                    "thumbUrl": "https://d1nm1d2txb83wa.cloudfront.net/video/%s/poster.jpg" % cid,
                    "playbackUrl": "https://d1nm1d2txb83wa.cloudfront.net/video/%s/master.mp4" % cid,
                }))
            if path == "/v1/content":
                q = self.path
                m = re.search(r"channelId=([^&]+)", q)
                if m:
                    body = fixture("content", m.group(1))
                    if body:
                        return self.send_json(body)
                return self.send_json('{"items":[]}')
            return self.send_json('{"error":"NOT_AVAILABLE_LOCALLY"}', 404)
        return super().do_GET()

if __name__ == "__main__":
    if not FIX or not os.path.isdir(FIX):
        print("no API fixtures: run  python scripts/dev/capture-fixtures.py  to snapshot the dev API "
              "into <private data>/fixtures/api/ (%s). Serving the static pages with an empty API." % HOWTO)
    print("NIL TV local  ->  http://localhost:%d   (Ctrl+C stops)" % PORT)
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
