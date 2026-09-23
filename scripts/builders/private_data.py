# -*- coding: utf-8 -*-
"""Where the private data lives (never committed).

Athlete records + photos, API fixture snapshots, the brand roster and the
ambassador roster are kept OUTSIDE the repo. Resolution order:

  1. the NILTV_PRIVATE_DATA environment variable, if set
  2. ../private-data/niltv-web next to the repo checkout, if it exists

`private_root()` returns None when nothing is found; callers print a one-line
note and skip the private-data part of their build instead of crashing.
"""
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SIBLING = os.path.join(os.path.dirname(REPO), "private-data", "niltv-web")
HOWTO = "set NILTV_PRIVATE_DATA to the private data folder (see DEVELOPING.md)"


def private_root(create=False):
    """Absolute path of the private data folder, or None.
    create=True returns the env/sibling path even if it does not exist yet
    (and creates it) - for writers such as capture-fixtures.py."""
    env = os.environ.get("NILTV_PRIVATE_DATA")
    if env:
        if create:
            os.makedirs(env, exist_ok=True)
        return env if os.path.isdir(env) else None
    for cand in (SIBLING,):
        if os.path.isdir(cand):
            return cand
    if create:
        os.makedirs(SIBLING, exist_ok=True)
        return SIBLING
    return None


def private_path(*parts, **kw):
    """<private root>/<parts...>, or None when the folder is not available."""
    root = private_root(create=kw.get("create", False))
    return os.path.join(root, *parts) if root else None


def private_file(*parts):
    """Like private_path() but also None when the file itself is missing."""
    p = private_path(*parts)
    return p if p and os.path.exists(p) else None
