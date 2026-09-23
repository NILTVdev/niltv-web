/* NIL TV web - shared runtime.
   Data flow mirrors the mobile app (mobile/src/api/hooks.ts):
   /v1/home for the composed homepage, /v1/channels for the channel index,
   /v1/content?channelId= for cards (thumb only), /v1/content/{id} on demand
   for playbackUrl (active player item ±1, like the app's pager).
   Auth mirrors admin/src/auth.ts: Cognito SRP in the browser, JWT attached
   only to /v1/me* calls. Guest browsing stays fully public. */
window.NILTV = (function () {
  "use strict";

  var cfg = window.NILTV_CONFIG || {};
  var API = (cfg.apiBase || "").replace(/\/$/, "");

  /* ══ API + cache ═════════════════════════════════════════ */

  // 60s TTL matches the API's Cache-Control so page-to-page nav feels instant.
  function cacheGet(key) {
    try {
      var raw = sessionStorage.getItem("niltv:" + key);
      if (!raw) return null;
      var obj = JSON.parse(raw);
      if (Date.now() - obj.t > 60000) return null;
      return obj.v;
    } catch (e) { return null; }
  }
  function cacheSet(key, v) {
    try { sessionStorage.setItem("niltv:" + key, JSON.stringify({ t: Date.now(), v: v })); } catch (e) {}
  }

  var inflight = {};
  function api(path, opts) {
    opts = opts || {};
    if (!opts.auth && !opts.method) {
      var hit = cacheGet(path);
      if (hit) return Promise.resolve(hit);
      if (inflight[path]) return inflight[path];
    }
    var run = function (headers) {
      return fetch(API + path, {
        method: opts.method || "GET",
        headers: headers,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
      }).then(function (r) {
        if (!r.ok) {
          // surface the API's error body (e.g. VoteErrorCode) to callers
          return r.json().catch(function () { return {}; }).then(function (body) {
            var err = new Error(path + " → HTTP " + r.status);
            err.status = r.status;
            err.body = body;
            throw err;
          });
        }
        return r.status === 204 ? {} : r.json().catch(function () { return {}; });
      });
    };
    var p;
    if (opts.auth) {
      p = auth.getIdToken().then(function (token) {
        if (!token) throw new Error("not signed in");
        var h = { Authorization: "Bearer " + token };
        if (opts.body) h["Content-Type"] = "application/json";
        return run(h);
      });
    } else {
      p = run(opts.body ? { "Content-Type": "application/json" } : undefined).then(function (json) {
        if (!opts.method) cacheSet(path, json);
        delete inflight[path];
        return json;
      }, function (err) { delete inflight[path]; throw err; });
      if (!opts.method) inflight[path] = p;
    }
    return p;
  }

  function channelItems(channelId) {
    return api("/v1/content?channelId=" + encodeURIComponent(channelId) + "&limit=48")
      .then(function (res) { return res.items || []; });
  }
  var detailCache = {};
  function getDetail(item) {
    if (item.playbackUrl) return Promise.resolve(item);
    if (!detailCache[item.id]) {
      detailCache[item.id] = api("/v1/content/" + encodeURIComponent(item.id));
    }
    return detailCache[item.id];
  }

  /* ══ Lazy third-party loaders ════════════════════════════ */
  /* hls.js (617KB) and the Cognito SDK (112KB) used to load on every page.
     They now load on demand: hls when an .m3u8 is attached, Cognito when the
     user signs in or already has a stored session. */

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = function () { reject(new Error("failed to load " + src)); };
      document.head.appendChild(s);
    });
  }
  var hlsPromise = null;
  function loadHls() {
    if (window.Hls) return Promise.resolve();
    if (!hlsPromise) {
      hlsPromise = loadScript("/assets/js/vendor/hls.min.js")
        .catch(function (e) { hlsPromise = null; throw e; });
    }
    return hlsPromise;
  }
  var cognitoPromise = null;
  function loadCognito() {
    if (window.AmazonCognitoIdentity) return Promise.resolve();
    if (!cognitoPromise) {
      cognitoPromise = loadScript("/assets/js/vendor/amazon-cognito-identity.min.js")
        .catch(function (e) { cognitoPromise = null; throw e; });
    }
    return cognitoPromise;
  }
  function hasStoredSession() {
    try {
      var pref = "CognitoIdentityServiceProvider." + cfg.cognito.clientId + ".";
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf(pref) === 0) return true;
      }
    } catch (e) {}
    return false;
  }

  /* ══ DOM helpers ═════════════════════════════════════════ */

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  }
  function fmtDuration(sec) {
    if (sec == null) return "";
    var m = Math.floor(sec / 60), s = Math.round(sec % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }
  function thumbNode(item) {
    if (item.thumbUrl) {
      var img = document.createElement("img");
      img.loading = "lazy";
      img.src = item.thumbUrl;
      img.alt = "";
      img.onerror = function () { img.replaceWith(el("div", "ph-img", item.channelName)); };
      return img;
    }
    return el("div", "ph-img", item.channelName);
  }

  /* ══ Auth (Cognito SRP, same pool/client as the app) ═════ */

  var auth = (function () {
    var pool = null;
    function getPool() {
      // read the global at CALL time - the vendor bundle lazy-loads, so a
      // captured reference from module init is null forever (the bug behind
      // "Username and Pool information are required" / null.signUp)
      var C = window.AmazonCognitoIdentity;
      if (!pool && C && cfg.cognito) {
        pool = new C.CognitoUserPool({
          UserPoolId: cfg.cognito.userPoolId,
          ClientId: cfg.cognito.clientId,
        });
      }
      return pool;
    }
    function currentUser() {
      var p = getPool();
      return p ? p.getCurrentUser() : null;
    }
    function getSession() {
      return loadCognito().then(function () {
        return new Promise(function (resolve) {
          var u = currentUser();
          if (!u) return resolve(null);
          u.getSession(function (err, session) {
            resolve(err || !session || !session.isValid() ? null : session);
          });
        });
      }).catch(function () { return null; });
    }
    function getIdToken() {
      return getSession().then(function (s) { return s ? s.getIdToken().getJwtToken() : null; });
    }
    function signIn(email, password) {
      return loadCognito().then(function () {
        return new Promise(function (resolve, reject) {
          var C = window.AmazonCognitoIdentity;
          var user = new C.CognitoUser({ Username: email, Pool: getPool() });
          var details = new C.AuthenticationDetails({ Username: email, Password: password });
          user.authenticateUser(details, {
            onSuccess: function () { resolve(); },
            onFailure: reject,
            newPasswordRequired: function () { reject(new Error("Password reset required. Use the app to finish setup.")); },
          });
        });
      });
    }
    function signUp(email, password, name, birthdate) {
      return loadCognito().then(function () {
        return new Promise(function (resolve, reject) {
          var C = window.AmazonCognitoIdentity;
          var attrs = [
            new C.CognitoUserAttribute({ Name: "name", Value: name }),
            new C.CognitoUserAttribute({ Name: "birthdate", Value: birthdate }),
          ];
          getPool().signUp(email, password, attrs, null, function (err, res) {
            if (err) reject(err); else resolve(res);
          });
        });
      });
    }
    function confirm(email, code) {
      return loadCognito().then(function () {
        return new Promise(function (resolve, reject) {
          var C = window.AmazonCognitoIdentity;
          var user = new C.CognitoUser({ Username: email, Pool: getPool() });
          user.confirmRegistration(code, true, function (err) {
            if (err) reject(err); else resolve();
          });
        });
      });
    }
    function forgot(email) {
      return loadCognito().then(function () {
        return new Promise(function (resolve, reject) {
          var C = window.AmazonCognitoIdentity;
          var user = new C.CognitoUser({ Username: email, Pool: getPool() });
          user.forgotPassword({
            onSuccess: function () { resolve(); },
            onFailure: reject,
            inputVerificationCode: function () { resolve(); },
          });
        });
      });
    }
    function confirmForgot(email, code, newPassword) {
      return loadCognito().then(function () {
        return new Promise(function (resolve, reject) {
          var C = window.AmazonCognitoIdentity;
          var user = new C.CognitoUser({ Username: email, Pool: getPool() });
          user.confirmPassword(code, newPassword, {
            onSuccess: function () { resolve(); },
            onFailure: reject,
          });
        });
      });
    }
    function signOut() {
      var u = currentUser();
      if (u) u.signOut();
      me = null;
    }
    return { getIdToken: getIdToken, getSession: getSession, signIn: signIn, signUp: signUp, confirm: confirm, forgot: forgot, confirmForgot: confirmForgot, signOut: signOut };
  })();

  // Mirrors the pool's password policy (foundation-stack.ts) and the mobile
  // app's AuthForms.tsx: 8+ chars, upper, lower, digit; symbols optional.
  var PASSWORD_RULES = "Passwords need 8+ characters with an uppercase letter, a lowercase letter, and a number.";
  function passwordIssues(pw) {
    var issues = [];
    if (pw.length < 8) issues.push("8+ characters");
    if (!/[A-Z]/.test(pw)) issues.push("an uppercase letter");
    if (!/[a-z]/.test(pw)) issues.push("a lowercase letter");
    if (!/[0-9]/.test(pw)) issues.push("a number");
    return issues;
  }
  // Cognito's own wording is technical ("Password did not conform with policy: ...");
  // swap it for the same line the app shows.
  function friendlyAuthError(e2) {
    var m = (e2 && (e2.message || String(e2))) || "";
    if (e2 && (e2.code === "InvalidPasswordException" || /conform with policy|Password not long enough/i.test(m))) return PASSWORD_RULES;
    if (e2 && e2.code === "UsernameExistsException") return "An account with this email already exists. Try signing in instead.";
    return m;
  }

  var me = null; // /v1/me payload once signed in
  var onAuthed = []; // one-shot callbacks replayed after a successful sign-in
  // Page scripts (athlete-signup) gate on a signed-in NIL TV account: run cb now
  // if already signed in, else after the next successful sign-in.
  function whenAuthed(cb) { if (me) { cb(me); return; } onAuthed.push(cb); }
  function loadMe() {
    return api("/v1/me", { auth: true }).then(function (m) {
      me = m;
      renderAvatar();
      var cbs = onAuthed.splice(0);
      cbs.forEach(function (cb) { try { cb(m); } catch (e) {} });
      return m;
    }).catch(function () { me = null; renderAvatar(); return null; });
  }
  function initials(name) {
    var parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    return (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
  }
  function renderAvatar() {
    var av = document.getElementById("nav-avatar");
    if (!av) return;
    if (me) {
      av.textContent = initials(me.name || me.email);
      av.classList.add("signed");
      av.title = me.name || me.email;
    } else {
      av.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/></svg>';
      av.classList.remove("signed");
      av.title = "Sign in";
    }
  }

  /* ══ Site chrome (nav / footer / overlays) ═══════════════ */

  // mirrors the cinema template nav: Channels, Competitions, Featured, About
  var NAV_LINKS = [
    ["Channels", "/channels/"],
    ["Competitions", "/competitions/"],
    ["Featured", "/featured/"],
    ["About", "/about/"],
  ];

  function buildNav(active, overHero) {
    var nav = el("nav", "topnav" + (overHero ? "" : " solid"));
    nav.id = "topnav";
    // Inner wrapper shares the --maxw rail with hero copy, section heads and
    // rows, so the logo and every heading below it sit on one vertical line.
    var wrap = el("div", "nav-wrap");
    nav.appendChild(wrap);
    var left = el("div", "nav-left");
    var logo = el("a", "logo");
    logo.href = "/";
    var limg = document.createElement("img");
    limg.src = "/assets/img/niltv-logo-sm.webp";
    limg.alt = "NIL TV";
    logo.appendChild(limg);
    left.appendChild(logo);
    var links = el("div", "navlinks");
    NAV_LINKS.forEach(function (l) {
      var a = el("a", active === l[0].toLowerCase() ? "active" : null, l[0]);
      a.href = l[1];
      links.appendChild(a);
    });
    left.appendChild(links);
    wrap.appendChild(left);

    var right = el("div", "nav-right");
    // no search or star icons in the nav

        var av = el("button", "avatar");
    av.id = "nav-avatar";
    av.addEventListener("click", function () { me ? openAccount() : openAuth(); });
    right.appendChild(av);
    wrap.appendChild(right);

    var burger = el("button", "nav-burger");
    burger.setAttribute("aria-label", "Menu");
    burger.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';
    burger.addEventListener("click", function () { document.getElementById("mobile-menu").classList.toggle("open"); });
    right.insertBefore(burger, right.firstChild);

    return nav;
  }

  function buildMobileMenu(active) {
    var m = el("div", "mobile-menu");
    m.id = "mobile-menu";
    NAV_LINKS.forEach(function (l) {
      var a = el("a", active === l[0].toLowerCase() ? "active" : null, l[0]);
      a.href = l[1];
      m.appendChild(a);
    });
    var p = el("a", null, "Partners");
    p.href = "/partners/";
    m.appendChild(p);
    return m;
  }

  function buildFooter() {
    // 3-zone footer: big logo + social icons | nav columns | newsletter
    var f = el("footer");
    f.innerHTML =
      '<div class="foot-wrap"><div class="foot-top">' +
      '<div class="foot-brand">' +
      '<a href="/" class="logo"><img src="/assets/img/niltv-logo-sm.webp" alt="NIL TV"></a>' +
      '<div class="foot-socials">' +
      '<a href="https://www.instagram.com/niltv" target="_blank" rel="noopener" aria-label="NIL TV on Instagram">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="17" height="17"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r="1" fill="currentColor" stroke="none"/></svg></a>' +
      '<a href="https://www.instagram.com/nilstar" target="_blank" rel="noopener" aria-label="NIL Star on Instagram">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="17" height="17"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></a>' +
      '<a href="https://truebluetv.com" target="_blank" rel="noopener" aria-label="TrueBlueTV">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="17" height="17"><rect x="2" y="6" width="20" height="14" rx="2"/><path d="M8 2l4 4 4-4"/></svg></a>' +
      '</div></div>' +
      '<div class="foot-links">' +
      '<div class="foot-col">' +
      '<a href="/channels/">Channels</a><a href="/competitions/">Competitions</a>' +
      '<a href="/featured/">Featured</a><a href="/about/">About</a></div>' +
      '<div class="foot-col">' +
      '</div>' +
      '<div class="foot-col"><h4>Legal</h4>' +
      '<a href="/legal/privacy/">Privacy Policy</a>' +
      '<a href="/legal/terms/">Terms of Use</a>' +
      '<a href="/legal/contest-notice/">Contest Notice</a><a href="/payments/">Athlete Portal</a></div>' +
      '</div>' +
      '<div class="foot-news"><h4>Get NIL TV Updates</h4>' +
      '<form id="news-form" novalidate>' +
      '<div class="news-row"><input type="email" id="news-email" aria-label="Email address" placeholder="Your email here" autocomplete="email" required>' +
      '<button type="submit" class="btn btn-play">Sign Up</button></div>' +
      '<label class="news-consent"><input type="checkbox" id="news-consent"> ' +
      'I am 18 or older and agree to receive email updates from NIL TV. ' +
      '<a href="/legal/privacy/">Privacy Policy</a></label>' +
      '<div class="news-msg" id="news-msg" role="status"></div>' +
      '</form></div>' +
      '</div>' +
      '<div class="foot-bottom">© 2026 NIL TV. A TrueBlueTV Network Production. All athlete footage used with permission.</div></div>';
    return f;
  }

  function wireNewsletter() {
    var form = document.getElementById("news-form");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = (document.getElementById("news-email").value || "").trim().toLowerCase();
      var consent = document.getElementById("news-consent").checked;
      var msg = document.getElementById("news-msg");
      msg.classList.remove("ok");
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { msg.textContent = "Enter a valid email address."; return; }
      if (!consent) { msg.textContent = "Please confirm you are 18 or older and agree to receive emails."; return; }
      msg.textContent = "…";
      // source must be a NewsletterSource enum value (@niltv/types primitives.ts) -
      // the API rejects anything else. The footer band is "home_band" everywhere;
      // the season recap page reports as "recap". Add a "site" value to the enum
      // before inventing new page-level strings here.
      api("/v1/newsletter", { method: "POST", body: { email: email, source: (location.pathname.indexOf("/nilstar/") === 0 ? "recap" : "home_band") } })
        .then(function () {
          msg.textContent = "You're on the list. Welcome to NIL TV.";
          msg.classList.add("ok");
          form.reset();
        })
        .catch(function () { msg.textContent = "Sign-up failed. Try again in a minute."; });
    });
  }


  /* ══ Cinema shell mount: binds search/auth/follows into the promoted
     cinema pages' own nav instead of injecting the legacy chrome. ══ */
  function initCinema() {
    var nav = document.getElementById("nav");
    if (!nav) return;
    var right = nav.querySelector(".nav-right");
    if (!right) { right = el("div", "nav-right"); nav.appendChild(right); }
    // no search or star icons in the nav
            var av = el("button", "nav-profile");
    av.id = "nav-avatar";
    av.addEventListener("click", function () { me ? openAccount() : openAuth(); });
    right.appendChild(av);
    wireNewsletter();
    renderAvatar();
    if (cfg.cognito && hasStoredSession()) loadMe();
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeSearch(); closeAuth();
        if (playerEl && playerEl.classList.contains("open")) closePlayer();
      }
    });
  }

  function init(opts) {
    opts = opts || {};
    var active = opts.active || "";
    document.body.insertBefore(buildMobileMenu(active), document.body.firstChild);
    document.body.insertBefore(buildNav(active, !!opts.overHero), document.body.firstChild);
    // Skip link first in tab order; give the page's main landmark an id.
    var main = document.querySelector("main");
    if (main && !main.id) main.id = "main";
    var skip = el("a", "skip-link", "Skip to content");
    skip.href = "#" + (main ? main.id : "main");
    document.body.insertBefore(skip, document.body.firstChild);
    document.body.appendChild(buildFooter());
    wireNewsletter();
    renderAvatar();
    // Only pull the Cognito SDK when a session already exists - guests never
    // pay for it until they choose to sign in.
    if (cfg.cognito && hasStoredSession()) loadMe();

    // transparent-over-hero nav goes solid on scroll (network-site behavior)
    if (opts.overHero) {
      var nav = document.getElementById("topnav");
      var onScroll = function () {
        nav.classList.toggle("solid", window.scrollY > 40);
      };
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeSearch(); closeAuth();
        if (playerEl && playerEl.classList.contains("open")) closePlayer();
      }
    });
  }

  /* ══ Search overlay (client-side over the live catalog) ══ */

  var searchEl = null, searchIndex = null;

  function buildSearchIndex() {
    if (searchIndex) return searchIndex;
    searchIndex = api("/v1/channels").then(function (res) {
      var channels = visibleChannels(res.channels);
      return Promise.all(channels.map(function (ch) {
        return channelItems(ch.id).catch(function () { return []; });
      })).then(function (lists) {
        var items = [];
        lists.forEach(function (l) { items = items.concat(l); });
        return { channels: channels, items: items };
      });
    });
    return searchIndex;
  }

  function openSearch() {
    if (!searchEl) {
      searchEl = el("div", "search-overlay");
      var box = el("div", "search-box");
      var input = document.createElement("input");
      input.type = "search";
      input.placeholder = "Search athletes, reels, channels…";
      input.id = "search-input";
      box.appendChild(input);
      var results = el("div", "search-results");
      results.id = "search-results";
      box.appendChild(results);
      searchEl.appendChild(box);
      var close = el("button", "player-close", "✕");
      close.addEventListener("click", closeSearch);
      searchEl.appendChild(close);
      searchEl.addEventListener("click", function (e) { if (e.target === searchEl) closeSearch(); });
      document.body.appendChild(searchEl);
      input.addEventListener("input", function () { runSearch(input.value); });
    }
    searchEl.classList.add("open");
    document.body.style.overflow = "hidden";
    document.getElementById("search-input").focus();
    buildSearchIndex().then(function () { runSearch(document.getElementById("search-input").value); });
  }
  function closeSearch() {
    if (searchEl) { searchEl.classList.remove("open"); document.body.style.overflow = ""; }
  }

  function runSearch(q) {
    var out = document.getElementById("search-results");
    if (!out) return;
    q = String(q || "").trim().toLowerCase();
    out.textContent = "";
    if (q.length < 2) {
      out.appendChild(el("div", "search-hint", "Type to search the network."));
      return;
    }
    buildSearchIndex().then(function (idx) {
      var chanHits = idx.channels.filter(function (c) { return c.name.toLowerCase().indexOf(q) >= 0; });
      var itemHits = idx.items.filter(function (it) {
        return it.title.toLowerCase().indexOf(q) >= 0 ||
               it.channelName.toLowerCase().indexOf(q) >= 0 ||
               (it.creatorName || "").toLowerCase().indexOf(q) >= 0;
      }).slice(0, 24);
      chanHits.forEach(function (c) {
        var row = el("a", "search-row");
        row.href = "/channels/" + channelSlug(c.id) + "/";
        row.appendChild(el("span", "search-kicker", "Channel"));
        row.appendChild(el("span", "search-title", c.name));
        out.appendChild(row);
      });
      itemHits.forEach(function (it, i) {
        var row = el("button", "search-row");
        var th = el("span", "search-thumb");
        th.appendChild(thumbNode(it));
        row.appendChild(th);
        var txt = el("span", "search-text");
        txt.appendChild(el("span", "search-title", it.title));
        txt.appendChild(el("span", "search-kicker", it.channelName + (it.duration != null ? " · " + fmtDuration(it.duration) : "")));
        row.appendChild(txt);
        row.addEventListener("click", function () {
          closeSearch();
          openPlayer(itemHits, i);
        });
        out.appendChild(row);
      });
      if (!chanHits.length && !itemHits.length) {
        out.appendChild(el("div", "search-hint", "No matches. Try an athlete, school, or channel name."));
      }
    });
  }

  /* ══ Auth modal ══════════════════════════════════════════ */

  var authEl = null;

  function authField(labelText, type, id, placeholder) {
    var wrap = el("label", "auth-field");
    wrap.appendChild(el("span", null, labelText));
    var input = document.createElement("input");
    input.type = type; input.id = id;
    if (placeholder) input.placeholder = placeholder;
    wrap.appendChild(input);
    return wrap;
  }

  function openAuth() {
    closeAuth();
    authEl = el("div", "auth-overlay");
    var box = el("div", "auth-box");
    box.appendChild(el("h3", null, "Sign in to NIL TV"));
    var err = el("div", "auth-error"); err.id = "auth-error";
    box.appendChild(err);
    box.appendChild(authField("Email", "email", "auth-email"));
    box.appendChild(authField("Password", "password", "auth-pass"));
    var pwHint = el("p", "auth-sub auth-pw-hint", PASSWORD_RULES);
    pwHint.style.display = "none";
    box.appendChild(pwHint);
    var btn = el("button", "btn btn-play auth-submit", "Sign In");
    box.appendChild(btn);
    var forgotLink = el("button", "btn-link auth-forgot", "Forgot password?");
    box.appendChild(forgotLink);
    var toggle = el("button", "btn-link auth-toggle", "New here? Create an account");
    box.appendChild(toggle);
    var assent = el("p", "auth-assent");
    assent.innerHTML = 'By creating an account you agree to the <a href="/legal/terms/">Terms of Use</a> and <a href="/legal/privacy/">Privacy Policy</a>.';
    assent.style.display = "none";
    box.appendChild(assent);
    forgotLink.addEventListener("click", function () {
      openForgot((document.getElementById("auth-email") || {}).value || "");
    });
    authEl.appendChild(box);
    var close = el("button", "player-close", "✕");
    close.addEventListener("click", closeAuth);
    authEl.appendChild(close);
    authEl.addEventListener("click", function (e) { if (e.target === authEl) closeAuth(); });
    document.body.appendChild(authEl);

    var mode = "signin";
    toggle.addEventListener("click", function () {
      err.textContent = "";
      if (mode === "signin") {
        mode = "signup";
        box.querySelector("h3").textContent = "Create your account";
        if (!document.getElementById("auth-name")) {
          box.insertBefore(authField("Name", "text", "auth-name"), box.querySelector(".auth-field"));
          box.insertBefore(authField("Birthdate", "date", "auth-dob"), btn);
        }
        document.getElementById("auth-name").parentElement.style.display = "";
        document.getElementById("auth-dob").parentElement.style.display = "";
        btn.textContent = "Create Account";
        toggle.textContent = "Have an account? Sign in";
        forgotLink.style.display = "none";
        assent.style.display = "";
        pwHint.style.display = "";
      } else {
        mode = "signin";
        box.querySelector("h3").textContent = "Sign in to NIL TV";
        var n = document.getElementById("auth-name"), d = document.getElementById("auth-dob");
        if (n) n.parentElement.style.display = "none";
        if (d) d.parentElement.style.display = "none";
        btn.textContent = "Sign In";
        toggle.textContent = "New here? Create an account";
        forgotLink.style.display = "";
        assent.style.display = "none";
        pwHint.style.display = "none";
      }
    });

    btn.addEventListener("click", function () {
      err.textContent = "";
      var email = document.getElementById("auth-email").value.trim();
      var pass = document.getElementById("auth-pass").value;
      if (!email || !pass) { err.textContent = "Email and password are required."; return; }
      btn.disabled = true;
      var done = function () { btn.disabled = false; };
      if (mode === "signin") {
        auth.signIn(email, pass).then(function () {
          closeAuth();
          return loadMe();
        }).catch(function (e2) { err.textContent = e2.message || String(e2); }).then(done);
      } else {
        var name = (document.getElementById("auth-name") || {}).value || "";
        var dob = (document.getElementById("auth-dob") || {}).value || "";
        if (!name.trim() || !dob) { err.textContent = "Name and birthdate are required."; done(); return; }
        var issues = passwordIssues(pass);
        if (issues.length) { err.textContent = "Password needs " + issues.join(", ") + "."; done(); return; }
        auth.signUp(email, pass, name.trim(), dob).then(function () {
          openConfirm(email, pass);
        }).catch(function (e2) { err.textContent = friendlyAuthError(e2); }).then(done);
      }
    });
  }

  function openConfirm(email, pass) {
    closeAuth();
    authEl = el("div", "auth-overlay");
    var box = el("div", "auth-box");
    box.appendChild(el("h3", null, "Check your email"));
    box.appendChild(el("p", "auth-sub", "We sent a confirmation code to " + email + "."));
    var err = el("div", "auth-error");
    box.appendChild(err);
    box.appendChild(authField("Confirmation code", "text", "auth-code", "123456"));
    var btn = el("button", "btn btn-play auth-submit", "Confirm");
    box.appendChild(btn);
    authEl.appendChild(box);
    document.body.appendChild(authEl);
    btn.addEventListener("click", function () {
      err.textContent = "";
      var code = document.getElementById("auth-code").value.trim();
      if (!code) return;
      btn.disabled = true;
      auth.confirm(email, code).then(function () {
        return auth.signIn(email, pass);
      }).then(function () {
        closeAuth();
        return loadMe();
      }).catch(function (e2) { err.textContent = e2.message || String(e2); btn.disabled = false; });
    });
  }

  function openForgot(prefill) {
    closeAuth();
    authEl = el("div", "auth-overlay");
    var box = el("div", "auth-box");
    box.appendChild(el("h3", null, "Reset your password"));
    var err = el("div", "auth-error");
    box.appendChild(err);
    box.appendChild(authField("Email", "email", "fp-email"));
    box.querySelector("#fp-email").value = prefill || "";
    var codeField = authField("Code from your email", "text", "fp-code", "123456");
    var passField = authField("New password", "password", "fp-pass");
    passField.appendChild(el("p", "auth-sub auth-pw-hint", PASSWORD_RULES));
    codeField.style.display = "none";
    passField.style.display = "none";
    box.appendChild(codeField);
    box.appendChild(passField);
    var btn = el("button", "btn btn-play auth-submit", "Send Code");
    box.appendChild(btn);
    var back = el("button", "btn-link auth-toggle", "Back to sign in");
    box.appendChild(back);
    back.addEventListener("click", openAuth);
    authEl.appendChild(box);
    var close = el("button", "player-close", "\u2715");
    close.addEventListener("click", closeAuth);
    authEl.appendChild(close);
    authEl.addEventListener("click", function (e) { if (e.target === authEl) closeAuth(); });
    document.body.appendChild(authEl);
    var stage = "send";
    btn.addEventListener("click", function () {
      err.textContent = "";
      var email = box.querySelector("#fp-email").value.trim();
      if (!email) { err.textContent = "Email is required."; return; }
      btn.disabled = true;
      var done = function () { btn.disabled = false; };
      if (stage === "send") {
        auth.forgot(email).then(function () {
          stage = "reset";
          codeField.style.display = "";
          passField.style.display = "";
          btn.textContent = "Reset Password";
        }).catch(function (e2) { err.textContent = e2.message || String(e2); }).then(done);
      } else {
        var code = box.querySelector("#fp-code").value.trim();
        var np = box.querySelector("#fp-pass").value;
        if (!code || !np) { err.textContent = "Code and new password are required."; done(); return; }
        var issues = passwordIssues(np);
        if (issues.length) { err.textContent = "Password needs " + issues.join(", ") + "."; done(); return; }
        auth.confirmForgot(email, code, np).then(function () {
          return auth.signIn(email, np);
        }).then(function () {
          closeAuth();
          return loadMe();
        }).catch(function (e2) { err.textContent = e2.message || String(e2); }).then(done);
      }
    });
  }

  function openAccount() {
    closeAuth();
    authEl = el("div", "auth-overlay");
    var box = el("div", "auth-box");
    box.appendChild(el("h3", null, me.name || me.email));
    box.appendChild(el("p", "auth-sub", me.email + " · " + (me.likes || []).length + " likes · " + (me.follows || []).length + " follows"));
    var btn = el("button", "btn btn-ghost auth-submit", "Sign Out");
    btn.addEventListener("click", function () {
      auth.signOut();
      renderAvatar();
      closeAuth();
    });
    box.appendChild(btn);
    authEl.appendChild(box);
    var close = el("button", "player-close", "✕");
    close.addEventListener("click", closeAuth);
    authEl.appendChild(close);
    authEl.addEventListener("click", function (e) { if (e.target === authEl) closeAuth(); });
    document.body.appendChild(authEl);
  }

  function closeAuth() {
    if (authEl) { authEl.remove(); authEl = null; }
  }

  /* ══ Follow channels (star icon) ═════════════════════════ */
  /* Follows target profiles, so each channel is followed through its creator
     profile (the ingest bridge makes one per channel account, e.g. p-nilstar).
     The channel's first card supplies the creatorId. */

  function channelProfileId(channelId) {
    return channelItems(channelId).then(function (items) {
      return items.length ? items[0].creatorId : null;
    }).catch(function () { return null; });
  }

  function openFollows() {
    if (!me) { openAuth(); return; }
    closeAuth();
    authEl = el("div", "auth-overlay");
    var box = el("div", "auth-box");
    box.appendChild(el("h3", null, "Follow Channels"));
    box.appendChild(el("p", "auth-sub", "Followed channels shape your feed in the NILTV app and on the web."));
    var listEl = el("div", "follow-list");
    listEl.appendChild(el("div", "search-hint", "Loading channels…"));
    box.appendChild(listEl);
    authEl.appendChild(box);
    var close = el("button", "player-close", "✕");
    close.addEventListener("click", closeAuth);
    authEl.appendChild(close);
    authEl.addEventListener("click", function (e) { if (e.target === authEl) closeAuth(); });
    document.body.appendChild(authEl);

    api("/v1/channels").then(function (res) {
      var channels = visibleChannels(res.channels);
      return Promise.all(channels.map(function (ch) {
        return channelProfileId(ch.id).then(function (pid) { return { ch: ch, pid: pid }; });
      }));
    }).then(function (rows) {
      listEl.textContent = "";
      rows.forEach(function (r) {
        var row = el("div", "follow-row");
        var logo = CHANNEL_LOGOS[r.ch.id];
        if (logo) {
          var img = document.createElement("img");
          img.src = logo; img.alt = "";
          row.appendChild(img);
        }
        row.appendChild(el("span", "follow-name", r.ch.name));
        var btn = el("button", "follow-btn");
        if (!r.pid) {
          btn.textContent = "Soon";
          btn.disabled = true;
        } else {
          var paint = function () {
            var on = (me.follows || []).indexOf(r.pid) >= 0;
            btn.textContent = on ? "Following" : "Follow";
            btn.classList.toggle("following", on);
          };
          paint();
          btn.addEventListener("click", function () {
            var on = (me.follows || []).indexOf(r.pid) >= 0;
            // optimistic, same as the app's follow toggle
            if (on) me.follows = me.follows.filter(function (id) { return id !== r.pid; });
            else me.follows = (me.follows || []).concat([r.pid]);
            paint();
            api("/v1/me/follows/" + encodeURIComponent(r.pid),
                { method: on ? "DELETE" : "PUT", auth: true })
              .catch(function () { loadMe().then(paint); });
          });
        }
        row.appendChild(btn);
        listEl.appendChild(row);
      });
    }).catch(function () {
      listEl.textContent = "";
      listEl.appendChild(el("div", "search-hint", "Channels are unavailable right now."));
    });
  }

  /* ══ Cards / rows ════════════════════════════════════════ */

  /* Hover preview: a muted loop starts after a short dwell (desktop pointers
     only; skipped for reduced-motion and for HLS sources to stay cheap). */
  var canHoverPreview = window.matchMedia &&
    window.matchMedia("(hover: hover)").matches &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function addHoverPreview(wrap, item) {
    if (!canHoverPreview) return;
    var timer = null, vid = null;
    wrap.addEventListener("mouseenter", function () {
      timer = setTimeout(function () {
        getDetail(item).then(function (detail) {
          if (/\.m3u8($|\?)/.test(detail.playbackUrl)) return; // mp4 only
          if (!vid) {
            vid = document.createElement("video");
            vid.muted = true;
            vid.loop = true;
            vid.playsInline = true;
            vid.className = "card-preview";
            vid.src = detail.playbackUrl;
            wrap.appendChild(vid);
          }
          vid.style.display = "";
          vid.play().catch(function () {});
        }).catch(function () {});
      }, 550);
    });
    wrap.addEventListener("mouseleave", function () {
      if (timer) { clearTimeout(timer); timer = null; }
      if (vid) { vid.pause(); vid.style.display = "none"; }
    });
  }

  function contentCard(item, list, idx, opts) {
    opts = opts || {};
    var card = el("div", "card");
    if (opts.rank) card.appendChild(el("span", "rank", String(opts.rank)));
    var wrap = el("div", "imgwrap");
    if (opts.badge) wrap.appendChild(el("span", "badge" + (opts.badge === "Live" ? " live" : ""), opts.badge));
    wrap.appendChild(thumbNode(item));
    addHoverPreview(wrap, item);
    card.appendChild(wrap);
    card.appendChild(el("div", "name", item.title));
    var info = item.channelName + (item.duration != null ? " · " + fmtDuration(item.duration) : "");
    card.appendChild(el("div", "info", info));
    card.addEventListener("click", function () { openPlayer(list, idx); });
    return card;
  }

  function chanCard(item, list, idx) {
    var card = el("div", "chan-card");
    card.style.cursor = "pointer";
    var wrap = el("div", "imgwrap");
    wrap.appendChild(thumbNode(item));
    addHoverPreview(wrap, item);
    card.appendChild(wrap);
    var body = el("div", "body");
    body.appendChild(el("div", "title", item.title));
    body.appendChild(el("div", "sub", item.channelName + (item.duration != null ? " · " + fmtDuration(item.duration) : "")));
    card.appendChild(body);
    card.addEventListener("click", function () { openPlayer(list, idx); });
    return card;
  }

  /* Anchor card for static navigation (watch-page Up Next, channel grids). */
  function linkCard(item) {
    var card = el("a", "card");
    card.href = "/watch/" + encodeURIComponent(item.id) + "/";
    var wrap = el("div", "imgwrap");
    wrap.appendChild(thumbNode(item));
    addHoverPreview(wrap, item);
    card.appendChild(wrap);
    card.appendChild(el("div", "name", item.title));
    card.appendChild(el("div", "info", item.channelName + (item.duration != null ? " · " + fmtDuration(item.duration) : "")));
    return card;
  }

  function phCard(name, info, cta) {
    var card = el("div", "card");
    var wrap = el("div", "imgwrap");
    wrap.appendChild(el("div", "ph-img", name));
    card.appendChild(wrap);
    card.appendChild(el("div", "cta", cta || "Coming Soon"));
    card.appendChild(el("div", "name", name));
    card.appendChild(el("div", "info", info || ""));
    return card;
  }

  function skeletonRow(container, n) {
    container.textContent = "";
    for (var i = 0; i < (n || 5); i++) {
      var sk = el("div", "card skeleton");
      sk.appendChild(el("div", "imgwrap"));
      container.appendChild(sk);
    }
  }

  // Arrow buttons on a .row-scroll (CBS/Max style). Call after filling.
  function rowArrows(container) {
    var parent = container.parentElement;
    if (!parent || parent.querySelector(".row-arrow")) return;
    parent.classList.add("row-holder");
    var prev = el("button", "row-arrow prev", "‹");
    prev.setAttribute("aria-label", "Scroll back");
    var next = el("button", "row-arrow next", "›");
    next.setAttribute("aria-label", "Scroll forward");
    prev.addEventListener("click", function () { container.scrollBy({ left: -container.clientWidth * 0.8, behavior: "smooth" }); });
    next.addEventListener("click", function () { container.scrollBy({ left: container.clientWidth * 0.8, behavior: "smooth" }); });
    parent.appendChild(prev);
    parent.appendChild(next);
  }

  // Rows on one page never repeat a clip (every page's rows draw from the
  // same channel pool). First row to render claims the item.
  var seenOnPage = {};
  function claimUnseen(items) {
    var fresh = items.filter(function (it) { return !seenOnPage[it.id]; });
    fresh.forEach(function (it) { seenOnPage[it.id] = true; });
    return fresh;
  }

  function fillRow(container, channelIds, opts) {
    opts = opts || {};
    if (typeof channelIds === "string") channelIds = [channelIds];
    skeletonRow(container);
    Promise.all(channelIds.map(function (id) {
      return channelItems(id).catch(function () { return []; });
    })).then(function (lists) {
      var items = [];
      lists.forEach(function (l) { items = items.concat(l); });
      if (opts.filter) items = items.filter(opts.filter);
      if (opts.sortNewest !== false) {
        items.sort(function (a, b) { return (b.publishedAt || "").localeCompare(a.publishedAt || ""); });
      }
      if (opts.limit) items = items.slice(0, opts.limit);
      if (opts.dedupe !== false) items = claimUnseen(items);
      container.textContent = "";
      if (!items.length) {
        (opts.fallback || [{ name: "Coming Soon", info: "" }]).forEach(function (f) {
          container.appendChild(phCard(f.name, f.info, f.cta));
        });
      } else {
        items.forEach(function (item, i) {
          container.appendChild(opts.kind === "chan"
            ? chanCard(item, items, i)
            : contentCard(item, items, i, {
                rank: opts.numbered ? i + 1 : null,
                badge: opts.badge ? opts.badge(item, i) : null,
                cta: opts.cta,
              }));
        });
      }
      rowArrows(container);
    });
  }

  function fillGrid(container, channelIds, opts) {
    opts = opts || {};
    if (typeof channelIds === "string") channelIds = [channelIds];
    Promise.all(channelIds.map(function (id) {
      return channelItems(id).catch(function () { return []; });
    })).then(function (lists) {
      var items = [];
      lists.forEach(function (l) { items = items.concat(l); });
      items.sort(function (a, b) { return (b.publishedAt || "").localeCompare(a.publishedAt || ""); });
      items = items.slice(0, opts.limit || 6);
      if (opts.dedupe !== false) items = claimUnseen(items);
      container.textContent = "";
      items.forEach(function (item, i) {
        var card = el("div", "feat-card");
        card.style.cursor = "pointer";
        var wrap = el("div", "imgwrap");
        wrap.appendChild(thumbNode(item));
        card.appendChild(wrap);
        var body = el("div", "fbody");
        body.appendChild(el("div", "kicker", item.channelName));
        body.appendChild(el("h3", null, item.title));
        body.appendChild(el("p", null, (item.duration != null ? fmtDuration(item.duration) + " · " : "") + "From the network feed"));
        card.appendChild(body);
        card.addEventListener("click", function () { openPlayer(items, i); });
        container.appendChild(card);
      });
    });
  }

  /* ══ Home page from /v1/home (the app's composed screen) ═ */

  function athChip(a) {
    var chip = el("div", "ath-chip");
    var av = el("div", "ath-avatar");
    if (a.avatarUrl) {
      var img = document.createElement("img");
      img.src = a.avatarUrl; img.alt = "";
      av.appendChild(img);
    } else {
      av.textContent = initials(a.name);
    }
    chip.appendChild(av);
    chip.appendChild(el("div", "ath-name", a.name));
    chip.appendChild(el("div", "ath-sub", a.school + " · " + a.sport));
    if (a.ambassadorRank) chip.appendChild(el("div", "ath-rank", "Ambassador #" + a.ambassadorRank));
    return chip;
  }

  function renderHomeRails(mount) {
    api("/v1/home").then(function (home) {
      mount.textContent = "";
      var rails = (home.rails || []).filter(function (r) { return r.items && r.items.length; });
      rails.forEach(function (r) {
        if (r.kind === "content") r.items = claimUnseen(r.items);
      });
      rails = rails.filter(function (r) { return r.items.length; });
      // Content rails first; athlete rails (Featured Ambassadors) held for the
      // bottom of the page while that module is reworked.
      var contentRails = rails.filter(function (r) { return r.kind !== "athletes"; });
      var athleteRails = rails.filter(function (r) { return r.kind === "athletes"; });

      function addRail(rail) {
        var section = el("section", "section");
        var head = el("div", "section-head");
        head.appendChild(el("h2", "section-title", rail.title));
        var link = el("a", "section-link", "See All ›");
        link.href = rail.kind === "athletes" ? "/about/" : "/channels/";
        head.appendChild(link);
        section.appendChild(head);
        var row = el("div", "row-scroll");
        if (rail.kind === "athletes") {
          rail.items.forEach(function (a) { row.appendChild(athChip(a)); });
        } else {
          rail.items.forEach(function (item, i) {
            row.appendChild(contentCard(item, rail.items, i, {
              badge: i === 0 ? "New" : null,
            }));
          });
        }
        var holder = el("div");
        holder.appendChild(row);
        section.appendChild(holder);
        mount.appendChild(section);
        rowArrows(row);
      }

      contentRails.forEach(addRail);

      // Campus row, same as the app's watch tab reach
      var campus = el("section", "section");
      var chead = el("div", "section-head");
      chead.appendChild(el("h2", "section-title", "Fresh From Campus"));
      var clink = el("a", "section-link", "See All ›");
      clink.href = "/channels/";
      chead.appendChild(clink);
      campus.appendChild(chead);
      var crow = el("div", "row-scroll");
      var choldr = el("div");
      choldr.appendChild(crow);
      campus.appendChild(choldr);
      mount.appendChild(campus);
      fillRow(crow, ["ch-chapelhilltv", "ch-dorecitytv", "ch-starkvilletv", "ch-truebluetv", "ch-collegestationtv"], { limit: 12 });

      athleteRails.forEach(addRail);
    }).catch(function (err) {
      console.error("home rails failed", err);
    });
  }

  // Update hero carousel badges from live event state (recap/live/upcoming).
  function applyHeroState() {
    api("/v1/home").then(function (home) {
      var hero = home.hero || {};
      var pill = document.getElementById("hero-live-pill");
      if (!pill) return;
      if (hero.state === "live") {
        pill.textContent = "Live Now · " + hero.event.title;
        pill.classList.add("solid");
      } else if (hero.state === "upcoming") {
        pill.textContent = "Up Next · " + hero.event.title;
      } else if (hero.state === "recap") {
        pill.textContent = "Now Crowned · " + hero.event.title;
      }
    }).catch(function () {});
  }

  /* ══ Channels page from /v1/channels ═════════════════════ */

  // Official roster on the chan3 transparents.
  var CHANNEL_LOGOS = {
    "ch-trueblue": "/assets/img/chan3/trueblue.webp",
    "ch-truebluetv": "/assets/img/chan3/trueblue.webp",
    "ch-chapelhilltv": "/assets/img/chan3/chapelhill.webp",
    "ch-dorecitytv": "/assets/img/chan3/dorecity.webp",
    "ch-starkvilletv": "/assets/img/chan3/starkville.webp",
    "ch-collegestationtv": "/assets/img/chan3/collegestation.webp",
    "ch-brazostv": "/assets/img/chan3/brazos.webp",
    "ch-goldendometv": "/assets/img/chan3/goldendome.webp",
    "ch-goldsalemtv": "/assets/img/chan3/goldsalem2.webp",
    "ch-redpacktv": "/assets/img/chan3/redpack.webp",
    "ch-saltcitytv": "/assets/img/chan3/saltcity.webp",
    "ch-nilstar": "/assets/img/nilstar-logo.png",
    "ch-niltv": "/assets/img/niltv-logo.webp",
  };
  // keep in sync with scripts/build-pages.mjs CHANNEL_SLUGS
  // channel page slug = the IG account name (ch-truebluetv -> /channels/truebluetv/)
  var CHANNEL_SLUGS = {
    "ch-trueblue": "truebluetv", "ch-truebluetv": "truebluetv",
    "ch-niltv": "niltv", "ch-nilstar": "nilstar",
    "ch-dorecitytv": "dorecitytv", "ch-chapelhilltv": "chapelhilltv",
    "ch-starkvilletv": "starkvilletv", "ch-collegestationtv": "collegestationtv",
    "ch-brazostv": "brazostv", "ch-goldendometv": "goldendometv",
    "ch-goldsalemtv": "goldsalemtv", "ch-redpacktv": "redpacktv",
    "ch-saltcitytv": "saltcitytv",
  };
  // Channels hidden from the web entirely
  var HIDDEN_CHANNELS = { "ch-esports": true };
  function visibleChannels(list) {
    return (list || []).filter(function (c) { return !HIDDEN_CHANNELS[c.id]; });
  }
  function channelSlug(id) {
    return CHANNEL_SLUGS[id] || id.replace(/^ch-/, "");
  }
  // Roster channels not yet live, as [name, logo] pairs. Empty while every
  // roster channel is live in /v1/channels.
  var COMING_SOON = [];

  function renderChannels(mount) {
    // Merge the channel directory with channels the home rails still
    // reference - the directory has drifted before (dev re-seed) while
    // the content lived on.
    Promise.all([
      api("/v1/channels").catch(function () { return { channels: [] }; }),
      api("/v1/home").catch(function () { return { rails: [] }; }),
    ]).then(function (results) {
      var channels = visibleChannels(results[0].channels).slice();
      var known = {};
      channels.forEach(function (c) { known[c.id] = true; });
      (results[1].rails || []).forEach(function (rail) {
        if (rail.kind !== "content") return;
        (rail.items || []).forEach(function (item) {
          if (item.channelId && !known[item.channelId]) {
            known[item.channelId] = true;
            channels.push({ id: item.channelId, name: item.channelName, about: "" });
          }
        });
      });
      var res = { channels: channels };
      mount.textContent = "";
      (res.channels || []).forEach(function (ch) {
        var section = el("section", "section");
        var head = el("div", "section-head");
        var hwrap = el("div", "chan-head");
        var logo = CHANNEL_LOGOS[ch.id];
        if (logo) {
          var img = document.createElement("img");
          img.src = logo; img.alt = "";
          hwrap.appendChild(img);
        }
        hwrap.appendChild(el("h2", "section-title", ch.name));
        head.appendChild(hwrap);
        var chLink = el("a", "section-link", "View Channel ›");
        chLink.href = "/channels/" + channelSlug(ch.id) + "/";
        head.appendChild(chLink);
        section.appendChild(head);
        var holder = el("div");
        var row = el("div", "row-scroll");
        holder.appendChild(row);
        section.appendChild(holder);
        mount.appendChild(section);
        fillRow(row, ch.id, {
          kind: "chan",
          fallback: [{ name: ch.name, info: (ch.about || "Reels land here soon") }],
        });
      });

      var soon = el("section", "section");
      soon.style.paddingBottom = "50px";
      var shead = el("div", "section-head");
      var shwrap = el("div", "chan-head");
      shwrap.appendChild(el("h2", "section-title", "More Campus Channels"));
      shwrap.appendChild(el("span", "badge-soon", "Coming Soon"));
      shead.appendChild(shwrap);
      soon.appendChild(shead);
      var sholder = el("div");
      var srow = el("div", "row-scroll");
      COMING_SOON.forEach(function (c) {
        var t = el("div", "tile-logo");
        var img = document.createElement("img");
        img.src = c[1]; img.alt = c[0];
        t.appendChild(img);
        t.appendChild(el("span", "soon", "Coming Soon"));
        srow.appendChild(t);
      });
      sholder.appendChild(srow);
      soon.appendChild(sholder);
      mount.appendChild(soon);
      rowArrows(srow);
    }).catch(function (err) {
      console.error("channels failed", err);
      mount.appendChild(el("div", "search-hint", "Channels are unavailable right now."));
    });
  }

  /* ══ Competitions page from /v1/events ═══════════════════ */

  // The API's start/end is the VOTING window; cards should show the full
  // event arc (entries open through champion decided), so known events get
  // a display override here.
  var EVENT_SPAN_DISPLAY = {
    "evt-nilstar-s1": { start: "2026-07-07T12:00:00", end: "2026-07-22T12:00:00" },
  };

  function renderEvents(mount) {
    api("/v1/events").then(function (res) {
      var events = (res.events || []).filter(function (e) {
        return e.id !== "evt-nilrapstar-s1"; // retired event, never listed
      });
      if (!events.length) return;
      mount.textContent = "";
      events.forEach(function (ev) {
        var card = el("div", "event-card");
        var status = el("span", "pill" + (ev.status === "live" ? " solid" : ""),
          ev.status === "live" ? "Live Now" : ev.status === "upcoming" ? "Upcoming" : "Ended");
        card.appendChild(status);
        card.appendChild(el("h3", null, ev.title));
        var span = EVENT_SPAN_DISPLAY[ev.id] || { start: ev.startsAt, end: ev.endsAt };
        var when = new Date(span.start).toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
          " - " + new Date(span.end).toLocaleDateString("en-US", { month: "short", day: "numeric" });
        card.appendChild(el("div", "event-when", when + (ev.prize ? " · " + ev.prize : "")));
        if (ev.blurb) card.appendChild(el("p", "event-blurb", ev.blurb));
        mount.appendChild(card);
      });
    }).catch(function () {});
  }

  /* ══ Hero carousel ═══════════════════════════════════════ */

  function heroCarousel(root, intervalMs) {
    var slides = root.querySelectorAll(".hslide");
    var dotsWrap = root.querySelector(".hcar-dots");
    var idx = 0, timer = null, dots = [], paused = false;
    // WCAG 2.2.2: auto-moving content needs a pause mechanism, and readers who
    // ask for reduced motion get no auto-advance at all.
    var reduceMotion = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    slides.forEach(function (_, i) {
      var d = el("button");
      d.setAttribute("aria-label", "Go to slide " + (i + 1));
      d.addEventListener("click", function () { go(i, true); });
      dotsWrap.appendChild(d);
      dots.push(d);
    });
    function go(n, manual) {
      idx = (n + slides.length) % slides.length;
      slides.forEach(function (s, i) {
        s.classList.toggle("on", i === idx);
        // pause any video on the slide we just left
        if (i !== idx) {
          s.querySelectorAll("video").forEach(function (v) { v.pause(); });
        }
      });
      dots.forEach(function (d, i) {
        d.classList.toggle("on", i === idx);
        d.setAttribute("aria-current", i === idx ? "true" : "false");
      });
      if (manual) restart();
    }
    // Hover, focus and playback are tracked separately: moving the mouse away
    // must not restart the rotation while a video is still playing.
    var hovered = false, focused = false, videoPlaying = false;
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    function sync() {
      stop();
      if (reduceMotion || hovered || focused || videoPlaying || slides.length < 2) return;
      timer = setInterval(function () { go(idx + 1); }, intervalMs || 8000);
    }
    function restart() { sync(); }
    function anyPlaying() {
      var vids = root.querySelectorAll("video");
      for (var i = 0; i < vids.length; i++) if (!vids[i].paused) return true;
      return false;
    }

    root.addEventListener("mouseenter", function () { hovered = true; sync(); });
    root.addEventListener("mouseleave", function () { hovered = false; sync(); });
    root.addEventListener("focusin", function () { focused = true; sync(); });
    root.addEventListener("focusout", function () { focused = false; sync(); });
    // never rotate out from under a playing video ("play" doesn't bubble)
    root.addEventListener("play", function () { videoPlaying = true; sync(); }, true);
    ["pause", "ended"].forEach(function (evt) {
      root.addEventListener(evt, function () {
        videoPlaying = anyPlaying();
        sync();
      }, true);
    });

    var prev = root.querySelector(".hcar-nav.prev");
    var next = root.querySelector(".hcar-nav.next");
    if (prev) prev.addEventListener("click", function () { go(idx - 1, true); });
    if (next) next.addEventListener("click", function () { go(idx + 1, true); });

    // Swipe: the arrows are hidden on phones, so this is the only way through.
    var tx = null, ty = null;
    root.addEventListener("touchstart", function (e) {
      var t = e.changedTouches[0];
      tx = t.clientX; ty = t.clientY;
    }, { passive: true });
    root.addEventListener("touchend", function (e) {
      if (tx === null) return;
      var t = e.changedTouches[0];
      var dx = t.clientX - tx, dy = t.clientY - ty;
      // horizontal intent only, so vertical page scrolling still works
      if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        go(dx < 0 ? idx + 1 : idx - 1, true);
      }
      tx = ty = null;
    }, { passive: true });

    go(0);
    restart();
  }

  /* ══ Fullscreen vertical player (with likes) ═════════════ */

  var muted = true, observer = null, playerEl = null, playerScroll = null;
  var recRail = null, playerList = [], seenIds = {}, activeIdx = -1;
  var preOpenUrl = null, pushedState = false, playerOpener = null;

  // stroke-style speaker icons matching the site's icon set (no emoji)
  function muteIcon(isMuted) {
    return isMuted
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a9.5 9.5 0 0 1 0 14"/></svg>';
  }

  function ensurePlayer() {
    if (playerEl) return;
    playerEl = el("div", "player");
    playerEl.setAttribute("role", "dialog");
    var close = el("button", "player-close", "✕");
    close.setAttribute("aria-label", "Close player");
    close.addEventListener("click", closePlayer);
    var layout = el("div", "player-layout");
    playerScroll = el("div", "player-scroll");
    recRail = el("div", "player-rec");
    layout.appendChild(playerScroll);
    layout.appendChild(recRail);
    playerEl.appendChild(close);
    playerEl.appendChild(layout);
    playerEl.appendChild(el("div", "player-hint", "Scroll for next · Esc to close"));
    document.body.appendChild(playerEl);
    document.addEventListener("keydown", function (e) {
      if (!playerEl.classList.contains("open")) return;
      if (e.key === "ArrowDown") { e.preventDefault(); jumpTo(activeIdx + 1); }
      if (e.key === "ArrowUp") { e.preventDefault(); jumpTo(activeIdx - 1); }
    });
  }

  function jumpTo(idx) {
    if (idx < 0 || idx >= playerList.length) return;
    var node = playerScroll.children[idx];
    if (node) node.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Append an item to the live feed (dedup by id); used for the initial list
  // and for the API's related[] recommendations as they stream in.
  function pushItem(item) {
    if (!item || !item.id || seenIds[item.id]) return;
    seenIds[item.id] = true;
    var idx = playerList.length;
    playerList.push(item);
    var node = buildPlayerItem(item, idx);
    playerScroll.appendChild(node);
    if (observer) observer.observe(node);
  }

  // "Up Next" rail: everything after the active reel, then wrap around.
  function renderRec() {
    if (!recRail) return;
    recRail.textContent = "";
    recRail.appendChild(el("div", "rec-head", "Up Next"));
    var order = [];
    for (var i = activeIdx + 1; i < playerList.length; i++) order.push(i);
    for (var j = 0; j < activeIdx; j++) order.push(j);
    order.forEach(function (idx, pos) {
      var item = playerList[idx];
      var row = el("button", "rec-item" + (pos === 0 ? " up-first" : ""));
      var th = el("span", "rec-thumb");
      th.appendChild(thumbNode(item));
      row.appendChild(th);
      var txt = el("span", "rec-text");
      txt.appendChild(el("span", "rec-title", item.title));
      txt.appendChild(el("span", "rec-sub", item.channelName + (item.duration != null ? " · " + fmtDuration(item.duration) : "")));
      row.appendChild(txt);
      row.addEventListener("click", function () { jumpTo(idx); });
      recRail.appendChild(row);
    });
  }

  function onActive(idx) {
    activeIdx = idx;
    renderRec();
    // every reel is linkable: the address bar follows the active item
    if (pushedState && playerList[idx]) {
      try { history.replaceState({ niltvPlayer: 1 }, "", "/watch/" + encodeURIComponent(playerList[idx].id) + "/"); } catch (e) {}
    }
    getDetail(playerList[idx]).then(function (detail) {
      (detail.related || []).forEach(pushItem);
      if (activeIdx === idx) renderRec();
    }).catch(function () {});
  }

  // provider:"hls" does not guarantee .m3u8 (social-ingest rows are mp4) - 
  // sniff the URL, not the provider field.
  // Resolves once a playable source is attached (hls.js loads lazily).
  function attachSource(video, url, fallbackUrl) {
    if (video.dataset.attached) return Promise.resolve();
    video.dataset.attached = "1";
    var isHls = /\.m3u8($|\?)/.test(url);
    if (!isHls) { video.src = url; return Promise.resolve(); }
    // Safari plays HLS natively
    if (video.canPlayType("application/vnd.apple.mpegurl")) { video.src = url; return Promise.resolve(); }
    return loadHls().then(function () {
      if (!window.Hls.isSupported()) throw new Error("MSE unsupported");
      var h = new window.Hls();
      h.on(window.Hls.Events.ERROR, function (evt, data) {
        if (!data.fatal) return;
        console.error("hls fatal error:", data.type, data.details);
        h.destroy();
        video._hls = null;
        if (fallbackUrl) {
          video.src = fallbackUrl;
          video.play().catch(function () {});
        }
      });
      h.loadSource(url);
      h.attachMedia(video);
      video._hls = h;
    }).catch(function (e) {
      // hls.js blocked/unavailable: an .m3u8 in video.src silently does
      // nothing in Chrome, so use the mp4 fallback.
      console.warn("hls unavailable (" + e.message + "); falling back to mp4");
      video.src = fallbackUrl || url;
    });
  }

  function likeButton(item) {
    var btn = el("button", "player-like");
    function paint() {
      var liked = me && (me.likes || []).indexOf(item.id) >= 0;
      btn.innerHTML = liked ? "♥" : "♡";
      btn.classList.toggle("liked", !!liked);
    }
    paint();
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (!me) { openAuth(); return; }
      var liked = (me.likes || []).indexOf(item.id) >= 0;
      var method = liked ? "DELETE" : "POST";
      // optimistic - mirror the app's like toggle
      if (liked) me.likes = me.likes.filter(function (id) { return id !== item.id; });
      else me.likes = (me.likes || []).concat([item.id]);
      paint();
      api("/v1/me/likes/" + encodeURIComponent(item.id), { method: method, auth: true })
        .catch(function () { loadMe(); paint(); });
    });
    return btn;
  }

  function buildPlayerItem(item, idx) {
    var wrap = el("div", "player-item");
    wrap.dataset.idx = idx;
    var frame = el("div", "player-frame");
    var video = document.createElement("video");
    video.playsInline = true;
    video.muted = muted;
    video.loop = true;
    video.preload = "none";
    if (item.thumbUrl) video.poster = item.thumbUrl;
    video.addEventListener("click", function () {
      if (video.paused) video.play(); else video.pause();
    });
    frame.appendChild(video);

    var mute = el("button", "player-mute");
    mute.innerHTML = muteIcon(muted);
    mute.setAttribute("aria-label", muted ? "Unmute" : "Mute");
    mute.addEventListener("click", function (e) {
      e.stopPropagation();
      muted = !muted;
      playerScroll.querySelectorAll("video").forEach(function (v) { v.muted = muted; });
      playerScroll.querySelectorAll(".player-mute").forEach(function (b) {
        b.innerHTML = muteIcon(muted);
        b.setAttribute("aria-label", muted ? "Unmute" : "Mute");
      });
    });
    frame.appendChild(mute);
    frame.appendChild(likeButton(item));
    var share = el("button", "player-share");
    share.setAttribute("aria-label", "Share this reel");
    share.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="10.5" x2="15.4" y2="6.5"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/></svg>';
    share.addEventListener("click", function (e) {
      e.stopPropagation();
      var url = location.origin + "/watch/" + encodeURIComponent(item.id) + "/";
      if (navigator.share) {
        navigator.share({ title: item.title, url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () {
          share.classList.add("copied");
          setTimeout(function () { share.classList.remove("copied"); }, 1200);
        });
      }
    });
    frame.appendChild(share);
    frame.appendChild(el("div", "player-shade"));
    var meta = el("div", "player-meta");
    meta.appendChild(el("div", "player-net", item.channelName));
    meta.appendChild(el("div", "player-name", item.title));
    if (item.duration != null) meta.appendChild(el("div", "player-sub", fmtDuration(item.duration)));
    frame.appendChild(meta);
    wrap.appendChild(frame);
    return wrap;
  }

  function openPlayer(list, startIdx) {
    ensurePlayer();
    playerScroll.textContent = "";
    recRail.textContent = "";
    playerList = []; seenIds = {}; activeIdx = -1;
    list.forEach(pushItem);
    playerEl.classList.add("open");
    document.body.style.overflow = "hidden";
    // deep link: the overlay owns a real /watch/{id} URL while it is open
    playerOpener = document.activeElement;
    if (!pushedState) {
      preOpenUrl = location.pathname + location.search;
      var startItem = playerList[startIdx] || playerList[0];
      if (startItem) {
        try {
          history.pushState({ niltvPlayer: 1 }, "", "/watch/" + encodeURIComponent(startItem.id) + "/");
          pushedState = true;
        } catch (e) {}
      }
    }
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var video = entry.target.querySelector("video");
        if (!video) return;
        var idx = Number(entry.target.dataset.idx);
        if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
          if (idx !== activeIdx) onActive(idx);
          [idx - 1, idx + 1].forEach(function (n) {
            if (playerList[n]) getDetail(playerList[n]).catch(function () {});
          });
          getDetail(playerList[idx]).then(function (detail) {
            return attachSource(video, detail.playbackUrl).then(function () {
              video.muted = muted;
              video.play().catch(function () {});
            });
          }).catch(function (err) {
            console.error("playback unavailable for", playerList[idx].id, err);
          });
        } else {
          video.pause();
          if (entry.intersectionRatio === 0 && video.dataset.attached) video.currentTime = 0;
        }
      });
    }, { root: playerScroll, threshold: [0, 0.6] });
    playerScroll.querySelectorAll(".player-item").forEach(function (n) { observer.observe(n); });
    var target = playerScroll.querySelector('[data-idx="' + startIdx + '"]');
    if (target) target.scrollIntoView({ behavior: "instant", block: "start" });
  }

  function closePlayer(fromPopstate) {
    if (observer) { observer.disconnect(); observer = null; }
    playerScroll.querySelectorAll("video").forEach(function (v) {
      v.pause();
      if (v._hls) { v._hls.destroy(); v._hls = null; }
      v.removeAttribute("src");
      v.load();
    });
    playerScroll.textContent = "";
    recRail.textContent = "";
    playerList = []; seenIds = {}; activeIdx = -1;
    playerEl.classList.remove("open");
    document.body.style.overflow = "";
    if (pushedState) {
      pushedState = false;
      if (!fromPopstate) {
        try { history.replaceState(null, "", preOpenUrl || "/"); } catch (e) {}
      }
    }
    if (playerOpener && playerOpener.focus) { try { playerOpener.focus(); } catch (e) {} }
    playerOpener = null;
  }
  window.addEventListener("popstate", function () {
    if (playerEl && playerEl.classList.contains("open")) closePlayer(true);
  });

  /* Inline vertical video inside a feature card or hero panel.
     Fetches the reel's detail on first tap so the playbackUrl stays fresh.
     opts: { poster, kicker, title, duration } - a plain string is still
     accepted as the poster for older call sites. */
  function inlineVideo(mount, contentId, opts) {
    if (typeof opts === "string") opts = { poster: opts };
    opts = opts || {};
    var wrap = el("div", "fhv-wrap");
    var frame = el("div", "fhv-frame");
    var video = document.createElement("video");
    video.playsInline = true;
    video.loop = true;
    video.preload = "none";
    if (opts.poster) video.poster = opts.poster;
    frame.appendChild(video);
    var overlay = el("div", "fhv-play");
    overlay.appendChild(el("span", null, "▶"));
    frame.appendChild(overlay);
    // A click is intent to watch, so start with sound; fall back to muted only
    // if the browser refuses.
    // No mute control on inline videos - every click-to-play retries with
    // sound first, so a muted fallback self-corrects on the next tap.
    function startWithSound(url) {
      attachSource(video, url, opts.fallbackSrc).then(function () {
        video.muted = false;
        video.play().catch(function () {
          video.muted = true;
          video.play().catch(function () {});
        });
      });
    }
    frame.addEventListener("click", function () {
      if (!video.paused) { video.pause(); return; }
      // opts.src plays a file directly (e.g. the network sizzle reel on
      // VideoPress); otherwise resolve playbackUrl through the API.
      if (opts.src) { startWithSound(opts.src); return; }
      api("/v1/content/" + encodeURIComponent(contentId)).then(function (detail) {
        if (!video.poster && detail.thumbUrl) video.poster = detail.thumbUrl;
        startWithSound(detail.playbackUrl);
      }).catch(function (err) { console.error("inline video unavailable", err); });
    });
    video.addEventListener("play", function () { frame.classList.add("playing"); });
    video.addEventListener("pause", function () { frame.classList.remove("playing"); });
    wrap.appendChild(frame);
    mount.appendChild(wrap);
    // ambient blurred backdrop behind the portrait frame (fills the panel)
    if (opts.poster) mount.style.setProperty("--poster", "url('" + opts.poster + "')");
  }

  /* ══ Watch page (/watch/{id}) ════════════════════════════ */

  function renderWatch(contentId) {
    var mount = document.getElementById("watch-mount");
    if (!mount) return;
    api("/v1/content/" + encodeURIComponent(contentId)).then(function (detail) {
      document.title = detail.title + " - " + detail.channelName + " | NIL TV";
      mount.textContent = "";
      var layout = el("div", "watch-layout");

      var left = el("div", "watch-video");
      inlineVideo(left, contentId, { poster: detail.thumbUrl });
      layout.appendChild(left);

      var info = el("div", "watch-info");
      var chanLink = el("a", "watch-kicker", detail.channelName);
      chanLink.href = "/channels/" + channelSlug(detail.channelId) + "/";
      info.appendChild(chanLink);
      info.appendChild(el("h1", "watch-title", detail.title));
      var metaBits = [];
      if (detail.duration != null) metaBits.push(fmtDuration(detail.duration));
      if (detail.likes) metaBits.push(detail.likes + (detail.likes === 1 ? " like" : " likes"));
      if (metaBits.length) info.appendChild(el("div", "watch-meta", metaBits.join(" · ")));
      if (detail.creator) {
        var cr = el("div", "watch-creator");
        var av = el("span", "ath-avatar");
        if (detail.creator.avatarUrl) {
          var ci = document.createElement("img");
          ci.src = detail.creator.avatarUrl; ci.alt = "";
          av.appendChild(ci);
        } else {
          av.textContent = initials(detail.creator.name);
        }
        cr.appendChild(av);
        var ct = el("span", "watch-creator-text");
        ct.appendChild(el("span", "watch-creator-name", detail.creator.name));
        ct.appendChild(el("span", "watch-creator-sub", detail.creator.school + " · " + detail.creator.sport));
        cr.appendChild(ct);
        info.appendChild(cr);
      }
      if (detail.description) {
        info.appendChild(el("p", "watch-desc", detail.description));
      }
      var actions = el("div", "btn-row");
      var shareBtn = el("button", "btn btn-ghost", "Share");
      shareBtn.addEventListener("click", function () {
        var url = location.origin + "/watch/" + encodeURIComponent(contentId) + "/";
        if (navigator.share) navigator.share({ title: detail.title, url: url }).catch(function () {});
        else if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () {
          shareBtn.textContent = "Link Copied";
          setTimeout(function () { shareBtn.textContent = "Share"; }, 1400);
        });
      });
      actions.appendChild(shareBtn);
      info.appendChild(actions);
      layout.appendChild(info);
      mount.appendChild(layout);

      if (detail.related && detail.related.length) {
        var sec = el("section", "section");
        var head = el("div", "section-head");
        head.appendChild(el("h2", "section-title", "Up Next"));
        sec.appendChild(head);
        mount.appendChild(sec);
        var grid = el("div", "watch-grid");
        detail.related.forEach(function (it) { grid.appendChild(linkCard(it)); });
        mount.appendChild(grid);
      }
    }).catch(function () {
      mount.innerHTML = "";
      var state = el("div", "watch-missing");
      state.appendChild(el("h1", null, "Reel Unavailable"));
      state.appendChild(el("p", null, "This reel may have been removed or is not published yet."));
      var back = el("a", "btn btn-play", "Back to NIL TV");
      back.href = "/";
      state.appendChild(back);
      mount.appendChild(state);
    });
  }

  /* ══ Channel page (/channels/{slug}) ═════════════════════ */

  function renderChannelPage(channelId, name, logo, about) {
    var mount = document.getElementById("channel-mount");
    if (!mount) return;
    mount.textContent = "";
    var head = el("div", "chanpage-head");
    if (logo) {
      var img = document.createElement("img");
      img.src = logo; img.alt = name;
      head.appendChild(img);
    }
    var ht = el("div", "chanpage-text");
    ht.appendChild(el("h1", null, name));
    if (about) ht.appendChild(el("p", null, about));
    head.appendChild(ht);

    var follow = el("button", "follow-btn", "Follow");
    follow.style.display = "none";
    channelProfileId(channelId).then(function (pid) {
      if (!pid) return;
      follow.style.display = "";
      function paint() {
        var on = me && (me.follows || []).indexOf(pid) >= 0;
        follow.textContent = on ? "Following" : "Follow";
        follow.classList.toggle("following", !!on);
      }
      paint();
      onAuthed.push(paint);
      follow.addEventListener("click", function () {
        if (!me) { onAuthed.push(paint); openAuth(); return; }
        var on = (me.follows || []).indexOf(pid) >= 0;
        if (on) me.follows = me.follows.filter(function (id) { return id !== pid; });
        else me.follows = (me.follows || []).concat([pid]);
        paint();
        api("/v1/me/follows/" + encodeURIComponent(pid), { method: on ? "DELETE" : "PUT", auth: true })
          .catch(function () { loadMe().then(paint); });
      });
    });
    head.appendChild(follow);
    mount.appendChild(head);

    var grid = el("div", "watch-grid");
    mount.appendChild(grid);
    channelItems(channelId).then(function (items) {
      if (!items.length) {
        grid.appendChild(el("div", "search-hint", "Reels land here soon."));
        return;
      }
      items.forEach(function (it, i) {
        grid.appendChild(contentCard(it, items, i, {}));
      });
    }).catch(function () {
      grid.appendChild(el("div", "search-hint", "This channel is unavailable right now."));
    });
  }

  /* ══ Vote page (/vote/) ══════════════════════════════════ */

  var VOTE_ERRORS = {
    AGE_GATE: "You must be 18 or older to vote.",
    WINDOW_CLOSED: "Voting is closed for this event.",
    ALREADY_VOTED: "You already voted in this event.",
    INVALID_ENTRY: "That entry is no longer available.",
  };

  function renderVote() {
    var mount = document.getElementById("vote-mount");
    if (!mount) return;
    api("/v1/events").then(function (res) {
      var events = (res.events || []).filter(function (e) {
        return e.id !== "evt-nilrapstar-s1"; // retired event, never listed
      });
      var ev = events.filter(function (e) { return e.status === "live"; })[0] ||
               events.filter(function (e) { return e.status === "upcoming"; })[0] ||
               events[0];
      if (!ev) {
        mount.appendChild(el("div", "search-hint", "No events on the calendar yet."));
        return;
      }
      return api("/v1/events/" + encodeURIComponent(ev.id)).then(function (detail) {
        renderVoteEvent(mount, detail);
      });
    }).catch(function () {
      mount.appendChild(el("div", "search-hint", "Events are unavailable right now."));
    });
  }

  function renderVoteEvent(mount, detail) {
    var ev = detail.event;
    mount.textContent = "";
    var head = el("div", "vote-head");
    head.appendChild(el("span", "pill" + (ev.status === "live" ? " solid" : ""),
      ev.status === "live" ? "Voting Open Now" : ev.status === "upcoming" ? "Upcoming" : "Ended"));
    head.appendChild(el("h1", null, ev.title));
    var when = new Date(ev.startsAt).toLocaleDateString("en-US", { month: "long", day: "numeric" }) +
      " - " + new Date(ev.endsAt).toLocaleDateString("en-US", { month: "long", day: "numeric" });
    head.appendChild(el("div", "watch-meta", when + (ev.prize ? " · " + ev.prize + " grand prize" : "")));
    if (ev.blurb) head.appendChild(el("p", "sec-lede", ev.blurb));
    mount.appendChild(head);

    if (ev.status === "upcoming") {
      var up = el("div", "vote-upcoming");
      up.appendChild(el("p", "sec-lede", "Fan voting opens " +
        new Date(ev.startsAt).toLocaleDateString("en-US", { month: "long", day: "numeric" }) +
        ". Entries are being collected now."));
      if (ev.submitUrl) {
        var enter = el("a", "btn btn-play", "＋ Submit Your Audition");
        enter.href = ev.submitUrl;
        enter.target = "_blank";
        enter.rel = "noopener";
        up.appendChild(enter);
      }
      mount.appendChild(up);
      return;
    }

    if (ev.status === "ended" && detail.recap) {
      var recap = el("div", "vote-recap");
      recap.appendChild(el("h2", "section-title", "Final Leaderboard"));
      var byId = {};
      (detail.entries || []).forEach(function (en) { byId[en.id] = en; });
      detail.recap.leaderboard.forEach(function (row) {
        var en = byId[row.entryId] || {};
        var r = el("div", "vote-lb-row" + (row.entryId === detail.recap.championEntryId ? " champ" : ""));
        r.appendChild(el("span", "vote-lb-rank", "#" + row.rank));
        r.appendChild(el("span", "vote-lb-name", en.name || row.entryId));
        r.appendChild(el("span", "vote-lb-votes", row.votes.toLocaleString() + " votes"));
        recap.appendChild(r);
      });
      mount.appendChild(recap);
      return;
    }

    var entries = detail.entries || [];
    if (!entries.length) {
      mount.appendChild(el("div", "search-hint", "Entries are on the way."));
      return;
    }
    var grid = el("div", "vote-grid");
    entries.forEach(function (en) {
      grid.appendChild(voteEntryCard(ev, en, entries));
    });
    mount.appendChild(grid);
  }

  function voteEntryCard(ev, en, entries) {
    var card = el("div", "vote-card");
    var av = el("div", "ath-avatar");
    if (en.avatarUrl) {
      var img = document.createElement("img");
      img.src = en.avatarUrl; img.alt = "";
      av.appendChild(img);
    } else {
      av.textContent = initials(en.name);
    }
    card.appendChild(av);
    card.appendChild(el("h3", null, en.name));
    card.appendChild(el("div", "ath-sub", en.school + " · " + en.sport));
    if (en.bio) card.appendChild(el("p", "vote-bio", en.bio));
    card.appendChild(el("div", "vote-count", en.votes.toLocaleString() + " votes"));
    var row = el("div", "btn-row");
    if (en.auditionContentId) {
      var watch = el("button", "btn btn-ghost", "▶ Audition");
      watch.addEventListener("click", function () {
        openPlayer([{ id: en.auditionContentId, title: en.name + " - Audition", channelName: ev.title }], 0);
      });
      row.appendChild(watch);
    }
    var voteBtn = el("button", "btn btn-play", "Vote");
    function paintVoted() {
      if (me && me.votes && me.votes[ev.id]) {
        var mine = me.votes[ev.id] === en.id;
        voteBtn.textContent = mine ? "✓ Your Vote" : "Vote";
        voteBtn.disabled = true;
        if (mine) voteBtn.classList.add("voted");
      }
    }
    paintVoted();
    onAuthed.push(paintVoted);
    voteBtn.addEventListener("click", function () {
      var cast = function () {
        voteBtn.disabled = true;
        api("/v1/events/" + encodeURIComponent(ev.id) + "/vote",
            { method: "POST", auth: true, body: { entryId: en.id } })
          .then(function () {
            me.votes = me.votes || {};
            me.votes[ev.id] = en.id;
            en.votes++;
            card.querySelector(".vote-count").textContent = en.votes.toLocaleString() + " votes";
            voteBtn.textContent = "✓ Your Vote";
            voteBtn.classList.add("voted");
          })
          .catch(function (err) {
            voteBtn.disabled = false;
            var code = err.body && err.body.error;
            alertVote(card, VOTE_ERRORS[code] || "Vote failed. Try again.");
            if (code === "ALREADY_VOTED") loadMe();
          });
      };
      if (!me) { onAuthed.push(cast); openAuth(); return; }
      cast();
    });
    row.appendChild(voteBtn);
    card.appendChild(row);
    var msg = el("div", "auth-error");
    card.appendChild(msg);
    return card;
  }

  function alertVote(card, text) {
    var msg = card.querySelector(".auth-error");
    if (msg) msg.textContent = text;
  }

  return {
    init: init,
    renderWatch: renderWatch,
    renderChannelPage: renderChannelPage,
    renderVote: renderVote,
    fillRow: fillRow,
    fillGrid: fillGrid,
    renderHomeRails: renderHomeRails,
    renderChannels: renderChannels,
    renderEvents: renderEvents,
    applyHeroState: applyHeroState,
    heroCarousel: heroCarousel,
    openPlayer: openPlayer,
    initCinema: initCinema,
    openSearch: openSearch,
    openFollows: openFollows,
    inlineVideo: inlineVideo,
    auth: { getIdToken: auth.getIdToken, getSession: auth.getSession, signOut: auth.signOut },
    openAuth: openAuth,
    whenAuthed: whenAuthed,
    me: function () { return me; },
  };
})();
