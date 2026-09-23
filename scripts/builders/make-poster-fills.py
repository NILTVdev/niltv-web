# -*- coding: utf-8 -*-
"""Detect letterboxed posters (16:9 content baked into a 9:16 canvas with
black bars - typical for Singing Star audition submissions) and publish a
cropped poster-fill.jpg beside each so cards can fill edge to edge.

Rerunnable: skips ids already in poster-fills.json. New content: run this,
commit the updated json, redeploy. Uploads via the aws CLI to the dev video
bucket (same origin CloudFront serves).

Usage: python scripts/builders/make-poster-fills.py [--limit N]
"""
import io, os, json, subprocess, sys, tempfile, urllib.request
from PIL import Image

CDN = "https://d1nm1d2txb83wa.cloudfront.net"
BUCKET = "s3://niltv-dev-video-hls-858321320457"
HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "poster-fills.json")
LIB_URL = CDN + "/v1/channels"

BAR_LUMA = 16        # rows darker than this count as bar rows
MIN_BAR_FRAC = 0.12  # bars must eat at least this much of top AND bottom

def rows_mean(img):
    g = img.convert("L")
    w, h = g.size
    px = g.load()
    step = max(1, w // 64)
    means = []
    for y in range(h):
        s = 0; c = 0
        for x in range(0, w, step):
            s += px[x, y]; c += 1
        means.append(s / c)
    return means

def content_band(img):
    means = rows_mean(img)
    h = len(means)
    top = 0
    while top < h and means[top] < BAR_LUMA:
        top += 1
    bot = h - 1
    while bot > top and means[bot] < BAR_LUMA:
        bot -= 1
    return top, bot + 1

def fetch_ids():
    def get(url):
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    ids = []
    for ch in get(LIB_URL)["channels"]:
        cursor = ""
        while True:
            u = "%s/v1/content?channelId=%s&limit=48%s" % (CDN, ch["id"],
                "&cursor=" + urllib.parse.quote(cursor) if cursor else "")
            page = get(u)
            ids += [it["id"] for it in page.get("items", [])]
            cursor = page.get("cursor") or ""
            if not cursor:
                break
    return ids

def main():
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    done = json.load(open(REG, encoding="utf-8")) if os.path.exists(REG) else []
    done_set = set(done)
    ids = fetch_ids()
    print("library: %d items, already filled: %d" % (len(ids), len(done)))
    made = 0
    for vid in ids:
        if vid in done_set:
            continue
        try:
            with urllib.request.urlopen("%s/video/%s/poster.jpg" % (CDN, vid), timeout=30) as r:
                raw = r.read()
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            print("skip %s (%s)" % (vid, e))
            continue
        w, h = img.size
        top, bot = content_band(img)
        if top < h * MIN_BAR_FRAC or (h - bot) < h * MIN_BAR_FRAC:
            continue  # not letterboxed
        if bot - top < h * 0.15:
            continue  # nearly black poster - a crop would be garbage
        crop = img.crop((0, max(0, top - 2), w, min(h, bot + 2)))
        tmp = os.path.join(tempfile.gettempdir(), vid + "-fill.jpg")
        crop.save(tmp, "JPEG", quality=85, optimize=True)
        dest = "%s/video/%s/poster-fill.jpg" % (BUCKET, vid)
        subprocess.run(["aws", "s3", "cp", tmp, dest, "--content-type", "image/jpeg",
                        "--cache-control", "public, max-age=31536000, immutable"],
                       check=True, capture_output=True)
        os.remove(tmp)
        done.append(vid)
        done_set.add(vid)
        made += 1
        print("filled %s (bars %d+%d of %d)" % (vid, top, h - bot, h))
        if limit and made >= limit:
            break
    json.dump(sorted(done), open(REG, "w", encoding="utf-8"), indent=1)
    print("new fills: %d, registry total: %d" % (made, len(done)))

if __name__ == "__main__":
    main()
