# Promote the built cinema pages to the site itself: root homepage (from the
# chrome template) + the vertical pages. Old pages are backed up to _legacy/
# (ignored, never deployed).
import io, os, shutil

W = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")).replace("\\", "/") + "/"
ORIGIN = "https://dev.dkdfgvugisb3v.amplifyapp.com"

os.makedirs(W + "_legacy", exist_ok=True)
for src, name in [("index.html", "index.html"), ("competitions/index.html", "competitions.html"),
                  ("channels/index.html", "channels.html"),
                  ("featured/index.html", "featured.html"), ("about/index.html", "about.html"), ("vote/index.html", "vote.html"), ("partners/index.html", "partners.html")]:
    if os.path.exists(W + src) and not os.path.exists(W + "_legacy/" + name):
        shutil.copy2(W + src, W + "_legacy/" + name)
        print("backed up", src)

SEO = {
    "": ("NIL TV - Real Name. Real Game. Real TV.",
         "The first media network exclusively for college athlete content. Watch the newest reels, original series, and campus channels from student athletes across the country."),
    "competitions/": ("Competitions | NIL TV",
         "NIL Star crowned its first champion. Season 1 is in the books, and the national NIL competitions live here."),
    "channels/": ("Channels | NIL TV",
         "The channels of the NIL TV network, across the country."),
    "about/": ("About NIL TV | Real Name. Real Game. Real TV.",
         "NIL TV gives athletes ownership of their narrative: 275+ athlete creators across 108 schools, fan-voted competitions, and campus channels."),
    "nilstar/": ("NIL Star | NIL TV",
         "NIL Star is the events arm of NIL TV. Singing Star Season 1 crowned its first champion."),
    "nilstar/season-1/": ("NIL Star Season 1 | NIL TV",
         "Bella Calvanese is your first ever NIL Star. Relive the Top 20 finalists and the season that drew 1M+ fan votes."),    "vote/": ("Vote | NIL TV",
         "Fan voting decides every NIL Star event. See what is open now and cast your votes."),
    "athletes/": ("NIL TV Athletes | NIL TV",
         "The NIL TV roster: the athletes creating across the network. Search any name to watch their videos."),
    "partners/": ("Partner With NIL TV | Brand Campaigns",
         "Put your brand on air: athlete led campaigns across NIL TV, NIL Star, and the campus channels. 30M+ impressions, 280+ network brands, real campaign proof with NIL TV Athletes."),
    "contact/": ("Contact NIL TV | Get In Touch",
         "Reach the NIL TV team: partnerships, general questions, and legal."),
    "featured/": ("Featured | NIL TV",
         "Our Athletes: vertical, unfiltered, athlete first. The most watched cuts across the NIL TV network."),
}

CARD_RE = None
def watchify(p):
    # cards whose poster comes off the CDN get a real /watch/{id}/ href;
    # the theater JS intercepts plain clicks, so this powers open-in-new-tab
    # and no-JS navigation without changing the click behavior.
    import re as _re
    return _re.sub(
        r'(<a class="card card-(?:wide|reel)") href="#">(\s*<img src="https://d1nm1d2txb83wa\.cloudfront\.net/video/([^/"]+)/poster(?:-fill)?\.jpg")',
        lambda m: m.group(1) + ' href="/watch/' + m.group(3) + '/">' + m.group(2),
        p)

def graft_chmq(p):
    # The channels page carries the network-marquee hero. A regeneration
    # that lacks it must transplant it from the current on-disk page: hero
    # section + its CSS.
    if p.count('class="chmq-card"') == 63:
        # build-sections emits the marquee itself - grafting on top would
        # duplicate the chmq CSS; nothing to do
        return p
    try:
        old = io.open(W + "channels/index.html", encoding="utf-8").read()
    except FileNotFoundError:
        return p
    if old.count('class="chmq-card"') != 63:
        print("WARNING: on-disk channels page has no intact chmq marquee; not grafting")
        return p
    h0 = old.index('<section class="hero hero-sm" id="hero"')
    h1 = old.index("</section>", old.index('<div class="chmq"')) + len("</section>")
    g0 = p.index('<section class="hero hero-sm" id="hero"')
    g1 = p.index("</section>", g0) + len("</section>")
    p = p[:g0] + old[h0:h1] + p[g1:]
    c0 = old.index("/* ---------- HERO : network marquee")
    c1 = old.index("/* ===== about page ===== */")
    if ".chmq{" not in p:
        p = p.replace("/* ===== about page ===== */", old[c0:c1] + "/* ===== about page ===== */", 1)
    assert p.count('class="chmq-card"') == 63, "chmq graft failed"
    return p

def promote(src_path, out_rel):
    if out_rel: os.makedirs(W + out_rel, exist_ok=True)
    p = io.open(src_path, encoding="utf-8").read()
    # cinema-local links become site links
    p = p.replace('href="/concepts/cinema/"', 'href="/"')
    p = p.replace('href="/concepts/cinema/', 'href="/')
    p = watchify(p)
    title, desc = SEO[out_rel]
    # swap the concept title + add the SEO head block
    import re
    p = re.sub(r"<title>.*?</title>",
        "<title>%s</title>\n" % title +
        '<meta name="description" content="%s">\n' % desc +
        '<link rel="canonical" href="%s/%s">\n' % (ORIGIN, out_rel) +
        '<meta property="og:title" content="%s">\n' % title +
        '<meta property="og:description" content="%s">\n' % desc +
        '<meta property="og:url" content="%s/%s">\n' % (ORIGIN, out_rel) +
        '<meta property="og:image" content="%s/assets/img/og-card.png">\n' % ORIGIN +
        '<meta property="og:type" content="website">\n' +
        '<meta property="og:site_name" content="NIL TV">\n' +
        '<meta name="twitter:card" content="summary_large_image">\n' +
        '<meta name="theme-color" content="#060608">', p, count=1)
    if out_rel == "channels/":
        p = graft_chmq(p)
    # footer legal text becomes real links
    p = p.replace("&copy; 2026 NIL TV. All rights reserved. Terms - Privacy - Contact",
        '&copy; 2026 NIL TV. All rights reserved. <a href="/legal/terms/">Terms</a> - <a href="/legal/privacy/">Privacy</a> - <a href="/legal/contest-notice/">Contest Notice</a>')
    io.open(W + out_rel + "index.html", "w", encoding="utf-8", newline="\n").write(p)
    print("promoted", out_rel or "/")

C = W + "concepts/cinema/"   # build-sections output (ignored, regenerated)
promote(W + "scripts/builders/cinema-template.html", "")
promote(C + "channels/index.html", "channels/")
promote(C + "featured/index.html", "featured/")
promote(C + "about/index.html", "about/")
promote(C + "competitions/index.html", "competitions/")
promote(C + "nilstar/season-1/index.html", "nilstar/season-1/")
promote(C + "vote/index.html", "vote/")
promote(C + "athletes/index.html", "athletes/")
promote(C + "partners/index.html", "partners/")
promote(C + "contact/index.html", "contact/")

# channels page: tiles point at the real per-channel pages
ch = io.open(W + "channels/index.html", encoding="utf-8").read()
# channel page slugs = the IG account names (e.g. /channels/truebluetv/)
for img, slug in [("chan3/trueblue.webp","truebluetv"),("chan3/dorecity.webp","dorecitytv"),
                  ("chan3/chapelhill.webp","chapelhilltv"),("chan3/starkville.webp","starkvilletv"),
                  ("chan3/collegestation.webp","collegestationtv")]:
    ch = ch.replace('<a class="chan-tile" href="#">\n      <img src="/assets/img/%s"' % img,
                    '<a class="chan-tile" href="/channels/%s/">\n      <img src="/assets/img/%s"' % (slug, img))
io.open(W + "channels/index.html", "w", encoding="utf-8", newline="\n").write(ch)
print("channel tiles wired to /channels/{slug}/")
