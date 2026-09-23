# Page builders

Generators for the cinema-look pages. Run them from the repo root.

- `cinema-template.html` - the chrome template every page is built from. Edit
  it here; `chrome-sync.py` pushes chrome changes to the committed pages.
- `build-sections.py` - rebuilds the vertical pages (competitions / channels /
  featured / nilstar / vote / athletes / partners / contact) into
  `concepts/cinema/` (ignored scratch) from the template plus live API rails.
- `promote.py` - promotes the built pages over the site pages (backs the old
  ones up under `_legacy/`, ignored, never deployed).
- `build-athletes.py`, `network_brands.py`, `build-payments.py` - see
  DEVELOPING.md for the private data folder they read from.
- `make-chmq-assets.py`, `make-poster-fills.py`, `make-dupe-registry.py` -
  asset helpers; `durations.json`, `poster-fills.json`, `poster-dupes.json`
  are their committed outputs.

Rules:

1. These are the only copies that count. Commit output changes.
2. The channels hero in `build-sections.py` (`channels_head`) carries the
   network marquee (`.chmq`, 63 cards) as a self-contained section; keep it.
