# -*- coding: utf-8 -*-
"""Prod-artifact sweep, run by deploy.ps1 -Env prod against the STAGING copy.

The working tree is dev-flavored on purpose (dev CDN in committed pages, dev
origin defaults). Prod never edits the tree: deploy.ps1 stages a copy, runs
build-pages.mjs against the prod API, then this sweep rewrites every remaining
baked reference:

  dev content CDN  -> prod content CDN
  dev Amplify origin -> https://niltv.com
  poster-fill.jpg  -> poster.jpg   (only with --fills off, for when the derived
                                    fill crops are not in the prod bucket)

Usage: python deploy-sweep.py <staging_root> <origin> <cdn> [--fills off]
"""
import io, os, re, sys

DEV_CDN = "https://d1nm1d2txb83wa.cloudfront.net"
DEV_ORIGIN = "https://dev.dkdfgvugisb3v.amplifyapp.com"
EXTS = (".html", ".xml", ".txt", ".js", ".webmanifest")
# Dev-only review material never ships to prod: sections fenced by a DRAFT
# comment.
DRAFT_RE = re.compile(r"[ \t]*<!--(?:(?!-->).)*draft(?:(?!-->).)*-->\s*", re.S | re.I)
# Cuts for features that are on main but not signed off for prod go here: a
# regex applied to the staging copy plus a line in the hard guard below.
# Athletes nav link: deploy.ps1 ships /athletes/ only when it built the
# published athlete pages (--athletes on). Otherwise the nav link is cut and
# the guard fails any page that still links there.
ATHLETES_NAV_RE = re.compile(r'[ \t]*<a href="/athletes/"(?: class="active")?>Athletes</a>\n?')
ATHLETES_JS_RE = re.compile(r'[ \t]*\["Athletes", "/athletes/"\],\n')

def flag(name, default):
    """Value after `name` on the command line, or default."""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default

def main():
    root, origin, cdn = sys.argv[1], sys.argv[2], sys.argv[3]
    fills_off = flag("--fills", "on") == "off"
    athletes_on = flag("--athletes", "off") == "on"
    files = swaps = fillfix = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.lower().endswith(EXTS):
                continue
            p = os.path.join(dirpath, fn)
            t = io.open(p, encoding="utf-8", errors="strict").read()
            t2 = t.replace(DEV_CDN, cdn).replace(DEV_ORIGIN, origin)
            if fn.lower().endswith(".html"):
                t2, n_draft = DRAFT_RE.subn("", t2)
                if not athletes_on:
                    t2 = ATHLETES_NAV_RE.sub("", t2)
            if fn.lower().endswith(".js") and not athletes_on:
                t2 = ATHLETES_JS_RE.sub("", t2)
            if fills_off:
                n = t2.count("/poster-fill.jpg")
                if n:
                    t2 = t2.replace("/poster-fill.jpg", "/poster.jpg")
                    fillfix += n
            if t2 != t:
                io.open(p, "w", encoding="utf-8", newline="").write(t2)
                swaps += 1
            files += 1
    print("sweep: %d files scanned, %d rewritten, %d fill urls downgraded, athletes %s" % (files, swaps, fillfix, "on" if athletes_on else "off"))
    # hard guard: nothing dev-flavored may survive
    left = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.lower().endswith(EXTS):
                continue
            p = os.path.join(dirpath, fn)
            t = io.open(p, encoding="utf-8", errors="ignore").read()
            if "d1nm1d2txb83wa" in t or "dkdfgvugisb3v" in t or (not athletes_on and '"/athletes/' in t):
                left.append(os.path.relpath(p, root))
    if left:
        print("SWEEP GUARD FAILED - dev references or /athletes/ links remain in:")
        for p in left[:20]:
            print("  ", p)
        sys.exit(1)
    print("sweep guard: zero dev references remain")

if __name__ == "__main__":
    main()
