# -*- coding: utf-8 -*-
"""Which channel rails the /channels/ hub shows, from data.

channels-hub.json holds only what the API can't tell us: the order of the
rails and each channel's logo. Names and schools come from /v1/channels, so a
new campus channel gets a rail without a code change once it has enough
videos. build-sections.py renders the rails; this module only chooses them.
Tests: python -m unittest scripts/builders/channels_hub_test.py
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "channels-hub.json")


def check(cfg):
    """Fail the build on a malformed file instead of dropping rails quietly."""
    for key in ("count", "minVideos"):
        if not isinstance(cfg.get(key), int) or cfg[key] < 1:
            raise ValueError("channels-hub.json: %s must be a whole number of at least 1" % key)
    for key in ("order", "hidden"):
        if not isinstance(cfg.get(key, []), list):
            raise ValueError("channels-hub.json: %s must be a list of channel ids" % key)
    if not isinstance(cfg.get("logos", {}), dict):
        raise ValueError("channels-hub.json: logos must map channel ids to logo names")
    return cfg


def load(path=CONFIG):
    with open(path, encoding="utf-8") as f:
        return check(json.load(f))


def hub_channels(api_channels, cfg):
    """[(channel id, display name, logo or None)] in rail order.

    Only channels with a school are campus channels; NIL TV and NIL Star
    have none and are not railed here.
    """
    hidden = set(cfg.get("hidden", []))
    campus = {c["id"]: c for c in api_channels if c.get("school") and c["id"] not in hidden}
    order = [cid for cid in cfg.get("order", []) if cid in campus]
    rest = sorted((cid for cid in campus if cid not in order), key=lambda cid: campus[cid]["name"].lower())
    logos = cfg.get("logos", {})
    return [(cid, html.escape(campus[cid]["name"], quote=False), logos.get(cid)) for cid in order + rest]
