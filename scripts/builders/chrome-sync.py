# -*- coding: utf-8 -*-
"""Push the cinema template's nav / mobile menu / footer into the pages that are
NOT generated from it, so the header is one thing sitewide:
  - athletes/{slug}/index.html   (athlete pages)
  - the ambassador page factory template (optional, via NILTV_AMBASSADOR_TEMPLATE)
  - legal/{privacy,terms,contest-notice}/index.html  (standalone docs:
    get the nav + footer markup, the chrome CSS extracted from the template,
    the fonts, and app.js/initCinema; their light document body is untouched)
Idempotent: every injected block sits between markers and is replaced on re-run.
"""
import io, os, re, glob

W = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")).replace("\\", "/") + "/"
TPL = W + "scripts/builders/cinema-template.html"
tpl = io.open(TPL, encoding="utf-8").read()
root = lambda s: s.replace("/concepts/cinema/", "/")

def block(s, start, end, name):
    i = s.index(start); j = s.index(end, i) + len(end)
    return s[i:j]

NAV = root(block(tpl, '<nav class="nav" id="nav">', "</nav>", "nav"))
MENU = root(block(tpl, '<div class="mobile-menu" id="mobileMenu">', "</div>", "menu"))
FOOT = root(block(tpl, '<footer class="footer">', "</footer>", "footer"))
FONTS = re.search(r'<link href="https://fonts\.googleapis\.com/css2\?[^"]*"[^>]*>', tpl).group(0)
TAG_RULE = re.search(r"\.footer-tag\{[^}]*\}", tpl).group(0)
# the stacked-mobile footer rules travel with the footer markup (the
# mobile footer mirrors the desktop zones); injected as a marker style tag
MOBILE_FOOT = re.search(r"@media \(max-width:900px\)\{\n  /\* stacked mobile footer.*?\n\}", tpl, re.S).group(0)

# ---------- chrome CSS extracted from the template's inline stylesheet ----------
css = tpl[tpl.index("<style>") + 7:tpl.index("</style>")]
css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
TOKEN = re.compile(r"(^|[\s,>+~(])(\.nav[\w-]*|\.mobile-menu[\w-]*|\.footer[\w-]*|\.foot-grid|\.fg-[\w-]*|\.consent|#news[\w-]*|\.btn[\w-]*|#nav\b|#mobileMenu|#navBurger)")

def rules(s):
    out, i, n = [], 0, len(s)
    while True:
        j = s.find("{", i)
        if j < 0: break
        sel = s[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            depth += (s[k] == "{") - (s[k] == "}"); k += 1
        out.append((sel, s[j + 1:k - 1])); i = k
    return out

def keep(sel):
    return sel == ":root" or bool(TOKEN.search(sel))

def extract(s, top=True):
    kept = []
    for sel, body in rules(s):
        if sel.startswith("@media"):
            inner = extract(body, False)
            if inner.strip(): kept.append("%s{%s}" % (sel, inner))
        elif sel.startswith("@"):
            continue
        elif keep(sel):
            kept.append("%s{%s}" % (sel, body.strip()))
    return "\n".join(kept)

CHROME_CSS = extract(css) + "\nbody{padding-top:56px}\n"

def swap_between(s, start_marker, end_marker, new):
    if start_marker in s:
        i = s.index(start_marker); j = s.index(end_marker, i) + len(end_marker)
        return s[:i] + new + s[j:]
    return None

# ---------- 1) athlete pages + their factory template: swap the three blocks ----------
def sync_blocks(path):
    s = io.open(path, encoding="utf-8").read()
    o = s
    s = re.sub(r'<nav class="nav" id="nav">.*?</nav>', lambda m: NAV, s, count=1, flags=re.S)
    s = re.sub(r'<div class="mobile-menu" id="mobileMenu">.*?</div>', lambda m: MENU, s, count=1, flags=re.S)
    s = re.sub(r'<footer class="footer">.*?</footer>', lambda m: FOOT, s, count=1, flags=re.S)
    s = re.sub(r"\.footer-tag\{[^}]*\}", lambda m: TAG_RULE, s, count=1)
    s = re.sub(r'<style id="cinema-foot-mobile">.*?</style>\n?', "", s, flags=re.S)
    s = s.replace("</head>", '<style id="cinema-foot-mobile">\n' + MOBILE_FOOT + "\n</style>\n</head>", 1)
    if s != o:
        io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("synced blocks:", path, "(changed)" if s != o else "(no change)")

# the ambassador page factory's template lives outside this repo; point
# NILTV_AMBASSADOR_TEMPLATE at it so rebuilds there keep the same chrome
_extra = [p for p in [os.environ.get("NILTV_AMBASSADOR_TEMPLATE")] if p and os.path.exists(p)]
for p in sorted(glob.glob(W + "athletes/*/index.html")) + _extra:
    sync_blocks(p)

# ---------- 2) legal pages: inject chrome around the document ----------
HEAD_BLOCK = ('<!-- cinema-chrome:head -->\n' + FONTS +
              '\n<link rel="stylesheet" href="/assets/css/cinema-chrome.css">\n<style id="cinema-chrome-css">\n' +
              CHROME_CSS + '</style>\n<!-- /cinema-chrome:head -->')
TOP_BLOCK = '<!-- cinema-chrome:top -->\n' + NAV + "\n" + MENU + '\n<!-- /cinema-chrome:top -->'
FOOT_BLOCK = '<!-- cinema-chrome:footer -->\n' + FOOT + '\n<!-- /cinema-chrome:footer -->'
SCRIPT_BLOCK = ('<!-- cinema-chrome:scripts -->\n<script src="/config.js"></script>\n<script src="/assets/js/app.js"></script>\n'
                '<script>\nNILTV.initCinema();\nvar _b=document.getElementById("navBurger"),_m=document.getElementById("mobileMenu");\n'
                'if(_b&&_m){_b.addEventListener("click",function(){var o=_m.classList.toggle("open");_b.setAttribute("aria-expanded",o?"true":"false");});}\n'
                '</script>\n<!-- /cinema-chrome:scripts -->')

for path in sorted(glob.glob(W + "legal/*/index.html")):
    s = io.open(path, encoding="utf-8").read()
    o = s
    r = swap_between(s, "<!-- cinema-chrome:head -->", "<!-- /cinema-chrome:head -->", HEAD_BLOCK)
    s = r if r else s.replace("</head>", HEAD_BLOCK + "\n</head>", 1)
    r = swap_between(s, "<!-- cinema-chrome:top -->", "<!-- /cinema-chrome:top -->", TOP_BLOCK)
    s = r if r else s.replace("<body>", "<body>\n" + TOP_BLOCK, 1)
    r = swap_between(s, "<!-- cinema-chrome:footer -->", "<!-- /cinema-chrome:footer -->", FOOT_BLOCK)
    if r: s = r
    else:
        # replace the document's own one-line footer with the site footer
        s = re.sub(r'<footer class="footer">.*?</footer>', lambda m: FOOT_BLOCK, s, count=1, flags=re.S)
    r = swap_between(s, "<!-- cinema-chrome:scripts -->", "<!-- /cinema-chrome:scripts -->", SCRIPT_BLOCK)
    s = r if r else s.replace("</body>", SCRIPT_BLOCK + "\n</body>", 1)
    if s != o:
        io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("legal chrome:", path, "(changed)" if s != o else "(no change)")

print("chrome css rules extracted: %d chars" % len(CHROME_CSS))
