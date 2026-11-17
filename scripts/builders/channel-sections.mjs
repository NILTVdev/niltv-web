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
//   filter   { maxDays, minSeconds, maxSeconds, sport, school } - all
//            optional. sport and school match the video creator's, ignoring
//            case and "&" vs "and"; give one name or a list of names.
//   sort     a key of SORTS
//   limit    most videos to show (optional)
//   newTag   { days } - tag the first video "New Episode" when it is at most
//            this many days old (optional)
//   groupBy  "sport" or "school" (optional): one shelf per sport or school
//            instead of one shelf. "{group}" in the title becomes the name.
//            Groups with fewer than minPerGroup videos (default 8) are left
//            out, and the biggest group comes first. Videos whose creator has
//            no sport or school are not in any group.
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
export const GROUPS = ["sport", "school"];

export const daysOld = (d, now) => (now - time(d)) / DAY;

// The creator's sport or school. The list payload has no creator; the
// detail payload build-pages.mjs merges in does.
export const groupOf = (d, key) => String((d.creator && d.creator[key]) || "").trim();
// "Track & Field" and "track and field" are the same sport.
export const sameName = (s) => s.toLowerCase().replace(/&/g, " and ").replace(/\s+/g, " ").trim();
const names = (v) => (Array.isArray(v) ? v : [v]).map(sameName);

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
      if (s.groupBy != null && !GROUPS.includes(s.groupBy)) {
        throw new Error(`${at}: groupBy must be one of ${GROUPS.join(", ")}`);
      }
      for (const key of GROUPS) {
        const v = s.filter && s.filter[key];
        if (v != null && !(typeof v === "string" || (Array.isArray(v) && v.every((x) => typeof x === "string")))) {
          throw new Error(`${at}: filter.${key} must be a name or a list of names`);
        }
      }
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
    (f.maxSeconds == null || secs(d) <= f.maxSeconds) &&
    GROUPS.every((key) => f[key] == null || names(f[key]).includes(sameName(groupOf(d, key)))));
  out.sort(SORTS[section.sort]);
  return section.limit ? out.slice(0, section.limit) : out;
}

// A groupBy section becomes one plain section per sport or school. Each one
// keeps the parent's settings, with a filter for that group. Groups are
// counted among the videos that pass the parent's own filter, so "last 40
// days, by sport" only makes shelves for sports with recent videos. The name
// shown is the first spelling met in the list.
export function expandGroups(items, section, now) {
  if (!section.groupBy) return [section];
  const { groupBy: key, minPerGroup, ...rest } = section;
  const min = minPerGroup ?? 8;
  const groups = new Map(); // same name -> { name, count }
  for (const d of pickItems(items, { ...rest, limit: 0 }, now)) {
    const name = groupOf(d, key);
    if (!name) continue;
    if (!groups.has(sameName(name))) groups.set(sameName(name), { name, count: 0 });
    groups.get(sameName(name)).count++;
  }
  return [...groups.values()]
    .filter((g) => g.count >= min)
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .map((g) => ({ ...rest, group: g.name, filter: { ...(rest.filter || {}), [key]: g.name } }));
}

// HTML for every shelf that has videos. `r` is { reelCell, wideCard,
// shelfHtml, esc } from build-pages.mjs.
export function renderSections(items, sections, { channelName, now }, r) {
  const shelves = [];
  for (const s of sections.flatMap((s) => expandGroups(items, s, now))) {
    const picked = pickItems(items, s, now);
    if (!picked.length) continue;
    const cells = picked.map((d, i) => {
      if (s.layout === "wide") return r.wideCard(d, channelName);
      const tag = s.newTag && i === 0 && daysOld(d, now) <= s.newTag.days ? "New Episode" : null;
      return r.reelCell(d, channelName, tag);
    });
    const title = s.title.replace("{channel}", r.esc(channelName)).replace("{group}", r.esc(s.group || ""));
    shelves.push(r.shelfHtml(title, s.sub || "", cells, { gold: !!s.gold, wrapped: s.layout === "grid" }));
  }
  return shelves;
}
