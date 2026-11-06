# ADR-001: Where the search index comes from

**Status:** Proposed
**Date:** 2026-11-06
**Deciders:** NIL TV web team; the API owner for anything under Option C

## Context

The search overlay in `assets/js/app.js` builds its index in the browser.
When search opens, it calls `/v1/channels`, then fetches the first page
(48 clips) of every channel, all in parallel. Athletes and schools come from
`athletes/index.json`, which `build-athletes.py` publishes at deploy time.
[search-review.md](search-review.md) has the full baseline. These numbers are
from the fixtures captured on the date above:

| | |
|---|---|
| Catalog (sum of `clipCount`, 12 visible channels) | 801 videos |
| Indexed today (first page per channel) | 218 (27%) |
| Requests per search open | 13 API calls (+ the roster file when athlete pages ship) |
| Open → first results, Lighthouse mobile profile | ~1.0 s |
| Same, every API call a cold cache miss (~1.2 s each) | ~4.2 s |
| Main-thread cost per search, 4× CPU | ~20–40 ms |

The "cold" row is a worst case. API responses carry
`Cache-Control: public, max-age=300` and CloudFront serves repeats from its
edge cache. A cold call took 1.14 s, and the same call warm took 53–66 ms.
Visitors share that edge cache, so the typical open is closer to the ~1.0 s
row.

What the browser can't get from today's API:

- **Most of the catalog.** Reaching all 801 videos means following cursors:
  26 requests, including a chain of 8 that must run one after another for
  `ch-niltv`. With cold calls that chain alone is ~10 s.
- **Sport, and the athlete's own school, on videos.** Those only exist on
  `/v1/content/{id}` (detail), one request per video. School can come from
  the channel (already done). Sport can't, so the sport filter only narrows
  athletes.
- **Tags.** No endpoint returns any.

Two existing facts shape the options:

1. **Every deploy already walks the full catalog.** `scripts/build-pages.mjs`
   follows every cursor on every channel and fetches every video's detail
   to write the `/watch/{id}/` pages. That's exactly the data a complete
   search index needs, including `creator.sport` and `creator.school`.
2. **Prod deploys follow ingest.** `.github/workflows/deploy-prod.yml` is
   dispatched by the ingest Lambda right after new clips publish, with a
   3-hourly safety net. The site already accepts that a just-published clip
   can predate the last build: the `/watch/` fallback page exists for it.

## Decision

Recommended: **Option B. `build-pages.mjs` writes a compact search index
during the walk it already does, and the overlay loads that one file
instead of making 13 API calls.** It keeps the current in-browser approach
as a fallback when the file is missing, so local dev and branches without
built pages keep working.

Option C (a server-side search endpoint) is not needed yet. Revisit it at
the triggers listed under Consequences.

## Options considered

### Option A: Keep indexing in the browser (status quo)

Optionally extended to follow every cursor so the whole catalog is covered.

| Dimension | Assessment |
|---|---|
| Complexity | Low as is; Medium to page through everything |
| Cost | None beyond current API traffic, which grows ~2× with full paging |
| Scalability | Poor. Requests and the sequential cursor chain grow with the catalog |
| Team familiarity | High. It's what ships today |

**Pros:** no build or backend change; always as fresh as the API.

**Cons:** covers 27% of videos, or pays ~26 requests and an 8-deep
sequential chain to cover them all. Still no sport on videos without a
detail request per video. Every visitor's phone repeats the same walk.

### Option B: Deploy-time static index (recommended)

`build-pages.mjs` emits one compact JSON file (for example
`/search/index.json`), one record per video: id, title, channel, creator,
school, sport, duration, date and thumbnail path. The overlay fetches it
once from the same host as the page.

| Dimension | Assessment |
|---|---|
| Complexity | Low–Medium. One more output from an existing walk, plus a loader swap in `app.js` |
| Cost | No new infrastructure. A static file on the existing host |
| Scalability | Good to a few thousand videos (sizes below), then the file gets heavy for phones |
| Team familiarity | High. Same script and pipeline as the watch pages |

Estimated size, from a compact record built from the current fixtures
(~196 B raw, ~45 B gzipped per video):

| Videos | Raw | Gzipped |
|---|---|---|
| 801 (today) | ~153 KB | ~35 KB |
| 2,000 | ~382 KB | ~88 KB |
| 5,000 | ~956 KB | ~220 KB |

**Pros:**

- **Speed:** one request instead of 13, with no 5-minute API cache to
  miss, so it should be faster than today's warm path.
- **Coverage:** all 801 videos instead of 218.
- **Sport and school on videos:** from the detail data the build already
  fetches. Only about 20% of details carry a sport today (athlete-posted
  clips; channel-account clips have none), but that's the most any option
  can show without upstream data changes.
- **Less API load:** visitors' phones no longer each repeat the channel walk.

**Cons:**

- **Freshness:** results are as fresh as the last deploy. In practice
  that's minutes after ingest on prod, but dev deploys are manual.
- **Initial download:** the index downloads whole on first open (about
  35 KB today).
- **Size ceiling:** past a few thousand videos the file becomes a real cost
  on slow phones.
- **Prod sweep:** the file goes through `deploy-sweep.py`. Records must
  store paths, not dev hosts, and athlete data stays in the separately
  gated roster.

### Option C: Server-side search endpoint (`/v1/search`)

A new API route in the backend repo that takes a query and filters and
returns ranked results.

| Dimension | Assessment |
|---|---|
| Complexity | High. The content cursor decodes to a DynamoDB-style key (`PK`/`SK`/`GSI1PK`), so there's no text search to lean on; it needs a search service or a scan-and-rank Lambda |
| Cost | New infrastructure and per-query compute; ongoing ownership |
| Scalability | Best. The phone downloads only results, whatever the catalog size |
| Team familiarity | Lower. Lives outside this repo with a different owner |

**Pros:** no index download; works at any catalog size; always fresh; room
for typo tolerance, popularity ranking and personalization; one search
shared by web and the mobile app.

**Cons:**

- **A network round trip on every query.** On a cold or slow connection
  that's slower per keystroke than the in-memory matching measured here.
- **Delivery is outside this repo.** It needs backend work, infrastructure
  and an owner.
- **Ranking changes move to the backend.** The scoring and normalization
  built in this branch would need porting or replacing.

## Trade-off analysis

- **Coverage and sport.** Only B and C reach the whole catalog and sport on
  videos. B gets there by reusing a walk deploys already do; C needs new
  backend work.
- **Speed on phones.** B wins: one static file, then matching in memory.
  A is ~1 s warm and up to ~4 s cold. C trades the download for a round
  trip on every query.
- **Freshness.** A and C are live. B lags by one deploy, and prod deploys
  are dispatched by ingest, so the lag is small. The same lag already
  applies to `/watch/` pages and channel pages.
- **Scale.** B's limit is file size. At today's growth that is far off
  (801 videos is ~35 KB gzipped), and the trigger below makes it explicit
  instead of a surprise.

## Consequences

- **Easier:** complete results, sport on athlete clips, faster first
  results on phones, and less API traffic per visitor.
- **Harder:** search freshness now depends on deploys running. A stalled
  pipeline means stale search as well as stale watch pages. The index
  format becomes a contract between `build-pages.mjs` and `app.js`.
- **Revisit with Option C when any of these happen:** the gzipped index
  passes ~200 KB (around 5,000 videos); search needs data that changes
  faster than deploys (live counts, personalization); or the mobile app
  wants the same search.

## Action items

1. [ ] In `build-pages.mjs`, write the compact index during the existing
   walk: one record per published video, thumbnail as a path (no host),
   school from the channel or creator, sport from `creator.sport`.
2. [ ] Make sure the prod sweep and guard pass with the new file. It must
   contain no dev hosts and no `"/athletes/` strings.
3. [ ] In `app.js`, load the index file first, and fall back to the
   current per-channel API walk if it's missing (local dev, unbuilt
   branches). Give videos a `sportKey` so the sport filter covers them,
   and update the filter note.
4. [ ] Re-measure with `scripts/dev/bench-search.mjs` (`load` and
   `typing`) and record the before/after in [search-review.md](search-review.md).
5. [ ] Track index size per deploy (log it in the build output) against
   the ~200 KB gzipped trigger.
