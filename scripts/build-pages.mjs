/* NIL TV web - build-time page generator.
   Walks the live API and writes static, SEO-complete pages:
     watch/{id}/index.html      one per video (title/OG/VideoObject)
     channels/{slug}/index.html one per channel
     sitemap.xml, robots.txt
   Run by deploy.ps1 before zipping. Node 18+ (global fetch), no deps.

   CHROME: every generated page wears the cinema chrome. The nav, footer,
   CSS and scripts come from the cinema template (scripts/builders/cinema-template.html)
   at build time - the same head/tail split the section-page builder uses -
   so the header is one thing sitewide. The legacy stylesheet still loads
   (BEFORE the cinema styles, so cinema wins on shared names) because the
   watch/channel bodies are hydrated by app.js with its .watch-* / .chanpage-*
   layout classes.

   Extend this for future page types: each one is one more template here. */

import { mkdir, writeFile, readFile, readdir, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
// Environment: deploy.ps1 sets these per branch.
//   dev  -> dev content stack + dev Amplify origin (the defaults)
//   prod -> prod content stack + https://niltv.com (canonicals use it)
const ENV = process.env.NILTV_ENV || "dev";
const API = process.env.NILTV_API || "https://d1nm1d2txb83wa.cloudfront.net";
const ORIGIN = process.env.NILTV_ORIGIN || "https://dev.dkdfgvugisb3v.amplifyapp.com";

// Channel page slug = the IG account name (e.g. /channels/truebluetv/).
// Anything unmapped strips the ch- prefix (ch-brazostv -> brazostv).
const CHANNEL_SLUGS = {
  "ch-trueblue": "truebluetv",
  "ch-truebluetv": "truebluetv",
  "ch-niltv": "niltv",
  "ch-nilstar": "nilstar",
  "ch-dorecitytv": "dorecitytv",
  "ch-chapelhilltv": "chapelhilltv",
  "ch-starkvilletv": "starkvilletv",
  "ch-collegestationtv": "collegestationtv",
  "ch-brazostv": "brazostv",
  "ch-goldendometv": "goldendometv",
  "ch-goldsalemtv": "goldsalemtv",
  "ch-redpacktv": "redpacktv",
  "ch-saltcitytv": "saltcitytv",
};
// Channel hero pins: channel id -> content id. A pinned clip plays in
// the channel page billboard instead of the newest drop. Unpinned channels
// (and a pin whose clip has left the library) fall back to the newest drop.
const CHANNEL_FEATURED = {
  "ch-dorecitytv": "ig-18015379163731306", // Media day BTS
};
// clean official transparents (assets/img/chan3)
const CHANNEL_LOGOS = {
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

const slugFor = (id) => CHANNEL_SLUGS[id] || id.replace(/^ch-/, "");
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const truncate = (s, n) => {
  s = String(s ?? "").replace(/\s+/g, " ").trim();
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
};
const isoDuration = (sec) => (sec == null ? undefined : `PT${Math.floor(sec / 60)}M${Math.round(sec % 60)}S`);

async function api(p) {
  const r = await fetch(API + p);
  if (!r.ok) throw new Error(`${p} -> ${r.status}`);
  return r.json();
}

/* ---- cinema chrome, lifted from the template at build time ---- */
const TPL = await readFile(path.join(ROOT, "scripts", "builders", "cinema-template.html"), "utf8");
const HERO_MARK = "<!-- HERO BILLBOARD";
const FOOT_MARK = "<!-- FOOTER : credits roll -->";
if (TPL.indexOf(HERO_MARK) < 0 || TPL.indexOf(FOOT_MARK) < 0) {
  throw new Error("cinema template markers missing - cannot build chrome");
}
// concept-local links become root links, exactly like promote.py does
const cinHead = TPL.slice(0, TPL.indexOf(HERO_MARK)).replace(/\/concepts\/cinema\//g, "/");
const cinTail = TPL.slice(TPL.indexOf(FOOT_MARK)).replace(/\/concepts\/cinema\//g, "/");
const VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1.0">';
if (cinHead.indexOf(VIEWPORT) < 0) throw new Error("cinema template viewport meta missing");

/* Wrap a page body in the cinema chrome with its own SEO head. */
function shell({ title, desc, canonical, image, extra = "", active = "", body, script, legacyCss = true }) {
  const seo = `${VIEWPORT}
<meta name="description" content="${esc(desc)}">
<link rel="canonical" href="${esc(canonical)}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:type" content="video.other">
<meta property="og:url" content="${esc(canonical)}">
<meta property="og:image" content="${esc(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(title)}">
<meta name="twitter:image" content="${esc(image)}">
<meta name="theme-color" content="#060608">
<link rel="preconnect" href="${API}">
${extra}${legacyCss ? '\n<link rel="stylesheet" href="/assets/css/style.css">' : ""}`;
  let head = cinHead
    .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(VIEWPORT, seo);
  if (active) {
    head = head.replace(`<a href="/${active}/">`, `<a href="/${active}/" class="active">`);
  }
  const tail = cinTail.replace("</body>", `<script>\n${script}\n</script>\n</body>`);
  const skip = '<a class="skip-link" href="#main">Skip to content</a>\n<span id="main"></span>\n';
  return head + skip + body + "\n" + tail;
}

function watchPage(detail) {
  const url = `${ORIGIN}/watch/${detail.id}/`;
  const desc = truncate(detail.description || detail.title, 160);
  const ld = {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: detail.title,
    description: desc,
    thumbnailUrl: detail.thumbUrl,
    uploadDate: detail.publishedAt,
    duration: isoDuration(detail.duration),
    contentUrl: detail.playbackUrl,
    url,
  };
  Object.keys(ld).forEach((k) => ld[k] === undefined && delete ld[k]);
  return shell({
    title: `${detail.title} - ${detail.channelName} | NIL TV`,
    desc,
    canonical: url,
    image: detail.thumbUrl || `${ORIGIN}/assets/img/og-card.png`,
    extra: `<meta property="og:video" content="${esc(detail.playbackUrl)}">
<meta property="og:video:type" content="video/mp4">
<script type="application/ld+json">${JSON.stringify(ld)}</script>`,
    body: `<main class="watch-page" id="watch-mount">
  <noscript><p style="padding:120px 24px;">Watch ${esc(detail.title)} on NIL TV - ${esc(detail.channelName)}.</p></noscript>
</main>`,
    script: `NILTV.renderWatch(${JSON.stringify(detail.id)});`,
  });
}

// School per channel comes from the brand-account registry's `campus` field.
const CHANNEL_SCHOOLS = {
  "ch-trueblue": "Duke", "ch-truebluetv": "Duke", "ch-dorecitytv": "Vanderbilt",
  "ch-chapelhilltv": "North Carolina", "ch-starkvilletv": "Mississippi State",
  "ch-collegestationtv": "Texas A&M", "ch-brazostv": "Baylor",
  "ch-goldendometv": "Notre Dame", "ch-redpacktv": "NC State",
  "ch-saltcitytv": "Syracuse", "ch-goldsalemtv": "Wake Forest",
};
// horizontal lockups for the hero title art
const CHANNEL_HLOGOS = {
  "ch-trueblue": "/assets/img/chanh/trueblue.webp", "ch-truebluetv": "/assets/img/chanh/trueblue.webp",
  "ch-dorecitytv": "/assets/img/chanh/dorecity.webp", "ch-chapelhilltv": "/assets/img/chanh/chapelhill.webp",
  "ch-starkvilletv": "/assets/img/chanh/starkville.webp", "ch-collegestationtv": "/assets/img/chanh/collegestation.webp",
  "ch-brazostv": "/assets/img/chanh/brazos.webp", "ch-goldendometv": "/assets/img/chanh/goldendome.webp",
  "ch-redpacktv": "/assets/img/chanh/redpack.webp", "ch-saltcitytv": "/assets/img/chanh/saltcity.webp",
  "ch-goldsalemtv": "/assets/img/chanh/goldsalem.webp",
  "ch-nilstar": "/assets/img/nilstar-logo-wide.webp",
};
const KICKERS = { "ch-niltv": "The Flagship Channel", "ch-nilstar": "NIL Star Events" };

const cleanTitle = (t) => {
  t = String(t ?? "").split("\n")[0];
  t = t.split(/\s+/).filter((w) => !w.startsWith("#") && !w.startsWith("@")).join(" ");
  t = esc(t).replace(/^[\s\-|]+|[\s\-|]+$/g, "");
  return t.length > 64 ? t.slice(0, 63).trimEnd() + "..." : (t || "Watch on NIL TV");
};
const fmtDur = (sec) => (sec == null ? null : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`);
const daysOld = (d) => (Date.now() - Date.parse(d.publishedAt || 0)) / 86400000;

// posters cropped from letterboxed originals (see builders/make-poster-fills.py)
let POSTER_FILLS = new Set();
try { POSTER_FILLS = new Set(JSON.parse(await readFile(new URL("./builders/poster-fills.json", import.meta.url), "utf8"))); } catch {}
const posterUrl = (id) => `${API}/video/${id}/poster${POSTER_FILLS.has(id) ? "-fill" : ""}.jpg`;

const reelCell = (d, chName, tag) => {
  let extra = tag ? `\n        <span class="tile-tag">${tag}</span>` : "";
  const dur = fmtDur(d.duration);
  if (dur) extra += `\n        <span class="dur">${dur}</span>`;
  return `    <div class="reel-cell">
      <a class="card card-reel" href="/watch/${d.id}/">
        <img src="${posterUrl(d.id)}" loading="lazy" decoding="async" alt="">${extra}
      </a>
      <p class="reel-caption">${cleanTitle(d.title)}</p>
    </div>`;
};
const wideCard = (d, chName) => `    <a class="card card-wide" href="/watch/${d.id}/">
      <img src="${posterUrl(d.id)}" loading="lazy" decoding="async" alt="">
      <span class="chan-tag">${esc(chName)}</span>
      <span class="art-title">${cleanTitle(d.title)}</span>
    </a>`;
const shelfHtml = (title, sub, cells, { gold = false, wrapped = false } = {}) => `<section class="shelf">
  <div class="shelf-head">
    <h2 class="shelf-title${gold ? " gold" : ""}">${title}</h2>
    <span class="shelf-sub">${sub}</span>
  </div>
  <div class="rail${wrapped ? " wrapped" : ""}">
${cells.join("\n")}
  </div>
</section>`;

/* Channel page = Concept B head (billboard hero playing the newest drop)
   over Concept A shelves (New This Week / Episodes / full library grid). */
function channelPage(ch, slug, details) {
  const url = `${ORIGIN}/channels/${slug}/`;
  const school = CHANNEL_SCHOOLS[ch.id];
  const hlogo = CHANNEL_HLOGOS[ch.id];
  const kicker = KICKERS[ch.id] || (school ? `${esc(school)} &middot; Campus Channel` : "Campus Channel");
  const dekSchool = school === "North Carolina" ? "UNC" : school;
  const dek = school ? `${esc(dekSchool)}&rsquo;s Athletes. New drops all season.`
    : esc(ch.about || `${ch.name} on NIL TV.`);
  const titleArt = hlogo
    ? `<h1 class="hero-title logo-title"><img class="hero-logo" style="height:clamp(64px,7vw,104px)" src="${hlogo}" alt="${esc(ch.name)}"></h1>`
    : `<h1 class="hero-title ht-sm">${esc(ch.name)}</h1>`;
  const desc = truncate(school ? `${ch.name}: ${school} NIL Student Athletes on NIL TV. Watch the newest drops.` :
    (ch.about || `${ch.name} on NIL TV - the newest athlete reels.`), 160);

  let body;
  let heroId = null;
  if (!details.length) {
    body = `<section class="hero hero-sm" id="hero" style="min-height:0">
  <div class="hero-slide vslide on" style="min-height:0">
    <div class="hero-copy" style="margin:120px 0 8px">
      <a class="chan-back" href="/channels/">&larr; All Channels</a>
      ${titleArt}
      <p class="hero-dek">${dek}</p>
      <div class="hero-ctas">
        <a class="btn btn-gold" href="/channels/">Browse Channels</a>
      </div>
    </div>
  </div>
  <div class="hero-progress" id="heroDots"><button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button></div>
</section>

<main class="shelves">
<div class="cta-band" style="width:calc(100% - 2*var(--gutter));max-width:calc(1280px - 2*var(--gutter));margin:20px auto 0">
  <div class="tx"><h2>First Drops Coming Soon</h2><p>${esc(ch.name)} is live on the network. The first clips land here the moment they post.</p></div>
  <a class="btn btn-gold" href="#" onclick="NILTV.openFollows();return false;">Follow</a>
</div>
</main>`;
  } else {
    const pin = CHANNEL_FEATURED[ch.id];
    const pinned = pin ? details.find((d) => d.id === pin) : null;
    if (pin && !pinned) console.warn(`  ${ch.id}: pinned hero ${pin} not in library, using newest drop`);
    const featured = pinned || details[0];
    heroId = featured.id;
    const hero = `<section class="hero hero-sm hero-bleed" id="hero">
  <div class="hero-slide vslide bleed on">
    <div class="hglow" style="background-image:url('${API}/video/${featured.id}/poster.jpg')"></div>
    <video class="hero-echo" muted loop playsinline preload="none" data-src="${API}/video/${featured.id}/master.mp4"></video>
    <div class="hero-scrim"></div>
    <div class="hreel"><video class="hero-video" muted loop playsinline preload="none" poster="${API}/video/${featured.id}/poster.jpg" data-src="${API}/video/${featured.id}/master.mp4"></video></div>
    <div class="hero-copy">
      <a class="chan-back" href="/channels/">&larr; All Channels</a>
      ${titleArt}
      <p class="hero-dek">${dek}</p>
      <div class="hero-ctas">
        <a class="btn btn-gold theater-open" href="/watch/${featured.id}/" data-mp4="${API}/video/${featured.id}/master.mp4" data-poster="${API}/video/${featured.id}/poster.jpg" data-kicker="" data-title="${cleanTitle(featured.title)}"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> ${pinned ? "Watch Now" : "Watch Latest"}</a>
        <a class="btn btn-ghost" href="#" onclick="NILTV.openFollows();return false;">Follow</a>
      </div>
    </div>
  </div>
  <div class="hero-progress" id="heroDots"><button class="hero-dot on" data-i="0" aria-label="Slide 1"><span></span></button></div>
</section>`;
    const shelves = [];
    // New This Week + Episodes shelves are PARKED: the channel page
    // shows only the full grid for now. Restore by uncommenting:
    // const recent = details.filter((d) => daysOld(d) <= 40);
    // if (recent.length) {
    //   shelves.push(shelfHtml("New This Week", "The newest drops from campus.",
    //     recent.map((d, i) => reelCell(d, ch.name, i === 0 && daysOld(d) <= 14 ? "New Episode" : null)), { gold: true }));
    // }
    // const episodes = details.filter((d) => (d.duration || 0) >= 120);
    // if (episodes.length) {
    //   shelves.push(shelfHtml("Episodes", "The longform cuts.", episodes.map((d) => wideCard(d, ch.name))));
    // }
    shelves.push(shelfHtml(`Everything on ${esc(ch.name)}`, "", details.map((d) => reelCell(d, ch.name)), { wrapped: true }));
    body = hero + '\n\n<main class="shelves">\n' + shelves.join("\n\n") + "\n</main>";
    if (slug === "truebluetv") {
      // EXPERIMENT: 3-column content grid on phones, IG-profile
      // density - truebluetv only while we judge it. Roll out by moving the
      // grid3m class + style to every channel page; kill by deleting this.
      body = body.replace('class="rail wrapped"', 'class="rail wrapped grid3m"') + `
<style>
@media (max-width:900px){
  /* CSS grid, not flex: three flex cells at exactly a third plus gaps sum
     to 100% and subpixel rounding wrapped the third cell to the next row
     at some widths (2-up below ~650). Grid columns cannot wrap. */
  .grid3m{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 8px}
  .grid3m .reel-cell{width:auto;min-width:0}
  /* the mobile base sets .card-reel to 36vw - wider than a 3-up cell, which
     made cards overlap; the card must fill its cell exactly */
  .grid3m .card-reel{width:100%;border-radius:10px}
  .grid3m .reel-caption{font-size:10px;line-height:1.3;margin-top:5px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .grid3m .dur{font-size:9px;padding:1px 5px;top:6px;right:6px}
  .grid3m .tile-tag{font-size:8px;top:6px;left:6px}
}
</style>`;
    }
  }

  return shell({
    title: `${ch.name} - Channels | NIL TV`,
    desc,
    canonical: url,
    image: heroId ? `${API}/video/${heroId}/poster.jpg` : `${ORIGIN}/assets/img/og-card.png`,
    active: "channels",
    body,
    script: `/* static page - chrome only */`,
    // the legacy stylesheet's old .hero/.hero-copy rules mangle the cinema
    // billboard; channel pages are pure cinema markup and don't need it
    legacyCss: false,
  });
}

async function main() {
  const { channels } = await api("/v1/channels");
  // Harden against channel-directory drift: recover any channel that
  // /v1/home still references but the list is missing.
  try {
    const home = await api("/v1/home");
    const known = new Set(channels.map((c) => c.id));
    for (const rail of home.rails || []) {
      if (rail.kind !== "content") continue;
      for (const item of rail.items || []) {
        if (item.channelId && !known.has(item.channelId)) {
          known.add(item.channelId);
          channels.push({ id: item.channelId, name: item.channelName, about: "" });
          console.warn(`  recovered channel missing from /v1/channels: ${item.channelId}`);
        }
      }
    }
  } catch (e) { console.warn(`  home recovery skipped: ${e.message}`); }
  const urls = [
    "", "competitions/", "nilstar/season-1/", "channels/", "featured/", "about/",
    "contact/", "legal/privacy/", "legal/terms/", "legal/contest-notice/",
  ];
  // vote + athletes are dev-only; prod excludes the pages entirely, so they
  // never enter its sitemap
  if (ENV !== "prod") urls.push("vote/", "athletes/");
  let watchCount = 0;

  const HIDDEN = new Set(["ch-esports"]); // hidden from the web
  for (const ch of channels) {
    if (HIDDEN.has(ch.id)) continue;
    const slug = slugFor(ch.id);

    // full history: follow cursors until the channel is exhausted
    const items = [];
    let cursor = "";
    do {
      const page = await api(`/v1/content?channelId=${encodeURIComponent(ch.id)}&limit=48` +
        (cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""));
      items.push(...(page.items || []));
      cursor = page.cursor || "";
    } while (cursor);
    const details = [];
    for (const item of items || []) {
      // seed fixtures (c-*) carry placeholder test streams - never publish
      // them as real pages
      if (item.id.startsWith("c-")) continue;
      try {
        const detail = await api(`/v1/content/${encodeURIComponent(item.id)}`);
        // the detail payload has no publishedAt - carry the list item's fields
        // (and hand the MERGED object to watchPage so VideoObject gets its
        // uploadDate; the raw detail has none)
        const merged = { ...item, ...detail, publishedAt: item.publishedAt || detail.publishedAt };
        details.push(merged);
        await mkdir(path.join(ROOT, "watch", merged.id), { recursive: true });
        await writeFile(path.join(ROOT, "watch", merged.id, "index.html"), watchPage(merged));
        urls.push(`watch/${merged.id}/`);
        watchCount++;
      } catch (e) {
        console.warn(`  skip ${item.id}: ${e.message}`);
      }
    }

    // channel page is built AFTER the walk so it renders the real library
    await mkdir(path.join(ROOT, "channels", slug), { recursive: true });
    await writeFile(path.join(ROOT, "channels", slug, "index.html"), channelPage(ch, slug, details));
    urls.push(`channels/${slug}/`);
  }

  // /watch/ fallback for ids published after the last build (Amplify rule
  // /watch/<*> -> watch/index.html 404-200): same cinema chrome, id from the path
  await writeFile(path.join(ROOT, "watch", "index.html"), shell({
    title: "Watch | NIL TV",
    desc: "Watch athlete reels on NIL TV. Real Name. Real Game. Real TV.",
    canonical: `${ORIGIN}/watch/`,
    image: `${ORIGIN}/assets/img/og-card.png`,
    extra: `<meta name="robots" content="noindex">`,
    body: `<main class="watch-page" id="watch-mount"></main>`,
    script: `var m = location.pathname.match(/\\/watch\\/([^/]+)/);
if (m) NILTV.renderWatch(decodeURIComponent(m[1]));
else location.replace("/");`,
  }));

  // static athlete pages (built by scripts/builders/build-athletes.py into
  // athletes/{slug}/; this script never writes there, only indexes them).
  // Dev-only.
  try {
    if (ENV === "prod") throw new Error("athletes are dev-only for now");
    for (const entry of await readdir(path.join(ROOT, "athletes"))) {
      try {
        await stat(path.join(ROOT, "athletes", entry, "index.html"));
        urls.push(`athletes/${entry}/`);
      } catch { /* not a page dir (e.g. the index.html file itself) */ }
    }
  } catch (e) { console.log(`  athlete page scan skipped: ${e.message}`); }

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${ORIGIN}/${u}</loc></url>`).join("\n")}
</urlset>
`;
  await writeFile(path.join(ROOT, "sitemap.xml"), sitemap);
  // prod is the indexable site; the dev branch stays out of search entirely
  // so it can never shadow niltv.com as duplicate content
  await writeFile(path.join(ROOT, "robots.txt"), ENV === "prod"
    ? `User-agent: *\nAllow: /\nSitemap: ${ORIGIN}/sitemap.xml\n`
    : `User-agent: *\nDisallow: /\n`);

  // llms.txt: point AI systems at the franchise pages
  await writeFile(path.join(ROOT, "llms.txt"),
    `# NIL TV\n\n> NIL TV is a student athlete media network: fan-voted national competitions, original campus series, and campus channels run with athletic departments. Real Name. Real Game. Real TV.\n\n## Main pages\n\n- [Home](${ORIGIN}/): the network front page\n- [Competitions](${ORIGIN}/competitions/): national NIL competitions - NIL Singing Star Season 1 finalists and auditions\n- [NIL Star Season 1 recap](${ORIGIN}/nilstar/season-1/): the first season, Top 20, and champion Bella Calvanese\n- [Channels](${ORIGIN}/channels/): the campus channels of the NIL TV network\n- [Featured](${ORIGIN}/featured/): athlete-created content across the network\n- [About](${ORIGIN}/about/): mission, co-founders, roadmap, and how to work with NIL TV\n- [Contact](${ORIGIN}/contact/): general, brand, and athlete contact points\n`);

  // build.json: the deploy stamp. deploy.ps1 checks it on the live site after
  // every deploy and the Verify Deploy workflow checks it on a schedule, so a
  // prod that stops rebuilding (or ships the wrong commit) fails a check
  // instead of going unnoticed. NILTV_BUILD_COMMIT is set by deploy.ps1 (the
  // prod stage has no .git) and by CI; a plain local run records "unknown".
  await writeFile(path.join(ROOT, "build.json"), JSON.stringify({
    commit: process.env.NILTV_BUILD_COMMIT || "unknown",
    branch: process.env.NILTV_BUILD_BRANCH || null,
    env: ENV,
    api: API,
    builtAt: new Date().toISOString(),
    watchPages: watchCount,
    channelPages: channels.length,
  }, null, 2) + "\n");

  console.log(`generated (${ENV}): ${watchCount} watch pages, ${channels.length} channel pages, sitemap (${urls.length} urls), robots.txt, llms.txt, build.json`);
}

main().catch((e) => { console.error(e); process.exit(1); });
