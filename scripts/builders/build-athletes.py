# -*- coding: utf-8 -*-
"""Athlete profile pages + the /athletes/ directory, generated from
athletes/_data/athletes.json in the PRIVATE data folder (see private_data.py
and DEVELOPING.md). Nothing athlete-specific lives in the repo: the generated
athletes/<slug>/ pages and athletes/index.json are gitignored, and
athletes/index.html is committed with its directory block empty.

    python scripts/builders/build-athletes.py            # build the published set
    python scripts/builders/build-athletes.py --report   # who is held back and why, no writes
    python scripts/builders/build-athletes.py --drafts   # local preview: skip the onboarding gate
    python scripts/builders/build-athletes.py --review   # dev review: every record with a hero photo,
                                                         # each page carries a status strip
    (NILTV_ATHLETES_REVIEW=1 turns review on for deploy.ps1 -Env dev; prod never runs this builder)
    python scripts/builders/build-athletes.py --review --notes   # also show the open-items strip
    (or NILTV_ATHLETES_NOTES=1)

The page template is scripts/builders/athlete-template.html.

PUBLISH GATE. A record becomes a page only when both hold:
  1. onboarding: athletes/_data/onboarding.json says the athlete is
     "accepted" (agreement signed and Stripe payouts set up). The file is
     written by sync-athlete-status.py from the dashboard; a record with no
     entry is held back.
  2. complete: class year, at least MIN_FACTS facts, a description, a
     social handle, About copy and a hero photo that exists on disk.
Held-back records print with the reason and get no page, no directory card.
Pages left over from an earlier build are removed, so a held-back athlete
never ships by accident.

Page shape: the TrueBlueTV athlete-speaker anatomy in the NIL TV
chrome. Eyebrow "{School} NIL Student Athlete", name, sport line, facts grid
(empty rows never print), handle-only social cards, no CTAs, no follower
counts. The facts grid, social cards and photo wall size themselves to the
number of items, so no row is left half empty.

Feed: "{First}'s feed" needs MIN_FEED of the athlete's own reels. With fewer,
the section is hidden and the page script tops it up from the athlete's
campus channel; it only appears if that reaches MIN_FEED. With no channel,
there is no feed section. "More on NIL TV" needs MIN_MORE tiles.

About = NIL TV's own words, no source line. Photos are copied from the
athlete's folder and resized; 1.jpg is the hero, then 1, 2 or 4 wall photos.

Hand-built athlete pages (not in athletes.json) live in the private folder as
athletes/<slug>/ and are mirrored into the tree at build time (dev only).

Dev-only: deploy.ps1 prunes athletes/ from prod.
"""
import io, json, os, re, sys, html, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from private_data import private_root, HOWTO

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PRIVATE = private_root()
DATA = os.path.join(PRIVATE, 'athletes', '_data', 'athletes.json') if PRIVATE else None
ONBOARDING = os.path.join(PRIVATE, 'athletes', '_data', 'onboarding.json') if PRIVATE else None
TEMPLATE = os.path.join(os.path.dirname(__file__), 'athlete-template.html')
INDEX = os.path.join(ROOT, 'athletes', 'index.html')
POSTER = 'https://dr60jt51m7xh2.cloudfront.net/video/%s/poster.jpg'

MIN_FEED = 6    # tiles the feed (own videos + campus channel) needs before it shows
MIN_MORE = 4    # tiles for "More on NIL TV"
RAIL_MAX = 10   # channel and network rails always fill to this many tiles
MIN_FACTS = 3   # class year + at least two more
MAX_WALL = 4    # wall photos: 1, 2 or 4 (3 drops to 2 so the grid stays square)
FACT_KEYS = [('Class', 'class_year'), ('Position', 'position'), ('Team', 'team'), ('Hometown', 'hometown'),
             ('Height', 'height'), ('High school', 'high_school')]

def esc(s):
    return html.escape(s or '', quote=True).replace('&#x27;', '&rsquo;')

def fmt_dur(sec):
    m, s = divmod(int(sec), 60)
    return '%d:%02d' % (m, s)

ICON = {
    'instagram': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r="1" fill="currentColor" stroke="none"/></svg>',
    'tiktok': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14.5 4v9.6a3.9 3.9 0 1 1-3.2-3.83"/><path d="M14.5 5.2c.7 1.9 2.2 3.2 4.5 3.4"/></svg>',
    'youtube': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2.5" y="5.5" width="19" height="13" rx="3.5"/><path d="M10 9.2l5 2.8-5 2.8z" fill="currentColor" stroke="none"/></svg>',
}
EXT = '<svg class="ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M9 7h8v8"/></svg>'
PLAY = '<span class="play"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>'

# ---------------------------------------------------------------- pieces
def val(a, k):
    v = a.get(k)
    return v.strip() if isinstance(v, str) else v

def facts_of(a):
    return [(label, val(a, k)) for label, k in FACT_KEYS if val(a, k)]

def socials_of(a):
    return [s for s in a.get('socials') or [] if s.get('url') and s.get('handle')]

def ap_head(a):
    sub = ['<b>%s</b>' % esc(a['sport'])]
    if val(a, 'position'): sub.append(esc(val(a, 'position')))
    if val(a, 'number'): sub.append('No. %s' % esc(val(a, 'number')))
    facts = facts_of(a)
    rows = ''.join('          <div class="fact"><div class="k">%s</div><div class="v">%s</div></div>\n' % (k, esc(v)) for k, v in facts)
    return ('      <div class="ap-head">\n'
            '        <p class="eyebrow">%s NIL Student Athlete</p>\n'
            '        <h1>%s</h1>\n'
            '        <p class="sub">%s</p>\n'
            '        <div class="facts n%d">\n%s        </div>\n'
            '      </div>' % (esc(a['school']), esc(a['name']), ' &middot; '.join(sub), len(facts), rows))

def platcards(a):
    cards = ''
    socials = socials_of(a)
    for so in socials:
        cards += ('      <a class="pc" href="%s" target="_blank" rel="noopener">\n'
                  '        <div class="pc-top"><span class="h">%s%s</span>%s</div>\n'
                  '        <div class="handle">%s</div>\n'
                  '      </a>\n' % (esc(so['url']), ICON.get(so['platform'], ''), esc(so['label']), EXT, esc(so['handle'])))
    return '    <div class="platcards n%d">\n%s    </div>' % (len(socials), cards)

def tile(r):
    dur = '        <span class="dur">%s</span>\n' % fmt_dur(r['duration']) if r.get('duration') else ''
    return ('      <a class="tile" href="/watch/%s/">\n'
            '        <img src="%s" alt="" loading="lazy">\n'
            '%s'
            '        %s\n'
            '        <div class="cap"><div class="t">%s</div></div>\n'
            '      </a>\n' % (r['id'], POSTER % r['id'], dur, PLAY, esc(r['title'])))

def rail_section(sec_id, kick, title, more, tiles, attrs=''):
    return ('<section class="feed" id="%s"%s>\n'
            '  <div class="wrap">\n'
            '    <div class="sec-head">\n'
            '      <div>\n'
            '        <p class="kick">%s</p>\n'
            '        <h2>%s</h2>\n'
            '      </div>\n%s'
            '    </div>\n'
            '    <div class="rail">\n%s'
            '    </div>\n'
            '  </div>\n'
            '</section>' % (sec_id, attrs, kick, title, more, tiles))

def feed_section(a):
    """One rail, "{First}'s feed": the athlete's own videos first (static, all
    of them), then their campus channel's latest, added by the page script up
    to RAIL_MAX. The rail shows only when the two together reach MIN_FEED.
    No campus channel = own videos only. "More on NIL TV" (template) follows."""
    reels = a.get('reels') or []
    ch = a.get('channel')
    if not ch and len(reels) < MIN_FEED:
        return '<!-- FEED: %d own videos and no campus channel, under %d, so no feed -->' % (len(reels), MIN_FEED)
    attrs = (' data-channel="%s"' % ch['id'] if ch else '') + ('' if len(reels) >= MIN_FEED else ' hidden')
    more = ('      <a class="more" href="/channels/%s/">Everything on %s &rarr;</a>\n' % (ch['slug'], esc(ch['name']))) if ch else ''
    kick = 'On NIL TV and %s' % esc(ch['name']) if ch else 'On NIL TV'
    return ('<!-- FEED: own videos first, then the campus channel up to %d; shown at %d+ -->\n' % (RAIL_MAX, MIN_FEED) +
            rail_section('feed', kick, "%s&rsquo;s feed" % esc(a['first']), more, ''.join(tile(r) for r in reels), attrs))

def about_section(a, wall_files):
    ab = a['about']
    paras = ''.join('        <p>%s</p>\n' % esc(p) for p in ab['paragraphs'] if p.strip())
    line = '        <p class="quote">%s</p>\n' % ab['line'] if (ab.get('line') or '').strip() else ''
    wall = ''.join('        <div class="ph"><img src="photos/%s" alt="" loading="lazy" style="object-position:%s"></div>\n' % (f, pos) for f, pos in wall_files)
    wall_block = '      <div class="wall n%d">\n%s      </div>\n' % (len(wall_files), wall) if wall_files else ''
    return ('<!-- ABOUT + PHOTOS -->\n'
            '<section class="about" id="about">\n'
            '  <div class="wrap">\n'
            '    <div class="about-grid%s">\n'
            '      <div>\n'
            '        <p class="kick">About %s</p>\n'
            '%s%s'
            '      </div>\n'
            '%s'
            '    </div>\n'
            '  </div>\n'
            '</section>' % ('' if wall_files else ' solo', esc(a['first']), line, paras, wall_block))

def wall_items(a):
    """1, 2 or 4 wall photos: a third photo would leave a hole in the 2-up grid."""
    wall = (a['photos'].get('wall') or [])[:MAX_WALL]
    return wall[:2] if len(wall) == 3 else wall

# ---------------------------------------------------------------- photos
def copy_photos(a, outdir):
    """1.jpg = hero, 2..N = wall. Resized to <=1200px tall, JPEG q86. Returns
    (hero_w, hero_h, [(file, pos), ...])."""
    from PIL import Image, ImageOps
    p = a['photos']; src = photo_dir(a)
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)   # a photo dropped from the record must not linger
    os.makedirs(outdir, exist_ok=True)
    items = [p['hero']] + wall_items(a)
    out = []; hero_wh = None
    for i, it in enumerate(items, start=1):
        im = Image.open(os.path.join(src, it['file']))
        im = ImageOps.exif_transpose(im).convert('RGB')
        if im.height > 1200 or im.width > 1200:
            im.thumbnail((1200, 1200))
        name = '%d.jpg' % i
        im.save(os.path.join(outdir, name), 'JPEG', quality=86, optimize=True)
        if i == 1: hero_wh = im.size
        else: out.append((name, it['pos']))
    return hero_wh[0], hero_wh[1], out

def photo_dir(a):
    src = (a.get('photos') or {}).get('src_dir') or ''
    return src if os.path.isabs(src) else os.path.join(PRIVATE, src)   # private-relative, e.g. athletes/_photos/<slug>

# ---------------------------------------------------------------- publish gate
def load_onboarding():
    """slug -> {"status": ..., "checked": ...} from onboarding.json (written by
    sync-athlete-status.py). Missing file = nobody is cleared yet."""
    if not ONBOARDING or not os.path.exists(ONBOARDING):
        return {}
    return json.load(io.open(ONBOARDING, encoding='utf-8')).get('athletes', {})

# Copy that talks about the page instead of the athlete goes stale the moment
# the page changes ("the rail below", "her page is ready for her first
# episode") and reads as a placeholder. Profiles have no CTAs, so no
# "work with her" either.
STALE_COPY = re.compile(r"\b(rail|feed)\b|\b(this|his|her|their) page\b|\bpage is ready\b|"
                        r"\bwork with (him|her|them)\b|\b(below|above)\b", re.I)

def stale_copy(a):
    ab = a.get('about') or {}
    texts = [a.get('description') or '', ab.get('line') or ''] + list(ab.get('paragraphs') or [])
    return sorted({m.group(0).lower() for t in texts for m in STALE_COPY.finditer(re.sub('<[^>]+>', '', t))})

def missing(a):
    """What keeps this record from a complete page. Empty list = complete."""
    out = [k for k in ('slug', 'name', 'first', 'school', 'sport', 'class_year', 'description') if not val(a, k)]
    n = len(facts_of(a))
    if n < MIN_FACTS:
        out.append('facts (%d of %d)' % (n, MIN_FACTS))
    if not socials_of(a):
        out.append('social handle')
    if not [p for p in (a.get('about') or {}).get('paragraphs') or [] if p.strip()]:
        out.append('about copy')
    stale = stale_copy(a)
    if stale:
        out.append('copy describes the page (%s)' % ', '.join(stale))
    ph = a.get('photos') or {}
    if not (ph.get('hero') or {}).get('file'):
        out.append('hero photo')
    else:
        d = photo_dir(a)
        for it in [ph['hero']] + wall_items(a):
            if not os.path.exists(os.path.join(d, it['file'])):
                out.append('photo file %s' % it['file'])
    return out

def gate(athletes, onboarding, drafts=False):
    """Split records into (publish, held) where held = [(record, reasons)]."""
    publish, held = [], []
    for a in athletes:
        why = missing(a)
        st = (onboarding.get(a.get('slug')) or {}).get('status')
        if st != 'accepted' and not drafts:
            why.insert(0, 'onboarding %s' % (st or 'not confirmed') + (' (Stripe not complete)' if st else ''))
        (held.append((a, why)) if why else publish.append(a))
    return publish, held

# ---------------------------------------------------------------- review mode
REVIEW = '--review' in sys.argv or os.environ.get('NILTV_ATHLETES_REVIEW') == '1'
# the review strip (open items per page) is off unless asked for, so review
# pages look exactly like prod pages
NOTES = '--notes' in sys.argv or os.environ.get('NILTV_ATHLETES_NOTES') == '1'
STATUS_LABEL = {
    'accepted': 'Stripe complete',
    'stripe_pending': 'Stripe invited, not finished',
    'signed': 'Agreement signed, Stripe not set up',
    'agreement_sent': 'Agreement sent, not signed',
    'approved': 'Approved, no agreement yet',
    'applicant': 'Applied, not reviewed',
    'declined': 'Declined',
}
REVIEW_CSS = ('<style id="review-strip">.rv{position:sticky;top:56px;z-index:90;background:#2a1f05;border-bottom:1px solid var(--goldline);'
              'color:var(--text);font-size:13px;line-height:1.5;padding:10px var(--gutter)}.rv b{color:var(--gold-bright)}'
              '.rv .ok{color:#6fdd9a}.rv .no{color:#ff8a8a}.rv ul{margin:4px 0 0;padding-left:18px}</style>')

def status_of(a, onboarding):
    return (onboarding.get(a['slug']) or {}).get('status')

def review_strip(a, onboarding, why):
    """Review notes only (missing facts, photo flags); no pipeline status on the page."""
    items = [w for w in why if not w.startswith('onboarding')] + list(a.get('review_notes') or [])
    lis = ''.join('<li>%s</li>' % esc(i) for i in items)
    return ('%s<div class="rv"><b>REVIEW</b> &middot; %s%s</div>\n'
            % (REVIEW_CSS, 'open items' if items else 'no open items', '<ul>%s</ul>' % lis if lis else ''))

# ---------------------------------------------------------------- build
def build_page(a, tpl, strip=''):
    outdir = os.path.join(ROOT, 'athletes', a['slug'])
    w, h, wall = copy_photos(a, os.path.join(outdir, 'photos'))
    reels = a.get('reels') or []
    page = (tpl.replace('{{page_title}}', esc('%s | %s %s | NIL TV' % (a['name'], a['school'], a['sport'])))
               .replace('{{name}}', esc(a['name']))
               .replace('{{description}}', esc(a['description']))
               .replace('{{slug}}', a['slug'])
               .replace('{{hero_w}}', str(w)).replace('{{hero_h}}', str(h))
               .replace('{{hero_pos}}', a['photos']['hero']['pos'])
               .replace('{{ap_head}}', ap_head(a))
               .replace('{{platcards}}', platcards(a))
               .replace('{{feed_section}}', feed_section(a))
               .replace('{{about_section}}', about_section(a, wall))
               .replace('{{seed}}', reels[0]['id'] if reels else '')
               .replace('{{min_feed}}', str(MIN_FEED)).replace('{{min_more}}', str(MIN_MORE)).replace('{{rail_max}}', str(RAIL_MAX))
               .replace('{{mine}}', json.dumps({r['id']: 1 for r in reels})))
    assert '{{' not in page, 'unfilled placeholder in ' + a['slug']
    if strip:
        page = page.replace('<main>', strip + '<main>', 1)
    io.open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8', newline='\n').write(page)
    return outdir

DIR_CSS = """
/* ---- athlete directory (build-athletes.py) ---- */
.ath-filters{margin:0 0 22px;padding:0 var(--gutter);display:grid;gap:12px}
.ath-filters .grp{display:flex;align-items:center;gap:8px;flex-wrap:nowrap;min-width:0}
/* filter chips: one sliding row with edge arrows (shown only when there is more that way) */
.chips-wrap{position:relative;flex:1;min-width:0}
.chips{display:flex;gap:8px;overflow-x:auto;scroll-behavior:smooth;scrollbar-width:none;padding:2px 0}
.chips::-webkit-scrollbar{display:none}
.chips .chip{flex:0 0 auto;white-space:nowrap}
.chip-arrow{position:absolute;top:50%;transform:translateY(-50%);z-index:2;width:32px;height:32px;border-radius:50%;border:1px solid var(--goldline);background:rgba(6,6,8,.92);color:var(--text);font-size:20px;line-height:1;display:flex;align-items:center;justify-content:center;cursor:pointer;opacity:0;visibility:hidden;transition:opacity .2s,background .2s,color .2s}
.chip-arrow.prev{left:0}
.chip-arrow.next{right:0}
.chip-arrow.on{opacity:1;visibility:visible}
.chip-arrow:hover{background:var(--gold);color:#060608}
.chips-wrap::before,.chips-wrap::after{content:"";position:absolute;top:0;bottom:0;width:56px;pointer-events:none;opacity:0;transition:opacity .2s;z-index:1}
.chips-wrap::before{left:0;background:linear-gradient(90deg,var(--bg),rgba(6,6,8,0))}
.chips-wrap::after{right:0;background:linear-gradient(270deg,var(--bg),rgba(6,6,8,0))}
.chips-wrap.more-left::before,.chips-wrap.more-right::after{opacity:1}
.ath-filters .lbl{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-right:6px;min-width:52px}
.chip{border:1px solid var(--border);background:transparent;color:var(--dim);border-radius:999px;padding:6px 14px;font-size:13px;font-weight:600;cursor:pointer;transition:color .15s,border-color .15s}
.chip:hover{color:var(--text)}
.chip.on{color:var(--gold);border-color:var(--gold)}
.ath-count{margin:0 0 12px;padding:0 var(--gutter);font-size:12.5px;color:var(--dim)}
.ath-grid{padding:0 var(--gutter);display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:18px}
.ath-card{position:relative;display:block;aspect-ratio:4/5;border-radius:14px;overflow:hidden;border:1px solid var(--border);background:var(--surface);transition:transform .2s ease,border-color .2s ease}
.ath-card:hover{transform:translateY(-4px);border-color:rgba(217,178,91,.5)}
.ath-card img{width:100%;height:100%;object-fit:cover;display:block}
.ath-card .cap{position:absolute;left:0;right:0;bottom:0;padding:70px 14px 14px;background:linear-gradient(180deg,rgba(6,6,8,0) 0%,rgba(6,6,8,.92) 70%)}
.ath-card .nm{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:22px;line-height:1;text-transform:uppercase;letter-spacing:.01em;color:var(--text)}
/* caption = three uniform lines: name, school, sport; each stays on one line */
.ath-card .nm,.ath-card .ss{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ath-card .ss{font-size:12.5px;line-height:1.35;color:var(--dim);margin-top:3px}
.ath-card .nm + .ss{margin-top:6px}
.ath-card[hidden]{display:none}
.ath-empty{padding:30px var(--gutter);color:var(--dim);font-size:14px}
@media (max-width:640px){.ath-grid{grid-template-columns:repeat(2,1fr);gap:12px}.ath-card .nm{font-size:18px}}
"""

WALL_CSS = """
/* ---- athlete action collage (build-athletes.py) ---- */
.ath-hero{padding:56px 0 0}
.ath-hero + .shelves{margin-top:0}
#athlete-videos .reel-by{margin:2px 0 0;font-size:11.5px;font-weight:600;letter-spacing:.04em;color:var(--gold);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:clamp(178px,16vw,236px)}
.ath-hero .collage{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));grid-template-rows:repeat(2,clamp(170px,20vw,320px));gap:4px;margin-bottom:clamp(36px,4vw,56px)}
.ath-hero .tl{position:relative;display:block;overflow:hidden;background:var(--surface)}
.ath-hero .tl img{width:100%;height:100%;object-fit:cover;display:block;filter:grayscale(1) contrast(1.1) brightness(.85);transition:filter .35s ease,transform .5s ease}
.ath-hero .tl::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(217,178,91,.55),rgba(120,84,24,.55));mix-blend-mode:color;transition:opacity .35s ease;pointer-events:none}
.ath-hero .tl:hover img{filter:none;transform:scale(1.03)}
.ath-hero .tl:hover::after{opacity:0}
.ath-hero .t1{grid-column:1/4;grid-row:1/3}
.ath-hero .t2{grid-column:4/5;grid-row:1/3}
.ath-hero .t3{grid-column:5/6;grid-row:1/2}.ath-hero .t4{grid-column:6/7;grid-row:1/2}
.ath-hero .t5{grid-column:5/6;grid-row:2/3}.ath-hero .t6{grid-column:6/7;grid-row:2/3}
.ath-hero .t1 .shade{position:absolute;inset:0;background:linear-gradient(0deg,rgba(6,6,8,.85) 0%,rgba(6,6,8,0) 55%);pointer-events:none;z-index:1}
.ath-hero .ttl{position:absolute;left:var(--gutter);bottom:clamp(20px,3vw,40px);z-index:2;margin:0;font-family:'Barlow Condensed',sans-serif;font-weight:800;text-transform:uppercase;line-height:.88;font-size:clamp(52px,7.5vw,120px);color:var(--text);pointer-events:none}
.ath-hero .ttl::after{content:"";display:block;width:56px;height:3px;background:var(--gold);margin-top:14px}
@media (max-width:760px){.ath-hero .collage{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:240px 150px 150px}.ath-hero .t1{grid-column:1/3;grid-row:1/2}.ath-hero .t2,.ath-hero .t3{display:none}.ath-hero .t4{grid-column:1/2;grid-row:2/3}.ath-hero .t5{grid-column:2/3;grid-row:2/3}.ath-hero .t6{grid-column:1/3;grid-row:3/4}}
@media (prefers-reduced-motion:reduce){.ath-hero .tl img,.ath-hero .tl::after{transition:none}}
"""

def load_collage(published):
    """athletes/_data/collage.json: [{slug, photo, pos}] - six action shots,
    first = the big frame, second = the tall one. Unpublished slugs drop out."""
    p = os.path.join(PRIVATE, 'athletes', '_data', 'collage.json') if PRIVATE else None
    if not p or not os.path.exists(p):
        return []
    ok = {a['slug'] for a in published}
    return [c for c in json.load(io.open(p, encoding='utf-8')) if c['slug'] in ok]

def wall_hero(athletes):
    """Action collage: one big frame with the title, one tall, four small, gold
    duotone that clears on hover. Needs all six shots, else title only."""
    tiles = load_collage(athletes)[:6]
    if len(tiles) < 6:
        return '<section class="ath-hero" id="hero">\n  <h1 class="ttl" style="position:static">The Athletes</h1>\n</section>'
    cells = ''
    for n, c in enumerate(tiles, 1):
        extra = '<div class="shade"></div><h1 class="ttl">The Athletes</h1>' if n == 1 else ''
        cells += ('<a class="tl t%d" href="/athletes/%s/"%s><img src="/athletes/%s/photos/%d.jpg" alt="" style="object-position:%s">%s</a>'
                  % (n, c['slug'], '' if n == 1 else ' tabindex="-1" aria-hidden="true"', c['slug'], c['photo'], c['pos'], extra))
    return '<section class="ath-hero" id="hero">\n  <div class="collage">%s</div>\n</section>' % cells

CHIP_JS = r"""<script>
/* filter chips: arrows slide the row; each arrow and edge fade shows only when
   there is more that way; the selected chip is scrolled into view */
(function(){
  document.querySelectorAll(".chips-wrap").forEach(function(wrap){
    var row = wrap.querySelector(".chips"), prev = wrap.querySelector(".chip-arrow.prev"), next = wrap.querySelector(".chip-arrow.next");
    var update = function(){
      var max = row.scrollWidth - row.clientWidth - 2;
      prev.classList.toggle("on", row.scrollLeft > 2); wrap.classList.toggle("more-left", row.scrollLeft > 2);
      next.classList.toggle("on", row.scrollLeft < max); wrap.classList.toggle("more-right", row.scrollLeft < max);
    };
    prev.addEventListener("click", function(){ row.scrollBy({left: -row.clientWidth * 0.7, behavior: "smooth"}); });
    next.addEventListener("click", function(){ row.scrollBy({left: row.clientWidth * 0.7, behavior: "smooth"}); });
    row.addEventListener("scroll", update, {passive: true});
    window.addEventListener("resize", update);
    var on = row.querySelector(".chip.on");
    if (on && on.offsetLeft + on.offsetWidth > row.clientWidth) row.scrollLeft = on.offsetLeft - 40;
    update();
  });
})();
</script>"""

SHELF_MAX = 24   # videos in the "From Our Athletes" shelf

def athlete_shelf(athletes):
    """Round-robin over athletes with their own videos (each list newest first),
    so the shelf alternates people instead of opening on one athlete's run."""
    queues = [(a, list(a.get('reels') or [])) for a in athletes if a.get('reels')]
    queues.sort(key=lambda x: -len(x[1]))   # lead with the athletes who have the most content
    picks, seen = [], set()
    while queues and len(picks) < SHELF_MAX:
        nxt = []
        for a, q in queues:
            while q and q[0]['id'] in seen:
                q.pop(0)
            if q:
                r = q.pop(0); seen.add(r['id']); picks.append((a, r))
            if q:
                nxt.append((a, q))
        queues = nxt
    if len(picks) < MIN_FEED:
        return ''
    cells = ''
    for a, r in picks:
        dur = '<span class="dur">%s</span>' % fmt_dur(r['duration']) if r.get('duration') else ''
        cells += ('    <div class="reel-cell">\n'
                  '      <a class="card card-reel" href="/watch/%s/" aria-label="%s">\n'
                  '        <img src="%s" loading="lazy" decoding="async" alt="%s">\n'
                  '        %s\n'
                  '      </a>\n'
                  '      <p class="reel-caption">%s</p>\n'
                  '      <p class="reel-by">%s</p>\n'
                  '    </div>\n' % (r['id'], esc(r['title']), POSTER % r['id'], esc(r['title']), dur, esc(r['title']), esc(a['name'])))
    return ('<!-- FROM OUR ATHLETES : the athletes\' own NIL TV videos (build-athletes.py) -->\n'
            '<section class="shelf" id="athlete-videos">\n'
            '  <div class="shelf-head">\n'
            '    <h2 class="shelf-title gold">From Our Athletes</h2>\n'
            '  </div>\n'
            '  <div class="rail">\n%s'
            '  </div>\n'
            '</section>\n\n' % cells)

def build_index(athletes, pills=None):
    s = io.open(INDEX, encoding='utf-8').read()
    # hero copy
    # hero: the portrait wall (replaces the old text hero; idempotent)
    # replace the wall CSS block on every build so edits to WALL_CSS land
    s = re.sub(r'\n/\* ---- athlete (?:portrait wall|action collage) \(build-athletes\.py\) ---- \*/.*?\n@media \(prefers-reduced-motion:reduce\)\{[^\n]*\n', '\n', s, count=1, flags=re.S)
    s = s.replace('</style>', WALL_CSS + '</style>', 1)
    hero_athletes = athletes
    s = re.sub(r'<section class="(?:hero hero-sm|ath-hero)" id="hero".*?</section>', lambda m: wall_hero(hero_athletes), s, count=1, flags=re.S)
    # hero: title only, no kicker, no dek
    s = re.sub(r'\s*<div class="hero-kicker">[^<]*</div>', '', s, count=1)
    s = re.sub(r'\s*<p class="hero-dek">[^<]*</p>', '', s, count=1)
    s = re.sub(r'(<h1 class="hero-title ht-sm">)[^<]*(</h1>)', r'\1The Athletes\2', s, count=1)
    s = s.replace('NIL TV Athletes | NIL TV', 'The Athletes | NIL TV')
    # css: replace the block on every build so edits to DIR_CSS land
    s = re.sub(r'\n/\* ---- athlete directory \(build-athletes\.py\) ---- \*/.*?\n@media \(max-width:640px\)\{\.ath-grid[^\n]*\n', '\n', s, count=1, flags=re.S)
    s = s.replace('</style>', DIR_CSS + '</style>', 1)
    athletes = sorted(athletes, key=lambda a: (a['name'].split()[-1].lower(), a['name'].lower()))
    schools = sorted({a['school'] for a in athletes}); sports = sorted({a['sport'] for a in athletes})
    def chips(kind, label, vals):
        # a filter with one option filters nothing, so it does not print
        if len(vals) < 2:
            return ''
        out = '<button class="chip on" data-%s="">All</button>' % kind
        for v in vals: out += '<button class="chip" data-%s="%s">%s</button>' % (kind, esc(v), esc(v))
        # one row that slides; arrows show only when there is more that way
        return ('    <div class="grp"><span class="lbl">%s</span><div class="chips-wrap">'
                '<button type="button" class="chip-arrow prev" aria-label="Scroll filters back">&lsaquo;</button>'
                '<div class="chips">%s</div>'
                '<button type="button" class="chip-arrow next" aria-label="Scroll filters forward">&rsaquo;</button>'
                '</div></div>\n' % (label, out))
    groups = chips('sport', 'Sport', sports)   # no school filter
    filters = '  <div class="ath-filters">\n%s  </div>\n' % groups if groups else ''
    empty = 'No athletes match that filter yet.' if athletes else 'Athlete profiles open soon.'
    cards = ''
    for a in athletes:
        cards += ('    <a class="ath-card" href="/athletes/%s/" data-school="%s" data-sport="%s">\n'
                  '      <img src="/athletes/%s/photos/1.jpg" alt="%s" loading="lazy" style="object-position:%s">\n'
                  '      <div class="cap"><div class="nm">%s</div><div class="ss">%s NIL Athlete</div><div class="ss">%s</div>%s</div>\n'
                  '    </a>\n' % (a['slug'], esc(a['school']), esc(a['sport']), a['slug'], esc(a['name']), a['photos']['hero']['pos'],
                                  esc(a['name']), esc(val(a, 'school_card') or a['school']), esc(a['sport']),   # school_card: shorter label for long names
                                  (pills or {}).get(a['slug'], '')))
    main = ('<main class="shelves">\n\n'
            '%s'
            '<!-- ATHLETE DIRECTORY : generated by scripts/builders/build-athletes.py from athletes/_data/athletes.json -->\n'
            '<section class="shelf" id="roster" style="padding-top:8px">\n'
            '%s'
            '  <div class="ath-count" id="athCount"></div>\n'
            '  <div class="ath-grid" id="athGrid">\n%s'
            '  </div>\n'
            '  <div class="ath-empty" id="athEmpty" hidden>%s</div>\n'
            '</section>\n'
            '<script>\n'
            '(function(){\n'
            '  var cards = Array.prototype.slice.call(document.querySelectorAll(".ath-card"));\n'
            '  var state = {school:"", sport:""};\n'
            '  try { var q = new URLSearchParams(location.search); state.school = q.get("school") || ""; state.sport = q.get("sport") || ""; } catch (e) {}\n'
            '  function apply(){\n'
            '    var n = 0;\n'
            '    cards.forEach(function(c){ var ok = (!state.school || c.dataset.school === state.school) && (!state.sport || c.dataset.sport === state.sport); c.hidden = !ok; if (ok) n++; });\n'
            '    document.querySelectorAll(".chip").forEach(function(b){ var k = b.dataset.school !== undefined ? "school" : "sport"; b.classList.toggle("on", (b.dataset[k] || "") === state[k]); });\n'
            '    document.getElementById("athCount").textContent = cards.length ? n + (n === 1 ? " athlete" : " athletes") : "";\n'
            '    document.getElementById("athEmpty").hidden = n > 0;\n'
            '    try { var u = new URL(location.href); state.school ? u.searchParams.set("school", state.school) : u.searchParams.delete("school"); state.sport ? u.searchParams.set("sport", state.sport) : u.searchParams.delete("sport"); history.replaceState(null, "", u); } catch (e) {}\n'
            '  }\n'
            '  document.querySelectorAll(".chip").forEach(function(b){ b.addEventListener("click", function(){ if (b.dataset.school !== undefined) state.school = b.dataset.school; else state.sport = b.dataset.sport; apply(); }); });\n'
            '  apply();\n'
            '})();\n'
            '</script>\n'
            '%s\n'
            '</main>' % (athlete_shelf(athletes), filters, cards, empty, CHIP_JS))
    s2 = re.sub(r'<main class="shelves">.*?</main>', lambda m: main, s, count=1, flags=re.S)
    assert s2 != s or '<!-- ATHLETE DIRECTORY' in s, 'index: main block not replaced'
    io.open(INDEX, 'w', encoding='utf-8', newline='\n').write(s2)
    index = [dict(slug=a['slug'], name=a['name'], school=a['school'], sport=a['sport'], classYear=val(a, 'class_year') or '',
                  portrait='/athletes/%s/photos/1.jpg' % a['slug'], channel=(a.get('channel') or {}).get('id')) for a in athletes]
    io.open(os.path.join(ROOT, 'athletes', 'index.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(index, indent=1))

def mirror_static(athletes):
    """Hand-built athlete pages: every <private>/athletes/<slug>/ that is not a
    generated record (and not _data/_photos) is copied into the tree as-is."""
    generated = {a['slug'] for a in athletes}
    src_root = os.path.join(PRIVATE, 'athletes')
    n = 0
    for name in sorted(os.listdir(src_root)):
        src = os.path.join(src_root, name)
        if name.startswith('_') or name in generated or not os.path.isdir(src):
            continue
        dst = os.path.join(ROOT, 'athletes', name)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        n += 1
        print('mirrored', os.path.relpath(dst, ROOT), '(hand-built page)')
    return n

def prune(keep):
    """Remove athletes/<dir>/ left from an earlier build that this build does not
    produce (a record that is now held back, renamed or deleted). Every
    athletes/<dir>/ is builder output (gitignored), so nothing tracked is lost."""
    root = os.path.join(ROOT, 'athletes')
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p) and name not in keep and not name.startswith('_'):
            shutil.rmtree(p)
            print('removed', os.path.relpath(p, ROOT), '(not published by this build)')

def report(publish, held):
    print('publish (%d): %s' % (len(publish), ', '.join(a['slug'] for a in publish) or '-'))
    for a, why in held:
        print('held back: %s | %s' % (a.get('slug') or a.get('name') or '?', '; '.join(why)))

def main():
    if not DATA or not os.path.exists(DATA):
        print('build-athletes: private data not found - skipping athlete pages (%s)' % HOWTO)
        return 1 if '--require' in sys.argv else 0
    drafts = '--drafts' in sys.argv
    athletes = json.load(io.open(DATA, encoding='utf-8'))
    onboarding = load_onboarding()
    if not onboarding and not drafts:
        print('build-athletes: no onboarding.json yet, so no athlete is cleared to publish (run sync-athlete-status.py)')
    publish, held = gate(athletes, onboarding, drafts)
    report(publish, held)
    if '--report' in sys.argv:
        return 0
    if drafts:
        print('DRAFTS: onboarding gate skipped. Local preview only; never deploy this tree.')
    tpl = io.open(TEMPLATE, encoding='utf-8').read()
    if REVIEW:
        return build_review(athletes, onboarding, tpl)
    prune({a['slug'] for a in publish})   # hand-built pages are copied back in by mirror_static
    for a in publish:
        out = build_page(a, tpl)
        n = len(a.get('reels') or [])
        feed = 'own feed' if n >= MIN_FEED else ('channel top-up' if a.get('channel') else 'no feed')
        print('built', os.path.relpath(out, ROOT), '| reels', n, '|', feed)
    build_index(publish)
    static = mirror_static(athletes)
    print('index:', len(publish), 'athletes', '| held back:', len(held), '| hand-built pages mirrored:', static)
    return 0

def build_review(athletes, onboarding, tpl):
    """Dev review: every record with a hero photo on disk gets a page, gates
    ignored, each page and directory card labelled with its pipeline status."""
    print('REVIEW: gates skipped, status strips on. Dev only.')
    ok = []
    for a in athletes:
        why = missing(a)
        if any(w.startswith('hero photo') or w.startswith('photo file') for w in why):
            print('skipped (no usable photos):', a['slug']); continue
        st = status_of(a, onboarding)
        ok.append((a, why, st))
    prune({a['slug'] for a, _, _ in ok})
    pills = {}
    for a, why, st in ok:
        build_page(a, tpl, review_strip(a, onboarding, why) if NOTES else '')
        print('built (review)', a['slug'], '|', STATUS_LABEL.get(st, 'status unknown'), '|', '; '.join(why) or 'complete')
    build_index([a for a, _, _ in ok], pills)
    print('index:', len(ok), 'athletes (review)')
    return 0

if __name__ == '__main__':
    sys.exit(main())
