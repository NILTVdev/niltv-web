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
.ask.mine{border-color:rgba(217,178,91,.45)}
.ask-act{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ask-act .btn{padding:9px 20px;font-size:13px}
.ask-msg{font-size:12px;color:var(--red)}
.btn[disabled]{opacity:.45;cursor:not-allowed;transform:none!important}
.hub-empty{font-size:13.5px;color:var(--dim);margin:0 0 60px}
#hubMine{scroll-margin-top:76px}
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

<div id="hubBoard" hidden>
  <div class="hub-wrap">
    <p class="hub-note" id="hubNote" hidden><b>Sample data.</b> The hub is not connected on this environment yet, so these asks are examples and your claims are saved in this browser only.</p>
    <div class="hub-state" id="hubState" role="status"></div>
  </div>
  <section class="shelf" id="hubMine" hidden>
    <div class="shelf-head">
      <h2 class="shelf-title gold">My Claims</h2>
      <span class="shelf-sub" id="hubMineCount"></span>
    </div>
    <div class="hub-grid" id="hubMineGrid"></div>
  </section>
  <section class="shelf" id="hubOpen" hidden>
    <div class="shelf-head">
      <h2 class="shelf-title gold">Open Asks</h2>
      <span class="shelf-sub" id="hubCount"></span>
    </div>
    <div class="hub-wrap"><p class="hub-empty" id="hubEmpty" hidden></p></div>
    <div class="hub-grid" id="hubGrid"></div>
  </section>
</div>

</main>"""

HUB_JS = r"""
<script>
/* Athlete Content Hub: the open content asks and the visitor's own claims.
   Where the environment has NIL TV accounts the hub shows only after sign-in.

   With NILTV_CONFIG.hubApi set (live), every call carries the account's ID
   token:
     GET  {hubApi}asks               -> {asks: [...]}; each ask carries `mine`,
                                        null or {status, claimed_at}
     POST {hubApi}asks/{id}/claim    -> 2xx, or 409 when the last spot has gone
     POST {hubApi}asks/{id}/unclaim  -> 2xx
   With none (demo) it runs on /hub/sample-asks.json, keeps claims in this
   browser's localStorage, and says so on the page.
   Ask text is rendered with textContent only. */
(function(){
  var cfg = window.NILTV_CONFIG || {};
  var N = window.NILTV || {};
  var demo = !cfg.hubApi;
  var gate = document.getElementById('hubGate');
  var board = document.getElementById('hubBoard');
  var state = document.getElementById('hubState');
  var note = document.getElementById('hubNote');
  var mineSec = document.getElementById('hubMine');
  var mineGrid = document.getElementById('hubMineGrid');
  var mineCount = document.getElementById('hubMineCount');
  var openSec = document.getElementById('hubOpen');
  var grid = document.getElementById('hubGrid');
  var count = document.getElementById('hubCount');
  var empty = document.getElementById('hubEmpty');

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
  // A claim time is an instant, so it is shown on the visitor's own calendar.
  function fmtWhen(iso){
    var d = new Date(iso || '');
    return isNaN(d) ? '' : d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
  }
  function isFull(ask){
    return ask.slots != null && ask.slots - (ask.claimed || 0) <= 0;
  }
  function slotsText(ask){
    var claimed = ask.claimed || 0;
    if (ask.slots == null) return 'Open to all athletes' + (claimed ? ' · ' + claimed + ' claimed' : '');
    if (isFull(ask)) return 'All spots claimed';
    return (ask.slots - claimed) + ' of ' + ask.slots + (ask.slots === 1 ? ' spot' : ' spots') + ' left';
  }

  /* ---- data: demo and live answer the same calls ---- */
  var CLAIMS_KEY = 'niltv:hub:claims';
  function readClaims(){
    try { return JSON.parse(localStorage.getItem(CLAIMS_KEY)) || {}; } catch (e) { return {}; }
  }
  function writeClaims(claims){
    try { localStorage.setItem(CLAIMS_KEY, JSON.stringify(claims)); } catch (e) {}
  }
  function httpError(status){
    var e = new Error('http ' + status);
    e.status = status;
    return e;
  }
  function authed(path, method){
    var tokenP = (N.auth && N.auth.getIdToken) ? N.auth.getIdToken() : Promise.resolve(null);
    return tokenP.then(function(token){
      var headers = {};
      if (token) headers.Authorization = 'Bearer ' + token;
      return fetch(cfg.hubApi + path, {method: method || 'GET', headers: headers});
    });
  }
  function listAsks(){
    return (demo ? fetch('/hub/sample-asks.json') : authed('asks')).then(function(r){
      if (!r.ok) throw httpError(r.status);
      return r.json();
    }).then(function(d){
      var asks = (d && d.asks) || [];
      if (!demo) return asks;
      var claims = readClaims();
      asks.forEach(function(a){
        a.mine = claims[a.id] || null;
        if (a.mine) a.claimed = (a.claimed || 0) + 1;
      });
      return asks;
    });
  }
  function setClaim(ask, on){
    if (demo){
      var claims = readClaims();
      if (on) claims[ask.id] = {status: 'claimed', claimed_at: new Date().toISOString()};
      else delete claims[ask.id];
      writeClaims(claims);
      return Promise.resolve();
    }
    return authed('asks/' + encodeURIComponent(ask.id) + (on ? '/claim' : '/unclaim'), 'POST')
      .then(function(r){ if (!r.ok) throw httpError(r.status); });
  }

  /* ---- cards ---- */
  function card(ask){
    var el = mk('article', 'ask' + (ask.mine ? ' mine' : ''));
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
    if (ask.mine){
      var when = fmtWhen(ask.mine.claimed_at);
      foot.appendChild(mk('b', null, 'You claimed this' + (when ? ' ' + when : '')));
    } else {
      foot.appendChild(mk('b', null, slotsText(ask)));
      var posted = fmtDay(ask.posted);
      if (posted) foot.appendChild(mk('span', null, 'Posted ' + posted));
    }
    el.appendChild(foot);

    var act = mk('div', 'ask-act');
    var full = !ask.mine && isFull(ask);
    var btn = mk('button', 'btn ' + (ask.mine ? 'btn-ghost' : 'btn-gold'), ask.mine ? 'Unclaim' : (full ? 'Full' : 'Claim'));
    btn.type = 'button';
    btn.disabled = full;
    var msg = mk('span', 'ask-msg');
    msg.setAttribute('role', 'status');
    btn.addEventListener('click', function(){
      var claiming = !ask.mine;
      btn.disabled = true;
      msg.textContent = '';
      setClaim(ask, claiming).then(function(){
        return refresh().then(function(){
          // the card just moved up the page: follow it
          if (claiming && mineSec.scrollIntoView) mineSec.scrollIntoView({behavior: 'smooth', block: 'start'});
        });
      }).catch(function(e){
        btn.disabled = false;
        var status = e && e.status;
        msg.textContent = status === 409 ? 'That last spot was just claimed.'
          : (status === 401 ? 'Your sign-in expired. Sign in again.' : 'That did not go through. Try again.');
      });
    });
    act.appendChild(btn);
    act.appendChild(msg);
    el.appendChild(act);
    return el;
  }
  function fill(target, asks){
    target.textContent = '';
    asks.forEach(function(a){ target.appendChild(card(a)); });
  }

  /* ---- page states ---- */
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
    var mine = asks.filter(function(a){ return a.mine; });
    var open = asks.filter(function(a){ return !a.mine; });
    say('');
    fill(mineGrid, mine);
    mineCount.textContent = mine.length ? mine.length + ' claimed' : '';
    mineSec.hidden = !mine.length;
    fill(grid, open);
    count.textContent = open.length ? open.length + ' open' : '';
    empty.textContent = mine.length ? 'You have claimed everything that is open. Check back soon.'
                                    : 'No open asks right now. Check back soon.';
    empty.hidden = !!open.length;
    openSec.hidden = false;
  }
  function failed(e){
    mineSec.hidden = true;
    openSec.hidden = true;
    if (e && e.status === 401){
      say('Your sign-in expired. Sign in again, then try again.', true);
      if (N.openAuth) N.openAuth();
      return;
    }
    say('Could not load the open asks. Check your connection and try again.', true);
  }
  // reload in place, without the loading line (used after a claim)
  function refresh(){
    return listAsks().then(render, failed);
  }
  function load(){
    mineSec.hidden = true;
    openSec.hidden = true;
    note.hidden = !demo;
    say('Loading open asks.');
    refresh();
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
