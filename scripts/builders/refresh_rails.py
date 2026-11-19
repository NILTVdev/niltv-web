# -*- coding: utf-8 -*-
"""Refresh the live rails in the committed pages from the content API.

deploy.ps1 runs this on every deploy, so the rails that are meant to follow
new uploads do, without regenerating whole pages. It rewrites only the cards
inside these rails and leaves every other byte of the page alone:

  featured/index.html  "New This Week": the newest clips on the network, then
                       recent clips spread across channels (at most 2 per
                       channel). Clips shown elsewhere on the page are skipped.
  channels/index.html  every channel rail (the ones with a See All link to
                       /channels/<slug>/): that channel's newest clips, as
                       many as channels-hub.json "count" says.

The hand-picked rails (homepage Trending, Sponsored, the category rails,
Featured's Media Day / Gear Drops / Day in the Life) are not touched; they
change by editing their data files.

If the API cannot be read, or a rail would come out shorter than its floor,
that rail keeps the cards it has: a refresh never ships an empty rail and
never blocks a deploy. A page whose rail can no longer be found is a real
mismatch between this script and the page, so that exits 1 (CI catches it).

Card markup matches build-sections.py reel_cell, with the dev CDN in poster
URLs like every committed page; the prod sweep rewrites them.

Usage: python refresh_rails.py <site_root> [--api URL] [--dry-run]
"""
import io, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_CDN = "https://d1nm1d2txb83wa.cloudfront.net"
# The network feed is campus channels + NIL TV. NIL Star competition clips
# stay on the competitions page; esports is hidden from the web.
NETWORK_SKIP = {"ch-nilstar", "ch-esports"}
# channel id -> page slug (same rule as build-pages.mjs CHANNEL_SLUGS)
SLUG_OVERRIDES = {"ch-trueblue": "truebluetv"}

FEATURED_NEW = 10       # newest first
FEATURED_SPREAD = 8     # then channel-diverse picks
FEATURED_FLOOR = 8      # fewer than this and the rail keeps its cards
SPREAD_DAYS = 21
SPREAD_PER_CHANNEL = 2


def _load_json(name, default):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return default
    return json.load(io.open(p, encoding="utf-8-sig"))


POSTER_FILLS = set(_load_json("poster-fills.json", []))
POSTER_DUPES = _load_json("poster-dupes.json", {})
HUB = _load_json("channels-hub.json", {})


def canon(vid):
    return POSTER_DUPES.get(vid, vid)


def slug_for(cid):
    return SLUG_OVERRIDES.get(cid, cid[3:] if cid.startswith("ch-") else cid)


# ---------- card markup (mirrors build-sections.py) ----------
_dash_sep = re.compile(u"\\s+[-\\u2013\\u2014]+\\s+")


def clean_title(t):
    t = (t or "").split("\n")[0]
    t = " ".join(w for w in t.split() if not w.startswith("#") and not w.startswith("@"))
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").strip(" -|")
    t = (t[:63].rstrip() + "...") if len(t) > 64 else (t or "Watch on NIL TV")
    return _dash_sep.sub(", ", t)


def fmt_dur(s):
    if not s:
        return None
    s = int(round(s))
    return "%d:%02d" % (s // 60, s % 60)


def poster_url(vid):
    return "%s/video/%s/poster%s.jpg" % (DEV_CDN, vid, "-fill" if vid in POSTER_FILLS else "")


def reel_cell(it, tag=None):
    title = clean_title(it.get("title"))
    extra = ""
    if tag:
        extra += '\n        <span class="tile-tag">%s</span>' % tag
    dur = fmt_dur(it.get("duration"))
    if dur:
        extra += '\n        <span class="dur">%s</span>' % dur
    aq = title.replace('"', "&quot;")
    return '''    <div class="reel-cell">
      <a class="card card-reel" href="/watch/%s/" aria-label="%s">
        <img src="%s" loading="lazy" decoding="async" alt="%s">%s
      </a>
      <p class="reel-caption">%s</p>
    </div>''' % (it["id"], aq, poster_url(it["id"]), aq, extra, title)


def days_old(it, now):
    try:
        p = datetime.strptime((it.get("publishedAt") or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return (now - p).days
    except ValueError:
        return 9999


# ---------- picking ----------
def network_feed(by_channel):
    """Every channel's clips in one list, newest first, one card per video."""
    pool = []
    for cid, items in by_channel.items():
        if cid in NETWORK_SKIP:
            continue
        pool.extend(items)
    pool.sort(key=lambda i: i.get("publishedAt") or "", reverse=True)
    seen, out = set(), []
    for it in pool:
        k = canon(it["id"])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def featured_picks(feed, exclude, now):
    """The newest clips, then recent clips spread across channels."""
    ex = {canon(v) for v in exclude}
    newest = []
    for it in feed:
        if canon(it["id"]) in ex:
            continue
        newest.append(it)
        ex.add(canon(it["id"]))
        if len(newest) >= FEATURED_NEW:
            break
    spread, per = [], {}
    # each pass looser than the last, so the rail fills even on a quiet week
    for max_days, cap in ((SPREAD_DAYS, SPREAD_PER_CHANNEL), (9999, SPREAD_PER_CHANNEL), (9999, 99)):
        for it in feed:
            if len(spread) >= FEATURED_SPREAD:
                break
            k, ch = canon(it["id"]), it.get("channelId", "")
            if k in ex or days_old(it, now) > max_days or per.get(ch, 0) >= cap:
                continue
            per[ch] = per.get(ch, 0) + 1
            ex.add(k)
            spread.append(it)
    return newest, spread


# ---------- page surgery ----------
SECTION_RE = re.compile(r'<section class="shelf"[^>]*>.*?</section>', re.S)
RAIL_RE = re.compile(r'(<div class="rail[^"]*">\n)(.*?)(\n  </div>\n</section>)$', re.S)
CARD_ID_RE = re.compile(r'/(?:video|watch)/([A-Za-z0-9_\-]+)/')


def replace_rail(section, cells):
    m = RAIL_RE.search(section)
    if not m:
        raise ValueError("rail markup not found")
    return section[:m.start(2)] + "\n".join(cells) + section[m.end(2):]


def refresh_featured(html, feed, now):
    secs = [m for m in SECTION_RE.finditer(html)
            if re.search(r'<h2 class="shelf-title[^"]*">New This Week</h2>', m.group(0))]
    if len(secs) != 1:
        raise ValueError("featured: expected one New This Week rail, found %d" % len(secs))
    m = secs[0]
    rest = html[:m.start()] + html[m.end():]
    newest, spread = featured_picks(feed, set(CARD_ID_RE.findall(rest)), now)
    picks = newest + spread
    if len(picks) < FEATURED_FLOOR:
        return html, "featured New This Week: only %d clips, kept the current cards" % len(picks)
    cells = [reel_cell(it, "Just Added" if (i == 0 and days_old(it, now) <= 7) else None)
             for i, it in enumerate(picks)]
    sec = replace_rail(m.group(0), cells)
    return html[:m.start()] + sec + html[m.end():], "featured New This Week: %d cards (newest %s)" % (
        len(cells), (picks[0].get("publishedAt") or "")[:10])


def refresh_channels(html, by_channel, now):
    count = int(HUB.get("count", 12))
    floor = int(HUB.get("minVideos", 7))
    slug_to_cid = {slug_for(cid): cid for cid in by_channel}
    notes, out, last, found = [], [], 0, 0
    for m in SECTION_RE.finditer(html):
        sec = m.group(0)
        s = re.search(r'class="shelf-logo"', sec) and re.search(r'<a class="shelf-all" href="/channels/([a-z0-9-]+)/">', sec)
        if not s:
            continue
        found += 1
        slug = s.group(1)
        cid = slug_to_cid.get(slug)
        items = by_channel.get(cid, []) if cid else []
        seen, picks = set(), []
        for it in items:  # the API lists a channel newest first
            k = canon(it["id"])
            if k not in seen:
                seen.add(k)
                picks.append(it)
            if len(picks) >= count:
                break
        if len(picks) < floor:
            notes.append("channels %s: only %d clips, kept the current cards" % (slug, len(picks)))
            continue
        cells = [reel_cell(it, "New Episode" if (i == 0 and days_old(it, now) <= 14) else None)
                 for i, it in enumerate(picks)]
        out.append(html[last:m.start()])
        out.append(replace_rail(sec, cells))
        last = m.end()
        notes.append("channels %s: %d cards (newest %s)" % (slug, len(cells), (picks[0].get("publishedAt") or "")[:10]))
    if not found:
        raise ValueError("channels: no channel rails found")
    out.append(html[last:])
    return "".join(out), notes


# ---------- API ----------
def fetch_json(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def load_api(api, per_channel=48):
    """{channel id: newest clips} for every channel the API lists."""
    chans = fetch_json(api + "/v1/channels").get("channels") or []
    if not chans:
        raise RuntimeError("/v1/channels returned no channels")
    out = {}
    for ch in chans:
        q = urllib.parse.urlencode({"channelId": ch["id"], "limit": per_channel})
        out[ch["id"]] = [it for it in fetch_json(api + "/v1/content?" + q).get("items") or []
                         if not it["id"].startswith("c-")]  # seed fixtures never ship
    return out


def main(argv):
    root = argv[1]
    api = argv[argv.index("--api") + 1] if "--api" in argv else DEV_CDN
    dry = "--dry-run" in argv
    try:
        by_channel = load_api(api.rstrip("/"))
    except Exception as e:  # network, JSON, empty list: keep every rail as it is
        print("refresh-rails: API unreadable (%s); every rail keeps its current cards" % e)
        return 0
    now = datetime.now(timezone.utc)
    jobs = [("featured/index.html", lambda h: (lambda r: (r[0], [r[1]]))(refresh_featured(h, network_feed(by_channel), now))),
            ("channels/index.html", lambda h: refresh_channels(h, by_channel, now))]
    for rel, fn in jobs:
        p = os.path.join(root, rel)
        html = io.open(p, encoding="utf-8").read()
        try:
            new, notes = fn(html)
        except ValueError as e:
            print("refresh-rails: %s (%s)" % (e, rel))
            return 1
        for n in notes:
            print("refresh-rails: " + n)
        if new != html and not dry:
            io.open(p, "w", encoding="utf-8", newline="\n").write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
