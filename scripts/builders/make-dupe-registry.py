# -*- coding: utf-8 -*-
"""Build poster-dupes.json: {duplicate_id: canonical_id} for videos that exist
under more than one content id (network cross-posts: the same reel on a campus
channel and on NIL TV). Detection: 16x16 average-hash over every poster; exact
hash groups plus a seeded list of known pairs. Canonical = the tbtv- (origin
channel) id when present, else the first seen.

Rerunnable; always rebuilds from the live library. Run after big ingests,
commit the json, redeploy.
"""
import io, os, json, urllib.request, urllib.parse
from PIL import Image

CDN = "https://d1nm1d2txb83wa.cloudfront.net"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "poster-dupes.json")

# known cross-post pairs - kept even if hashing misses them
SEED = {
    "ig-18097067524824632": "tbtv-DWHuvl3E_l_",
    "ig-18080547344300580": "tbtv-DYIovnpTmNP",
    "ig-17961107955069130": "tbtv-DW4wt_Ykx1v",
    "ig-18106477720644121": "tbtv-DSV9A9xDlrt",
    "ig-18004278872730304": "tbtv-DXkzKyDE6HE",
    "ig-18095410385039503": "tbtv-DWSJMWrjoCT",
}

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_ids():
    ids = []
    for ch in get(CDN + "/v1/channels")["channels"]:
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

def ahash(img):
    g = img.convert("L").resize((16, 16), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / len(px)
    return "".join("1" if p > avg else "0" for p in px)

def canonical(group):
    tb = [i for i in group if i.startswith("tbtv-")]
    return tb[0] if tb else group[0]

def main():
    ids = fetch_ids()
    print("library: %d items" % len(ids))
    groups = {}
    for n, vid in enumerate(ids):
        try:
            with urllib.request.urlopen("%s/video/%s/poster.jpg" % (CDN, vid), timeout=30) as r:
                h = ahash(Image.open(io.BytesIO(r.read())))
            groups.setdefault(h, []).append(vid)
        except Exception as e:
            print("skip %s (%s)" % (vid, e))
        if (n + 1) % 100 == 0:
            print("hashed %d/%d" % (n + 1, len(ids)))
    dupes = dict(SEED)
    for h, group in groups.items():
        if len(group) < 2:
            continue
        c = canonical(group)
        for vid in group:
            if vid != c:
                dupes[vid] = c
                print("dupe: %s -> %s" % (vid, c))
    json.dump(dupes, open(OUT, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print("registry: %d duplicate ids" % len(dupes))

if __name__ == "__main__":
    main()
