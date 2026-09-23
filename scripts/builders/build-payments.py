# Build two athlete-only pages from the contact page's chrome so nav, footer,
# theater and CSS stay byte-identical with the rest of the site:
#   /payments/        - quiet gate: sends athletes to their Stripe Express account
#                       (footer link "Athlete Payments")
#   /athlete-signup/  - the NIL TV College Athlete Application, question for
#                       question from the Google Form, plus the standing
#                       consent block
#
# Run after any chrome change:  python scripts/builders/build-payments.py
import io, os, re, html

W = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")).replace("\\", "/") + "/"
ORIGIN = "https://dev.dkdfgvugisb3v.amplifyapp.com"
CONSENT_VERSION = "2026-09-08"

base = io.open(W + "contact/index.html", encoding="utf-8").read()

PAY_CSS = r"""
/* ---------- athlete pages (hand pages, built by scripts/builders/build-payments.py) ---------- */
.pay-panel{margin:0 var(--gutter);max-width:640px;border:1px solid rgba(217,178,91,.35);
  background:linear-gradient(180deg,rgba(217,178,91,.07),rgba(23,23,28,.5));border-radius:18px;padding:34px 34px 30px}
.pay-panel .pk{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--gold);font-weight:700;margin-bottom:8px}
.pay-panel h2{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:32px;text-transform:uppercase;line-height:1;margin-bottom:10px}
.pay-panel p{font-size:13.5px;color:var(--dim)}
.pay-panel .acts{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px;align-items:center}
.pay-panel .note{font-size:12px;color:var(--dim);opacity:.85;margin-top:18px;padding-top:14px;border-top:1px solid var(--border)}
.pay-panel .note a{color:var(--gold-bright)}
.pay-panel .spin{width:30px;height:30px;border-radius:50%;border:3px solid var(--border);border-top-color:var(--gold);animation:payspin .8s linear infinite;margin:6px 0 14px}
@keyframes payspin{to{transform:rotate(360deg)}}
.pay-panel.err{border-color:rgba(224,51,74,.45)}
.pay-panel.err h2{color:var(--red)}
.pay-panel + .pay-panel{margin-top:18px}
a.pay-panel{display:block;color:inherit;text-decoration:none;transition:border-color .25s ease,box-shadow .25s ease,transform .25s ease}
a.pay-panel:hover{border-color:var(--gold);box-shadow:0 0 28px rgba(217,178,91,.22);transform:translateY(-2px)}
a.pay-panel .btn{pointer-events:none}
.btn[disabled],.btn.is-off{opacity:.45;cursor:not-allowed;transform:none!important}
/* application form: follows the printed Google Form flow (numbered, one column) */
.apply-wrap{margin:0 var(--gutter);max-width:760px}
.apply-wrap .lead{font-size:13.5px;color:var(--dim);margin-bottom:18px;max-width:640px}
.apply-wrap .lead a{color:var(--gold-bright)}
.gf-head{border:1px solid var(--border);border-top:6px solid var(--gold);background:rgba(23,23,28,.4);border-radius:14px;padding:26px 28px 18px;margin-bottom:14px}
.gf-title{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:30px;text-transform:uppercase;line-height:1;margin-bottom:12px}
.gf-head .lead{margin-bottom:10px;max-width:none}
.gf-head .lead b{color:var(--text)}
.gf-req{font-size:12px;color:var(--red);margin-top:6px}
.apply-form .q{display:flex;gap:14px;border:1px solid var(--border);background:rgba(23,23,28,.4);border-radius:14px;padding:20px 22px;margin-bottom:12px}
.apply-form .qn{flex:none;width:28px;font-size:13px;color:var(--dim);padding-top:2px;font-variant-numeric:tabular-nums}
.apply-form .qb{flex:1;min-width:0}
.apply-form label,.apply-form .ql{display:block;font-size:14px;font-weight:600;color:var(--text);margin-bottom:12px}
.apply-form .mo{font-size:12px;font-style:italic;color:var(--dim);margin:-6px 0 10px}
.apply-form input[type=text],.apply-form input[type=email],.apply-form input[type=tel],.apply-form select,.apply-form textarea{
  background:rgba(245,245,247,.06);border:1px solid var(--border);color:var(--text);padding:10px 14px;border-radius:10px;
  font-family:inherit;font-size:13px;width:100%;max-width:420px}
.apply-form textarea{max-width:none;min-height:96px;resize:vertical}
.apply-form select option{color:#111}
.apply-form input:focus,.apply-form select:focus,.apply-form textarea:focus{outline:none;border-color:rgba(217,178,91,.6)}
.apply-form .ovals{display:flex;flex-direction:column;gap:10px}
.apply-form .ovals label{display:flex;gap:10px;align-items:center;font-weight:400;font-size:13.5px;margin:0;cursor:pointer;position:relative}
.apply-form .ovals input{position:absolute;opacity:0;width:0;height:0}
.apply-form .ovals span{width:30px;height:18px;border-radius:999px;border:1.5px solid var(--dim);flex:none;transition:background .15s,border-color .15s}
.apply-form .ovals input:checked + span{background:var(--gold);border-color:var(--gold)}
.apply-form .ovals input:focus-visible + span{outline:2px solid var(--gold);outline-offset:2px}
.apply-form .chk{display:flex;gap:10px;align-items:flex-start;font-size:12.5px;color:var(--dim);line-height:1.5;margin:0 0 12px;font-weight:400}
.apply-form .chk input{margin-top:3px;flex:none;width:16px;height:16px;accent-color:var(--gold)}
.apply-form .chk b{color:var(--text);font-weight:600}
.apply-form .chk a{color:var(--gold-bright)}
.apply-form .req{color:var(--gold)}
.apply-form .hint{font-size:11.5px;color:var(--dim);margin:-4px 0 14px}
.gf-alt{font-size:12.5px;color:var(--dim);margin:0 0 60px}
.gf-alt a{color:var(--gold-bright)}
.gf-embed{background:#fff;border-radius:14px;padding:8px;margin:0 0 60px;max-width:656px;overflow-x:auto}
.gf-embed iframe{display:block;max-width:100%}
.apply-form .submit-row{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:6px 0 60px}
#apply-msg{font-size:12.5px;color:var(--red);min-height:18px}
.apply-done{border:1px solid rgba(111,221,154,.45);background:rgba(23,23,28,.5);border-radius:14px;padding:26px;margin-bottom:60px}
.apply-done h3{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:26px;text-transform:uppercase;margin-bottom:8px}
.apply-done p{font-size:13px;color:var(--dim);margin-bottom:8px}
.apply-done ol{font-size:13px;color:var(--dim);padding-left:20px;margin:6px 0 8px}
.apply-done li{margin-bottom:4px}
.apply-done pre{font-size:11px;line-height:1.45;color:var(--dim);background:rgba(0,0,0,.35);border:1px solid var(--border);border-radius:10px;padding:14px;overflow:auto;max-height:320px;margin-top:12px}
"""

# ------------------------------------------------------------ /payments/
PAY_MAIN = r"""<main class="shelves centered" id="main">

<section class="pay-panel" id="payPanel" aria-live="polite">
  <div class="pk">NIL TV Athletes</div>
  <h2>Your Stripe Account</h2>
  <div class="acts"><a class="btn btn-gold" href="https://connect.stripe.com/express_login" target="_blank" rel="noopener">Open Stripe Account</a></div>
  <div class="note">Stripe signs you in with the email on your NIL TV account and a code sent to your phone.<br>First time here? Use the setup link from your welcome text or email. It finishes your Stripe setup and never expires.<br>Questions about a payment: <a href="mailto:contact@niltv.com">contact@niltv.com</a>.</div>
</section>

<a class="pay-panel pay-link" href="/athlete-signup/">
  <div class="pk">Not on NIL TV yet?</div>
  <h2>College Athlete Application</h2>
  <p>Apply to join the NIL TV athlete network. Sign in with your NIL TV account and the form takes about ten minutes.</p>
  <div class="acts"><span class="btn btn-gold">Start Your Application</span></div>
</a>

</main>"""

PAY_JS = r"""
<script>
/* Athlete Payments gate.
   No token: the static panel above (Stripe Express login).
   ?t=<token>: the permanent setup link. Asks the payout backend for status
   and sends the athlete straight to Stripe onboarding or their dashboard. */
(function(){
  var cfg = window.NILTV_CONFIG || {};
  var token = new URLSearchParams(location.search).get('t');
  if (!token) return;
  var panel = document.getElementById('payPanel');
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function render(html, err){ panel.innerHTML = html; panel.classList.toggle('err', !!err); }
  function fail(title, msg){
    render('<div class="pk">NIL TV Athletes</div><h2>' + esc(title) + '</h2><p>' + esc(msg) + '</p>' +
      '<div class="acts"><button class="btn btn-gold" type="button" onclick="location.reload()">Try Again</button></div>' +
      '<div class="note">Still stuck? Reply to the text or email that sent you here.</div>', true);
  }
  function go(){
    render('<div class="pk">NIL TV Athletes</div><div class="spin"></div><p>Opening Stripe.</p>');
    fetch(cfg.payoutsApi + '?t=' + encodeURIComponent(token))
      .then(function(r){ return r.json().then(function(b){ return {ok:r.ok, body:b}; }); })
      .then(function(res){
        var b = res.body || {};
        if (res.ok && b.url) location.replace(b.url);
        else if (b.error === 'invalid_link') fail('Link Problem', 'This link is not valid. Use the exact link we sent you.');
        else fail('Stripe did not respond', 'Give it a minute and try again.');
      })
      .catch(function(){ fail('Could not connect', 'Check your signal and try again.'); });
  }
  if (!cfg.payoutsApi){
    render('<div class="pk">NIL TV Athletes</div><h2>Setup Link Recognized</h2>' +
      '<p>Payout setup is not connected on this environment yet. Once it is, this link opens Stripe onboarding the first time and your Stripe dashboard after that.</p>' +
      '<div class="acts"><button class="btn btn-gold is-off" type="button" disabled>Continue to Stripe</button></div>' +
      '<div class="note">Backend pending: the niltv-payouts-start function URL.</div>');
    return;
  }
  render('<div class="pk">NIL TV Athletes</div><div class="spin"></div><p>Checking your setup.</p>');
  fetch(cfg.payoutsApi + '?t=' + encodeURIComponent(token) + '&check=1')
    .then(function(r){ return r.json().then(function(b){ return {ok:r.ok, body:b}; }); })
    .then(function(res){
      var b = res.body || {};
      if (!res.ok){
        if (b.error === 'invalid_link') fail('Link Problem', 'This link is not valid. Use the exact link we sent you.');
        else fail('Stripe did not respond', 'Give it a minute and try again.');
        return;
      }
      var ready = b.kind === 'dashboard';
      render('<div class="pk">NIL TV Athletes</div><h2>' + (ready ? 'Your Stripe Account' : 'Finish Your Setup') + '</h2>' +
        '<p>' + (ready ? 'Your account is verified and connected to your bank.' : 'Stripe still needs a few details before NIL TV can pay you. Identity check and bank details take about five minutes.') + '</p>' +
        '<div class="acts"><button class="btn btn-gold" type="button" id="goStripe">' + (ready ? 'Open Stripe Account' : 'Continue to Stripe') + '</button></div>' +
        (ready ? '' : '<div class="note">Have your government ID and bank routing and account numbers ready.</div>'));
      document.getElementById('goStripe').addEventListener('click', go);
    })
    .catch(function(){ fail('Could not connect', 'Check your signal and try again.'); });
})();
</script>
"""

# ------------------------------------------------------------ /athlete-signup/
# Mirrors the Google Form: same titles, order, types, required flags and
# choices. (title, name, type, required, choices)
CHANNELS = ['No', 'True Blue TV (Duke athletes)', 'Chapel Hill TV (UNC athletes)', 'Red Pack TV (NC State athletes)',
            'Dore City TV (Vanderbilt athletes)', 'Starkville TV (Mississippi State athletes)',
            'College Station TV (Texas A&M athletes)', 'Brazos TV (Baylor athletes)', 'Golden Dome TV (Notre Dame athletes)',
            'Salt City TV (Syracuse athletes)', 'Gold Sun TV (ASU athletes)', 'Gold Salem TV (Wake Forest athletes)',
            'Not listed', 'Not listed, but I would love to help launch one!']
SPORTS = ["Men's Cross Country", "Women's Cross Country", 'Field Hockey', 'Football', "Women's Soccer", "Men's Soccer",
          "Women's Volleyball", 'Water Polo', "Men's Swim and Dive", "Women's Swim and Dive", "Men's Basketball",
          "Women's Basketball", 'Bowling', 'Fencing', "Men's Gymnastics", "Women's Gymnastics", "Men's Ice Hockey",
          "Women's Ice Hockey", 'Rifle', 'Skiing', "Men's Track and Field", "Women's Track and Field", "Men's Wrestling",
          "Women's Wrestling", 'Baseball', 'Beach Volleyball', "Men's Golf", "Women's Golf", "Men's Lacrosse",
          "Women's Lacrosse", 'Rowing', 'Softball', "Men's Tennis", "Women's Tennis", "Men's Volleyball",
          "Women's Water Polo", 'Triathlon', 'Cheer', 'Dance', 'Other']
QUESTIONS = [
    ("Email", "email", "email", True, None),
    ("First Name", "firstName", "short", True, None),
    ("Last Name", "lastName", "short", False, None),
    ("Does your college also have a channel? If so, which one?", "campusChannel", "dropdown", False, CHANNELS),
    ("University", "university", "short", True, None),
    ("College Email", "collegeEmail", "email", True, None),
    ("Phone Number", "phone", "tel", True, None),
    ("Are you an international student?", "international", "radio", True, ["Yes", "No"]),
    ("Sport", "sport", "dropdown", True, SPORTS),
    ("Year this Fall", "year", "radio", True, ["Freshman", "Sophomore", "Junior", "Senior", "Graduate Student"]),
    ("Link to your official roster profile", "rosterLink", "short", True, None),
    ("Instagram link", "instagram", "short", True, None),
    ("# of Instagram Followers", "instagramFollowers", "short", False, None),
    ("TikTok link", "tiktok", "short", True, None),
    ("# of TikTok Followers", "tiktokFollowers", "short", False, None),
    ("Youtube link", "youtube", "short", True, None),
    ("# of YouTube Subscribers", "youtubeSubscribers", "short", False, None),
    ("# of Followers on other platforms (please specify)", "otherFollowers", "short", False, None),
    ("What type of content are you producing? (nutrition, training, fashion, singing, etc.)", "contentType", "paragraph", True, None),
    ("What\u2019s your purpose behind posting?", "purpose", "paragraph", True, None),
    ("What companies have you done NIL deals with?", "nilDealsDone", "paragraph", True, None),
    ("What companies do you still want to partner with and why?", "nilDealsWanted", "paragraph", True, None),
]
FORM_DESC = [
    "<b>MUST BE AN ACTIVE COLLEGE ATHLETE</b>",
    "Are you a college athlete who loves creating content? Apply here to join our national NIL TV Athlete community with other college athlete creators just like you.",
    "Once you're in, you'll have the opportunity to collab your content with @NILTV, gain exposure across our entire media network, and unlock access to exclusive media and NIL opportunities.",
]


def field(n, title, name, kind, required, choices):
    t = html.escape(title)
    req = ' <span class="req">*</span>' if required else ''
    r = ' required' if required else ''
    if kind == "dropdown":
        ctl = '<div class="mo">Mark only one.</div><select id="q-%s" name="%s"%s><option value="">Choose</option>%s</select>' % (
            name, name, r, ''.join('<option>%s</option>' % html.escape(c) for c in choices))
    elif kind == "radio":
        ctl = '<div class="mo">Mark only one.</div><div class="ovals">' + ''.join(
            '<label><input type="radio" name="%s" value="%s"%s><span></span>%s</label>' % (name, html.escape(c), r, html.escape(c))
            for c in choices) + '</div>'
    elif kind == "paragraph":
        ctl = '<textarea id="q-%s" name="%s"%s rows="4"></textarea>' % (name, name, r)
    else:
        itype = {"email": "email", "tel": "tel"}.get(kind, "text")
        auto = {"email": "email", "firstName": "given-name", "lastName": "family-name", "collegeEmail": "email", "phone": "tel"}.get(name)
        ctl = '<input type="%s" id="q-%s" name="%s"%s%s>' % (itype, name, name, r, (' autocomplete="%s"' % auto) if auto else '')
    lab = '<label for="q-%s">%s%s</label>' % (name, t, req) if kind != "radio" else '<div class="ql">%s%s</div>' % (t, req)
    return '<div class="q"><div class="qn">%d.</div><div class="qb">%s%s</div></div>' % (n, lab, ctl)


APPLY_MAIN = r"""<main class="shelves centered" id="main">
<div class="apply-wrap">
  <div class="gf-head">
    <div class="gf-title">NIL TV College Athlete Application</div>
    %s
    <div class="gf-req">* Indicates required question</div>
  </div>

  <form class="apply-form" id="applyForm" novalidate>
%s

    <div class="q q-consent"><div class="qn">23.</div><div class="qb">
      <div class="ql">Permissions <span class="req">*</span></div>
      <label class="chk"><input type="checkbox" name="consentTerms" required> <span>I have read the <a href="/legal/terms/" target="_blank" rel="noopener">Terms of Use</a> and <a href="/legal/privacy/" target="_blank" rel="noopener">Privacy Policy</a>. Accepted athletes sign an ambassador agreement and set up a Stripe account before any payment. <span class="req">*</span></span></label>
      <label class="chk"><input type="checkbox" name="consentProgramEmail" required> <span>NIL TV may email me about my application, the program, agreements, and payouts. <span class="req">*</span></span></label>
      <label class="chk"><input type="checkbox" name="consentSms"> <span>NIL TV may text me about the program, deadlines, and payout setup. Message and data rates may apply. Reply STOP to opt out.</span></label>
      <label class="chk"><input type="checkbox" name="consentMarketing"> <span>Email me NIL TV network news, new competitions, and opportunities beyond the program.</span></label>
      <label class="chk"><input type="checkbox" name="consentPartners"> <span>NIL TV may send me offers from its brand partners and use my information to deliver relevant partner marketing.</span></label>
      <label class="chk"><input type="checkbox" name="confirmAge" required> <span>I am 18 or older. Under 18? Apply anyway; a parent or guardian signs with you before anything goes live or any payment is made. <span class="req">*</span></span></label>
    </div></div>

    <div class="submit-row"><button class="btn btn-gold" type="submit" id="applySubmit">Submit</button><div id="apply-msg" role="status"></div></div>
  </form>

  <div class="apply-done" id="applyDone" hidden></div>
</div>
</main>"""

APPLY_JS = r"""
<script>
/* Athlete signup: posts to NILTV_CONFIG.applicationsApi when it exists
   (planned POST /v1/applications, which then sends the DocuSign agreement and
   the Stripe setup link). Until then it runs in demo mode and shows the exact
   payload the backend would receive. */
(function(){
  var cfg = window.NILTV_CONFIG || {};
  var form = document.getElementById('applyForm');
  var msg = document.getElementById('apply-msg');
  var done = document.getElementById('applyDone');
  var btn = document.getElementById('applySubmit');
  function say(text){ msg.textContent = text; }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    say('');
    var bad = form.querySelector(':invalid');
    if (bad){
      bad.focus();
      say(bad.type === 'checkbox' ? 'Please tick the required permissions.' : (bad.type === 'radio' ? 'Please answer every required question.' : 'Please fill in the required fields.'));
      return;
    }
    var fd = new FormData(form), body = {};
    fd.forEach(function(v, k){ if (v !== '') body[k] = v; });
    ['consentTerms','consentProgramEmail','consentSms','consentMarketing','consentPartners','confirmAge'].forEach(function(k){ body[k] = !!form.elements[k].checked; });
    body.source = 'athlete-signup';
    body.consentVersion = '%s';
    body.submittedAt = new Date().toISOString();
    body.userAgent = navigator.userAgent;

    btn.disabled = true;
    function finish(mode){
      form.hidden = true;
      done.hidden = false;
      done.innerHTML =
        '<h3>Application received</h3>' +
        '<p>Thanks, ' + body.firstName + '. Here is what happens next, all to <b>' + body.collegeEmail + '</b>:</p>' +
        '<ol><li>The NIL TV team reviews your application.</li><li>Accepted athletes get the ambassador agreement to sign electronically.</li><li>Once signed, you get your Stripe setup link so NIL TV can pay you.</li></ol>' +
        (mode === 'demo'
          ? '<p><b>Demo mode.</b> No backend is connected on this environment. This is the payload the planned POST /v1/applications endpoint would store:</p><pre>' + JSON.stringify(body, null, 2).replace(/</g,'&lt;') + '</pre>'
          : '');
      done.scrollIntoView({behavior:'smooth', block:'start'});
    }
    if (!cfg.applicationsApi){ finish('demo'); return; }
    fetch(cfg.applicationsApi, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})
      .then(function(r){ if (!r.ok) throw new Error('http ' + r.status); finish('live'); })
      .catch(function(){ btn.disabled = false; say('Could not send. Check your connection and try again.'); });
  });
})();
</script>
""" % CONSENT_VERSION


def build(out_rel, title, desc, kicker, h1, main_html, extra_js, dek=None):
    p = base
    p = p.replace("<title>Contact NIL TV | Get In Touch</title>", "<title>%s</title>" % title)
    p = p.replace('<meta name="description" content="Reach the NIL TV team: partnerships, general questions, and legal.">',
                  '<meta name="description" content="%s">\n<meta name="robots" content="noindex">' % desc)
    p = p.replace('<meta property="og:description" content="Reach the NIL TV team: partnerships, general questions, and legal.">',
                  '<meta property="og:description" content="%s">' % desc)
    p = p.replace('<meta property="og:title" content="Contact NIL TV | Get In Touch">', '<meta property="og:title" content="%s">' % title)
    p = p.replace(ORIGIN + "/contact/", ORIGIN + "/" + out_rel)
    hero_copy = '<div class="hero-kicker">%s</div><h1 class="hero-title ht-sm">%s</h1>' % (kicker, h1)
    if dek:
        hero_copy += '<p class="hero-dek dek-2line">%s</p>' % dek
    p = re.sub(r'<div class="hero-kicker">Contact</div><h1 class="hero-title ht-sm">Get In Touch</h1>', hero_copy, p, count=1)
    p = re.sub(r'<main class="shelves">.*?</main>', lambda m: main_html, p, count=1, flags=re.S)
    p = p.replace("</style>", PAY_CSS + "</style>", 1)
    p = p.replace("</body>", extra_js + "</body>", 1)
    assert 'class="chmq-card"' not in p
    os.makedirs(W + out_rel, exist_ok=True)
    io.open(W + out_rel + "index.html", "w", encoding="utf-8", newline="\n").write(p)
    print("built", out_rel)


build("payments/",
      "Athlete Payments | NIL TV",
      "NIL TV athletes: open your Stripe account for payouts, receipts, and tax forms.",
      "NIL TV Athletes", "Athlete Payments",
      PAY_MAIN, PAY_JS,
      dek="Payouts, receipts, and tax forms live in your Stripe account.")

lead = ''.join('<p class="lead">%s</p>' % d for d in FORM_DESC)
fields = '\n'.join('      ' + field(i + 1, *q) for i, q in enumerate(QUESTIONS))
build("athlete-signup/",
      "NIL TV College Athlete Application",
      "Apply to join the national NIL TV Athlete community.",
      "NIL TV Athletes", "College Athlete Application",
      APPLY_MAIN % (lead, fields), APPLY_JS,
      dek="Join the national NIL TV Athlete community. About ten minutes.")
