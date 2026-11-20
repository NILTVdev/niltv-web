# Page builders

Generators for the cinema-look pages. Run them from the repo root.

- `cinema-template.html` - the chrome template every page is built from. Edit
  it here; `chrome-sync.py` pushes chrome changes to the committed pages.
- `build-sections.py` - rebuilds the vertical pages (competitions / channels /
  featured / nilstar / vote / athletes / partners / contact) into
  `concepts/cinema/` (ignored scratch) from the template plus live API rails.
- `channels-hub.json` - the order and logos of the channel rails on
  `/channels/`; names and schools come from the API, so a new campus channel
  gets a rail by itself once it has enough videos. Read by `channels_hub.py`.
  Tests: `python -m unittest scripts/builders/channels_hub_test.py`.
- `promote.py` - promotes the built pages over the site pages (backs the old
  ones up under `_legacy/`, ignored, never deployed).
- `build-athletes.py`, `network_brands.py`, `build-payments.py` - see
  DEVELOPING.md for the private data folder they read from.
- `build-hub.py` - builds `/hub/` (the Athlete Content Hub, dev-only) from the
  contact page's chrome. Run it after a chrome change.
- `channel-sections.json` - which shelves every channel page shows, what goes
  in each and how it is sorted. `../build-pages.mjs` reads it through
  `channel-sections.mjs`; to bring back or add a shelf, edit the JSON, not the
  code. Tests: `node --test scripts/builders/channel-sections.test.mjs`.
- `make-chmq-assets.py`, `make-poster-fills.py`, `make-dupe-registry.py` -
  asset helpers; `durations.json`, `poster-fills.json`, `poster-dupes.json`
  are their committed outputs.
- `refresh_rails.py` - run by `deploy.ps1` on every deploy (dev and prod).
  Rewrites only the cards inside the live rails of the committed pages:
  Featured "New This Week" and each channel rail on `/channels/`, from the
  API the deploy targets. Everything else on those pages stays as committed,
  so it never has to rerun `build-sections.py`. An unreadable API or a thin
  channel keeps the committed cards. A channel rail must already exist on
  `/channels/` to be refreshed; a new channel still needs a page rebuild.
  Tests: `python -m unittest scripts/builders/refresh_rails_test.py`.
- `pinned-lists.json` - the hand-picked, fixed-order video lists: homepage
  Trending and Sponsored Content, and the competitions page's Auditions. Read
  by `pinned_lists.py`; each list's `_notes` say how it is picked. Tests:
  `python -m unittest scripts/builders/pinned_lists_test.py`.

Rules:

1. These are the only copies that count. Commit output changes.
2. The channels hero in `build-sections.py` (`channels_head`) carries the
   network marquee (`.chmq`, 63 cards) as a self-contained section; keep it.
