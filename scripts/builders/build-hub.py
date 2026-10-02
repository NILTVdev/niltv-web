# Build the Athlete Content Hub page from the contact page's chrome so nav,
# footer, theater and CSS stay byte-identical with the rest of the site:
#   /hub/  - the open content asks, for signed-in NIL TV athletes
#
# Dev-only: /hub/ is outside the prod page list in deploy.ps1, so it never
# ships to prod, and no prod page links to it.
#
# Run after any chrome change:  python scripts/builders/build-hub.py
import io, os, re

W = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")).replace("\\", "/") + "/"
ORIGIN = "https://dev.dkdfgvugisb3v.amplifyapp.com"

base = io.open(W + "contact/index.html", encoding="utf-8").read()

HUB_CSS = r"""
/* ---------- athlete content hub (built by scripts/builders/build-hub.py) ---------- */
.hub-wrap{padding:0 var(--gutter)}
.hub-gate{border:1px solid var(--border);border-top:6px solid var(--gold);background:rgba(23,23,28,.5);border-radius:14px;padding:26px 28px;margin-bottom:60px;max-width:640px}
.hub-gate h3{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:26px;text-transform:uppercase;margin-bottom:8px}
.hub-gate p{font-size:13.5px;color:var(--dim);margin-bottom:12px;max-width:560px}
.hub-gate .hint{font-size:12px;opacity:.8;margin-bottom:0}
.hub-gate a{color:var(--gold-bright)}
.hub-note{font-size:12px;color:var(--dim);border:1px solid rgba(217,178,91,.35);border-radius:10px;padding:10px 14px;margin:0 0 16px;max-width:640px}
.hub-note b{color:var(--gold-bright);font-weight:700}
.hub-state{font-size:13.5px;color:var(--dim);margin:0 0 60px}
.hub-state .btn{margin-top:14px}
.hub-grid{margin:0 0 60px;padding:0 var(--gutter);display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.ask{border:1px solid var(--border);background:rgba(23,23,28,.4);border-radius:14px;padding:22px 22px 18px;display:flex;flex-direction:column;gap:10px}
.ask-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.ask-cat{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--gold);font-weight:700}
.ask-due{font-size:12px;color:var(--dim);white-space:nowrap}
.ask h3{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:26px;text-transform:uppercase;line-height:1}
.ask-sum{font-size:13.5px;color:var(--dim)}
.ask-steps{display:flex;flex-direction:column;gap:7px}
.ask-steps li{font-size:12.5px;padding-left:18px;position:relative}
.ask-steps li::before{content:"";position:absolute;left:0;top:6px;width:7px;height:7px;background:var(--gold);transform:rotate(45deg)}
.ask-foot{margin-top:auto;padding-top:12px;border-top:1px solid var(--border);display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 12px;font-size:12px;color:var(--dim)}
.ask-foot b{color:var(--text);font-weight:600}
.ask-foot span{white-space:nowrap}
@media (max-width:700px){.hub-grid{grid-template-columns:1fr}}
"""

HUB_MAIN = r"""<main class="shelves" id="main">

<div class="hub-wrap">
  <div class="hub-gate" id="hubGate">
    <h3>Sign in to see open asks</h3>
    <p>The Content Hub is where NIL TV athletes find the content the network is looking for. Sign in with your NIL TV account to see what is open.</p>
    <p><button class="btn btn-gold" type="button" id="hubSignIn">Sign in or create your account</button></p>
    <p class="hint">Already signed in? The list appears in a moment. Not a NIL TV athlete yet? <a href="/athlete-signup/">Apply here</a>.</p>
  </div>
</div>

<section class="shelf" id="hubBoard" hidden>
  <div class="shelf-head">
    <h2 class="shelf-title gold">Open Asks</h2>
    <span class="shelf-sub" id="hubCount"></span>
  </div>
  <div class="hub-wrap">
    <p class="hub-note" id="hubNote" hidden><b>Sample data.</b> The hub is not connected on this environment yet, so these asks are examples.</p>
    <div class="hub-state" id="hubState" role="status"></div>
  </div>
  <div class="hub-grid" id="hubGrid"></div>
</section>

</main>"""

HUB_JS = r"""
<script>
/* Athlete Content Hub: the open content asks.
   Where the environment has NIL TV accounts the list shows only after
   sign-in. With NILTV_CONFIG.hubApi set it loads GET {hubApi}asks with the
   account's ID token; with none it runs on /hub/sample-asks.json and says so.
   Ask text is rendered with textContent only. */
(function(){
  var cfg = window.NILTV_CONFIG || {};
  var N = window.NILTV || {};
  var gate = document.getElementById('hubGate');
  var board = document.getElementById('hubBoard');
  var grid = document.getElementById('hubGrid');
  var state = document.getElementById('hubState');
  var count = document.getElementById('hubCount');
  var note = document.getElementById('hubNote');

  function mk(tag, cls, text){
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  // "2026-11-14" is a calendar day, not an instant: build it in local time so
  // it never slips a day in a western time zone.
  function fmtDay(iso){
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    if (!m) return '';
    return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
  }
  function slotsText(ask){
    var claimed = ask.claimed || 0;
    if (ask.slots == null) return 'Open to all athletes' + (claimed ? ' · ' + claimed + ' claimed' : '');
    var left = Math.max(0, ask.slots - claimed);
    if (!left) return 'All spots claimed';
    return left + ' of ' + ask.slots + (ask.slots === 1 ? ' spot' : ' spots') + ' left';
  }
  function card(ask){
    var el = mk('article', 'ask');
    var top = mk('div', 'ask-top');
    top.appendChild(mk('span', 'ask-cat', ask.category || 'Content'));
    var due = fmtDay(ask.due);
    top.appendChild(mk('span', 'ask-due', due ? 'Due ' + due : 'No deadline'));
    el.appendChild(top);
    el.appendChild(mk('h3', null, ask.title || ''));
    if (ask.summary) el.appendChild(mk('p', 'ask-sum', ask.summary));
    if (ask.steps && ask.steps.length){
      var ul = mk('ul', 'ask-steps');
      ask.steps.forEach(function(s){ ul.appendChild(mk('li', null, s)); });
      el.appendChild(ul);
    }
    var foot = mk('div', 'ask-foot');
    foot.appendChild(mk('b', null, slotsText(ask)));
    var posted = fmtDay(ask.posted);
    if (posted) foot.appendChild(mk('span', null, 'Posted ' + posted));
    el.appendChild(foot);
    return el;
  }

  function say(text, retry){
    state.textContent = text || '';
    state.hidden = !text;
    if (retry){
      state.appendChild(document.createElement('br'));
      var b = mk('button', 'btn btn-gold', 'Try Again');
      b.type = 'button';
      b.addEventListener('click', load);
      state.appendChild(b);
    }
  }
  function render(asks){
    grid.textContent = '';
    count.textContent = asks.length ? asks.length + ' open' : '';
    if (!asks.length){ say('No open asks right now. Check back soon.'); return; }
    say('');
    asks.forEach(function(a){ grid.appendChild(card(a)); });
  }
  function load(){
    grid.textContent = '';
    count.textContent = '';
    say('Loading open asks.');
    var demo = !cfg.hubApi;
    note.hidden = !demo;
    var req = demo
      ? fetch('/hub/sample-asks.json')
      : ((N.auth && N.auth.getIdToken) ? N.auth.getIdToken() : Promise.resolve(null)).then(function(token){
          var headers = {};
          if (token) headers.Authorization = 'Bearer ' + token;
          return fetch(cfg.hubApi + 'asks', {headers: headers});
        });
    req.then(function(r){
      if (r.status === 401){
        say('Your sign-in expired. Sign in again, then try again.', true);
        if (N.openAuth) N.openAuth();
        return;
      }
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json().then(function(d){ render((d && d.asks) || []); });
    }).catch(function(){ say('Could not load the open asks. Check your connection and try again.', true); });
  }
  function reveal(){
    gate.hidden = true;
    board.hidden = false;
    load();
  }

  var signIn = document.getElementById('hubSignIn');
  if (signIn) signIn.addEventListener('click', function(){ if (N.openAuth) N.openAuth(); });
  if (N.whenAuthed && cfg.cognito && cfg.cognito.userPoolId) {
    N.whenAuthed(reveal);
  } else {
    // No account system on this environment (the local server): open the hub.
    reveal();
  }
})();
</script>
"""


def swap(p, old, new):
    assert old in p, "contact page chrome changed, not found: " + old[:60]
    return p.replace(old, new)


def build(out_rel, title, desc, kicker, h1, main_html, extra_js, dek=None):
    p = base
    p = swap(p, "<title>Contact NIL TV | Get In Touch</title>", "<title>%s</title>" % title)
    p = swap(p, '<meta name="description" content="Reach the NIL TV team: partnerships, general questions, and legal.">',
             '<meta name="description" content="%s">\n<meta name="robots" content="noindex">' % desc)
    p = swap(p, '<meta property="og:description" content="Reach the NIL TV team: partnerships, general questions, and legal.">',
             '<meta property="og:description" content="%s">' % desc)
    p = swap(p, '<meta property="og:title" content="Contact NIL TV | Get In Touch">', '<meta property="og:title" content="%s">' % title)
    p = swap(p, ORIGIN + "/contact/", ORIGIN + "/" + out_rel)
    hero_copy = '<div class="hero-kicker">%s</div><h1 class="hero-title ht-sm">%s</h1>' % (kicker, h1)
    if dek:
        hero_copy += '<p class="hero-dek dek-2line">%s</p>' % dek
    p = swap(p, '<div class="hero-kicker">Contact</div><h1 class="hero-title ht-sm">Get In Touch</h1>', hero_copy)
    p, n = re.subn(r'<main class="shelves">.*?</main>', lambda m: main_html, p, count=1, flags=re.S)
    assert n == 1, "contact page main block not found"
    p = p.replace("</style>", HUB_CSS + "</style>", 1)
    p = p.replace("</body>", extra_js + "</body>", 1)
    assert 'class="chmq-card"' not in p
    os.makedirs(W + out_rel, exist_ok=True)
    io.open(W + out_rel + "index.html", "w", encoding="utf-8", newline="\n").write(p)
    print("built", out_rel)


build("hub/",
      "Athlete Content Hub | NIL TV",
      "NIL TV athletes: see the content the network is looking for.",
      "NIL TV Athletes", "Content Hub",
      HUB_MAIN, HUB_JS,
      dek="The content NIL TV is looking for right now. Find an ask that fits you.")
