# Builds the cinema-look vertical pages (competitions/channels/
# featured) from the repaired cinema template's chrome (nav/CSS/footer/theater/JS).
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from private_data import private_file, HOWTO

W = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")).replace("\\", "/") + "/"
TPL = W + "scripts/builders/cinema-template.html"
OUT = W + "concepts/cinema/"
CDN = "https://d1nm1d2txb83wa.cloudfront.net"
# local assets are root-relative (works on any origin; the deploy sweep
# never has to touch them). Keep the constant for callers.
DEV = ""

# Brand slider data (network-brands.json in the private data folder; rendered
# by network_brands.py, which renders empty when the private data is missing).
# Used on /partners/ (with stat tiles) and /about/ (title + slider).
import network_brands as _nb
_NB = _nb.load()
HOST = CDN + "/video/ig-18080096294690324"
BELLA = CDN + "/video/ig-18106275875112509"

# head/tail split happens after refresh_home() below (live rails first)

import json as _json, urllib.request as _rq, os as _os
_DURC = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "durations.json")
try: _durs = _json.load(open(_DURC))
except Exception: _durs = {}
def dur_of(vid):
    # every portrait card carries its real runtime; wide cards never do
    if vid in _durs: return _durs[vid]
    try:
        d = _json.load(_rq.urlopen(CDN + "/v1/content/" + vid, timeout=15))
        s = d.get("duration")
        _durs[vid] = ("%d:%02d" % (s // 60, s % 60)) if s else None
    except Exception:
        _durs[vid] = None
    _json.dump(_durs, open(_DURC, "w"))
    return _durs[vid]

# posters cropped from letterboxed originals (make-poster-fills.py publishes
# poster-fill.jpg beside them; registry committed as poster-fills.json)
import json as _pjson, os as _pos
_pf_path = _pos.path.join(_pos.path.dirname(_pos.path.abspath(__file__)), "poster-fills.json")
POSTER_FILLS = set(_pjson.load(io.open(_pf_path, encoding="utf-8-sig"))) if _pos.path.exists(_pf_path) else set()
def poster_url(vid):
    return "%s/video/%s/poster%s.jpg" % (CDN, vid, "-fill" if vid in POSTER_FILLS else "")

# cross-post duplicate registry (make-dupe-registry.py): {dupe_id: canonical_id}.
# Rule: a video never appears twice in one carousel, even under
# two content ids. Every shelf and the homepage Feed rail dedupe through this.
_pd_path = _pos.path.join(_pos.path.dirname(_pos.path.abspath(__file__)), "poster-dupes.json")
POSTER_DUPES = _pjson.load(io.open(_pd_path, encoding="utf-8-sig")) if _pos.path.exists(_pd_path) else {}
import re as _cell_re
_cell_id = _cell_re.compile(r'/video/([^/"]+)/')
def dedupe_cells(cells):
    seen, kept = set(), []
    for c in cells:
        m = _cell_id.search(c)
        key = POSTER_DUPES.get(m.group(1), m.group(1)) if m else None
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        kept.append(c)
    return kept

import re as _nd_re
_dash_sep = _nd_re.compile(u"\\s+[-\\u2013\\u2014]+\\s+")
def no_dash(t):
    # dashes never appear as punctuation in visible copy -
    # spaced dashes become commas. Applied at render so ingest captions and
    # curated lists are both covered.
    return _dash_sep.sub(", ", t or "")

def reel_cell(vid, chan, title, dur=None, tag=None, label=None):
    # captions show the title only (no channel names on cards);
    # label= keeps a bold prefix for the rails that need one (Sponsored brands)
    title = no_dash(title)
    if dur is None:
        dur = dur_of(vid)
    extra = ""
    if tag: extra += '\n        <span class="tile-tag">%s</span>' % tag
    if dur: extra += '\n        <span class="dur">%s</span>' % dur
    cap = ('<b>%s</b> &middot; %s' % (label, title)) if label else title
    aq = title.replace('"', '&quot;')
    return '''    <div class="reel-cell">
      <a class="card card-reel" href="/watch/%s/" aria-label="%s">
        <img src="%s" loading="lazy" decoding="async" alt="%s">%s
      </a>
      <p class="reel-caption">%s</p>
    </div>''' % (vid, aq, poster_url(vid), aq, extra, cap)

def wide_card(img, chan, title, tag=None, href="#", pos=None, vid=None):
    title = no_dash(title)
    # pos: object-position for vertical posters in the 16:9 crop, e.g. "50% 25%"
    # to keep a face in frame instead of the default center band (chin/nose)
    # vid: the episode's content id - the card gets a real /watch/ href plus
    # data-mp4/data-poster so the chrome's card-wide handler opens the theater
    # in place (series episodes play like the carousels).
    t = '\n      <span class="tile-tag">%s</span>' % tag if tag else ""
    style = ' style="object-position:%s"' % pos if pos else ""
    data = ""
    if vid:
        href = "/watch/%s/" % vid
        data = ' data-mp4="%s/video/%s/master.mp4" data-poster="%s/video/%s/poster.jpg"' % (CDN, vid, CDN, vid)
    if href == "#":
        # no destination exists (image posts like Fuel Friday) - not a link
        return '''    <div class="card card-wide">
      <img src="%s"%s loading="lazy" decoding="async" alt="">%s
      <span class="art-title">%s</span>
    </div>''' % (img, style, t, title)
    return ('''    <a class="card card-wide" href="%s"''' % href) + data + ('''>
      <img src="%s"%s loading="lazy" decoding="async" alt="">%s
      <span class="art-title">%s</span>
    </a>''' % (img, style, t, title))

def ranked(cells):
    # Top-10 style: big gold numerals in front of the trending cards
    return ['<div class="rank-cell"><span class="rank-n">%d</span>\n%s\n</div>' % (n, c)
            for n, c in enumerate(cells, 1)]

def shelf(title, sub, cells, gold=False, see=None, anchor="", logo=None, rail_cls="", title_cls=""):
    title, sub = no_dash(title), no_dash(sub)
    cells = dedupe_cells(cells)
    if not [c for c in cells if c and c.strip()]:
        return ""  # a rail with zero cells never renders as an orphan heading
    g = (" gold" if gold else "") + title_cls
    if logo:
        img = '<img class="shelf-logo" src="%s/assets/img/chanh/%s.webp" alt="%s">' % (DEV, logo, title)
        title = ('<a href="%s" aria-label="%s">%s</a>' % (see, title, img)) if see else img
    see_a = '\n    <a class="shelf-all" href="%s">See All</a>' % see if see else ""
    return '''<section class="shelf"%s>
  <div class="shelf-head">
    <h2 class="shelf-title%s">%s</h2>%s%s
  </div>
  <div class="rail%s">
%s
  </div>
</section>''' % (anchor, g, title, ('\n    <span class="shelf-sub">%s</span>' % sub) if sub else "", see_a, rail_cls, "\n".join(cells))

def hero_sm(kicker, title_html, meta, dek, ctas, glow, reel=None, reel_mp4=None, reel_poster=None, copy_first=False, bleed=False, copy_cls=""):
    kicker, meta, dek = no_dash(kicker), no_dash(meta), no_dash(dek)
    # reel: a content id (CDN paths derived), or pass reel_mp4/reel_poster direct.
    if reel:
        reel_mp4 = "%s/video/%s/master.mp4" % (CDN, reel)
        reel_poster = "%s/video/%s/poster.jpg" % (CDN, reel)
    reel_html = echo_html = ""
    if reel_mp4:
        echo_html = '''
    <video class="hero-echo" muted loop playsinline preload="none" data-src="%s"></video>''' % reel_mp4
        reel_html = '''
    <div class="hreel"><video class="hero-video" muted loop playsinline preload="none"
      poster="%s" data-src="%s"></video></div>''' % (reel_poster, reel_mp4)
    meta_html = ('\n      <div class="hero-meta">%s</div>' % meta) if meta else ""
    kick_html = ('<div class="hero-kicker">%s</div>\n      ' % kicker) if kicker else ""
    dek_html = ('\n      <p class="hero-dek%s">%s</p>' % (" dek-2line" if 'class="nw"' in dek else "", dek)) if dek else ""
    copy_html = ('''
    <div class="hero-copy%s">''' % ((" " + copy_cls) if copy_cls else "")) + '''
      %s%s%s%s
      <div class="hero-ctas">
%s
      </div>
    </div>''' % (kick_html, title_html, meta_html, dek_html, ctas)
    # copy_first: on phones the reel is in normal flow, so DOM order decides
    # what a visitor sees first. Event pages put the pitch + CTA above the reel.
    inner = (copy_html + reel_html) if copy_first else (reel_html + copy_html)
    bcls = " hero-bleed" if bleed else ""
    bslide = " bleed" if bleed else ""
    return '''<section class="hero hero-sm%s" id="hero">
  <div class="hero-slide vslide%s on">
    <div class="hglow" style="background-image:url('%s')"></div>%s
    <div class="hero-scrim"></div>%s
  </div>
  <div class="hero-progress" id="heroDots">
    <button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button>
  </div>
</section>''' % (bcls, bslide, glow, echo_html, inner)

def meta_row(rate, *items):
    parts = ['<span class="rate">%s</span>' % rate] if rate else []
    for n, it in enumerate(items):
        if n or parts and not rate: pass
        parts.append('<span>%s</span>' % it)
    return '<span class="sep">&middot;</span>'.join(parts) if not rate else \
        parts[0] + "".join(('<span class="sep">&middot;</span>' if n else '') + p for n, p in enumerate(parts[1:]))

def watch_btn(vid, kicker, title, gold=True, label="Watch"):
    cls = "btn-gold" if gold else "btn-ghost"
    return '''        <a class="btn %s theater-open" href="/watch/%s/"
           data-mp4="%s/video/%s/master.mp4"
           data-poster="%s/video/%s/poster.jpg"
           data-kicker="%s" data-title="%s">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          %s
        </a>''' % (cls, vid, CDN, vid, CDN, vid, kicker, title, label)

GOLD_BTN = '        <a class="btn btn-gold" href="%s">%s</a>'
GHOST_BTN = '        <a class="btn btn-ghost" href="%s">%s</a>'

def page(slug, name, hero, main_sections, nav_label=None, nav_slug=None, main_cls=""):
    nav_label = nav_label or name
    nav_slug = nav_slug or slug
    p = head
    p = p.replace("<title>Concept B - CINEMA | NIL TV</title>",
                  "<title>%s - Cinema | NIL TV</title>" % name, 1)
    p = p.replace('<a href="/concepts/cinema/%s/">%s</a>' % (nav_slug, nav_label),
                  '<a href="/concepts/cinema/%s/" class="active">%s</a>' % (nav_slug, nav_label), 1)
    body = hero + '\n\n<main class="shelves%s">\n\n' % ((" " + main_cls) if main_cls else "") + "\n\n".join(main_sections) + "\n\n</main>\n\n"
    io.open(OUT + slug + "/index.html", "w", encoding="utf-8", newline="\n").write(p + body + tail)
    print("wrote", slug)

# ---------- live rails: fetched from the API at every build ----------
import re as _re, datetime as _dt
_NOW = _dt.datetime.utcnow()
def fetch_items(cid, n=12):
    # the API caps limit at 48, so follow cursors until n items (ch-nilstar
    # holds the full Season 1 audition pool now - 70+ items)
    items, cursor = [], ""
    try:
        while len(items) < n:
            u = CDN + "/v1/content?channelId=%s&limit=48" % cid
            if cursor:
                u += "&cursor=" + _rq.quote(cursor)
            d = _json.load(_rq.urlopen(u, timeout=20))
            items += d.get("items", [])
            cursor = d.get("cursor") or ""
            if not cursor:
                break
        return items[:n]
    except Exception:
        return items
def clean_title(t):
    t = (t or "").split("\n")[0]
    t = " ".join(w for w in t.split() if not w.startswith("#") and not w.startswith("@"))
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").strip(" -|")
    return (t[:63].rstrip() + "...") if len(t) > 64 else (t or "Watch on NIL TV")
def days_old(it):
    try:
        p = _dt.datetime.strptime((it.get("publishedAt") or "")[:19], "%Y-%m-%dT%H:%M:%S")
        return (_NOW - p).days
    except Exception:
        return 9999
def item_cell(it, chan=None, tag=None):
    return reel_cell(it["id"], chan or it.get("channelName", "NIL TV"), clean_title(it.get("title")), tag=tag)
def channel_cells(cid, n, chan_name):
    items = fetch_items(cid, n)
    cells = []
    for i, it in enumerate(items):
        # tag policy: "New Episode" only when the newest clip is genuinely recent
        tag = "New Episode" if (i == 0 and days_old(it) <= 14) else None
        cells.append(item_cell(it, chan=chan_name, tag=tag))
    return cells
_latest_cache = None
def network_latest(n=10):
    global _latest_cache
    if _latest_cache is None:
        chans = _json.load(_rq.urlopen(CDN + "/v1/channels", timeout=20))["channels"]
        pool = []
        for ch in chans:
            # the network feed is campus channels + NIL TV only - NIL Star
            # competition content stays on the competitions page
            if ch["id"] == "ch-nilstar":
                continue
            for it in fetch_items(ch["id"], 12):
                it["_chan"] = ch.get("name", "")
                pool.append(it)
        pool.sort(key=lambda i: i.get("publishedAt") or "", reverse=True)
        seen, out = set(), []
        for it in pool:
            if it["id"] in seen: continue
            seen.add(it["id"]); out.append(it)
        _latest_cache = out
    return _latest_cache[:n]

# ---- live Trending: time-claiming rails must be live.
# network_latest re-ranked: trailing window, max per_channel cards per channel,
# page-deduped via exclude. Both Trending rails feed from here.
def _canon(vid):
    return POSTER_DUPES.get(vid, vid)
SERIES_IDS = {"tbtv-DVbUNKQERl1", "tbtv-DVxAxL8DyCo", "tbtv-DWZwBSNhS6R",
              "tbtv-DWuADuEkdY5", "tbtv-DX9pD_jRvG4", "tbtv-DXFbRbEAdKJ",
              "tbtv-DXPYxm2EbyW", "tbtv-DXFxLkBk08Q", "tbtv-DXKNvGdDh5n",
              "tbtv-DT_OGfyE3tJ", "tbtv-DU60ehtE-DU", "tbtv-DUHPUPxE12I",
              "tbtv-DUWYUkJkx2m", "tbtv-DUjI-QsE3ZH", "tbtv-DVY-U_sE754",
              "ig-17908049181280440", "c-meet-freshman", "tbtv-DYkyFXvSDjT", "tbtv-DXXadIQk-Ti", "ig-17942549967185006", "tbtv-DW4wt_Ykx1v", "tbtv-DWnGV6FkphB", "tbtv-DU_bYSkkv3p", "tbtv-DU1etbuETV7"}
def trending_items(n=7, days=21, per_channel=2, exclude=None):
    ex = {_canon(v) for v in (exclude or set())}
    out, per = [], {}
    # three passes, each looser (fresh + channel-diverse, then any age,
    # then any channel mix) so the rail always fills to n even when the
    # page's other rails have claimed most of the recent pool
    for pass_days, pass_cap in ((days, per_channel), (9999, per_channel), (9999, 99)):
        for it in network_latest(120):
            k = _canon(it["id"])
            ch = it.get("_chan", "")
            if k in ex or days_old(it) > pass_days or per.get(ch, 0) >= pass_cap:
                continue
            per[ch] = per.get(ch, 0) + 1
            ex.add(k)
            out.append(it)
            if len(out) >= n:
                return out
    return out
def trending_cells_live(items):
    return [wide_card(poster_url(it["id"]), it.get("_chan", "NIL TV"), clean_title(it.get("title")),
                      "New Episode" if (i == 0 and days_old(it) <= 7) else None, vid=it["id"])
            for i, it in enumerate(items)]
def cells_ids(cells):
    out = set()
    for c in cells:
        m = _cell_id.search(c)
        if m:
            out.add(_canon(m.group(1)))
    return out

# ---- themed rails: curated data lives in themed_rails.py ----
import os as _os
_tns = {}
exec(io.open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "themed_rails.py"), encoding="utf-8").read(), _tns)
THEMED, HOME_THEMED, FEAT_THEMED = _tns["THEMED"], _tns["HOME_THEMED"], _tns["FEAT_THEMED"]
def themed_shelf(key, gold=False, exclude=None):
    # exclude: canonical ids already claimed by earlier rails on the same
    # page (the featured live rails claim first) - a curated
    # entry that collides is simply skipped for this build.
    title, sub, entries = THEMED[key]
    ex = exclude or set()
    return shelf(title, sub, [reel_cell(v, c, t) for v, c, t in entries
                              if _canon(v) not in ex], gold=gold)

# Channel visibility rule: campus tiles and rails appear only once a
# channel has at least CHANNEL_MIN_POSTS posts. Counts are live at every
# build, so a channel graduates onto the wall and homepage rail on its own.
# GATE OFF at 0. Set CHANNEL_MIN_POSTS to 8 to enable the graduation rule.
CHANNEL_MIN_POSTS = 0
_ch_counts = {}
def channel_qualifies(cid):
    if CHANNEL_MIN_POSTS <= 0:
        return True
    if cid not in _ch_counts:
        _ch_counts[cid] = len(fetch_items(cid, CHANNEL_MIN_POSTS))
    return _ch_counts[cid] >= CHANNEL_MIN_POSTS

CHAN_CAPS = {"trueblue":"Duke","dorecity":"Vanderbilt","chapelhill":"UNC",
             "starkville":"Mississippi State","collegestation":"Texas A&amp;M",
             "brazos":"Baylor","goldendome":"Notre Dame","redpack":"NC State",
             "saltcity":"Syracuse","goldsalem":"Wake Forest"}
LIVE_SLUGS = {"trueblue","dorecity","chapelhill","starkville","collegestation",
              "brazos","goldendome","redpack","saltcity","goldsalem"}
CHAN_TILES = [
    ("chan3/trueblue.webp","TrueBlue TV"),("chan3/dorecity.webp","Dore City TV"),
    ("chan3/chapelhill.webp","Chapel Hill TV"),("chan3/starkville.webp","Starkville TV"),
    ("chan3/collegestation.webp","College Station TV"),("chan3/brazos.webp","Brazos TV"),
    ("chan3/goldendome.webp","Golden Dome TV"),("chan3/redpack.webp","Red Pack TV"),
    ("chan3/saltcity.webp","Salt City TV"),("chan3/goldsalem2.webp","Gold Salem TV")]
COMING_SOON_MIN = 6   # channels under this are "Coming Soon"
GRID_REMOVED = {"brazos", "goldsalem"}  # hidden on the channels page
SLIDER_REMOVED = {"goldsalem"}          # hidden on the homepage slider
_cc_cache = {}
def _chan_fill(slug):
    cid = "ch-%stv" % slug
    if cid not in _cc_cache:
        try:
            _cc_cache[cid] = len(fetch_items(cid, COMING_SOON_MIN))
        except Exception:
            _cc_cache[cid] = 0
    return _cc_cache[cid]

def chan_row(grid=False):
    # live channels first, Coming Soon tiles trail (both surfaces)
    rows = []
    for f, a in CHAN_TILES:
        cell = chan_cell(f, a, grid=grid)
        if not cell:
            continue
        s = f.split("/")[-1].rsplit(".", 1)[0].rstrip("0123456789")
        rows.append((_chan_fill(s) < COMING_SOON_MIN, cell))
    return "\n".join(cell for _soon, cell in sorted(rows, key=lambda x: x[0]))

def chan_cell(f, a, grid=False):
    # cache-busted logo names (goldsalem2.webp) still map to the base slug;
    # the file extension is ignored
    slug = f.split("/")[-1].rsplit(".", 1)[0].rstrip("0123456789")
    if not channel_qualifies("ch-%stv" % slug):
        return ""
    if grid and slug in GRID_REMOVED:
        return ""
    if not grid and slug in SLIDER_REMOVED:
        return ""
    # both surfaces show the horizontal mark; the stacked chan3
    # files in CHAN_TILES only carry the slug + display name
    f = "chanh/%s.webp" % slug
    filled = _chan_fill(slug) >= COMING_SOON_MIN
    cap = CHAN_CAPS.get(slug)
    if not filled:
        # unfilled channels read Coming Soon on every surface
        capline = '<span class="chan-cap chan-cap-soon">Coming Soon</span>'
        return """    <div class="chan-cell">
    <div class="chan-tile">
      <img src="%s/assets/img/%s" alt="%s">
    </div>
      %s
    </div>""" % (DEV, f, a, capline)
    capline = ('<span class="chan-cap">%s&rsquo;s Athletes</span>' % cap) if cap \
        else '<span class="chan-cap">&nbsp;</span>'
    if slug not in LIVE_SLUGS:
        return '''    <div class="chan-cell">
    <div class="chan-tile">
      <img src="%s/assets/img/%s" alt="%s">
    </div>
      %s
    </div>''' % (DEV, f, a, capline)
    return '''    <div class="chan-cell">
    <a class="chan-tile" href="/channels/%stv/">
      <img src="%s/assets/img/%s" alt="%s">
    </a>
      %s
    </div>''' % (slug, DEV, f, a, capline)

# Season 1 finalists (name, sport, school, audition id, tag) - used by the
# recap page grid and the Season 1 shelf.
TOP20 = [
 ("Bella Calvanese","Lacrosse","Sacred Heart University","ig-18090687326638212","Champion"),
 ("Taylee Chirrick","Basketball","Montana State University","ig-18032459951649287",None),
 ("Anna &amp; Tom Lardner","Tennis &amp; Football","Middlebury &amp; Bowdoin","ig-17885005557669640",None),
 ("Charlie Moore","Ice Hockey","Colby College","ig-18005583791944416",None),
 ("Kali Boychuk","Ice Hockey","Saint Michael's College","ig-18105514307111514",None),
 ("Kayliah Love","Track &amp; Field","DePaul University","ig-18148933864451059",None),
 ("Miguel Hall","Track &amp; Field","Abilene Christian University","ig-18088349483186091",None),
 ("Jasmine Connor","Lacrosse","American University","ig-17968578101935272",None),
 ("Aleithia Wilson","Volleyball","Wheeling University","ig-17879255838614337",None),
 ("Grace &amp; Taylor Hasselbeck","Lacrosse &amp; Football","Vanderbilt &amp; Wyoming","ig-18085956953359667",None),
 ("Keagan Cunningham","Football","Texas Christian University","ig-18407599015157352",None),
 ("Mia Girgis","Soccer","UMass Lowell","ig-18021282023853993",None),
 ("Zander Vasquez","Fencing","UC San Diego","ig-18604893316048710",None),
 ("Keely Eslinger","Soccer","Liberty University","ig-18217919269327952",None),
 ("Drew Collins","Swimming","University of Louisville","ig-18059364485762372",None),
 ("Eliana Geva","Fencing","Temple University","ig-17960315856137760",None),
 ("Jaylin Lott","Volleyball","Thomas Jefferson University","ig-17997167144792706",None),
 ("Colin Coffey","Football","Alma College","ig-17992218497811714",None),
 ("Chihiro Bringman","Swim &amp; Dive","Stonehill College","ig-18116745598768277",None),
 ("Simon Lioznyansky","Fencing","University of Pennsylvania","ig-17960395157963864",None),
]

# All 20 finalists (the full field; the champion cell is Bella's full
# singing audition, not the winner-announcement clip).
sing_cells = [reel_cell(vid, ("Champion" if tag == "Champion" else "Finalist"), name,
                        tag=("Season 1 Champion" if tag == "Champion" else None))
              for name, sport, school, vid, tag in TOP20]

def refresh_home():
    t = io.open(TPL, encoding="utf-8").read()
    # page dedupe: curated rails claim ids first, the live
    # Trending rail claims next, and The Feed backfills around all of them -
    # a homepage scroller never sees the same video twice.
    used = set(SERIES_IDS)
    used |= {_canon(v) for v, _, _ in _tns["SPONSORED"]}
    for _k in HOME_THEMED:
        used |= {_canon(v) for v, _, _ in THEMED[_k][2]}
    # Trending on NIL TV is PINNED: the fixed most-viewed lineup
    # from themed_rails.TRENDING_PINNED renders verbatim, in order. Empty the
    # list to fall back to the live recency feed. The pinned ids join `used`
    # so no later rail can dupe them.
    pinned = _tns.get("TRENDING_PINNED", [])
    if pinned:
        used |= {_canon(v) for v, _, _ in pinned}
        reel_html = "\n".join(reel_cell(v, c, tt) for v, c, tt in pinned)
    else:
        latest = [it for it in network_latest(40) if _canon(it["id"]) not in used][:9]
        reel_html = "\n".join(dedupe_cells([item_cell(it, chan=it.get("_chan"),
            tag=("Just Added" if (i == 0 and days_old(it) <= 7) else None))
            for i, it in enumerate(latest)]))

    t = _re.sub(r"<!-- AUTORAIL:reels -->.*?<!-- /AUTORAIL:reels -->",
                lambda m: "<!-- AUTORAIL:reels -->\n" + reel_html + "\n<!-- /AUTORAIL:reels -->", t, flags=_re.S)
    # No per-channel homepage rail: the Channels logo rail is the only
    # channel surface on the homepage.

    _cr_html = chan_row(grid=False)
    t = _re.sub(r"<!-- AUTORAIL:chanrail -->.*?<!-- /AUTORAIL:chanrail -->",
                (lambda h2: lambda m: "<!-- AUTORAIL:chanrail -->\n" + h2 + "\n<!-- /AUTORAIL:chanrail -->")(_cr_html), t, flags=_re.S)
    _fin_html = shelf("NIL Singing Star Season 1", "", list(sing_cells), see="/competitions/")
    t = _re.sub(r"<!-- AUTORAIL:finalists -->.*?<!-- /AUTORAIL:finalists -->",
                (lambda h2: lambda m: "<!-- AUTORAIL:finalists -->\n" + h2 + "\n<!-- /AUTORAIL:finalists -->")(_fin_html), t, flags=_re.S)
    _sp_cells = [reel_cell(v, br, tt, label=br) for v, br, tt in _tns["SPONSORED"]]
    _sp_html = shelf("Sponsored Content", "", _sp_cells)
    t = _re.sub(r"<!-- AUTORAIL:sponsored -->.*?<!-- /AUTORAIL:sponsored -->",
                (lambda h2: lambda m: "<!-- AUTORAIL:sponsored -->\n" + h2 + "\n<!-- /AUTORAIL:sponsored -->")(_sp_html), t, flags=_re.S)
    for _k in HOME_THEMED:
        _html = themed_shelf(_k, gold=(_k == HOME_THEMED[0]))
        t = _re.sub(r"<!-- AUTORAIL:theme-%s -->.*?<!-- /AUTORAIL:theme-%s -->" % (_k, _k),
                    (lambda h: lambda m: "<!-- AUTORAIL:theme-%s -->\n" % _k + h + "\n<!-- /AUTORAIL:theme-%s -->" % _k)(_html), t, flags=_re.S)
    # brand slider: title + slider. Leads the shelves, right under the
    # hero carousel; replaced in place on every refresh, inserted at the
    # top of <main> if the template lacks it
    _bs = _nb.block(_NB, anchor="brands", cls="nbm-lead")
    if "<!-- BRANDSLIDER -->" in t:
        t = _re.sub(r"<!-- BRANDSLIDER -->.*?<!-- /BRANDSLIDER -->", lambda m: _bs, t, flags=_re.S)
    else:
        t = t.replace('<main class="shelves" id="main">\n', '<main class="shelves" id="main">\n\n' + _bs + "\n", 1)
    io.open(TPL, "w", encoding="utf-8", newline="\n").write(t)
    print("homepage rails refreshed from the API")

refresh_home()
tpl = io.open(TPL, encoding="utf-8").read()
head = tpl[:tpl.index("<!-- HERO BILLBOARD")]
tail = tpl[tpl.index("<!-- FOOTER : credits roll -->"):]

import os
for s in ["competitions", "nilstar/season-1", "channels", "featured", "vote"]:
    os.makedirs(OUT + s, exist_ok=True)

# TAG POLICY (until rails render from the API): "New Episode" = the channel's
# newest clip; "New Channel" = a channel's first-ever content; "Just Added" =
# the newest ingest on The Reels rail. Duration pills: every portrait card,
# never wide cards.
# ================= COMPETITIONS =================
# Coming Soon event tile markup, for use once an upcoming event is announced:
#   <div class="chan-tile"><span class="soon">EVENT NAME<small>Coming Soon</small></span></div>
# ---- Events carousel: one logo tile per event, linking to the event page.
# Future events are one more tuple here (name, href, logo, logo-class, meta,
# state, line, cta, live).
EVENTS = [
    ("NIL Star Season 1", "/nilstar/season-1/", "nilstar-logo-wide.webp", "ev-logo-wide", "Season 1 &middot; Jul 7 - Jul 22, 2026",
     "Completed", "Champion crowned Jul 22. 20 finalists, 1M+ votes.", "Watch the Recap", False),
]
def event_tile(name, href, logo, lcls, dates, state, line, cta, live):
    return '''    <a class="card ev-tile%s" href="%s" aria-label="%s - %s">
      <span class="ev-state">%s</span>
      <span class="ev-logo-box"><img class="ev-logo %s" src="/assets/img/%s" alt="%s" loading="lazy" decoding="async"></span>
      <span class="ev-foot">
        <span class="ev-line">%s</span>
        <span class="ev-meta">%s<b>%s</b></span>
      </span>
    </a>''' % (" live" if live else "", href, name, state, state, lcls, logo, name, line, dates, cta)
event_cells = [event_tile(*e) for e in EVENTS]
print("events: " + ", ".join("%s=%s" % (e[0], e[5]) for e in EVENTS))

# Event JSON-LD (SEO guidance): machine-readable dates for each EVENTS entry.
# The sweep rewrites the dev origin to niltv.com on prod deploys.
EVENT_DATES = {"NIL Star Season 1": ("2026-07-07", "2026-07-22")}
EVENT_LD = "\n".join(
    '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Event",'
    '"name":"%s","startDate":"%s","endDate":"%s",'
    '"eventStatus":"https://schema.org/EventScheduled",'
    '"eventAttendanceMode":"https://schema.org/OnlineEventAttendanceMode",'
    '"location":{"@type":"VirtualLocation","url":"https://dev.dkdfgvugisb3v.amplifyapp.com%s"},'
    '"image":"https://dev.dkdfgvugisb3v.amplifyapp.com/assets/img/nilstar-logo-wide.webp",'
    '"description":"%s",'
    '"organizer":{"@type":"Organization","name":"NIL TV","url":"https://dev.dkdfgvugisb3v.amplifyapp.com/"}}'
    "</script>" % (name, EVENT_DATES[name][0], EVENT_DATES[name][1], href, line)
    for (name, href, _logo, _lcls, _dates, _state, line, _cta, _live) in EVENTS
    if name in EVENT_DATES)



# Entry-window AUDITIONS: the athletes' original collab-post auditions,
# newest first. Every NIL Star repost is a distinct edit of different
# footage, so an original here is never a dupe of a Season 1 shelf card.
AUDITION_IDS = [
    ("ig-18539419810078105", "College Athletes: post your next carpool karaoke to win $10,000"),
    ("ig-17919562527182213", "Caden Redmond - Defiance College Football"),
    ("ig-17897946027496513", "Madison Walcott - Assumption Field Hockey"),
    ("ig-18180934726405773", "Abby Cunningham - Fight For Me (Heathers)"),
    ("ig-18094567163165109", "Robin Kucler - Cups (Wake Forest XC)"),
    ("ig-18113933899902354", "Noah Sentnor - Colorado Ultimate Frisbee"),
    ("ig-17884755516665461", "Teddy Tolbert - Die on This Hill"),
    ("ig-17918818842181668", "Tatyana Green - Eastern Michigan Track"),
    ("ig-18085619087451279", "I Miss the Mountains - Next to Normal"),
    ("ig-18158019676419817", "An Original Song For Every Athlete"),
    ("ig-17884869510414822", "Savannah Breitwiser - Audition Cover"),
    ("ig-18066609356375167", "Violet Hewett - Duke Track"),
    ("ig-17959556736138023", "Jersey Giant - Sam Barber Cover"),
    # ---- finalist ORIGINALS: the athletes' own full auditions,
    # appended at the back because the finalists are already featured in the
    # Season 1 shelf above (their NIL Star edits - different footage). Top 20
    # announcement order, trimmed to keep the rail at the 24-card cap.
    # Originals with no playable media are left out.
    ("ig-18166221412439513", "Taylee Chirrick, Montana State Basketball"),
    ("ig-18025761827840117", "Anna and Tom Lardner, Middlebury and Bowdoin"),
    ("ig-18085637768097206", "Charlie Moore, Colby Ice Hockey"),
    ("ig-18112296895940804", "Kayliah Love, DePaul Track and Field"),
    ("ig-17959643186965122", "Jasmine Connor, American University Lacrosse"),
    ("ig-18120209332665246", "Aleithia Wilson, Wheeling Volleyball"),
    ("ig-18114673171680811", "Keagan Cunningham, TCU Football"),
    ("ig-18132846328607840", "Zander Vasquez, UC San Diego Fencing"),
    ("ig-17863728654632876", "Keely Eslinger, Liberty Soccer"),
    ("ig-17851262943695464", "Eliana Geva, Temple Fencing"),
    ("ig-18594161446025211", "Jaylin Lott, Thomas Jefferson Volleyball"),
]
audition_cells = [reel_cell(v, "NIL Star", t) for v, t in AUDITION_IDS]

# Nav label + slug: "Competitions"; /nilstar/ 301s here.
page("competitions", "Competitions",
    hero_sm("Season 1 Champion Crowned",
        '<h1 class="hero-title logo-title"><img class="hero-logo hl-nilstar" src="/assets/img/nilstar-logo-wide.webp" alt="NIL Star"></h1>',
        "",
        '<span class="nw">Bella Calvanese is our first ever NIL STAR, taking home $10,000.</span><br>Season 2 arrives in 2027.',
        watch_btn("ig-18106275875112509", "Season 1 Champion", "Bella Calvanese"),
        CDN + "/video/ig-18106275875112509/poster.jpg", reel="ig-18106275875112509", bleed=True),
    # Events shelf PARKED: only one event exists. Restore by
    # putting shelf("Events", "Every event stands alone. Pick one to see
    # where it stands.", event_cells, gold=True) back at the top of this
    # list when a second event is announced; event_tile/EVENTS stay live.
    [shelf("NIL Singing Star Season 1", "", sing_cells, gold=True),
     shelf("The Auditions", "", audition_cells),
     EVENT_LD])

# ================= CHANNELS =================
chan_tiles = "\n".join('''    <a class="chan-tile" href="#">
      <img src="%s/assets/img/%s" alt="%s">
    </a>''' % (DEV, f, a) for f, a in [
    ("chan3/trueblue.webp","TrueBlue TV"),("chan3/dorecity.webp","Dore City TV"),
    ("chan3/chapelhill.webp","Chapel Hill TV"),("chan3/starkville.webp","Starkville TV"),
    ("chan3/collegestation.webp","College Station TV"),("chan3/brazos.webp","Brazos TV"),
    ("chan3/goldendome.webp","Golden Dome TV"),("chan3/redpack.webp","Red Pack TV"),
    ("chan3/saltcity.webp","Salt City TV"),("chan3/goldsalem2.webp","Gold Salem TV")])
tb_cells = [reel_cell(v, "TrueBlue TV", t, tag=("New Episode" if n == 0 else None)) for n, (v, t) in enumerate([
    ("tbtv-DYVOnP7Py68","Back like we never left on our home field"),
    ("tbtv-DYP2awaucJT","Back at it in the hometown"),
    ("tbtv-DYIsojsRHTH","Fired up"),
    ("tbtv-DYC4tKNutMb","When life gives you sunglasses"),
    ("tbtv-DXkTqkekUps","Nothing better than a rivalry win"),
    ("tbtv-DXhqNZtk_eT","Ideal game conditions"),
    ("tbtv-DY-qu5Ez4PC","Balancing classes, training and everything in between"),
    ("tbtv-DYfPCxLCZf1","Swinging into championship week")])]
more_campus = [
    reel_cell("ig-18091748873389340", "Chapel Hill TV", "Shoutout to 30witdachalk &amp; jumpman23", "3:00", "New Episode"),
    reel_cell("ig-18129644020643497", "Chapel Hill TV", "She touched the line gate in time lapse form", "0:29"),
    reel_cell("ig-18004077713755504", "Chapel Hill TV", "Always in a silly goofy mood", "0:14"),
    reel_cell("ig-18108576370921903", "Starkville TV", "Me literally googling: is it normal that my ankles..."),
    reel_cell("ig-18106682875737198", "Starkville TV", "Good luck to everyone racing this weekend"),
    reel_cell("ig-17880741309441315", "Starkville TV", "Embrassinggggg"),
    reel_cell("ig-18109119643888008", "College Station TV", "Get ready w salt &amp; peppa", tag="New Channel"),
]
niltv_cells = [
    reel_cell("ig-18138746563511713", "NIL TV", "Season opener baby"),
    reel_cell("tbtv-DYkgWILp9ga", "TrueBlue TV", "Who doesn't love a good long toss?", "0:44"),
    reel_cell("ig-18109119643888008", "College Station TV", "Get ready with Salt and Peppa", "0:23"),

    reel_cell("ig-18090211613394406", "NIL TV", "Got told my room was boring - so I decorated", "0:15"),
    reel_cell("ig-18106955224869294", "NIL TV", "I love my grass and this trend"),
]
nilstar_cells = [
    reel_cell("ig-18106275875112509", "NIL Star", "Your first ever NIL Star: Bella Calvanese", "0:24", "Champion"),
    reel_cell("ig-18032459951649287", "NIL Star", "Finalist - Taylee Chirrick", "0:32"),
    reel_cell("ig-18105514307111514", "NIL Star", "Finalist - Kali Boychuk"),
    reel_cell("ig-18148933864451059", "NIL Star", "Finalist - Kayliah Love"),
    reel_cell("ig-17968578101935272", "NIL Star", "Finalist - Jasmine Connor"),
    reel_cell("ig-17879255838614337", "NIL Star", "Finalist - Aleithia Wilson"),
]
dore_cells = [
    reel_cell("ig-17908049181280440", "Dore City TV", "From our first episode with Grace Hasselbeck", "0:28", "New Episode"),
    reel_cell("ig-18275620366295532", "Dore City TV", "Back up and at em in less than a month", "0:28"),
    reel_cell("ig-17902243089530973", "Dore City TV", "We did it - first game coming soon", "0:29"),
    reel_cell("ig-18121260613806693", "Dore City TV", "4 days till preseason", "2:14"),
    reel_cell("ig-17909147277446918", "Dore City TV", "Seasons here", "0:07"),
]
# School per channel comes from the brand-account registry's `campus`
# field, not guesses. Caption follows the "School NIL Student Athletes"
# naming rule.
wall_cells = chan_row(grid=True)
channels_head = '''<section class="hero hero-sm" id="hero" style="min-height:0">
  <div class="hero-slide vslide on chmq-slide" style="min-height:clamp(380px,30vw,440px)">
    <div class="hero-copy" style="margin:0;max-width:none">
      <!-- exactly two lines at every width: each line is nowrap and the size is
           capped against the viewport so the longer line always fits -->
      <h1 class="hero-title ht-sm" style="white-space:nowrap;font-size:min(clamp(32px,4.6vw,62px),6vw)">Student Athlete Run Channels<br>Local Content Created Their Way</h1>
    </div>
    <!-- network marquee: two slow rails of real posters (8/31 decision; motion, not video) -->
    <div class="chmq" aria-hidden="true">
      <div class="chmq-mq chmq-mq--a">
      <div class="chmq-track">
    <div class="chmq-group">
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18275620366295532.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYmqvT-vf5k.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18138746563511713.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17928150768394197.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18106682875737198.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYkyFXvSDjT.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18087898862367539.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYIsojsRHTH.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18026514830905320.jpg" width="300" height="533" decoding="async" alt=""></div>
    </div>
    <div class="chmq-group">
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18275620366295532.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYmqvT-vf5k.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18138746563511713.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17928150768394197.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18106682875737198.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYkyFXvSDjT.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18087898862367539.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYIsojsRHTH.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18026514830905320.jpg" width="300" height="533" decoding="async" alt=""></div>
    </div>
    <div class="chmq-group">
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18275620366295532.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYmqvT-vf5k.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18138746563511713.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17928150768394197.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18106682875737198.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYkyFXvSDjT.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18087898862367539.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYIsojsRHTH.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18026514830905320.jpg" width="300" height="533" decoding="async" alt=""></div>
    </div>
      </div>
      </div>
      <div class="chmq-mq chmq-mq--b">
      <div class="chmq-track">
    <div class="chmq-group">
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17902243089530973.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYP2awaucJT.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17909147277446918.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYnsMfYsQQ-.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYIsojsRHTH.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18004077713755504.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18108576370921903.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17908049181280440.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17928150768394197.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17880741309441315.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18121260613806693.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYfPCxLCZf1.jpg" width="300" height="533" decoding="async" alt=""></div>
    </div>
    <div class="chmq-group">
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17902243089530973.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYP2awaucJT.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17909147277446918.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYnsMfYsQQ-.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYIsojsRHTH.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18004077713755504.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18108576370921903.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17908049181280440.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17928150768394197.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17880741309441315.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18121260613806693.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYfPCxLCZf1.jpg" width="300" height="533" decoding="async" alt=""></div>
    </div>
    <div class="chmq-group">
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17902243089530973.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYP2awaucJT.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17909147277446918.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYnsMfYsQQ-.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYIsojsRHTH.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18004077713755504.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18108576370921903.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17908049181280440.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17928150768394197.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-17880741309441315.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/ig-18121260613806693.jpg" width="300" height="533" decoding="async" alt=""></div>
      <div class="chmq-card"><img src="/assets/img/chmq/tbtv-DYfPCxLCZf1.jpg" width="300" height="533" decoding="async" alt=""></div>
    </div>
      </div>
      </div>
    </div>
    <div class="chmq-scrim-l" aria-hidden="true"></div>
    <div class="chmq-scrim-b" aria-hidden="true"></div>
  </div>
  <div class="hero-progress" id="heroDots">
    <button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button>
  </div>
<style>
/* HERO network marquee (8/31): graphic, not video. Self-contained so the
   builder pipeline (build-sections.py -> promote.py) can never ship a bare hero. */
.hero-sm .hero-slide.chmq-slide{justify-content:center}
.chmq{position:absolute;z-index:1;top:calc(50% + 26px);right:-3%;width:min(72%,1640px);transform:translateY(-50%) rotate(-2deg);pointer-events:none}
.chmq-mq{overflow:hidden;width:100%;-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 20%,#000 90%,transparent 100%);mask-image:linear-gradient(90deg,transparent 0,#000 20%,#000 90%,transparent 100%)}
.chmq-mq--b{margin-top:18px;opacity:.88}
.chmq-track{display:flex;width:max-content;will-change:transform}
.chmq-mq--a .chmq-track{animation:chmq-a 192s linear infinite;animation-delay:-22s}
.chmq-mq--b .chmq-track{animation:chmq-b 240s linear infinite;animation-delay:-58s}
@keyframes chmq-a{from{transform:translateX(0)}to{transform:translateX(-33.3333%)}}
@keyframes chmq-b{from{transform:translateX(0)}to{transform:translateX(-33.3333%)}}
.chmq-group{display:flex;align-items:center;gap:14px;padding-right:14px;flex:none}
.chmq-card{flex:none;height:180px;aspect-ratio:300/532;border-radius:8px;overflow:hidden;background:var(--bg-alt);box-shadow:0 0 0 1px rgba(255,255,255,.05)}
.chmq-card img{width:100%;height:100%;object-fit:cover;display:block}
.chmq-mq--b .chmq-card{height:154px}
.chmq-scrim-l{position:absolute;z-index:2;top:0;bottom:0;left:0;width:88%;pointer-events:none;background:linear-gradient(90deg,var(--bg) 0%,var(--bg) 60%,rgba(6,6,8,0) 100%)}
.chmq-scrim-b{position:absolute;z-index:2;left:0;right:0;bottom:0;height:110px;pointer-events:none;background:linear-gradient(180deg,rgba(6,6,8,0) 0%,var(--bg) 100%)}
/* channels page only: tighten the hero-to-carousel gap (8/31) */
.hero-sm + .shelves{padding-top:12px}
@media (prefers-reduced-motion:reduce){.chmq-track{animation-play-state:paused}}
@media (max-width:900px){
  .chmq-slide[style]{min-height:0!important}
  .chmq{position:relative;top:auto;right:auto;width:114%;margin:22px 0 4px -7%;transform:rotate(-2deg)}
  .chmq-mq{-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 10%,#000 90%,transparent 100%);mask-image:linear-gradient(90deg,transparent 0,#000 10%,#000 90%,transparent 100%)}
  .chmq-card{height:118px}
  .chmq-mq--b .chmq-card{height:100px}
  .chmq-scrim-l{display:none}
  .chmq-scrim-b{height:70px}
}

/* 9/2: MOBILE ONLY - the marquee leads the channels hero; the title sits below it */
@media (max-width:700px){
.chmq-slide{display:flex;flex-direction:column;justify-content:flex-start;gap:4px;min-height:0!important;padding:78px 0 12px}
.chmq-slide .chmq{position:relative;top:auto;right:auto;left:auto;transform:none;width:100%;margin:0}
.chmq-slide .chmq-scrim-l{display:none}
.chmq-slide .hero-copy{order:2;padding-top:10px}
}
</style></section>'''
page("channels", "Channels",
    channels_head,
    [shelf("Local Channels", "", [wall_cells], rail_cls=" rail-tight rail-chlocal", title_cls=" shelf-title--local")] +
    [shelf(nm, "", cells, gold=(i == 0), see="/channels/" + cid[3:] + "/", logo=slug)
     for i, (cid, nm, sub, slug, cells) in enumerate(
         (cid, nm, sub, slug, channel_cells(cid, n, nm)) for cid, nm, sub, slug, n in [
             ("ch-truebluetv", "TrueBlue TV", "Duke&rsquo;s NIL Student Athletes", "trueblue", 12),
             ("ch-dorecitytv", "Dore City TV", "Vanderbilt&rsquo;s NIL Student Athletes", "dorecity", 12),
             ("ch-chapelhilltv", "Chapel Hill TV", "North Carolina&rsquo;s NIL Student Athletes", "chapelhill", 12),
             ("ch-starkvilletv", "Starkville TV", "Mississippi State&rsquo;s NIL Student Athletes", "starkville", 12),
             ("ch-collegestationtv", "College Station TV", "Texas A&amp;M&rsquo;s NIL Student Athletes", "collegestation", 12),
             ("ch-brazostv", "Brazos TV", "Baylor&rsquo;s NIL Student Athletes", "brazos", 12),
             ("ch-goldendometv", "Golden Dome TV", "Notre Dame&rsquo;s NIL Student Athletes", "goldendome", 12),
             ("ch-redpacktv", "Red Pack TV", "NC State&rsquo;s NIL Student Athletes", "redpack", 12),
             ("ch-saltcitytv", "Salt City TV", "Syracuse&rsquo;s NIL Student Athletes", "saltcity", 12),
             ("ch-goldsalemtv", "Gold Salem TV", "Wake Forest&rsquo;s NIL Student Athletes", None, 12),
         ]) if len(cells) >= 7])

# ================= FEATURED =================
trend = [
    wide_card(CDN+"/video/tbtv-DYkyFXvSDjT/poster.jpg", "TrueBlue TV", "Bringing the NIL conversation to the forefront", "New Episode", pos="50% 25%"),
    wide_card(CDN+"/video/ig-18138746563511713/poster.jpg", "NIL TV", "Season opener baby"),
    wide_card(CDN+"/video/tbtv-DY-qu5Ez4PC/poster.jpg", "TrueBlue TV", "Balancing classes, training and everything in between"),
    wide_card(CDN+"/video/ig-18087898862367539/poster.jpg", "Dore City TV", "Vandy soccer is back", "New Episode"),
    wide_card(CDN+"/video/ig-18129644020643497/poster.jpg", "Chapel Hill TV", "She touched the line gate in time lapse form"),
    wide_card(CDN+"/video/tbtv-DYfPCxLCZf1/poster.jpg", "TrueBlue TV", "Swinging into championship week"),
]
reels = [
    reel_cell("ig-17961794499169577", "NIL TV", "Missing Zoey Zubich already", "0:05", "Just Added"),

    reel_cell("ig-18275620366295532", "Dore City TV", "Back up and at em in less than a month", "0:28"),
    reel_cell("ig-18004077713755504", "Chapel Hill TV", "Always in a silly goofy mood", "0:14"),
    reel_cell("tbtv-DYkgWILp9ga", "TrueBlue TV", "Who doesn't love a good long toss?", "0:44"),
    reel_cell("ig-18109119643888008", "College Station TV", "Get ready with Salt and Peppa", "0:23"),

    reel_cell("tbtv-DYmqvT-vf5k", "TrueBlue TV", "All about who you share these moments with", "0:28"),

    reel_cell("ig-17902243089530973", "Dore City TV", "We did it - first game coming soon", "0:29"),
    reel_cell("ig-18090211613394406", "NIL TV", "Got told my room was boring - so I decorated", "0:15"),
]
nilstar_cells = list(sing_cells)  # the complete Season 1 field
campus = [
    reel_cell("ig-18275620366295532", "Dore City TV", "Back up and at em in less than a month", "0:28"),
    reel_cell("ig-17909147277446918", "Dore City TV", "Seasons here", "0:07"),
    reel_cell("ig-18004077713755504", "Chapel Hill TV", "Always in a silly goofy mood", "0:14"),
    reel_cell("ig-18129644020643497", "Chapel Hill TV", "She touched the line gate in time lapse form", "0:29"),
    reel_cell("ig-18108576370921903", "Starkville TV", "Me literally googling: is it normal that my ankles..."),
    reel_cell("ig-18106682875737198", "Starkville TV", "Good luck to everyone racing this weekend"),
    reel_cell("ig-17880741309441315", "Starkville TV", "Embrassinggggg"),
    reel_cell("ig-18121260613806693", "Dore City TV", "4 days till preseason", "2:14"),
]
# ---- Spotlight: Athlete Video of the Week + Featured Athlete of the Week.
# VIDEO_OF_WEEK pins a content id; None = the newest
# athlete reel on the network at build time. The featured athlete is a
# profile-page athlete (consent on file).
VIDEO_OF_WEEK = None
_vow = next((it for it in network_latest(20) if it["id"] == VIDEO_OF_WEEK), None) if VIDEO_OF_WEEK else network_latest(1)[0]
spotlight = """<section class="shelf" id="spotlight">
  <div class="shelf-head">
    <h2 class="shelf-title gold">This Week on NIL TV</h2>
    <span class="shelf-sub">Athlete produced content. One video, one athlete, every week.</span>
  </div>
  <div class="spot-grid">
    <div class="spot">
""" + item_cell(_vow, chan=_vow.get("_chan")) + """
      <div class="spot-tx">
        <span class="spot-k">Athlete Video of the Week</span>
        <h3>""" + clean_title(_vow.get("title")) + """</h3>
        <p>""" + (_vow.get("_chan") or "NIL TV") + """. Produced by the athlete, streaming on the network.</p>
        <a class="btn btn-gold" href="/watch/""" + _vow["id"] + """/">Watch</a>
      </div>
    </div>
    <div class="spot">
    <a class="athf-card" href="/athletes/emily-cole/">
      <img src="/athletes/emily-cole/portrait.jpg" loading="lazy" decoding="async" alt="Emily Cole">
      <span class="nm">Emily Cole</span>
      <span class="sp">Track &amp; XC</span>
    </a>
      <div class="spot-tx">
        <span class="spot-k">Featured Athlete of the Week</span>
        <h3>Emily Cole</h3>
        <p>NIL TV co-founder and track athlete. Her profile, her latest posts, and her story on the network.</p>
        <a class="btn btn-gold" href="/athletes/emily-cole/">See Her Profile</a>
      </div>
    </div>
  </div>
</section>"""
# featured page dedupe (sized for the 24-card rails): claim order
# MATCHES render order - hero + Editor's Picks, then the live New This
# Week and Trending get first pick of the fresh pool, and the big curated
# rails filter out whatever the live rails claimed (a 24-card rail losing a
# card or two beats New This Week flipping to "Latest on the Network"
# because curated lists swallowed every fresh clip).
_feat_used = {_canon("ig-17961794499169577")}
_nw_items = [it for it in network_latest(40) if _canon(it["id"]) not in _feat_used][:10]
_feat_used |= {_canon(it["id"]) for it in _nw_items}
_tr_items = trending_items(8, exclude=_feat_used)
_feat_used |= {_canon(it["id"]) for it in _tr_items}
# New This Week + Trending + Editor's Picks merged into ONE vertical rail
_merged = dedupe_cells(
    [item_cell(it, chan=it.get("_chan"), tag=("Just Added" if (i == 0 and days_old(it) <= 7) else None))
     for i, it in enumerate(_nw_items)]
    + [item_cell(it, chan=it.get("_chan")) for it in _tr_items]
    + list(reels))
_feat_used |= cells_ids(_merged)

page("featured", "Featured",
    hero_sm("",
        '<h1 class="hero-title ht-sm ht-feat">NIL TV Athletes<br>Creating Content Their Way</h1>',
        meta_row(None, "New Drops Daily"),
        "",
        watch_btn("ig-17961794499169577", "Our Athletes", "Missing Zoey Zubich already"),
        CDN + "/video/ig-17961794499169577/poster.jpg", reel="ig-17961794499169577", bleed=True, copy_cls="hc-wide"),
    [shelf("New This Week", "", _merged, gold=True)]
    + [themed_shelf(k, exclude=_feat_used) for k in FEAT_THEMED])


# ================= ABOUT PAGE =================
FOUNDERS = [
 ("Chief Marketing Officer","Emily Cole","Duke University &middot; Track &amp; XC",
  "First NCAA athlete to publish a book with NIL. A leading voice in NIL equity for female athletes.","700K+ followers"),
 ("Chief Content Officer","Chloe Mitchell","Aquinas College &middot; Volleyball",
  "First college athlete to monetize their NIL. Built one of the first NIL marketplaces.","4M+ followers"),
 ("Business Development","Will Levis","Kentucky &middot; Football",
  "Signed first ever NIL deal between a student athlete and a Thoroughbred stallion.","500K+ followers"),
 ("Financial Oversight","Neal Begovich","Stanford &middot; Duke Basketball",
  "Used his NIL to earn a Duke/Fuqua MBA, then land a job in sports Venture Capital.","5K+ followers"),
 ("NIL Compliance","Anthony Egbo","Abilene Christian &middot; Football",
  "First WAC/AUC Athlete to do an NIL deal. Testified to Congress on the value and needs for NIL.","25K+ followers"),
]
HEADSHOT = {"Emily Cole":"emily-cole.jpg","Chloe Mitchell":"chloe-mitchell.jpg","Will Levis":"will-levis.jpg",
            "Neal Begovich":"neal-begovich.jpg","Anthony Egbo":"anthony-egbo.jpg"}
founder_cells = ["""    <div class="founder-card">
      <img class="fh" src=""" + '"' + DEV + """/assets/img/team/%s" loading="lazy" decoding="async" alt="%s">
      <div class="inner">
        <span class="nm">%s</span>
        <span class="sch">%s</span>
        <p class="bio">%s</p>
        <span class="fw">%s</span>
      </div>
    </div>""" % (HEADSHOT[f[1]], f[1], f[1], f[2], f[3], f[4]) for f in FOUNDERS]


# Content pillars (three pillars, no phase labels, no chips)
PILLARS = [
 ("Content Collaboration","Cross campus, cross sport collaborations between athletes and colleges. Unique content that lives on NIL TV channels and builds athlete audiences from day one."),
 ("Competitions","Submissions driven competitions like NIL Star, giving athletes a platform to compete, go viral, and earn real recognition beyond their sport."),
 ("Original Content","Athlete powered original productions that build meaningful brand partnerships and generate real, recurring revenue for the creators behind them."),
]
phase_cells = ["""    <div class="phase-card">
      <span class="t">%s</span>
      <p>%s</p>
    </div>""" % (t, d) for t, d in PILLARS]


about_hero = """<section class="hero hero-sm" id="hero">
  <div class="hero-slide vslide v-wide on">
    <div class="hglow" style="background-image:url('%s/assets/img/sizzle-poster-wide.jpg')"></div>
    <video class="hero-echo" muted loop playsinline preload="none" data-src="%s/video/sizzle/niltv-wide-720a.mp4"></video>
    <video class="hero-video vw-desk" muted loop playsinline preload="none"
      poster="%s/assets/img/sizzle-poster-wide.jpg" data-src="%s/video/sizzle/niltv-wide-720a.mp4"></video>
    <div class="hero-copy">
      <h1 class="hero-title ht-sm">The Media Network<br>for the NIL Era</h1>
      <p class="hero-dek">Real Name. Real Game. Real TV.</p>

      <div class="hero-ctas">
        <a class="btn btn-gold" href="#work-with-niltv">Partner With Us</a>
      </div>
    </div>
  </div>
  <div class="hero-progress" id="heroDots">
    <button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button>
  </div>
</section>""" % (DEV, CDN, DEV, CDN)

ADVISORY = [
 ("Sion James","NBA Player &middot; Charlotte Hornets","/assets/img/advisory/sion-james.webp","Duke Men&rsquo;s Basketball alumnus and Charlotte Hornets guard, selected 33rd overall in the 2025 NBA Draft after Duke&rsquo;s ACC title run.","2025 NBA Draft &middot; Pick 33"),
 ("Julia Cole","Recording Artist","/assets/img/advisory/julia-cole2.webp","Nashville recording artist and Vanderbilt Volleyball alumna writing &ldquo;Sisterhood Country&rdquo; to empower women, with 700M+ streams.","IG 600k &middot; TikTok 1.1M"),
 ("Clifford Taylor IV","Content Creator &middot; Podcast Host","/assets/img/advisory/clifford-taylor-iv.webp","Viral sports content creator, mental health advocate, and former Florida walk-on football player. Hosts The Clifford Show podcast.","IG 251k &middot; TikTok 1.3M"),
 ("Alyssa Ustby","Professional Basketball Player","/assets/img/advisory/alyssa-ustby.webp","UNC Women&rsquo;s Basketball all-time rebound record holder now playing pro overseas, with a degree in Advertising &amp; PR and Business.","IG 70k &middot; TikTok 130k"),
 ("Jen Munoz","Founder &middot; Sporty Spice Collective","/assets/img/advisory/jen-munoz.webp","New Mexico Soccer alumna and former pro player whose 2026 World Cup promo partners include Audi USA, Coke, Adidas, and Google.","IG 234k &middot; TikTok 240k"),
 ("Jessica Gardner","Student Anesthesiologist Asst. &middot; UNMC","/assets/img/advisory/jessica-gardner.webp","Nebraska track alumna and sports &amp; lifestyle content creator, now training as a Student Anesthesiologist Assistant at UNMC.","IG 128k &middot; TikTok 209k"),
 ("Olivia Fabry","AI Specialist &middot; Franklin Templeton","/assets/img/advisory/olivia-fabry.webp","Notre Dame pole vault alumna building The Table, a growing community that helps female college athletes launch careers in finance.","IG 70k &middot; TikTok 110.3k"),
 ("Alex Jean Glover","Sports Broadcaster &middot; NIL Consultant","/assets/img/advisory/alex-jean-glover.webp","SMU Volleyball alumna and broadcaster with dual B.S. degrees in Operations Research and Data Science, plus an M.S. in Business.","IG 67k &middot; TikTok 80.8k"),
]
advisory_cells = ["""    <div class="adv-card">
      <img class="fh" src="%s" loading="lazy" decoding="async" alt="%s">
      <div class="inner">
        <span class="nm">%s</span>
        <span class="role">%s</span>
        <p class="bio">%s</p>
        <span class="fw">%s</span>
      </div>
    </div>""" % (img, nm, nm, role, bio, fw) for nm, role, img, bio, fw in ADVISORY]

about_sections = [
    """<div class="stat-band">
    <div class="st"><div class="n">275+</div><div class="l">Athlete Creators</div></div>
    <div class="st"><div class="n">108</div><div class="l">Schools Represented</div></div>
    <div class="st"><div class="n">55M+</div><div class="l">Impressions</div></div>
    <div class="st"><div class="n">17M+</div><div class="l">Social Reach</div></div>
  </div>""",
    """<div class="about-copy">
    <h2>Our Mission</h2>
    <p>NIL TV exists to give every college athlete a stage. We have launched the first national media network dedicated entirely to the NIL Era. The network makes it possible for all student athletes to showcase their stories, compete, and build relationships with brands on their own terms and in control of their NIL.</p>
    <p>Examples include NIL Star, NIL TV&rsquo;s flagship student athlete competition platform, NIL Collaborations, our home for viral, everyday moments, and NIL Local, our growing network of student athlete run affiliate channels. NIL TV is creating a place where athletes don&rsquo;t just play the game, they own their platform, their audience, and their future.</p>
    <p><b>NIL TV is where college athlete creator culture lives, and where the next generation of athletes becomes the next generation of media stars.</b></p>
  </div>""",
    shelf("NIL TV Co-Founders", "", founder_cells, gold=True, anchor=' data-grid="founders"'),
    shelf("NIL TV Advisory Board", "", advisory_cells, gold=True, anchor=' data-grid="advisory"'),
    shelf('Three Content Pillars,<br class="mbr"> One Media Network', "", phase_cells, anchor=' data-grid="roadmap"'),
    """<div class="work-band work-open" id="work-with-niltv">
    <h2>Work With NIL TV</h2>
    <div class="wb-grid">
      <div class="phase-card"><span class="t">Brands</span><p>Reach a fully engaged, fan voting audience through athlete led campaigns and event sponsorships.</p><p class="wb-mail"><a href="mailto:partners@niltv.com">partners@niltv.com</a></p></div>
      <div class="phase-card"><span class="t">Athletes</span><p>Enter the national competitions and create with the network from day one.</p><p class="wb-mail"><a href="/athlete-signup/">NIL TV College Athlete Application</a></p></div>
      <div class="phase-card"><span class="t">Organizations</span><p>Launch a channel run by your own athletes, produced the way their audience already watches.</p><p class="wb-mail"><a href="mailto:contact@niltv.com">contact@niltv.com</a></p></div>
    </div>
  </div>""",
    """<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"NIL TV","url":"https://dev.dkdfgvugisb3v.amplifyapp.com/","logo":"https://dev.dkdfgvugisb3v.amplifyapp.com/assets/img/niltv-logo.webp","description":"NIL TV is a student athlete media network: fan-voted national competitions, original campus series, and campus channels run with athletic departments.","sameAs":["https://www.instagram.com/niltv","https://www.instagram.com/nilstar","https://truebluetv.com"]}</script>""",
]

os.makedirs(OUT + "about", exist_ok=True)
_p = head.replace("<title>Concept B - CINEMA | NIL TV</title>", "<title>About - Cinema | NIL TV</title>", 1)
_p = _p.replace('<a href="/about/">About</a>', '<a href="/about/" class="active">About</a>', 1)
_body = about_hero + '\n\n<main class="shelves centered">\n\n' + "\n\n".join(about_sections) + "\n\n</main>\n\n"
io.open(OUT + "about/index.html", "w", encoding="utf-8", newline="\n").write(_p + _body + tail)
print("wrote about")


# ================= EVENT PAGES =================
def phase_cards(cards):
    cells = ["""    <div class="phase-card">
      <span class="ph">%s</span>
      <span class="t">%s</span>
      <p>%s</p>
    </div>""" % t for t in cards]
    return cells

os.makedirs(OUT + "nilstar", exist_ok=True)

# ---- /nilstar/ : season 1 recap ----
top20_cells = "\n".join(reel_cell(vid, name, sport, tag=tag)
                         for name, sport, school, vid, tag in TOP20)
ns_hero = hero_sm("Season 1 Champion Crowned",
    '<h1 class="hero-title logo-title"><img class="hero-logo hl-nilstar" src="/assets/img/nilstar-logo-wide.webp" alt="NIL Star"></h1>',
    "",
    "Bella Calvanese, Sacred Heart University NIL Student Athlete, Your first ever NIL Star.",
    watch_btn("ig-18106275875112509", "NIL Star Season 1", "Your first ever NIL Star is Bella Calvanese", label="Watch the Winner") +
    "\n" + (GHOST_BTN % ("#finalists", "The Top 20")),
    BELLA + "/poster.jpg", reel="ig-18106275875112509")

# Dates match @nilstar's own posts: launch May 8, entries due Jul 1,
# Top 20 announced Jul 7, Round 2 voting live Jul 13, champion Jul 22.
ns_road = shelf("Road to the Crown", "One season, 1M+ fan votes.", phase_cards([
    ("May 8","Auditions Open","The first NIL Star launches. Student athletes nationwide post their auditions in collab with @NILSTAR. Entries closed July 1."),
    ("Jul 7","Top 20 Selected","The finalists are announced. Twenty athletes advance to the final round."),
    ("Jul 13","Voting Opens","Round 2 goes live. Fans vote for their NIL Star across the network."),
    ("Jul 22","Champion Crowned","Bella Calvanese takes the first NIL Star title and the $10,000 grand prize."),
]), anchor=' data-grid="phases"')

ns_top20 = ("""<section class="shelf" id="finalists" data-grid="top20">
  <div class="shelf-head">
    <h2 class="shelf-title gold">The Top 20</h2>
    <span class="shelf-sub">The twenty who advanced to the final round of voting. Tap any card to rewatch their audition.</span>
  </div>
  <div class="rail wrapped">
""" + top20_cells + """
  </div>
</section>""")

ns_band = """<div class="cta-band">
    <div class="tx">
      <h2>More From the Network</h2>
      <p>New athlete content drops every day across the campus channels.</p>
    </div>
    <a class="btn btn-gold" href="/concepts/cinema/channels/">Browse Channels</a>
  </div>"""

page("nilstar/season-1", "NIL Star Season 1", ns_hero, [ns_road, ns_top20, ns_band], nav_label="Competitions", nav_slug="competitions")


# ================= ATHLETES PAGE (roster CSV from the private data folder) =================
import csv as _csv
os.makedirs(OUT + "athletes", exist_ok=True)
roster = []
_roster_csv = private_file("niltv_campus_ambassadors_f26.csv")
if _roster_csv:
    with open(_roster_csv, encoding="utf-8-sig") as fh:
        for row in _csv.DictReader(fh):
            nm = (row.get("NAME") or "").strip()
            sp = (row.get("SPORT") or "").strip()
            if nm and sp:
                roster.append((nm, sp))
else:
    print("build-sections: private ambassador roster not found - concept athletes page renders with no names (%s)" % HOWTO)
ath_cells = ["""    <button class="amb-plate ath-go" data-name="%s">
      <span class="ini">%s</span>
      <span class="nm">%s</span>
      <span class="ss">%s</span>
    </button>""" % (nm.replace('"', ''), "".join(w[0] for w in nm.split() if w[0].isalpha())[:2].upper(),
                    nm.replace("&", "&amp;"), sp.replace("&", "&amp;").replace("'", "&#39;"))
             for nm, sp in roster]
ath_head = '''<section class="hero hero-sm" id="hero" style="min-height:0">
  <div class="hero-slide vslide on" style="min-height:0">
    <div class="hero-copy" style="margin:120px 0 8px">
      <div class="hero-kicker">NIL TV Athletes</div>
      <h1 class="hero-title ht-sm">The Roster</h1>
      <p class="hero-dek">600+ athletes create with NIL TV. Tap any name on the roster to search their videos on the network.</p>
    </div>
  </div>
  <div class="hero-progress" id="heroDots">
    <button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button>
  </div>
</section>'''
ath_grid = '''<section class="shelf">
  <div class="shelf-head">
    <h2 class="shelf-title gold">The Roster</h2>
    <span class="shelf-sub">Tap any athlete to search their videos.</span>
  </div>
  <div class="rail wrapped">
''' + "\n".join(ath_cells) + '''
  </div>
</section>
<script>
document.addEventListener("DOMContentLoaded", function(){
  document.querySelectorAll(".ath-go").forEach(function(b){
    b.addEventListener("click", function(){
      if (!window.NILTV || !NILTV.openSearch) return;
      NILTV.openSearch();
      var inp = document.getElementById("search-input");
      if (inp){ inp.value = b.dataset.name; inp.dispatchEvent(new Event("input")); }
    });
  });
});
</script>'''
page("athletes", "Athletes",
    ath_head,
    [ath_grid])


# ================= VOTE PAGE (cinema shell around the live vote renderer) =================
vote_head = '''<section class="hero hero-sm" id="hero" style="min-height:0">
  <div class="hero-slide vslide on" style="min-height:0">
    <div class="hero-copy" style="margin:120px 0 8px">
      <div class="hero-kicker">NIL Star</div>
      <h1 class="hero-title ht-sm">Vote</h1>
      <p class="hero-dek">Fan voting decides every NIL Star event. Windows open with each competition.</p>
    </div>
  </div>
  <div class="hero-progress" id="heroDots">
    <button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button>
  </div>
</section>'''
vote_main = '''<div id="vote-mount" style="padding:0 var(--gutter)"></div>
<script>
window.addEventListener("load", function(){
  if (window.NILTV && NILTV.renderVote) NILTV.renderVote();
});
</script>'''
page("vote", "Vote", vote_head, [vote_main], nav_label="Competitions", nav_slug="competitions")


# ================= PARTNERS PAGE =================
os.makedirs(OUT + "partners", exist_ok=True)
p_brands = _nb.block(_NB)   # brand slider + stat tiles (no chip list)
MAILTO = "mailto:partnerships@niltv.com"
# Campaign figures are private build data (partners/campaigns.json in the
# private data folder); without it the page builds with no campaign shelf.
_pc_file = private_file("partners", "campaigns.json")
_pc = _pjson.load(io.open(_pc_file, encoding="utf-8")) if _pc_file else {}
P_LOGOS = ["ale8one.png","big12.png","brucebolt-dark.png","champssports.png","cheribundi.png",
 "claiborne.png","dicks.png","directv.png","drpepper.png","easton.png","elias.png","espn.png",
 "familydollar.png","garmin.png","grandslam.png","hellmanns.jpg","hrblock.png","invesco.png",
 "linktree.png","lmnt-mark.png","malones.jpg","nilstore.png","nobull.png","oofos.png",
 "sidelinebags.png","smartcups.png","therabody.png","trickplay.png"]
p_wall = "\n".join('    <div class="p-tile"><img src="%s/assets/img/partners2/%s" loading="lazy" decoding="async" alt=""></div>' % (DEV, f.rsplit(".", 1)[0] + ".png") for f in P_LOGOS)

p_hero = hero_sm("Partner With NIL TV",
    '<h1 class="hero-title ht-sm">Put Your Brand<br>On Air</h1>',
    meta_row(None, *[x for x in (_pc.get("impressions"), "%s Network Brands" % _nb.headline(_NB),
                                 _pc.get("campaignCount")) if x]),
    "Brands reach a fully engaged, fan voting audience through athlete led campaigns across the NIL TV network.",
    ('        <a class="btn btn-gold" href="' + MAILTO + '">Email Partnerships</a>'),
    CDN + "/video/tbtv-DXxxF97zEZZ/poster.jpg", reel="tbtv-DXxxF97zEZZ")

p_why = shelf("Why Brands Partner With NIL TV",
    "Every channel is hosted, produced, and shared by the athletes themselves.", phase_cards([
    ("01","Athlete Led Reach","Sponsorship shows up inside content their audience already follows. Native, not bolted on."),
    ("02","Real Campaign Proof","Live campaigns with NIL TV Athletes, with the numbers to show for it."),
    ("03","Campus-Level Precision","Target one school, or run the full network."),
    ("04","Built-In Compliance","Disclosure and contracting handled for you."),
]))

p_deals = shelf("Campaign Work - TrueBlue TV",
    "Real branded campaigns produced with NIL TV Athletes.",
    phase_cards([tuple(c) for c in _pc["campaigns"]]), gold=True) if _pc.get("campaigns") else ""

p_wall_sec = """<section class="shelf">
  <div class="shelf-head">
    <h2 class="shelf-title">The Founding Five Brand Network</h2>
    <span class="shelf-sub">A selection of brands our founding athletes have worked with across their careers. LMNT and Therabody are founder athlete brands from this network.</span>
  </div>
  <div class="p-wall">
""" + p_wall + """
  </div>
</section>"""

p_how = shelf("How Partnering Works", "Three steps from first call to on-air.", phase_cards([
    ("Step 1","Partner","Tell us your goals and audience. We map you to the pillar and schools that fit."),
    ("Step 2","Activate","Your integration goes live inside real programming, produced by the athletes hosting it."),
    ("Step 3","Measure","Track delivery with campaign reporting from the network dashboard."),
]))

p_faq = """<section class="shelf">
  <div class="shelf-head">
    <h2 class="shelf-title">Partner FAQ</h2>
  </div>
  <div class="faq">
    <details><summary>What does a NIL TV sponsorship actually include?</summary><p>Placement inside NIL Star competition episodes, weekly series drops, or a school's campus channel, plus campaign reporting and disclosure handled by the network.</p></details>
    <details><summary>Can we target a single school instead of the whole network?</summary><p>Yes. Campus packages run on one school's channel. National packages run across the network and every live campus channel.</p></details>
    <details><summary>How is NIL compliance handled?</summary><p>Every athlete integration is contracted and disclosed under NIL TV's compliance process before it airs.</p></details>
    <details><summary>Where do I see past campaign results?</summary><p>The campaign rail above shows live work with NIL TV Athletes, including plays and reach on the posts we can measure.</p></details>
  </div>
</section>"""

p_band = ('''<div class="cta-band">
    <div class="tx">
      <h2>Let's Put Your Brand On Air</h2>
      <p>Email our partnerships team to talk channel fit, campus targeting, and available inventory.</p>
    </div>
    <a class="btn btn-gold" href="''' + MAILTO + '''">Email Partnerships</a>
  </div>''')

page("partners", "Partners", p_hero, [x for x in (p_why, p_deals, p_wall_sec, p_brands, p_how, p_faq, p_band) if x])


# ================= CONTACT PAGE =================
os.makedirs(OUT + "contact", exist_ok=True)
contact_head = ('<section class=\"hero hero-sm\" id=\"hero\" style=\"min-height:0\">'
 '<div class=\"hero-slide vslide on\" style=\"min-height:0\">'
 '<div class=\"hero-copy\" style=\"margin:120px 0 8px\">'
 '<div class=\"hero-kicker\">Contact</div>'
 '<h1 class=\"hero-title ht-sm\">Get In Touch</h1>'

 '</div></div>'
 '<div class=\"hero-progress\" id=\"heroDots\"><button class=\"hero-dot on\" data-i=\"0\" aria-label=\"Slide 1\"><span></span></button></div>'
 '</section>')
contact_body = ('<div class=\"work-band\" style=\"margin-top:0\">'
 '<h2>Reach NIL TV</h2>'

 '<div class=\"wb-grid\">'
 '<div class=\"wb-card\"><div class=\"t\">General</div><p>Press, questions, and everything else.</p><p style=\"margin-top:10px\"><a href=\"mailto:contact@niltv.com\">contact@niltv.com</a></p></div>'
 '<div class=\"wb-card\"><div class=\"t\">Brands &amp; Partners</div><p>Campaigns, sponsorships, and organization channels.</p><p style=\"margin-top:10px\"><a href=\"mailto:partners@niltv.com\">partners@niltv.com</a></p></div>'
 '<div class=\"wb-card\"><div class=\"t\">Athletes</div><p>Join the network as an athlete creator.</p><p style=\"margin-top:10px\"><a href=\"/athlete-signup/\">NIL TV College Athlete Application</a></p></div>'
 '</div>'
 
 '</div>')
page("contact", "Contact", contact_head, [contact_body])
