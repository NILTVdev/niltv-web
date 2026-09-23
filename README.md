# niltv-web

Static site for niltv.com. Pages are committed HTML; the watch and channel
pages, sitemap, robots and a build stamp are generated from the content API at
deploy time. Hosted on Amplify (S3 + CloudFront) as a manual deploy, no build
on the Amplify side.

| Tier | Branch | URL | Content API |
|---|---|---|---|
| local | your branch | http://localhost:8787 | fixture snapshots (`scripts/dev/serve.py`) |
| dev | `main` | https://dev.dkdfgvugisb3v.amplifyapp.com (basic auth) | dev stack |
| prod | `release` | https://prod.dkdfgvugisb3v.amplifyapp.com (canonical: niltv.com) | prod stack |

The full developer guide is [DEVELOPING.md](DEVELOPING.md).

## How to test

**Local.** No AWS account, no build step.

```
python scripts/dev/serve.py        # http://localhost:8787
python scripts/dev/capture-fixtures.py   # once: snapshot the dev API so /v1/* answers
```

Generated `/watch/` pages and athlete pages are not in the repo; the in-page
player covers playback and the private data folder supplies the rest (see
DEVELOPING.md). To run the exact checks CI runs, including page generation
against the live APIs and the prod sweep guard:

```
powershell -File deploy.ps1 -Env dev -Check
powershell -File deploy.ps1 -Env prod -Check
```

**Dev.** Open a PR against `main`. Site CI runs both checks above on the PR.
After merge, a maintainer deploys with `deploy.ps1` (dev, from a clean `main`);
the script then verifies the live site serves that commit with the marquee
intact. Review at the dev URL with the basic-auth login.

**Prod.** After sign-off, promote and deploy:

```
git push origin main:release
```

The push starts the Deploy Prod workflow. The prod build stages a copy,
regenerates against the prod API, sweeps every dev reference, prunes
unreleased pages, and refuses to upload if any guard fails. After upload it
verifies that `build.json` on the live site carries the commit. The workflow
also rebuilds when the API has new clips. The Verify Deploy workflow checks
the live site on a schedule.

## Guard rails

- **Checks**: the secret scan and the PR base rule in one run. A PR into
  `release` passes only from `main`, `hotfix/*` or `revert-*`; everything else
  is told to retarget to `main`.
- **Site CI**: `deploy.ps1 -Check` for prod and dev on every PR, under
  PowerShell 7 on a Linux runner.
- **Deploy Prod**: the only path to niltv.com; builds from `release` on a
  runner, assumes the `niltv-web-github-deploy` role via OIDC.
- **Verify Deploy**: scheduled and on-demand check of the live prod and dev
  sites against `build.json` and the API. The dev leg needs the `DEV_SITE_BASIC_AUTH`
  secret (the branch's basic-auth string from Amplify); it is skipped until set.
- **Unreleased features** must have a prod gate (directory prune, DRAFT fence
  or a `deploy-sweep.py` entry) before they merge to `main`. Promotion is
  all-or-nothing, so "we just won't promote yet" does not hold.

## Secret hygiene

Every commit is scanned for secret-shaped strings, locally and in CI.

1. Install gitleaks once: `go install github.com/zricethezav/gitleaks/v8@v8.24.3` (or `brew install gitleaks`).
2. Point git at the repo's hooks once per clone: `git config core.hooksPath .githooks`.

The `Checks` workflow runs the same scan over the full history on every pull request and every push to `main`. This site has no server-side secrets by design; anything that needs one belongs in the app backend, not here.

Maintainer clones also run a second scan from a private rule file in their pre-commit hook.

## License

The code in this repository is released under the MIT License (see
[LICENSE](LICENSE)). The license covers the code only. It does not grant any
right to:

- the NIL TV, NIL Star and TrueBlueTV names and logos, the campus channel
  marks, or any third-party brand, school, conference or league mark that
  appears in the assets;
- photographs, video, captions and other media of athletes and other people;
- athlete, applicant, subscriber and partner data, including anything the
  pipelines in this repository produce.

Third-party components keep their own licenses; see THIRD_PARTY_NOTICES.md
where present.
