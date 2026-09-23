# -*- coding: utf-8 -*-
"""Snapshot the channels-page marquee posters as LOCAL site assets
(the video CDN can stall or drop requests, which leaves black boxes in the
marquee, so the graphic is hard-coded instead of fetching 63 remote posters
at view time).

Reads the marquee ids straight out of channels_head in build-sections.py,
downloads each poster once, resizes to 2x display size, and writes
assets/img/chmq/{id}.jpg. The images are COMMITTED - the marquee then loads
same-origin, cache-friendly, and deploys atomically with the page. Rerun
after editing the marquee's id list, then rebuild + promote + deploy.
"""
import io, os, re, urllib.request
from PIL import Image

CDN = "https://d1nm1d2txb83wa.cloudfront.net"
HERE = os.path.dirname(os.path.abspath(__file__))
BUILDER = os.path.join(HERE, "build-sections.py")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "assets", "img", "chmq"))
TARGET_H = 360  # 2x the tallest rail card (180px desktop)

def main():
    t = io.open(BUILDER, encoding="utf-8").read()
    i = t.find("channels_head")
    seg = t[i:t.find("</style></section>", i)]
    ids = sorted(set(re.findall(r'/(?:video)/([^/]+)/poster\.jpg', seg)) |
                 set(re.findall(r'/assets/img/chmq/([^."]+)\.jpg', seg)))
    if not ids:
        raise SystemExit("no marquee ids found in channels_head - abort")
    os.makedirs(OUT_DIR, exist_ok=True)
    print("marquee ids: %d" % len(ids))
    for vid in ids:
        dst = os.path.join(OUT_DIR, vid + ".jpg")
        try:
            with urllib.request.urlopen("%s/video/%s/poster.jpg" % (CDN, vid), timeout=30) as r:
                im = Image.open(io.BytesIO(r.read())).convert("RGB")
            w = int(round(im.width * TARGET_H / im.height))
            im = im.resize((w, TARGET_H), Image.LANCZOS)
            im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)
            print("wrote %s (%dx%d, %dKB)" % (os.path.basename(dst), w, TARGET_H,
                                              os.path.getsize(dst) // 1024))
        except Exception as e:
            if os.path.exists(dst):
                print("KEEP existing %s (refresh failed: %s)" % (os.path.basename(dst), e))
            else:
                raise SystemExit("no local copy for %s and download failed: %s" % (vid, e))
    print("done: %d posters in %s" % (len(ids), OUT_DIR))

if __name__ == "__main__":
    main()
