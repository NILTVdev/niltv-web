# -*- coding: utf-8 -*-
"""Athlete profile pages + the /athletes/ directory, generated from
athletes/_data/athletes.json in the PRIVATE data folder (see private_data.py
and DEVELOPING.md). Nothing athlete-specific lives in the repo: the generated
athletes/<slug>/ pages and athletes/index.json are gitignored, and
athletes/index.html is committed with its directory block empty.

    python scripts/builders/build-athletes.py            # build everything

The page template is scripts/builders/athlete-template.html.

Page shape: the TrueBlueTV athlete-speaker anatomy in the NIL TV
chrome. Eyebrow "{School} NIL Student Athlete", name, sport line, facts grid
(empty rows never print), handle-only social cards, no CTAs, no follower
counts. Feed order: the athlete's own reels, else the athlete's channel (the
page script fills it), else no feed section. About = NIL TV's own words, no
source line. Photos are copied from the athlete's folder and resized; 1.jpg is
the hero, 2..N the wall.

Hand-built athlete pages (not in athletes.json) live in the private folder as
athletes/<slug>/ and are mirrored into the tree at build time.

Dev-only: deploy.ps1 prunes athletes/ from prod.
"""
import io, json, os, re, sys, html, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from private_data import private_root, HOWTO

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PRIVATE = private_root()
DATA = os.path.join(PRIVATE, 'athletes', '_data', 'athletes.json') if PRIVATE else None
TEMPLATE = os.path.join(os.path.dirname(__file__), 'athlete-template.html')
INDEX = os.path.join(ROOT, 'athletes', 'index.html')
ORIGIN = 'https://dev.dkdfgvugisb3v.amplifyapp.com'
POSTER = 'https://dr60jt51m7xh2.cloudfront.net/video/%s/poster.jpg'

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
def ap_head(a):
    sub = ['<b>%s</b>' % esc(a['sport'])]
    if a.get('position'): sub.append(esc(a['position']))
    if a.get('number'): sub.append('No. %s' % esc(a['number']))
    facts = [('Class', a.get('class_year')), ('Position', a.get('position')), ('Hometown', a.get('hometown')),
             ('Height', a.get('height')), ('High school', a.get('high_school'))]
    rows = ''.join('          <div class="fact"><div class="k">%s</div><div class="v">%s</div></div>\n' % (k, esc(v)) for k, v in facts if v)
    return ('      <div class="ap-head">\n'
            '        <p class="eyebrow">%s NIL Student Athlete</p>\n'
            '        <h1>%s</h1>\n'
            '        <p class="sub">%s</p>\n'
            '        <div class="facts">\n%s        </div>\n'
            '      </div>' % (esc(a['school']), esc(a['name']), ' &middot; '.join(sub), rows))

def platcards(a):
    cards = ''
    for so in a.get('socials', []):
        cards += ('      <a class="pc" href="%s" target="_blank" rel="noopener">\n'
                  '        <div class="pc-top"><span class="h">%s%s</span>%s</div>\n'
                  '        <div class="handle">%s</div>\n'
                  '      </a>\n' % (esc(so['url']), ICON.get(so['platform'], ''), esc(so['label']), EXT, esc(so['handle'])))
    return '    <div class="platcards">\n%s    </div>' % cards

def tile(r):
    return ('      <a class="tile" href="/watch/%s/">\n'
            '        <img src="%s" alt="" loading="lazy">\n'
            '        <span class="dur">%s</span>\n'
            '        %s\n'
            '        <div class="cap"><div class="t">%s</div></div>\n'
            '      </a>\n' % (r['id'], POSTER % r['id'], fmt_dur(r['duration']), PLAY, esc(r['title'])))

def feed_section(a):
    ch = a.get('channel'); reels = a.get('reels') or []
    if not reels and not ch:
        return '<!-- FEED : no own reels and no campus channel, so no feed section (feed order rule) -->'
    chan_attr = ' data-channel="%s" data-channel-name="%s"' % (ch['id'], esc(ch['name'])) if ch else ''
    more = ('      <a class="more" id="feedMore" href="/channels/%s/">Everything on %s &rarr;</a>\n' % (ch['slug'], esc(ch['name']))) if ch else ''
    title = "%s&rsquo;s feed" % esc(a['first']) if reels else 'On %s' % esc(ch['name'])
    kick = 'On %s' % esc(ch['name']) if ch else 'On NIL TV'
    return ('<!-- FEED ORDER: 1) the athlete\'s own posts (static tiles), 2) if none, the posts of the\n'
            '     athlete\'s channel (data-channel, loaded by the script), 3) if neither, no section. -->\n'
            '<section class="feed" id="feed"%s>\n'
            '  <div class="wrap">\n'
            '    <div class="sec-head">\n'
            '      <div>\n'
            '        <p class="kick">%s</p>\n'
            '        <h2 id="feedTitle">%s</h2>\n'
            '      </div>\n%s'
            '    </div>\n'
            '    <div class="rail" id="feedRail">\n%s'
            '    </div>\n'
            '  </div>\n'
            '</section>' % (chan_attr, kick, title, more, ''.join(tile(r) for r in reels)))

def about_section(a, wall_files):
    ab = a['about']
    paras = ''.join('        <p>%s</p>\n' % esc(p) for p in ab['paragraphs'])
    wall = ''.join('        <div class="ph"><img src="photos/%s" alt="" loading="lazy" style="object-position:%s"></div>\n' % (f, pos) for f, pos in wall_files)
    return ('<!-- ABOUT + PHOTOS -->\n'
            '<section class="about" id="about">\n'
            '  <div class="wrap">\n'
            '    <div class="about-grid">\n'
            '      <div>\n'
            '        <p class="kick">About %s</p>\n'
            '        <p class="quote">%s</p>\n%s'
            '      </div>\n'
            '      <div class="wall">\n%s'
            '      </div>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>' % (esc(a['first']), ab['line'], paras, wall))

# ---------------------------------------------------------------- photos
def copy_photos(a, outdir):
    """1.jpg = hero, 2..N = wall. Resized to <=1200px tall, JPEG q86. Returns
    (hero_w, hero_h, [(file, pos), ...])."""
    from PIL import Image, ImageOps
    p = a['photos']; src = p['src_dir']
    if not os.path.isabs(src):
        src = os.path.join(PRIVATE, src)   # private-relative, e.g. athletes/_photos/<slug>
    os.makedirs(outdir, exist_ok=True)
    items = [p['hero']] + p['wall']
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

# ---------------------------------------------------------------- build
def build_page(a, tpl):
    outdir = os.path.join(ROOT, 'athletes', a['slug'])
    w, h, wall = copy_photos(a, os.path.join(outdir, 'photos'))
    reels = a.get('reels') or []
    page = (tpl.replace('{{name}}', esc(a['name']))
               .replace('{{description}}', esc(a['description']))
               .replace('{{slug}}', a['slug'])
               .replace('{{hero_w}}', str(w)).replace('{{hero_h}}', str(h))
               .replace('{{hero_pos}}', a['photos']['hero']['pos'])
               .replace('{{ap_head}}', ap_head(a))
               .replace('{{platcards}}', platcards(a))
               .replace('{{feed_section}}', feed_section(a))
               .replace('{{about_section}}', about_section(a, wall))
               .replace('{{seed}}', reels[0]['id'] if reels else '')
               .replace('{{mine}}', json.dumps({r['id']: 1 for r in reels})))
    assert '{{' not in page, 'unfilled placeholder in ' + a['slug']
    io.open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8', newline='\n').write(page)
    return outdir

DIR_CSS = """
/* ---- athlete directory (build-athletes.py) ---- */
.ath-filters{max-width:1280px;margin:0 auto 22px;padding:0 var(--gutter);display:grid;gap:12px}
.ath-filters .grp{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ath-filters .lbl{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-right:6px;min-width:52px}
.chip{border:1px solid var(--border);background:transparent;color:var(--dim);border-radius:999px;padding:6px 14px;font-size:13px;font-weight:600;cursor:pointer;transition:color .15s,border-color .15s}
.chip:hover{color:var(--text)}
.chip.on{color:var(--gold);border-color:var(--gold)}
.ath-count{max-width:1280px;margin:0 auto 12px;padding:0 var(--gutter);font-size:12.5px;color:var(--dim)}
.ath-grid{max-width:1280px;margin:0 auto;padding:0 var(--gutter);display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:18px}
.ath-card{position:relative;display:block;aspect-ratio:4/5;border-radius:14px;overflow:hidden;border:1px solid var(--border);background:var(--surface);transition:transform .2s ease,border-color .2s ease}
.ath-card:hover{transform:translateY(-4px);border-color:rgba(217,178,91,.5)}
.ath-card img{width:100%;height:100%;object-fit:cover;display:block}
.ath-card .cap{position:absolute;left:0;right:0;bottom:0;padding:70px 14px 14px;background:linear-gradient(180deg,rgba(6,6,8,0) 0%,rgba(6,6,8,.92) 70%)}
.ath-card .nm{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:22px;line-height:1;text-transform:uppercase;letter-spacing:.01em;color:var(--text)}
.ath-card .ss{font-size:12.5px;color:var(--dim);margin-top:4px}
.ath-card[hidden]{display:none}
.ath-empty{max-width:1280px;margin:0 auto;padding:30px var(--gutter);color:var(--dim);font-size:14px}
@media (max-width:640px){.ath-grid{grid-template-columns:repeat(2,1fr);gap:12px}.ath-card .nm{font-size:18px}}
"""

def build_index(athletes):
    s = io.open(INDEX, encoding='utf-8').read()
    # hero copy
    s = re.sub(r'<p class="hero-dek">[^<]*</p>', '<p class="hero-dek">Athletes on the NIL TV network. Filter by school or sport, open a profile, watch their episodes.</p>', s, count=1)
    # css (idempotent)
    if '/* ---- athlete directory (build-athletes.py) ---- */' not in s:
        s = s.replace('</style>', DIR_CSS + '</style>', 1)
    schools = sorted({a['school'] for a in athletes}); sports = sorted({a['sport'] for a in athletes})
    def chips(kind, vals):
        out = '<button class="chip on" data-%s="">All</button>' % kind
        for v in vals: out += '<button class="chip" data-%s="%s">%s</button>' % (kind, esc(v), esc(v))
        return out
    cards = ''
    for a in athletes:
        cards += ('    <a class="ath-card" href="/athletes/%s/" data-school="%s" data-sport="%s">\n'
                  '      <img src="/athletes/%s/photos/1.jpg" alt="%s" loading="lazy" style="object-position:%s">\n'
                  '      <div class="cap"><div class="nm">%s</div><div class="ss">%s &middot; %s</div></div>\n'
                  '    </a>\n' % (a['slug'], esc(a['school']), esc(a['sport']), a['slug'], esc(a['name']), a['photos']['hero']['pos'],
                                  esc(a['name']), esc(a['school']), esc(a['sport'])))
    main = ('<main class="shelves">\n\n'
            '<!-- ATHLETE DIRECTORY : generated by scripts/builders/build-athletes.py from athletes/_data/athletes.json -->\n'
            '<section class="shelf" id="roster">\n'
            '  <div class="shelf-head">\n'
            '    <h2 class="shelf-title gold">Athletes</h2>\n'
            '  </div>\n'
            '  <div class="ath-filters">\n'
            '    <div class="grp"><span class="lbl">School</span>%s</div>\n'
            '    <div class="grp"><span class="lbl">Sport</span>%s</div>\n'
            '  </div>\n'
            '  <div class="ath-count" id="athCount"></div>\n'
            '  <div class="ath-grid" id="athGrid">\n%s'
            '  </div>\n'
            '  <div class="ath-empty" id="athEmpty" hidden>No athletes match that filter yet.</div>\n'
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
            '    document.getElementById("athCount").textContent = n + (n === 1 ? " athlete" : " athletes");\n'
            '    document.getElementById("athEmpty").hidden = n > 0;\n'
            '    try { var u = new URL(location.href); state.school ? u.searchParams.set("school", state.school) : u.searchParams.delete("school"); state.sport ? u.searchParams.set("sport", state.sport) : u.searchParams.delete("sport"); history.replaceState(null, "", u); } catch (e) {}\n'
            '  }\n'
            '  document.querySelectorAll(".chip").forEach(function(b){ b.addEventListener("click", function(){ if (b.dataset.school !== undefined) state.school = b.dataset.school; else state.sport = b.dataset.sport; apply(); }); });\n'
            '  apply();\n'
            '})();\n'
            '</script>\n\n'
            '</main>' % (chips('school', schools), chips('sport', sports), cards))
    s2 = re.sub(r'<main class="shelves">.*?</main>', lambda m: main, s, count=1, flags=re.S)
    assert s2 != s or '<!-- ATHLETE DIRECTORY' in s, 'index: main block not replaced'
    io.open(INDEX, 'w', encoding='utf-8', newline='\n').write(s2)
    index = [dict(slug=a['slug'], name=a['name'], school=a['school'], sport=a['sport'], classYear=a.get('class_year', ''),
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

def main():
    if not DATA or not os.path.exists(DATA):
        print('build-athletes: private data not found - skipping athlete pages (%s)' % HOWTO)
        return 1 if '--require' in sys.argv else 0
    tpl = io.open(TEMPLATE, encoding='utf-8').read()
    athletes = json.load(io.open(DATA, encoding='utf-8'))
    for a in athletes:
        out = build_page(a, tpl)
        print('built', os.path.relpath(out, ROOT), '| reels', len(a.get('reels') or []), '| channel', (a.get('channel') or {}).get('id') or '-')
    build_index(athletes)
    static = mirror_static(athletes)
    print('index:', len(athletes), 'athletes', '| hand-built pages mirrored:', static)
    return 0

if __name__ == '__main__':
    sys.exit(main())
