# Run: python -m unittest scripts/builders/pinned_lists_test.py
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pinned_lists as pl

GOOD = {
    "trending": {"videos": [{"id": "a", "channel": "A TV", "title": "One"}, {"id": "b", "channel": "B TV", "title": "Two"}]},
    "sponsored": {"videos": [{"id": "s", "brand": "Brand", "title": "Ad"}]},
    "auditions": {"entries": [{"id": "e", "title": "Entry"}], "finalistOriginals": [{"id": "f", "title": "Final"}]},
}


class PinnedLists(unittest.TestCase):
    def test_tuples_in_file_order(self):
        self.assertEqual(pl.parse(GOOD), {
            "trending": [("a", "A TV", "One"), ("b", "B TV", "Two")],
            "sponsored": [("s", "Brand", "Ad")],
            "auditions": [("e", "Entry")],
            "finalist_originals": [("f", "Final")],
        })

    def test_empty_trending_is_allowed(self):
        data = copy.deepcopy(GOOD)
        data["trending"]["videos"] = []
        self.assertEqual(pl.parse(data)["trending"], [])

    def test_bad_files_fail_with_where(self):
        cases = [
            (lambda d: d.pop("sponsored"), "missing sponsored.videos"),
            (lambda d: d["trending"].update(videos="a"), "trending.videos must be a list"),
            (lambda d: d["sponsored"]["videos"][0].pop("brand"), r"sponsored.videos\[0\] needs a brand"),
            (lambda d: d["auditions"]["entries"][0].update(title="  "), r"auditions.entries\[0\] needs a title"),
            (lambda d: d["trending"]["videos"].append({"id": "a", "channel": "X", "title": "Y"}), "lists a twice"),
        ]
        for change, message in cases:
            data = copy.deepcopy(GOOD)
            change(data)
            with self.assertRaisesRegex(ValueError, message):
                pl.parse(data)

    def test_real_file_is_valid(self):
        lists = pl.load()
        self.assertTrue(lists["sponsored"])
        self.assertTrue(lists["auditions"])


if __name__ == "__main__":
    unittest.main()
