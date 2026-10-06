# -*- coding: utf-8 -*-
"""Streaming tab prototype (esports): hero, CSS and body for build-sections.py.

Dev only. streaming/ is outside the prod page whitelist in deploy.ps1, and the
Streaming nav tab exists only on this page, so nothing here reaches prod.

Everything on the page is mock data except the players: the live embeds load
real Twitch / YouTube sources so they can be tested on desktop and phone. The
Twitch `parent` is taken from location.hostname at runtime, so the same page
works on localhost, the dev site and any later host without a rebuild.
Partner requirements: docs/streaming-prototype.md.
"""

HERO = '''<section class="hero hero-sm" id="hero" style="min-height:0">
  <div class="hero-slide vslide on" style="min-height:0">
    <div class="hero-copy" style="margin:120px 0 8px">
      <div class="hero-kicker">Esports <span class="st-proto">Prototype &middot; dev only</span></div>
      <h1 class="hero-title ht-sm">Streaming</h1>
      <p class="hero-dek">Live college esports from across the network, the week ahead, and replays of every broadcast.</p>
    </div>
  </div>
  <div class="hero-progress" id="heroDots">
    <button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button>
  </div>
</section>'''

CSS = '''<style>
/* ===== streaming tab (prototype) ===== */
.st-proto{font-family:'Inter',sans-serif;font-size:10px;font-weight:700;letter-spacing:.14em;
  color:var(--dim);border:1px solid var(--border);border-radius:4px;padding:3px 8px}
.st-wrap{padding:0 var(--gutter)}
.st-live{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(260px,1fr);gap:18px;align-items:start}
.st-player{position:relative;width:100%;aspect-ratio:16/9;min-height:220px;background:#000;border-radius:var(--radius);
  overflow:hidden;border:1px solid var(--border)}
.st-player iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.st-now{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:12px}
.st-now h3{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:22px;letter-spacing:.02em;margin-right:auto}
.st-chip{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;padding:3px 9px;border-radius:4px;background:var(--surface-hi);color:var(--dim);white-space:nowrap}
.st-chip.twitch{color:#c9b3ff}.st-chip.youtube{color:#ff8a8a}
.st-diag{margin-top:8px;font-size:12px;color:var(--dim);font-variant-numeric:tabular-nums}
.st-diag .warn{color:var(--gold-bright)}
.st-side{display:flex;flex-direction:column;gap:10px}
.st-src{display:flex;flex-direction:column;gap:6px;text-align:left;width:100%;padding:14px 16px;border-radius:12px;
  background:var(--surface);border:1px solid var(--border);color:var(--text);font:inherit;cursor:pointer;
  transition:border-color .18s,background .18s}
.st-src:hover{background:var(--surface-hi)}
.st-src[aria-pressed="true"]{border-color:var(--gold)}
.st-src b{font-size:15px;font-weight:700}
.st-src span{font-size:12px;color:var(--dim)}
.st-src .st-row{display:flex;gap:8px;align-items:center}
.st-test{margin-top:4px;padding:14px 16px;border-radius:12px;border:1px dashed var(--border)}
.st-test label{display:block;font-size:12px;font-weight:600;color:var(--dim);margin-bottom:8px}
.st-test .st-row{display:flex;gap:8px}
.st-test select,.st-test input{background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:8px;
  padding:9px 10px;font:inherit;font-size:14px;min-width:0}
.st-test input{flex:1}
.st-test button{background:var(--gold);color:#060608;border:0;border-radius:8px;padding:9px 14px;font-weight:700;cursor:pointer}
.st-test p{font-size:11px;color:var(--dim);margin-top:8px;line-height:1.5}
.st-day{margin-bottom:18px}
.st-day h3{font-family:'Barlow Condensed',sans-serif;font-weight:600;font-size:15px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--dim);margin-bottom:8px}
.st-match{display:grid;grid-template-columns:84px minmax(0,1fr) auto auto;gap:14px;align-items:center;
  padding:14px 16px;border-radius:12px;background:var(--surface);border:1px solid var(--border);margin-bottom:8px}
.st-time{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:20px;font-variant-numeric:tabular-nums}
.st-teams b{display:block;font-size:15px}
.st-teams span{font-size:12px;color:var(--dim)}
.st-remind{background:transparent;color:var(--text);border:1px solid var(--border);border-radius:999px;
  padding:7px 14px;font:inherit;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap}
.st-remind[aria-pressed="true"]{border-color:var(--gold);color:var(--gold)}
.st-rail{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(240px,300px);gap:14px;overflow-x:auto;
  padding:0 var(--gutter) 8px;scroll-padding-inline:var(--gutter);scroll-snap-type:x mandatory}
.st-vod{scroll-snap-align:start;text-align:left;background:none;border:0;color:var(--text);font:inherit;cursor:pointer;padding:0}
.st-thumb{position:relative;aspect-ratio:16/9;border-radius:12px;overflow:hidden;border:1px solid var(--border);
  display:grid;place-items:center;font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:34px;
  letter-spacing:.06em;color:rgba(255,255,255,.88)}
.st-thumb .st-dur{position:absolute;right:8px;bottom:8px;font-family:'Inter',sans-serif;font-size:11px;font-weight:700;
  background:rgba(0,0,0,.75);padding:2px 6px;border-radius:4px}
.st-vod b{display:block;margin-top:9px;font-size:14px;line-height:1.35}
.st-vod > span:not(.st-thumb){font-size:12px;color:var(--dim)}
.st-vod:hover .st-thumb{border-color:var(--gold)}
@media (max-width:900px){
  .st-live{grid-template-columns:minmax(0,1fr)}
}
@media (max-width:600px){
  .st-match{grid-template-columns:64px minmax(0,1fr);row-gap:10px}
  .st-match .st-chip{justify-self:start;grid-column:2}
  .st-match .st-remind{grid-column:2;justify-self:start}
  .st-time{font-size:18px}
  .st-rail{grid-auto-columns:78vw}
  .st-test .st-row{flex-wrap:wrap}
  .st-test input{flex-basis:100%}
}
</style>
'''

MAIN = '''<section class="shelf" id="live">
  <div class="shelf-head">
    <h2 class="shelf-title">Live Now</h2>
    <span class="shelf-sub">Test sources until a partner channel is wired in.</span>
  </div>
  <div class="st-wrap st-live">
    <div>
      <div class="st-player" id="stPlayer"></div>
      <div class="st-now">
        <h3 id="stTitle">Loading&hellip;</h3>
        <span class="live-pill" id="stLive">Live</span>
        <span class="st-chip" id="stPlat"></span>
      </div>
      <p class="st-diag" id="stDiag" aria-live="polite"></p>
    </div>
    <div class="st-side" id="stSide">
      <form class="st-test" id="stTest">
        <label for="stInput">Test any channel</label>
        <div class="st-row">
          <select id="stPlatIn" aria-label="Platform"><option value="twitch">Twitch</option><option value="youtube">YouTube</option></select>
          <input id="stInput" placeholder="Channel name, channel ID or URL" autocomplete="off">
          <button type="submit">Load</button>
        </div>
        <p>Twitch: a channel name or twitch.tv link (a /videos/ link plays a past broadcast). YouTube: the live video's URL or ID. A channel ID (UC&hellip;) tries YouTube's channel live embed, which failed in testing.</p>
      </form>
    </div>
  </div>
</section>

<section class="shelf" id="schedule">
  <div class="shelf-head">
    <h2 class="shelf-title">Schedule</h2>
    <span class="shelf-sub">Mock data. Times in your local time zone.</span>
  </div>
  <div class="st-wrap" id="stSched"></div>
</section>

<section class="shelf" id="past">
  <div class="shelf-head">
    <h2 class="shelf-title">Past Streams</h2>
    <span class="shelf-sub">Mock titles; replays play the test channel's uploads.</span>
  </div>
  <div class="st-rail" id="stPast"></div>
</section>

<script>
(function(){
  /* Test sources: an esports organisation channel on Twitch and a 24/7
     YouTube live stream (always live, so the YouTube Live path can be
     checked any time). YouTube is embedded by the live video's ID: the
     channel-based embed/live_stream URL showed "This video is unavailable"
     in testing. 24/7 streams are restarted under new IDs now and then; if
     this one ends, take the new ID from youtube.com/channel/<id>/live.
     Swap for partner channels when one signs on. */
  var LIVE = [
    {platform:'twitch', channel:'riotgames', title:'Twitch live test', sub:'twitch.tv/riotgames'},
    {platform:'youtube', video:'1-LpQekNa9g', title:'YouTube Live test', sub:'24/7 live stream, by video ID'}
  ];
  var REPLAY = {platform:'youtube', playlist:'UUSJ4gkVC6NrvII8umztf0Ow'};  // that channel's uploads
  var GAMES = {
    'Valorant':['#ff4655','#1b0d12'], 'Rocket League':['#1f8fff','#0b1424'],
    'League of Legends':['#c89b3c','#0a1820'], 'Overwatch 2':['#f99e1a','#1c140a']
  };
  var HOUR = 36e5, now = Date.now(), base = new Date(); base.setMinutes(0,0,0);
  function at(dayOffset, hour){ var d = new Date(base); d.setDate(d.getDate()+dayOffset); d.setHours(hour); return d; }
  /* Synthetic schools and events; start times are relative to today so the
     mockup always looks current. */
  var MATCHES = [
    {t:new Date(base.getTime()+2*HOUR), game:'Valorant', a:'Northgate Owls', b:'Lakeshore Comets', ev:'Fall Invitational, Week 4', p:'twitch'},
    {t:new Date(base.getTime()+5*HOUR), game:'Rocket League', a:'Ridgeview Foxes', b:'Harbor State Gulls', ev:'Conference Play', p:'youtube'},
    {t:at(1,18), game:'League of Legends', a:'Pinecrest Bears', b:'Northgate Owls', ev:'Fall Invitational, Week 4', p:'twitch'},
    {t:at(1,20), game:'Overwatch 2', a:'Summit Tech Rams', b:'Bayside Herons', ev:'Showcase Series', p:'youtube'},
    {t:at(2,19), game:'Valorant', a:'Lakeshore Comets', b:'Ridgeview Foxes', ev:'Fall Invitational, Week 4', p:'twitch'},
    {t:at(4,17), game:'Rocket League', a:'Bayside Herons', b:'Pinecrest Bears', ev:'Conference Play', p:'youtube'}
  ];
  var PAST = [
    {d:1, game:'Valorant', title:'Northgate Owls vs Summit Tech Rams', ev:'Fall Invitational, Week 3', dur:'2:41:08'},
    {d:2, game:'League of Legends', title:'Harbor State Gulls vs Pinecrest Bears', ev:'Fall Invitational, Week 3', dur:'3:12:44'},
    {d:3, game:'Rocket League', title:'Lakeshore Comets vs Bayside Herons', ev:'Conference Play', dur:'1:58:30'},
    {d:5, game:'Overwatch 2', title:'Ridgeview Foxes vs Northgate Owls', ev:'Showcase Series', dur:'2:20:15'},
    {d:6, game:'Valorant', title:'Grand Final: Summit Tech Rams vs Lakeshore Comets', ev:'Summer Cup', dur:'4:05:52'},
    {d:9, game:'Rocket League', title:'Pinecrest Bears vs Harbor State Gulls', ev:'Conference Play', dur:'1:47:03'}
  ];

  function enc(s){ return encodeURIComponent(s); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function embedUrl(s){
    if (s.platform === 'twitch'){
      // parent must name the embedding host or Twitch refuses to play
      var q = s.video ? 'video=' + enc(s.video) : 'channel=' + enc(s.channel);
      return 'https://player.twitch.tv/?' + q + '&parent=' + enc(location.hostname) + '&muted=true';
    }
    var yq = 'autoplay=1&mute=1&playsinline=1&rel=0';
    if (s.video) return 'https://www.youtube.com/embed/' + enc(s.video) + '?' + yq;
    if (s.playlist) return 'https://www.youtube.com/embed/videoseries?list=' + enc(s.playlist) + '&playsinline=1&rel=0';
    return 'https://www.youtube.com/embed/live_stream?channel=' + enc(s.channel) + '&' + yq;
  }

  var player = document.getElementById('stPlayer'), diag = document.getElementById('stDiag');
  var current = null;
  function diagnose(){
    if (!current) return;
    var w = Math.round(player.clientWidth), h = Math.round(player.clientHeight);
    var msg = 'Player ' + w + ' x ' + h + 'px on ' + esc(location.hostname) + '.';
    if (current.platform === 'twitch' && (w < 400 || h < 300))
      msg += ' <span class="warn">Below Twitch\\'s 400 x 300 minimum: autoplay is not guaranteed, tap play.</span>';
    if (current.platform === 'youtube' && (w < 200 || h < 200))
      msg += ' <span class="warn">Below YouTube\\'s 200 x 200 minimum.</span>';
    diag.innerHTML = msg;
  }
  function play(s, title, isLive){
    current = s;
    var f = document.createElement('iframe');
    f.src = embedUrl(s);
    f.title = title;
    f.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture';
    f.allowFullscreen = true;
    player.innerHTML = '';
    player.appendChild(f);
    document.getElementById('stTitle').textContent = title;
    document.getElementById('stLive').style.display = isLive ? '' : 'none';
    var chip = document.getElementById('stPlat');
    chip.className = 'st-chip ' + s.platform;
    chip.textContent = s.platform === 'twitch' ? 'Twitch' : 'YouTube';
    document.querySelectorAll('.st-src').forEach(function(b){ b.setAttribute('aria-pressed', b._src === s ? 'true' : 'false'); });
    diagnose();
  }
  window.addEventListener('resize', diagnose);

  var side = document.getElementById('stSide'), testForm = document.getElementById('stTest');
  LIVE.forEach(function(s){
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'st-src'; b._src = s;
    b.innerHTML = '<span class="st-row"><span class="live-pill">Live</span><span class="st-chip ' + s.platform + '">' +
      (s.platform === 'twitch' ? 'Twitch' : 'YouTube') + '</span></span><b>' + esc(s.title) + '</b><span>' + esc(s.sub) + '</span>';
    b.addEventListener('click', function(){ play(s, s.title, true); });
    side.insertBefore(b, testForm);
  });

  /* Accepts what a tester will paste: a bare name / ID or a full URL. */
  function parseInput(platform, v){
    v = v.trim();
    if (!v) return null;
    var m;
    if (platform === 'twitch'){
      if ((m = v.match(/twitch\\.tv\\/videos\\/(\\d+)/))) return {platform:'twitch', video:'v' + m[1]};
      if ((m = v.match(/twitch\\.tv\\/([A-Za-z0-9_]+)/))) return {platform:'twitch', channel:m[1]};
      return /^[A-Za-z0-9_]{2,25}$/.test(v) ? {platform:'twitch', channel:v} : null;
    }
    if ((m = v.match(/(UC[\\w-]{22})/))) return {platform:'youtube', channel:m[1]};
    if ((m = v.match(/(?:v=|youtu\\.be\\/|\\/live\\/|\\/embed\\/)([\\w-]{11})/))) return {platform:'youtube', video:m[1]};
    return /^[\\w-]{11}$/.test(v) ? {platform:'youtube', video:v} : null;
  }
  testForm.addEventListener('submit', function(e){
    e.preventDefault();
    var plat = document.getElementById('stPlatIn').value, input = document.getElementById('stInput');
    var s = parseInput(plat, input.value);
    if (!s){ diag.innerHTML = '<span class="warn">Could not read that as a ' + (plat === 'twitch' ? 'Twitch' : 'YouTube') + ' channel or video.</span>'; return; }
    play(s, 'Test: ' + (s.video || s.channel), !(s.platform === 'twitch' && s.video));
  });

  // ---- schedule ----
  var dayFmt = new Intl.DateTimeFormat(undefined, {weekday:'long', month:'short', day:'numeric'});
  var timeFmt = new Intl.DateTimeFormat(undefined, {hour:'numeric', minute:'2-digit'});
  function dayLabel(d){
    var a = new Date(d); a.setHours(0,0,0,0);
    var t = new Date(); t.setHours(0,0,0,0);
    var diff = Math.round((a - t) / 864e5);
    return diff === 0 ? 'Today' : diff === 1 ? 'Tomorrow' : dayFmt.format(d);
  }
  var sched = document.getElementById('stSched'), lastDay = null, group = null;
  MATCHES.filter(function(m){ return m.t.getTime() > now; }).sort(function(x, y){ return x.t - y.t; }).forEach(function(m){
    var label = dayLabel(m.t);
    if (label !== lastDay){
      group = document.createElement('div'); group.className = 'st-day';
      group.innerHTML = '<h3>' + esc(label) + '</h3>';
      sched.appendChild(group); lastDay = label;
    }
    var row = document.createElement('div'); row.className = 'st-match';
    row.innerHTML = '<span class="st-time">' + esc(timeFmt.format(m.t)) + '</span>' +
      '<span class="st-teams"><b>' + esc(m.a) + ' vs ' + esc(m.b) + '</b><span>' + esc(m.game) + ' &middot; ' + esc(m.ev) + '</span></span>' +
      '<span class="st-chip ' + m.p + '">' + (m.p === 'twitch' ? 'Twitch' : 'YouTube') + '</span>' +
      '<button type="button" class="st-remind" aria-pressed="false">Remind me</button>';
    var r = row.querySelector('.st-remind');
    r.addEventListener('click', function(){   // mock: no account or notification wired up yet
      var on = r.getAttribute('aria-pressed') !== 'true';
      r.setAttribute('aria-pressed', on ? 'true' : 'false');
      r.textContent = on ? 'Reminder set' : 'Remind me';
    });
    group.appendChild(row);
  });

  // ---- past streams ----
  var past = document.getElementById('stPast');
  PAST.forEach(function(v){
    var c = GAMES[v.game], b = document.createElement('button');
    b.type = 'button'; b.className = 'st-vod';
    var initials = v.game.split(' ').filter(function(w){ return /^[A-Z0-9]/.test(w); }).map(function(w){ return w[0]; }).join('');
    b.innerHTML = '<span class="st-thumb" style="background:linear-gradient(135deg,' + c[0] + ' 0%,' + c[1] + ' 78%)">' +
      esc(initials) + '<span class="st-dur">' + esc(v.dur) + '</span></span>' +
      '<b>' + esc(v.title) + '</b><span>' + esc(v.ev) + ' &middot; ' + (v.d === 1 ? 'Yesterday' : v.d + ' days ago') + '</span>';
    b.addEventListener('click', function(){
      play(REPLAY, 'Replay: ' + v.title, false);
      document.getElementById('live').scrollIntoView({behavior:'smooth'});
    });
    past.appendChild(b);
  });

  play(LIVE[0], LIVE[0].title, true);
})();
</script>'''
