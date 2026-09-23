# Developing NIL TV web

## Run it locally (no AWS account needed)

1. Install Python 3 (3.10+).
2. From the repo root:

   ```
   python scripts/dev/serve.py
   ```

3. Open http://localhost:8787 — the full site, with video streaming from the
   public dev CDN. The `/v1/*` API is answered from fixture snapshots in your
   private data folder (see below); without them the pages still serve, the
   API just answers empty.

That's it. No keys, no cloud, no build step: the pages are committed, and the
local server swaps in a same-origin config so the runtime JS talks to the
fixtures instead of the real API.

To get the API answering locally, snapshot it once (the dev API is
public-readable, no credentials needed):

   ```
   python scripts/dev/capture-fixtures.py
   ```

Local limitations (by design):
- `/watch/…` deep-link pages are generated at deploy time and aren't in the
  repo; the in-page theater player covers playback locally.
- Sign-in is stubbed (guest browsing is the full local experience).
- Newsletter signups return ok without writing anywhere.

Re-run it whenever you want a fresher snapshot.

## Private data folder

Anything that names a person or comes from a private sheet is kept **outside
the repo** and is never committed: athlete records and photos, the generated
athlete pages, the API fixture snapshots, the brand roster, the ambassador
roster. The builders look for it in this order:

1. the `NILTV_PRIVATE_DATA` environment variable, if set;
2. `../private-data/niltv-web` next to the repo checkout.

The folder mirrors the repo layout, so a path in it is the same path the file
used to have in the tree:

```
<private>/athletes/_data/athletes.json      athlete records (build-athletes.py)
<private>/athletes/_photos/<slug>/          source photos referenced by the records
<private>/athletes/<slug>/                  hand-built athlete pages (mirrored as-is)
<private>/fixtures/api/                     API snapshots (capture-fixtures.py writes here)
<private>/scripts/builders/network-brands.json   brand roster (partners slider)
<private>/scripts/builders/_amb_files.json       collab file index
<private>/concepts-data.json                concept page data
<private>/drafts/                           design drafts, retired pages, draft builders
<private>/niltv_campus_ambassadors_f26.csv  ambassador roster (concept athletes page)
```

Contributors without the folder can still build and run everything else: the
builders print a one-line note and skip the private part (no athlete pages,
an empty brand slider, an empty API). `athletes/index.html` is committed with
its directory block empty; `build-athletes.py` fills it at build time and the
generated `athletes/<slug>/` pages and `athletes/index.json` are gitignored.
`deploy.ps1` (dev) runs the athlete build with `--require`, so a dev deploy
fails clearly when the folder is missing.

## Making changes

- Page chrome (nav, hero, theater, CSS, runtime JS) lives in
  `scripts/builders/cinema-template.html` — the single source the template pages are
  regenerated from.
- Section/rail composition lives in `scripts/builders/build-sections.py`;
  `scripts/builders/promote.py` copies template pages to the root with SEO
  injected.
- After editing the chrome or builders, regenerate and re-check locally:

  ```
  python scripts/builders/build-sections.py
  python scripts/builders/promote.py
  python scripts/dev/serve.py
  ```

## The pipeline: local → dev → prod

| Stage | Branch | Who | How |
|---|---|---|---|
| local | your branch / PR | anyone | `scripts/dev/serve.py`, `deploy.ps1 -Check` |
| dev   | `main` | maintainers | `deploy.ps1` (dev content stack, basic-auth site) |
| prod  | `release` | sign-off only | the Deploy Prod workflow, on every push to `release` |

`main` is the working branch: merged work goes out to the dev site for review.
Nothing reaches production automatically from a merge. Prod builds **only**
from the `release` branch, which is fast-forwarded to `main` after sign-off:

```
git push origin main:release
```

That push starts the Deploy Prod workflow, which builds on a GitHub runner
and is live within minutes. `deploy-prod-from-release.ps1` still works from a
maintainer's machine as a fallback. The prod deploy guard refuses any tree
that isn't exactly `origin/release`, so an approved PR can land on `main` and
appear on dev without ever touching niltv.com until it is promoted.

### What runs where

- **On every PR**: Site CI runs `deploy.ps1 -Env prod -Check` and
  `-Env dev -Check` under PowerShell 7 on a Linux runner. That is the real
  deploy path (stage, generate against the live API, sweep, the 63-card
  marquee guard, the zero-dev-references guard) with the upload left out.
  Run the same two commands locally to reproduce a failure. The Checks
  workflow runs the secret scan and fails any PR into `release` that is not
  from `main`, `hotfix/*` or `revert-*`.
- **After merge**: every deploy checks that `build.json` on the live site
  carries the deployed commit and that the channels page has its 63 marquee
  cards. `scripts/build-pages.mjs` writes the stamp from `NILTV_BUILD_COMMIT`.

### Rules that keep prod clean

- A feature that is on `main` but not signed off must have a prod gate before
  it merges: a directory outside the prod page whitelist, a DRAFT fence, or an
  entry in `scripts/deploy-sweep.py`. Promotion is all-or-nothing.
- Hotfixes go to `release` on a `hotfix/*` branch and are merged back into
  `main` right after.
- Reverting a release is a `revert-*` PR into `release`. Bring the fix back to
  `main` as a fresh commit (`git cherry-pick`), never by merging the original
  branch again.

## Drafts and retired pages

`concepts/` and `_legacy/` are ignored scratch directories. `build-sections.py`
writes its intermediate pages under `concepts/cinema/` and `promote.py` backs
old pages up under `_legacy/`; neither is committed. Design drafts and their
builders live in `<private>/drafts/`. To review a draft on the dev site, copy
it into `concepts/` before running `deploy.ps1 -Env dev`; the dev artifact
includes that directory only when it exists.
