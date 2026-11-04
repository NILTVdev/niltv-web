/* Community Star: one answer to "which stage is it?" for /communitystar/, the
   homepage slide, the competitions tile and the rules page.

   The public feed (GET /api/community-star/public) decides. The server clock
   and the staff publish actions drive it, so nothing here needs a deploy on a
   date. When the feed is missing, the clock only carries the page through the
   application window. After that it holds on "closed": this file can never
   announce finalists, a top 5 or winners by itself. All times are UTC:
     opens       Mon Nov 2   9:00am ET
     closes      Mon Nov 23 11:59pm PT
     finalists   Wed Nov 25  6:00pm ET
     videos      Wed Dec 9  11:59pm PT  (Round 2 videos due)
     voteOpens   Fri Dec 11  9:00am ET
     voteCloses  Sun Dec 13 11:59pm PT
     top5        Mon Dec 14 11:59pm PT  (only changes the wording of a hold)
     winners     Fri Dec 18 11:59pm PT  (only changes the wording of a hold)

   A view is a stage plus its hold: hold = closed past Nov 25 with nothing
   published, top5hold = voting closed with no top 5 published yet. */
(function(){
  var T = {
    opens: Date.parse('2026-11-02T14:00:00Z'),
    closes: Date.parse('2026-11-24T08:00:00Z'),
    finalists: Date.parse('2026-11-25T23:00:00Z'),
    videos: Date.parse('2026-12-10T08:00:00Z'),
    voteOpens: Date.parse('2026-12-11T14:00:00Z'),
    voteCloses: Date.parse('2026-12-14T08:00:00Z'),
    top5: Date.parse('2026-12-15T08:00:00Z'),
    winners: Date.parse('2026-12-19T08:00:00Z')
  };
  var FEED_TIMES = {opens: 'opens', closes: 'closes', finalists: 'finalists', voteOpens: 'vote_opens', voteCloses: 'vote_closes'};
  var STAGES = ['coming', 'open', 'closed', 'finalists', 'voting', 'top5', 'winners'];
  /* ?stage= previews, off production only: the view each one shows and a
     moment inside it, so countdowns and dates read true */
  var PREVIEWS = {
    coming:         {view: 'coming',    at: '2026-10-20T16:00:00Z'},
    open:           {view: 'open',      at: '2026-11-10T16:00:00Z'},
    closed:         {view: 'closed',    at: '2026-11-24T16:00:00Z'},
    hold:           {view: 'hold',      at: '2026-11-26T16:00:00Z'},
    finalists:      {view: 'finalists', at: '2026-12-01T16:00:00Z'},
    voting:         {view: 'voting',    at: '2026-12-12T16:00:00Z'},
    votingempty:    {view: 'voting',    at: '2026-12-11T15:00:00Z'},
    votinghidden:   {view: 'voting',    at: '2026-12-12T16:00:00Z'},
    paused:         {view: 'voting',    at: '2026-12-12T16:00:00Z'},
    top5hold:       {view: 'top5hold',  at: '2026-12-14T10:00:00Z'},
    top5:           {view: 'top5',      at: '2026-12-15T16:00:00Z'},
    winners:        {view: 'winners',   at: '2026-12-19T16:00:00Z'},
    confirm:        {view: 'voting',    at: '2026-12-12T16:00:00Z'},
    confirmdone:    {view: 'voting',    at: '2026-12-12T16:00:00Z'},
    confirmexpired: {view: 'voting',    at: '2026-12-12T16:00:00Z'},
    confirmclosed:  {view: 'top5hold',  at: '2026-12-14T10:00:00Z'},
    confirminvalid: {view: 'voting',    at: '2026-12-12T16:00:00Z'}
  };

  /* An allowlist, so any host not named here (niltv.com, the prod Amplify
     domain) counts as production. The prod artifact guard forbids the dev app
     id in shipped files, hence the pattern. */
  function devHost(){
    var h = location.hostname;
    return location.protocol === 'file:' || h === 'localhost' || h === '127.0.0.1' ||
      /^dev\.[a-z0-9]+\.amplifyapp\.com$/.test(h);
  }
  function preview(){
    if (!devHost()) return null;
    var q = (location.search.match(/[?&]stage=([a-z0-9]+)/) || [])[1];
    return q && PREVIEWS.hasOwnProperty(q) ? {key: q, view: PREVIEWS[q].view, at: Date.parse(PREVIEWS[q].at)} : null;
  }

  function times(feed){
    var t = {}, k;
    for (k in T) t[k] = T[k];
    var f = (feed && feed.times) || {};
    for (k in FEED_TIMES) {
      var v = Date.parse(f[FEED_TIMES[k]]);
      if (!isNaN(v)) t[k] = v;
    }
    return t;
  }
  function view(feed, t){
    var at = times(feed), list = (feed && feed.finalists) || [];
    var s = feed ? feed.stage : t < at.opens ? 'coming' : t < at.closes ? 'open' : 'closed';
    /* a feed read a moment ago must not outlive the deadline ahead of it */
    if (s === 'coming' && t >= at.opens) s = 'open';
    if (s === 'open' && t >= at.closes) s = 'closed';
    if (s === 'voting' && t >= at.voteCloses) s = 'top5';
    if (s === 'coming' || s === 'open') return s;
    if (!list.length) s = 'closed';
    if (s === 'closed') return t >= at.finalists ? 'hold' : 'closed';
    function any(k){ return list.some(function(f){ return f[k]; }); }
    if (s === 'winners' && feed.winners_published && any('winner')) return 'winners';
    if (s === 'winners' || s === 'top5') return feed.top5_published && any('top5') ? 'top5' : 'top5hold';
    return s;
  }
  function base(v){ return {hold: 'closed', top5hold: 'top5'}[v] || v; }
  /* what comes next, without promising a date that has already passed */
  function announce(v, t, feed){
    var at = times(feed);
    if (v === 'closed' || v === 'hold') return 'Finalists announced ' + (t < at.finalists ? 'Nov 25' : 'soon');
    if (v === 'top5hold') return 'Top 5 announced ' + (t < at.top5 ? 'Dec 14' : 'soon');
    if (v === 'top5') return 'Winners announced ' + (t < at.winners ? 'Dec 18' : 'soon');
    return '';
  }

  function api(path){
    var a = (window.NILTV_CONFIG || {}).communityStarApi || '';
    return a ? a.replace(/\/applications\/?$/, path) : '';
  }
  function clean(d){
    if (!d || STAGES.indexOf(d.stage) < 0) return null;
    if (!Array.isArray(d.finalists)) d.finalists = [];
    if (!d.board || !Array.isArray(d.board.rows)) d.board = {state: 'hidden', rows: []};
    if (!d.voting) d.voting = {open: false, paused: false, turnstile: false};
    var st = Date.parse(d.server_time);
    d.offset = isNaN(st) ? 0 : st - Date.now();
    return d;
  }
  /* resolves with the feed, or null for anything else: API down, 404 while the
     backend is not released, bad JSON. It never rejects. */
  var pending = null;
  function load(){
    var url = api('/public');
    if (!url) return Promise.resolve(null);
    if (pending) return pending;
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = ctl ? setTimeout(function(){ ctl.abort(); }, 6000) : 0;
    function done(d){ clearTimeout(timer); pending = null; return d; }
    pending = fetch(url, ctl ? {signal: ctl.signal} : {})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(clean)
      .then(done, function(){ return done(null); });
    return pending;
  }
  /* config.js loads at the end of the page, so wait for it */
  function watch(cb, every){
    function pull(){ load().then(cb); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', pull);
    else pull();
    setInterval(function(){ if (!document.hidden) pull(); }, every);
  }

  window.NILTV_CS = {T: T, PREVIEWS: PREVIEWS, devHost: devHost, preview: preview, times: times, view: view, base: base,
    announce: announce, api: api, load: load, watch: watch};
})();
