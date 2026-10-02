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
.ask-link{display:block;max-width:100%;font-size:12.5px;color:var(--gold-bright);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ask-noteline{font-size:12px;color:var(--dim)}
.ask-form{display:flex;flex-direction:column;gap:10px;border-top:1px solid var(--border);padding-top:12px}
.ask-form label{display:block;font-size:12px;color:var(--dim)}
.ask-form input{display:block;width:100%;margin-top:5px;background:rgba(245,245,247,.06);border:1px solid var(--border);color:var(--text);padding:9px 12px;border-radius:10px;font-family:inherit;font-size:13px}
.ask-form input:focus{outline:none;border-color:rgba(217,178,91,.6)}
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
    <p class="hub-note" id="hubNote" hidden><b>Sample data.</b> The hub is not connected on this environment yet, so these asks are examples and your claims and submissions are saved in this browser only.</p>
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
/* Athlete Content Hub: the open content asks, the visitor's own claims, and
   the link they submit for a claimed ask.
   Where the environment has NIL TV accounts the hub shows only after sign-in.

   With NILTV_CONFIG.hubApi set (live), every call carries the account's ID
   token:
     GET  {hubApi}asks               -> {asks: [...]}; each ask carries `mine`:
                                        null, or {status: claimed|submitted,
                                        claimed_at, submitted_at, url, note}
     POST {hubApi}asks/{id}/claim    -> 2xx, or 409 when the last spot has gone
     POST {hubApi}asks/{id}/unclaim  -> 2xx
     POST {hubApi}asks/{id}/submit   -> 2xx; JSON body {url, note}; a second
                                        submit replaces the first
   With none (demo) it runs on /hub/sample-asks.json, keeps claims and
   submissions in this browser's localStorage, and says so on the page.
   Ask text is rendered with textContent only; a submitted link becomes an
   anchor only when it parses as http(s). */
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
  var NOTE_MAX = 200;

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
  // A claim or submit time is an instant, shown on the visitor's own calendar.
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
  // "instagram.com/reel/abc" -> "https://instagram.com/reel/abc"; null when it
  // is not an http(s) address at all.
  function cleanUrl(raw){
    var v = String(raw || '').trim();
    if (!v || /\s/.test(v)) return null;
    if (!/^https?:\/\//i.test(v)) v = 'https://' + v;
    try {
      var u = new URL(v);
      if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
      // a real host has a dot in it; new URL() alone accepts almost anything
      if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(u.hostname)) return null;
      return u.href;
    } catch (e) { return null; }
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
  function authed(path, method, body){
    var tokenP = (N.auth && N.auth.getIdToken) ? N.auth.getIdToken() : Promise.resolve(null);
    return tokenP.then(function(token){
      var headers = {};
      if (token) headers.Authorization = 'Bearer ' + token;
      if (body) headers['Content-Type'] = 'application/json';
      return fetch(cfg.hubApi + path, {method: method || 'GET', headers: headers, body: body ? JSON.stringify(body) : undefined});
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
  function submitLink(ask, url, noteText){
    if (demo){
      var claims = readClaims();
      var mine = claims[ask.id] || {status: 'claimed', claimed_at: new Date().toISOString()};
      mine.status = 'submitted';
      mine.submitted_at = new Date().toISOString();
      mine.url = url;
      mine.note = noteText;
      claims[ask.id] = mine;
      writeClaims(claims);
      return Promise.resolve();
    }
    return authed('asks/' + encodeURIComponent(ask.id) + '/submit', 'POST', {url: url, note: noteText})
      .then(function(r){ if (!r.ok) throw httpError(r.status); });
  }

  /* ---- cards ---- */
  function failText(e){
    var status = e && e.status;
    if (status === 409) return 'That last spot was just claimed.';
    if (status === 401) return 'Your sign-in expired. Sign in again.';
    return 'That did not go through. Try again.';
  }
  function actionButton(label, cls, onClick){
    var b = mk('button', 'btn ' + cls, label);
    b.type = 'button';
    b.addEventListener('click', onClick);
    return b;
  }
  // the submit form, built when the athlete asks for it; it replaces the
  // card's button row until it is sent or cancelled
  function linkForm(ask, act, msg){
    var form = mk('form', 'ask-form');
    // the page checks the link itself (cleanUrl adds a missing https://), so
    // the browser's own URL rule must not block the submit first
    form.noValidate = true;
    var urlLabel = mk('label', null, 'Link to your post');
    var urlIn = document.createElement('input');
    urlIn.type = 'url';
    urlIn.required = true;
    urlIn.placeholder = 'https://www.instagram.com/reel/...';
    urlIn.value = (ask.mine && ask.mine.url) || '';
    urlLabel.appendChild(urlIn);
    form.appendChild(urlLabel);
    var noteLabel = mk('label', null, 'Note for the team (optional)');
    var noteIn = document.createElement('input');
    noteIn.type = 'text';
    noteIn.maxLength = NOTE_MAX;
    noteIn.value = (ask.mine && ask.mine.note) || '';
    noteLabel.appendChild(noteIn);
    form.appendChild(noteLabel);
    var row = mk('div', 'ask-act');
    var send = mk('button', 'btn btn-gold', 'Send');
    send.type = 'submit';
    row.appendChild(send);
    row.appendChild(actionButton('Cancel', 'btn-ghost', function(){
      form.remove();
      act.hidden = false;
    }));
    var formMsg = mk('span', 'ask-msg');
    formMsg.setAttribute('role', 'status');
    row.appendChild(formMsg);
    form.appendChild(row);
    form.addEventListener('submit', function(e){
      e.preventDefault();
      formMsg.textContent = '';
      var url = cleanUrl(urlIn.value);
      if (!url){
        formMsg.textContent = 'Paste the full link to your post.';
        urlIn.focus();
        return;
      }
      send.disabled = true;
      submitLink(ask, url, noteIn.value.trim().slice(0, NOTE_MAX)).then(refresh).catch(function(e2){
        send.disabled = false;
        formMsg.textContent = failText(e2);
      });
    });
    return form;
  }
  function card(ask){
    var mine = ask.mine;
    var submitted = !!(mine && mine.status === 'submitted');
    var el = mk('article', 'ask' + (mine ? ' mine' : ''));
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
    if (submitted){
      var sentWhen = fmtWhen(mine.submitted_at);
      foot.appendChild(mk('b', null, 'Submitted' + (sentWhen ? ' ' + sentWhen : '')));
    } else if (mine){
      var when = fmtWhen(mine.claimed_at);
      foot.appendChild(mk('b', null, 'You claimed this' + (when ? ' ' + when : '')));
    } else {
      foot.appendChild(mk('b', null, slotsText(ask)));
      var posted = fmtDay(ask.posted);
      if (posted) foot.appendChild(mk('span', null, 'Posted ' + posted));
    }
    el.appendChild(foot);
    if (submitted){
      var href = cleanUrl(mine.url);
      var link = mk(href ? 'a' : 'span', 'ask-link', mine.url || '');
      if (href){
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener';
      }
      el.appendChild(link);
      if (mine.note) el.appendChild(mk('p', 'ask-noteline', 'Note: ' + mine.note));
    }

    var act = mk('div', 'ask-act');
    var msg = mk('span', 'ask-msg');
    msg.setAttribute('role', 'status');
    function openForm(){
      act.hidden = true;
      msg.textContent = '';
      el.insertBefore(linkForm(ask, act, msg), act);
    }
    if (submitted){
      act.appendChild(actionButton('Change link', 'btn-ghost', openForm));
    } else if (mine){
      act.appendChild(actionButton('Submit', 'btn-gold', openForm));
      act.appendChild(actionButton('Unclaim', 'btn-ghost', function(){
        var b = this;
        b.disabled = true;
        msg.textContent = '';
        setClaim(ask, false).then(refresh).catch(function(e){
          b.disabled = false;
          msg.textContent = failText(e);
        });
      }));
    } else {
      var full = isFull(ask);
      var claim = actionButton(full ? 'Full' : 'Claim', 'btn-gold', function(){
        claim.disabled = true;
        msg.textContent = '';
        setClaim(ask, true).then(function(){
          return refresh().then(function(){
            // the card just moved up the page: follow it
            if (mineSec.scrollIntoView) mineSec.scrollIntoView({behavior: 'smooth', block: 'start'});
          });
        }).catch(function(e){
          claim.disabled = false;
          msg.textContent = failText(e);
        });
      });
      claim.disabled = full;
      act.appendChild(claim);
    }
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
    var sent = mine.filter(function(a){ return a.mine.status === 'submitted'; }).length;
    say('');
    fill(mineGrid, mine);
    mineCount.textContent = mine.length ? mine.length + ' claimed' + (sent ? ', ' + sent + ' submitted' : '') : '';
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
  // reload in place, without the loading line (used after every action)
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
