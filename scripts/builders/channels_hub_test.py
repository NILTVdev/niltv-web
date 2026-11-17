# Run: python -m unittest scripts/builders/channels_hub_test.py
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import channels_hub as hub

API = [
    {"id": "ch-niltv", "name": "NIL TV"},                              # no school: not a campus channel
    {"id": "ch-b", "name": "B TV", "school": "B State"},
    {"id": "ch-a", "name": "A TV", "school": "A Tech"},
    {"id": "ch-new", "name": "Zed & Co TV", "school": "Zed U"},       # not in the order list
    {"id": "ch-also", "name": "Apple TV", "school": "Apple U"},       # not in the order list
]
CFG = {"count": 12, "minVideos": 7, "order": ["ch-a", "ch-gone", "ch-b"], "logos": {"ch-a": "alogo"}, "hidden": []}


class HubChannels(unittest.TestCase):
    def test_order_first_then_new_channels_a_to_z(self):
        self.assertEqual(hub.hub_channels(API, CFG), [
            ("ch-a", "A TV", "alogo"),
            ("ch-b", "B TV", None),
            ("ch-also", "Apple TV", None),
            ("ch-new", "Zed &amp; Co TV", None),   # escaped for HTML
        ])

    def test_channel_missing_from_api_is_skipped(self):
        ids = [c[0] for c in hub.hub_channels(API, CFG)]
        self.assertNotIn("ch-gone", ids)
        self.assertNotIn("ch-niltv", ids)

    def test_hidden(self):
        ids = [c[0] for c in hub.hub_channels(API, dict(CFG, hidden=["ch-b", "ch-new"]))]
        self.assertEqual(ids, ["ch-a", "ch-also"])

    def test_no_api_channels_means_no_rails(self):
        self.assertEqual(hub.hub_channels([], CFG), [])

    def test_bad_config_fails(self):
        for bad in (dict(CFG, count=0), dict(CFG, minVideos="7"), dict(CFG, order="ch-a"), dict(CFG, logos=[])):
            with self.assertRaises(ValueError):
                hub.check(bad)

    def test_real_file_is_valid(self):
        cfg = hub.load()
        self.assertEqual(len(cfg["order"]), len(set(cfg["order"])), "a channel is listed twice in order")


if __name__ == "__main__":
    unittest.main()
