// Channel page sections from data: channel-sections.json says which shelves a
// channel page shows, which videos go in each and in what order. This file
// turns that into HTML. build-pages.mjs passes in the card and shelf markup
// (reelCell, wideCard, shelfHtml), so this module holds only the choosing.
//
// A section:
//   id       name used in logs and per-channel overrides
//   on       false hides it without deleting it
//   title    shelf heading; "{channel}" becomes the channel name
//   sub      line under the heading ("" for none)
//   layout   "rail" (one sideways row), "grid" (wraps), "wide" (wide cards)
//   gold     gold heading
//   filter   { maxDays, minSeconds, maxSeconds } - all optional
//   sort     a key of SORTS
//   limit    most videos to show (optional)
//   newTag   { days } - tag the first video "New Episode" when it is at most
//            this many days old (optional)
//
// "channels": { "<slug>": { ... } } changes one channel: phoneColumns: 3
// gives its grid three columns on phones, and "sections" replaces the list.

import { readFile } from "node:fs/promises";

const DAY = 86400000;
const time = (d) => Date.parse(d.publishedAt || "") || 0;
const secs = (d) => d.duration || 0;

export const SORTS = {
  newest: (a, b) => time(b) - time(a),
  oldest: (a, b) => time(a) - time(b),
  longest: (a, b) => secs(b) - secs(a),
  shortest: (a, b) => secs(a) - secs(b),
};
export const LAYOUTS = ["rail", "grid", "wide"];

export const daysOld = (d, now) => (now - time(d)) / DAY;

// Check the file once so a typo fails the build instead of quietly
// dropping a shelf.
export function checkConfig(config) {
  const lists = [["sections", config.sections]];
  for (const [slug, o] of Object.entries(config.channels || {})) {
    if (o.sections) lists.push([`channels.${slug}.sections`, o.sections]);
    if (o.phoneColumns != null && o.phoneColumns !== 3) {
      throw new Error(`channel-sections.json channels.${slug}: phoneColumns can only be 3`);
    }
  }
  for (const [where, list] of lists) {
    if (!Array.isArray(list)) throw new Error(`channel-sections.json ${where}: must be a list`);
    for (const s of list) {
      const at = `channel-sections.json ${where} "${s.id || "?"}"`;
      if (!s.id || typeof s.title !== "string") throw new Error(`${at}: needs an id and a title`);
      if (!LAYOUTS.includes(s.layout)) throw new Error(`${at}: layout must be one of ${LAYOUTS.join(", ")}`);
      if (!(s.sort in SORTS)) throw new Error(`${at}: sort must be one of ${Object.keys(SORTS).join(", ")}`);
    }
  }
  return config;
}

export async function loadConfig(file) {
  return checkConfig(JSON.parse(await readFile(file, "utf8")));
}

// The shelves one channel shows, and its phone grid setting.
export function sectionsFor(config, slug) {
  const own = (config.channels || {})[slug] || {};
  return {
    sections: (own.sections || config.sections).filter((s) => s.on !== false),
    phoneColumns: own.phoneColumns || null,
  };
}

// The videos for one section: filter, then sort (stable, so ties keep the
// API's order), then cut to the limit.
export function pickItems(items, section, now) {
  const f = section.filter || {};
  const out = items.filter((d) =>
    (f.maxDays == null || daysOld(d, now) <= f.maxDays) &&
    (f.minSeconds == null || secs(d) >= f.minSeconds) &&
    (f.maxSeconds == null || secs(d) <= f.maxSeconds));
  out.sort(SORTS[section.sort]);
  return section.limit ? out.slice(0, section.limit) : out;
}

// HTML for every shelf that has videos. `r` is { reelCell, wideCard,
// shelfHtml, esc } from build-pages.mjs.
export function renderSections(items, sections, { channelName, now }, r) {
  const shelves = [];
  for (const s of sections) {
    const picked = pickItems(items, s, now);
    if (!picked.length) continue;
    const cells = picked.map((d, i) => {
      if (s.layout === "wide") return r.wideCard(d, channelName);
      const tag = s.newTag && i === 0 && daysOld(d, now) <= s.newTag.days ? "New Episode" : null;
      return r.reelCell(d, channelName, tag);
    });
    const title = s.title.replace("{channel}", r.esc(channelName));
    shelves.push(r.shelfHtml(title, s.sub || "", cells, { gold: !!s.gold, wrapped: s.layout === "grid" }));
  }
  return shelves;
}
