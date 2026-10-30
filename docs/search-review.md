# Search overlay review

Baseline for the search improvements. Covers what the overlay in
`assets/js/app.js` (`buildSearchIndex`, `openSearch`, `runSearch`) indexes
today, how fast it is on a phone profile, and what the API gives us to build
on. Measured 2026-10-20 against the dev API.

## How it works today

1. First `openSearch()` call runs `buildSearchIndex()`, which fetches
   `/v1/channels`, then `/v1/content?channelId=<id>&limit=48` for every
   visible channel, all in parallel.
2. The resulting `{ channels, items }` promise is kept for the life of the
   page. It is never refreshed.
3. Every `input` event runs `runSearch(q)` (2+ characters): a substring match
   over every item, then the results list is cleared and rebuilt.

What a query is matched against:

| Result type | Fields matched                         |
|-------------|----------------------------------------|
| Channel     | `name`                                 |
| Video       | `title`, `channelName`, `creatorName`  |

Videos are capped at 24 results. There are no athlete, school or sport
results, no tags, no filters and no ranking (results come back in fetch order).

## Coverage

The index only holds the first page of each channel:

| | Clips |
|---|---|
| Total across 12 visible channels (`clipCount`) | 773 |
| Indexed (first 48 per channel) | 213 (28%) |
| `ch-niltv` | 48 of 362 |
| `ch-truebluetv` | 48 of 294 |

`/v1/content` returns a `cursor` for the next page, but search never follows it.

## What the API gives us

| Endpoint | Search-relevant fields |
|---|---|
| `/v1/channels` | `id`, `name`, `about`, `clipCount`, `school` (added after this review; set on 10 of 12 channels) |
| `/v1/content?channelId=` (list) | `title`, `channelName`, `creatorId`, `creatorName`, `creatorIsAmbassador`, `duration`, `publishedAt` |
| `/v1/content/{id}` (detail) | adds `description`, `creator.school`, `creator.sport` |
| `/v1/home` athletes rail | `id`, `name`, `school`, `sport` (8 featured ambassadors) |

Gaps that matter for the planned work:

- **No school or sport on list items.** Those fields only appear on detail,
  which costs one request per video. A video's school can now come from
  its channel's `school` instead, which search uses. Sport still has no
  cheap source.
- **No tags anywhere.** No endpoint returns a tags field. The closest thing
  is hashtags in titles (4 across the indexed clips), and title matching
  already finds those.
- **Athletes aren't linked to content.** The 213 indexed items come from 18
  distinct `creatorId`s. 7 of those are channel accounts, none are flagged
  ambassadors, and none match the athlete ids on the home rail.
- **The full roster isn't in the API.** `/athletes/` is generated at deploy
  time from private data (`build-athletes.py`). From the API, the browser
  can only reach the 8 athletes on the home rail, and those have no athlete
  pages (their detail requests 404). The build does publish the roster as
  `athletes/index.json` (slug, name, school, sport, class year, portrait),
  which search now uses for athlete and school results whenever the athlete
  pages ship.
- **No server-side search.** `/v1/search` returns 404, and
  `/v1/content?q=` returns 400.

## Speed on a phone

Measured in headless Edge 155 over the DevTools protocol, against
`scripts/dev/serve.py` with freshly captured fixtures (rerun these with
`scripts/dev/bench-search.mjs`, see [Measuring](#measuring)). 390×844 viewport,
cache disabled, 3 runs per profile. "Mobile" uses Lighthouse's mobile
defaults: 150 ms RTT, 1.6 Mbps down, 4× CPU slowdown. "Mobile + real API
latency" raises the RTT to 1200 ms, because each dev API request took
1.0–1.7 s from a desktop connection with curl, even for empty channels.

| Profile | Open → first results | Keystroke → rows painted (median / worst) |
|---|---|---|
| Unthrottled desktop | ~195 ms | 13 ms / 31 ms |
| Mobile | ~1.1 s | 27–72 ms / 172 ms |
| Mobile + real API latency | ~4.2 s | 31–45 ms / 84 ms |

Each open makes 13 API requests and downloads about 91 KB of uncompressed
JSON. The CDN gzips responses (one channel page went from 16.8 KB to 3.0 KB),
so bytes on the wire are small. The time goes to round trips:

- `/v1/channels` has to finish before any channel's content request can start.
- The local server uses HTTP/1.1, so the browser opens at most 6 connections
  and the 12 content requests ran in two waves. CloudFront serves HTTP/2,
  which should bring the third row closer to two round trips (roughly
  2.5–3 s). That is an estimate, not a measurement.

On a phone, keystrokes already take longer than one 16 ms frame with only
213 items. Indexing the full catalog plus more fields will make that worse,
unless matching gets cheaper and row rendering gets batched.

## Bugs found

1. **Fixed: duplicate results when typing before the index is ready.** Every
   keystroke clears the list right away but appends its results later, when
   the index promise resolves. If you type 3 characters while it is loading,
   up to 4 result sets get appended to the same list (3 keystrokes plus
   `openSearch`'s own). This reproduced on every throttled run: 104 rows
   shown, 26 unique. The same cause left stale rows under the "Type to
   search" hint when the query was deleted back below 2 characters during
   the load.
2. **Fixed: one failed `/v1/channels` request breaks search until reload.** The
   rejected promise is stored in `searchIndex` and reused forever.
   `runSearch` has no `.catch`, so the overlay stays blank with no message.
   (A failure on a single channel is handled: that channel falls back to `[]`.)
3. **No way to open search.** Both nav builders say "no search or star icons
   in the nav", and the only call to `NILTV.openSearch()` is in the legacy
   `scripts/builders/build-sections.py` athletes page. On the current pages,
   search can only be opened from the console.
4. **Every keystroke does full work.** There is no debounce, every field of
   every item is lowercased again per keystroke, and up to 24 rows (with
   `<img>` thumbnails) are built one by one in the live DOM. Lowercasing now
   happens once at index time. Debouncing and batched rendering were measured
   and turned out not to pay off (next section).

## Debouncing: measured, not adopted

Bug 4 suggested debouncing input and building result rows in a
`DocumentFragment`. With the index warm, typing `nil tv` on the mobile
profile (4× CPU, 7 runs each):

| Version | Typing speed | List rebuilds | Main-thread time for the word | Last key → results |
|---|---|---|---|---|
| No debounce (current) | 80 ms/key (fast) | 5 | ~107 ms | ~2 ms |
| | 200 ms/key (typical phone) | 5 | ~108 ms | ~2 ms |
| 150 ms debounce | 80 ms/key | 1 | ~61 ms | ~168 ms |
| | 200 ms/key | 5 | ~136 ms | ~168 ms |
| Debounce + fragment | 80 ms/key | 1 | ~58 ms | ~170 ms |
| | 200 ms/key | 5 | ~158 ms | ~164 ms |

At normal phone typing speed, each key arrives after the debounce window
has already passed. Nothing gets coalesced, and every result shows up
~165 ms later. Debouncing only helps fast typists, and even then it saves
about 45 ms of work across the whole word in exchange for that delay. The
fragment made no difference beyond run-to-run noise. A search costs about
20 ms of main-thread time at this catalog size, so neither change went in.
Re-measure once the index covers more fields or the full catalog, since
per-search cost grows with both.

Lowercasing fields once at index time (instead of per keystroke) did go
in, along with the fixes for bugs 1 and 2. The real phone cost is the
1–4 s index load, not typing.

## Measuring

`scripts/dev/bench-search.mjs` reproduces the numbers in this doc. It
launches its own headless Edge or Chrome against the local dev server,
with fixtures captured, and has no dependencies.

```
python scripts/dev/serve.py                                  # separate terminal
node scripts/dev/bench-search.mjs load [--profile mobile-api]
node scripts/dev/bench-search.mjs typing [--ms 80]
node scripts/dev/bench-search.mjs check
```

- `load`: cold open to first results, plus API requests and KB.
  `--profile` is `mobile` (default), `mobile-api` (1.2 s RTT) or `desktop`.
- `typing`: main-thread time, list rebuilds, and the delay from the last
  key to results, for typing `nil tv` at `--ms` per key (default 200).
- `check`: regression test for the fixes to bugs 1 and 2. It fails the
  index load, holds it open while typing, and exits 1 if any case fails.
  Against the code from before those fixes, all 5 cases fail.

On Node 20, run it as `node --experimental-websocket scripts/dev/bench-search.mjs …`.

## What this means for the rest of the work

- Ignoring stale results and recovering from failed loads (bugs 1 and 2)
  fit inside the current approach and are done. Debouncing and batched
  rendering were measured and left out (see above). Starting the index
  build earlier only makes sense once something on the page opens search
  (bug 3). Until then it would cost every visitor 13 requests.
- Channel, athlete and school results and a channel filter can use data
  the browser already has (athletes and schools come from the published
  roster, `athletes/index.json`).
- Sport and school filters across *videos*, tags, and full-catalog coverage
  cannot be done well in the browser with today's API. They need either
  school/sport/tags on list items plus a way to fetch the whole catalog
  cheaply, or a server-side search endpoint. That is the input to the
  "browser index vs API" decision, which gets its own write-up.
- Bug 3 (no entry point) is a product call: add a nav icon, or leave search
  reachable only from in-page links.
