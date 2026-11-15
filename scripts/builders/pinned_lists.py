# -*- coding: utf-8 -*-
"""Hand-picked video lists from pinned-lists.json.

Trending (homepage), Sponsored (homepage) and The Auditions (competitions)
are curated on purpose, so they stay lists in a fixed order. They live in
data rather than in code; build-sections.py gets them from load() in the
same tuple shapes it always used.
Tests: python -m unittest scripts/builders/pinned_lists_test.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "pinned-lists.json")

# list name -> (path in the file, fields each video needs, in tuple order)
LISTS = {
    "trending": (("trending", "videos"), ("id", "channel", "title")),
    "sponsored": (("sponsored", "videos"), ("id", "brand", "title")),
    "auditions": (("auditions", "entries"), ("id", "title")),
    "finalist_originals": (("auditions", "finalistOriginals"), ("id", "title")),
}


def _get(data, path):
    for key in path:
        if not isinstance(data, dict) or key not in data:
            raise ValueError("pinned-lists.json: missing %s" % ".".join(path))
        data = data[key]
    return data


def parse(data):
    """{list name: [tuple, ...]}. A bad entry fails the build with where it is."""
    out = {}
    for name, (path, fields) in LISTS.items():
        videos = _get(data, path)
        if not isinstance(videos, list):
            raise ValueError("pinned-lists.json: %s must be a list" % ".".join(path))
        rows = []
        for i, v in enumerate(videos):
            where = "pinned-lists.json: %s[%d]" % (".".join(path), i)
            for f in fields:
                if not isinstance(v, dict) or not isinstance(v.get(f), str) or not v[f].strip():
                    raise ValueError("%s needs a %s" % (where, f))
            rows.append(tuple(v[f] for f in fields))
        ids = [r[0] for r in rows]
        dupes = sorted({x for x in ids if ids.count(x) > 1})
        if dupes:
            raise ValueError("pinned-lists.json: %s lists %s twice" % (".".join(path), ", ".join(dupes)))
        out[name] = rows
    return out


def load(path=CONFIG):
    with open(path, encoding="utf-8") as f:
        return parse(json.load(f))
