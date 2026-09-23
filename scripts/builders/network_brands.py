# -*- coding: utf-8 -*-
"""Brand roster section used by the page builder (build-sections.py).

Data: scripts/builders/network-brands.json in the PRIVATE data folder (see
private_data.py). Brand-level only (no athlete names).
Without the private folder load() returns an empty roster and every section
renders empty instead of failing the build.

Names only. `logo` on each brand is the hook for logos: a chip renders an
<img> as soon as the field is set.
"""
import io, json, os, sys
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from private_data import private_file, HOWTO

DATA = private_file("scripts", "builders", "network-brands.json")
EMPTY = {"generated": "", "source": "", "totals": {"brands": 0, "athletes": 0, "partnerships": 0, "posts": 0},
         "groups": [], "brands": []}

# Household names to lead with in a proof strip. Filtered against the data so
# nothing renders that is not in the roster.
FEATURED = ["Nike", "adidas", "Gatorade", "Target", "Walmart", "Samsung", "Microsoft", "Meta", "McDonald's",
    "CVS Pharmacy", "Subway", "Crocs", "Hollister", "American Eagle", "Aerie", "Athleta", "Marriott Bonvoy",
    "CBS Sports", "Coach", "Amazon Music", "Doritos", "M&M'S", "Häagen-Dazs", "7-Eleven", "LEGO", "Notion",
    "Audible", "Liquid I.V.", "OLIPOP", "Propel", "C4 Energy", "Alani Nu", "AG1", "Quest Nutrition", "LMNT",
    "Hydro Flask", "YETI", "Brooks Running", "Bombas", "Vuori", "Hyperice", "CeraVe", "Aquaphor",
    "Sol de Janeiro", "Armani Beauty", "Valentino Beauty", "Beyond Meat", "Tyson", "Chiquita", "Best Western",
    "Cricket Wireless", "Oakley Meta", "Orgain", "Firefly Recovery", "VKTRY", "Good Molecules", "Cheetos",
    "Smoothie King", "Playa Bowls", "Noosa", "Kiss Nails", "Billie", "Clairol", "Febreze", "Dr. Scholl's",
    "Turtle Beach", "FloTrack", "Gametime", "Bloom Nutrition", "Barebells", "NOCCO", "Klean Athlete",
    "Ascent Protein", "GoMacro", "Purely Elizabeth", "Katjes USA", "Pocky USA", "Chex Mix", "Goli Nutrition"]

SUB = ("Every NIL TV athlete brings their own brand relationships to the network. This is who they have "
       "worked with, grouped by category. A gold number marks a brand that has worked with more than one NIL TV athlete.")
NOTE = ("Deals were arranged by the athletes directly or through NIL marketplaces such as Postgame. "
        "Names are listed for reference and do not imply an endorsement of NIL TV. "
        "The roster covers the athletes reported so far and grows as the sheet does.")


def load():
    if not DATA:
        print("network_brands: private network-brands.json not found - brand slider renders empty (%s)" % HOWTO)
        return json.loads(json.dumps(EMPTY))
    return json.load(io.open(DATA, encoding="utf-8"))


def n(x):
    return "{:,}".format(x)


def featured(d, limit=28):
    names = {b["name"] for b in d["brands"]}
    return [f for f in FEATURED if f in names][:limit]


def stat_band(d):
    t = d["totals"]
    return '''<div class="stat-band nb-stats">
    <div class="st"><div class="n">%s</div><div class="l">Brands</div></div>
    <div class="st"><div class="n">%s</div><div class="l">NIL TV Athletes</div></div>
    <div class="st"><div class="n">%s</div><div class="l">Athlete Brand Partnerships</div></div>
    <div class="st"><div class="n">%s</div><div class="l">Branded Posts Tracked</div></div>
  </div>''' % (n(t["brands"]), n(t["athletes"]), n(t["partnerships"]), n(t["posts"]))


def chip(b):
    badge = ('<span class="nb-n" aria-label="%d NIL TV athletes">%d</span>' % (b["athletes"], b["athletes"])) if b["athletes"] > 1 else ""
    img, cls = "", ""
    if b.get("logo"):
        img = '<img src="%s" alt="" loading="lazy" decoding="async">' % escape(b["logo"], quote=True)
        cls = " has-logo"
    return '<li class="nb-chip%s" data-slug="%s">%s<span class="nb-name">%s</span>%s</li>' % (
        cls, escape(b["slug"], quote=True), img, escape(b["name"]), badge)


def groups_html(d, collapsed=12):
    by = {}
    for b in d["brands"]:
        by.setdefault(b["group"], []).append(b)
    parts = []
    for g in list(d["groups"]) + [x for x in by if x not in d["groups"]]:
        items = by.get(g)
        if not items:
            continue
        more = ('\n    <button class="nb-more" type="button" aria-expanded="false">Show all %d</button>' % len(items)) \
            if len(items) > collapsed else ""
        parts.append('''  <div class="nb-group" data-count="%d">
    <h3 class="nb-h">%s <span>%d</span></h3>
    <ul class="nb-chips">
      %s
    </ul>%s
  </div>''' % (len(items), escape(g), len(items), "\n      ".join(chip(b) for b in items), more))
    return "\n".join(parts)


JS = ("document.querySelectorAll('.nb-more').forEach(function(b){b.addEventListener('click',function(){"
      "var g=b.closest('.nb-group'),o=g.classList.toggle('open');b.setAttribute('aria-expanded',o?'true':'false');"
      "b.textContent=o?'Show less':'Show all '+g.dataset.count;});});")


def section_html(d, title="Brands Our Athletes Have Worked With", sub=SUB, anchor="brands", stats=True, note=NOTE):
    return '''<section class="shelf nb" id="%s">
  <div class="shelf-head">
    <h2 class="shelf-title">%s</h2>
    <span class="shelf-sub">%s</span>
  </div>
  %s
  <div class="nb-groups">
%s
  </div>
  <p class="nb-note">%s</p>
</section>
<script>%s</script>''' % (anchor, escape(title), escape(sub), stat_band(d) if stats else "", groups_html(d), escape(note), JS)


CSS = r"""
/* ---------- brand roster (scripts/builders/network_brands.py) ---------- */
.nb .stat-band{margin:0 0 34px}
.nb-groups{padding:0 var(--gutter);display:grid;gap:26px;margin:0 0 18px}
.nb-h{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:15px;letter-spacing:.16em;text-transform:uppercase;color:var(--text);margin:0 0 10px;display:flex;align-items:baseline;gap:10px}
.nb-h span{font:600 11px/1 'Inter',sans-serif;letter-spacing:.08em;color:var(--dim)}
.nb-chips{display:flex;flex-wrap:wrap;gap:8px;list-style:none;margin:0;padding:0}
.nb-chip{display:inline-flex;align-items:center;gap:7px;padding:7px 12px;border:1px solid var(--border);border-radius:999px;background:rgba(23,23,28,.55);font-size:12.5px;font-weight:500;color:var(--text);line-height:1;white-space:nowrap}
.nb-chip img{width:16px;height:16px;object-fit:contain;border-radius:3px}
.nb-n{font-size:10px;font-weight:700;color:var(--gold);letter-spacing:.04em}
.nb-note{padding:0 var(--gutter);margin:0 0 60px;max-width:820px;font-size:11.5px;color:#75757f;line-height:1.55}
.nb-more{display:none;margin-top:10px;padding:8px 14px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--gold-bright);font:600 12px/1 'Inter',sans-serif;cursor:pointer}
@media (max-width:720px){
  .nb-group .nb-more{display:inline-flex}
  .nb-group:not(.open) .nb-chips li:nth-child(n+13){display:none}
}
/* brand marquee: two slow counter-scrolling rows */
.nbm{display:grid;gap:12px;padding:8px 0 6px;-webkit-mask-image:linear-gradient(90deg,transparent,#000 7%,#000 93%,transparent);mask-image:linear-gradient(90deg,transparent,#000 7%,#000 93%,transparent)}
.nbm-lbl{text-align:center;font:700 11px/1 'Inter',sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--dim);margin-bottom:8px}
.nbm-row{overflow:hidden}
.nbm-track{display:flex;width:max-content;animation:nbm 170s linear infinite}
.nbm-row.rev .nbm-track{animation-direction:reverse}
.nbm-track span{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:26px;letter-spacing:.05em;text-transform:uppercase;color:#cfcfd8;white-space:nowrap;display:inline-flex;align-items:center}
.nbm-track span::after{content:"";width:6px;height:6px;border-radius:50%;background:var(--gold);margin:0 36px;opacity:.85}
@keyframes nbm{to{transform:translateX(-50%)}}
.nbm-sec .stat-band{margin:0 0 26px}
.nbm-sec .nb-note{margin-top:14px}
@media (max-width:640px){.nbm-track span{font-size:20px}.nbm-track span::after{margin:0 22px}}
@media (prefers-reduced-motion:reduce){.nbm-track{animation:none;width:auto;flex-wrap:wrap;justify-content:center;row-gap:8px}.nbm-track .dup{display:none}}
/* lead slot (9/22): on the homepage the slider sits right under the hero
   carousel, so the title reads at billboard scale and wraps on phones */
.nbm-lead{padding:26px 0 30px}
.nbm-lead .shelf-head{margin-bottom:6px}
.nbm-lead .shelf-title{font-size:clamp(24px,2.9vw,36px);letter-spacing:.1em;line-height:1.05}
@media (max-width:700px){.nbm-lead{padding-top:18px}.nbm-lead .shelf-title{white-space:normal;overflow:visible;text-overflow:clip;font-size:23px;line-height:1.1}}
"""


# ---------------------------------------------------------------- marquee
# The brand slider: two slow counter-scrolling rows of household names, no
# "plus N more" line. This is the roster's public face; the full chip list
# stays available via section_html() but is not on any page.
MQ_SECONDS = 170
MQ_SUB = ("A selection of the brands NIL TV athletes have worked with across their careers, "
          "from national names to campus favorites. The full list is available on request.")
MQ_NOTE = ("Deals were arranged by the athletes directly or through NIL marketplaces. "
           "Names are listed for reference and do not imply an endorsement of NIL TV.")


def marquee_html(d, n=40, rows=2, label=None):
    names = featured(d, n)
    per = -(-len(names) // rows)
    out = []
    for r in range(rows):
        chunk = names[r * per:(r + 1) * per]
        if not chunk:
            continue
        spans = "".join("<span>%s</span>" % escape(x) for x in chunk)
        dup = "".join('<span class="dup" aria-hidden="true">%s</span>' % escape(x) for x in chunk)
        out.append('<div class="nbm-row%s"><div class="nbm-track">%s%s</div></div>' % (" rev" if r % 2 else "", spans, dup))
    lbl = ('<div class="nbm-lbl">%s</div>' % escape(label)) if label else ""
    return '<div class="nbm" aria-label="Brands NIL TV athletes have worked with">%s%s</div>' % (lbl, "".join(out))


def marquee_section(d, title="Brands Our Athletes Have Worked With", sub=MQ_SUB, anchor="brands", stats=True, note=MQ_NOTE, n=40, cls=""):
    head = '<h2 class="shelf-title">%s</h2>' % escape(title)
    if sub:
        head += '\n    <span class="shelf-sub">%s</span>' % escape(sub)
    return '''<section class="shelf nb nbm-sec%s" id="%s">
  <div class="shelf-head">
    %s
  </div>
  %s
  %s%s
</section>''' % ((" " + cls) if cls else "", anchor, head, stat_band(d) if stats else "", marquee_html(d, n),
                 ('\n  <p class="nb-note">%s</p>' % escape(note)) if note else "")


def block(d, **kw):
    """Self-contained brand strip for the live pages (/partners/ and the
    homepage via build-sections.py): scoped CSS + title + the slider. Nothing
    else. Wrapped in markers so a regen can replace it in place."""
    kw.setdefault("sub", "")
    kw.setdefault("stats", False)
    kw.setdefault("note", None)
    return "<!-- BRANDSLIDER -->\n<style>" + CSS + "</style>\n" + marquee_section(d, **kw) + "\n<!-- /BRANDSLIDER -->"


def headline(d):
    """Hero stat: brands in the roster plus the Founding Five network, rounded
    down to a clean tens figure, e.g. 288 -> '280+'."""
    total = d["totals"].get("network_brands") or d["totals"]["brands"]
    return "%d+" % (total // 10 * 10)


if __name__ == "__main__":
    d = load()
    print(section_html(d))
