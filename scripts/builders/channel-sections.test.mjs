// Run: node --test scripts/builders/channel-sections.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { checkConfig, pickItems, renderSections, sectionsFor } from "./channel-sections.mjs";

const NOW = Date.parse("2026-11-14T12:00:00Z");
const ago = (days) => new Date(NOW - days * 86400000).toISOString();
const vids = [
  { id: "a", publishedAt: ago(3), duration: 30 },
  { id: "b", publishedAt: ago(20), duration: 300 },
  { id: "c", publishedAt: ago(90), duration: 150 },
  { id: "d", duration: 10 }, // no date
];
const ids = (list) => list.map((d) => d.id);

// stand-ins for build-pages.mjs markup, so the output is easy to read
const r = {
  reelCell: (d, ch, tag) => `reel:${d.id}${tag ? `[${tag}]` : ""}`,
  wideCard: (d) => `wide:${d.id}`,
  shelfHtml: (title, sub, cells, o) => `${title}|${sub}|${o.gold}|${o.wrapped}|${cells.join(",")}`,
  esc: (s) => s.replace(/&/g, "&amp;"),
};

test("filters by age and length", () => {
  assert.deepEqual(ids(pickItems(vids, { sort: "newest", filter: { maxDays: 40 } }, NOW)), ["a", "b"]);
  assert.deepEqual(ids(pickItems(vids, { sort: "newest", filter: { minSeconds: 120 } }, NOW)), ["b", "c"]);
  assert.deepEqual(ids(pickItems(vids, { sort: "newest", filter: { maxSeconds: 30 } }, NOW)), ["a", "d"]);
});

test("sorts every way and cuts to the limit", () => {
  assert.deepEqual(ids(pickItems(vids, { sort: "newest" }, NOW)), ["a", "b", "c", "d"]);
  assert.deepEqual(ids(pickItems(vids, { sort: "oldest" }, NOW)), ["d", "c", "b", "a"]);
  assert.deepEqual(ids(pickItems(vids, { sort: "longest" }, NOW)), ["b", "c", "a", "d"]);
  assert.deepEqual(ids(pickItems(vids, { sort: "shortest", limit: 2 }, NOW)), ["d", "a"]);
});

test("does not reorder the input list", () => {
  const copy = vids.slice();
  pickItems(vids, { sort: "oldest" }, NOW);
  assert.deepEqual(vids, copy);
});

test("renders shelves, skips empty ones, tags a recent first video", () => {
  const sections = [
    { id: "new", title: "New", sub: "s", layout: "rail", gold: true, sort: "newest", filter: { maxDays: 40 }, newTag: { days: 14 } },
    { id: "none", title: "Empty", layout: "rail", sort: "newest", filter: { maxDays: 1 } },
    { id: "eps", title: "Episodes", layout: "wide", sort: "longest", filter: { minSeconds: 120 } },
    { id: "all", title: "Everything on {channel}", layout: "grid", sort: "newest" },
  ];
  assert.deepEqual(renderSections(vids, sections, { channelName: "A&B TV", now: NOW }, r), [
    "New|s|true|false|reel:a[New Episode],reel:b",
    "Episodes||false|false|wide:b,wide:c",
    "Everything on A&amp;B TV||false|true|reel:a,reel:b,reel:c,reel:d",
  ]);
});

test("no New Episode tag when the newest video is older than newTag.days", () => {
  const s = [{ id: "n", title: "N", layout: "rail", sort: "newest", newTag: { days: 2 } }];
  assert.equal(renderSections(vids, s, { channelName: "X", now: NOW }, r)[0], "N||false|false|reel:a,reel:b,reel:c,reel:d");
});

test("per-channel overrides and hidden sections", () => {
  const config = {
    sections: [{ id: "x", on: false, title: "X", layout: "grid", sort: "newest" },
               { id: "y", title: "Y", layout: "grid", sort: "newest" }],
    channels: { one: { phoneColumns: 3 }, two: { sections: [{ id: "z", title: "Z", layout: "rail", sort: "oldest" }] } },
  };
  assert.deepEqual(sectionsFor(config, "other"), { sections: [config.sections[1]], phoneColumns: null });
  assert.equal(sectionsFor(config, "one").phoneColumns, 3);
  assert.deepEqual(ids(sectionsFor(config, "two").sections), ["z"]);
});

test("a typo in the config fails loudly", () => {
  const ok = { id: "x", title: "X", layout: "grid", sort: "newest" };
  assert.throws(() => checkConfig({ sections: [{ ...ok, sort: "popular" }] }), /sort must be one of/);
  assert.throws(() => checkConfig({ sections: [{ ...ok, layout: "carousel" }] }), /layout must be one of/);
  assert.throws(() => checkConfig({ sections: [{ ...ok, id: "" }] }), /needs an id/);
  assert.throws(() => checkConfig({ sections: [ok], channels: { a: { phoneColumns: 2 } } }), /phoneColumns/);
  assert.doesNotThrow(() => checkConfig({ sections: [ok] }));
});

// videos with a creator, as build-pages.mjs merges in from the detail payload
const who = (id, sport, school, days = 1) => ({ id, publishedAt: ago(days), creator: { sport, school } });
const team = [
  who("b1", "Baseball", "Duke"), who("b2", "baseball", "Duke"), who("b3", "Baseball", "Vanderbilt", 60),
  who("t1", "Track & Field", "Duke"), who("t2", "Track and Field", "Vanderbilt"),
  who("g1", "Golf", "Duke"),
  who("x1", "", ""), { id: "x2", publishedAt: ago(2) }, // no sport, and no creator at all
];

test("filters by sport and school, ignoring case and & vs and", () => {
  assert.deepEqual(ids(pickItems(team, { sort: "newest", filter: { sport: "BASEBALL" } }, NOW)), ["b1", "b2", "b3"]);
  assert.deepEqual(ids(pickItems(team, { sort: "newest", filter: { sport: "track and field" } }, NOW)), ["t1", "t2"]);
  assert.deepEqual(ids(pickItems(team, { sort: "newest", filter: { sport: ["Golf", "Baseball"], school: "Duke" } }, NOW)),
    ["b1", "b2", "g1"]);
});

test("groupBy makes one shelf per sport, biggest first, skipping small and blank groups", () => {
  const s = [{ id: "by", title: "{group} on {channel}", layout: "rail", sort: "newest", groupBy: "sport", minPerGroup: 2 }];
  assert.deepEqual(renderSections(team, s, { channelName: "NIL TV", now: NOW }, r), [
    "Baseball on NIL TV||false|false|reel:b1,reel:b2,reel:b3",
    "Track &amp; Field on NIL TV||false|false|reel:t1,reel:t2", // escaped for HTML
  ]);
});

test("groupBy counts only videos that pass the section's own filter", () => {
  const s = [{ id: "by", title: "{group}", layout: "rail", sort: "newest", groupBy: "school", minPerGroup: 2, filter: { maxDays: 30 } }];
  // Vanderbilt has 2 videos, but one is 60 days old, so it is left out
  assert.deepEqual(renderSections(team, s, { channelName: "X", now: NOW }, r), ["Duke||false|false|reel:b1,reel:b2,reel:t1,reel:g1"]);
});

test("groupBy defaults to at least 8 videos per group", () => {
  const s = [{ id: "by", title: "{group}", layout: "rail", sort: "newest", groupBy: "sport" }];
  assert.deepEqual(renderSections(team, s, { channelName: "X", now: NOW }, r), []);
});

test("bad groupBy or sport filter fails loudly", () => {
  const ok = { id: "x", title: "X", layout: "grid", sort: "newest" };
  assert.throws(() => checkConfig({ sections: [{ ...ok, groupBy: "team" }] }), /groupBy must be one of/);
  assert.throws(() => checkConfig({ sections: [{ ...ok, filter: { sport: 5 } }] }), /filter.sport/);
  assert.doesNotThrow(() => checkConfig({ sections: [{ ...ok, groupBy: "school", filter: { sport: ["Golf"] } }] }));
});

test("the real channel-sections.json is valid", async () => {
  const file = new URL("./channel-sections.json", import.meta.url);
  const config = JSON.parse(await readFile(file, "utf8"));
  assert.doesNotThrow(() => checkConfig(config));
});
