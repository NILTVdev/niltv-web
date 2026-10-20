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
| `/v1/channels` | `id`, `name`, `about`, `clipCount` |
| `/v1/content?channelId=` (list) | `title`, `channelName`, `creatorId`, `creatorName`, `creatorIsAmbassador`, `duration`, `publishedAt` |
| `/v1/content/{id}` (detail) | adds `description`, `creator.school`, `creator.sport` |
| `/v1/home` athletes rail | `id`, `name`, `school`, `sport` (8 featured ambassadors) |

Gaps that matter for the planned work:

- **No school or sport on list items.** Those fields only appear on detail,
  which costs one request per video.
- **No tags anywhere.** No endpoint returns a tags field.
- **Athletes aren't linked to content.** The 213 indexed items come from 18
  distinct `creatorId`s. 7 of those are channel accounts, none are flagged
  ambassadors, and none match the athlete ids on the home rail.
- **The full roster isn't in the API.** `/athletes/` is generated at deploy
  time from private data (`build-athletes.py`). The browser can only reach
  the 8 athletes on the home rail.
- **No server-side search.** `/v1/search` returns 404, and
  `/v1/content?q=` returns 400.

## Speed on a phone

Measured in headless Edge 155 over the DevTools protocol, against
`scripts/dev/serve.py` with freshly captured fixtures. 390×844 viewport,
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

1. **Duplicate results when typing before the index is ready.** Every
   keystroke clears the list right away but appends its results later, when
   the index promise resolves. If you type 3 characters while it is loading,
   up to 4 result sets get appended to the same list (3 keystrokes plus
   `openSearch`'s own). This reproduced on every throttled run: 104 rows
   shown, 26 unique.
2. **One failed `/v1/channels` request breaks search until reload.** The
   rejected promise is stored in `searchIndex` and reused forever.
   `runSearch` has no `.catch`, so the overlay stays blank with no message.
   (A failure on a single channel is handled: that channel falls back to `[]`.)
3. **No way to open search.** Both nav builders say "no search or star icons
   in the nav", and the only call to `NILTV.openSearch()` is in the legacy
   `scripts/builders/build-sections.py` athletes page. On the current pages,
   search can only be opened from the console.
4. **Every keystroke does full work.** There is no debounce, every field of
   every item is lowercased again per keystroke, and up to 24 rows (with
   `<img>` thumbnails) are built one by one in the live DOM.

## What this means for the rest of the work

- Debouncing, ignoring stale results, batched rendering, per-item lowercase
  fields precomputed once, and starting the index build earlier all fit
  inside the current approach and fix bugs 1, 2 and 4.
- Channel and athlete results (home rail) and a channel filter can use data
  the browser already has.
- Sport and school filters across *videos*, tags, and full-catalog coverage
  cannot be done well in the browser with today's API. They need either
  school/sport/tags on list items plus a way to fetch the whole catalog
  cheaply, or a server-side search endpoint. That is the input to the
  "browser index vs API" decision, which gets its own write-up.
- Bug 3 (no entry point) is a product call: add a nav icon, or leave search
  reachable only from in-page links.
