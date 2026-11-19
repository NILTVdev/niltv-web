# Run: python -m unittest scripts/builders/refresh_rails_test.py
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refresh_rails as rr

NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


def clip(vid, ch, day, title="A clip", dur=15):
    return {"id": vid, "channelId": ch, "title": title, "duration": dur,
            "publishedAt": "2026-11-%02dT12:00:00.000Z" % day}


def shelf(head, ids):
    cells = "\n".join('    <div class="reel-cell">\n      <a class="card card-reel" href="/watch/%s/">x</a>\n    </div>' % i for i in ids)
    return ('<section class="shelf">\n  <div class="shelf-head">\n    %s\n  </div>\n'
            '  <div class="rail">\n%s\n  </div>\n</section>' % (head, cells))


FEATURED = "\n".join([
    '<section class="hero"><a href="/watch/hero-1/">hero</a></section>',
    shelf('<h2 class="shelf-title gold">New This Week</h2>', ["old-1", "old-2"]),
    shelf('<h2 class="shelf-title">Media Day</h2>', ["md-1"]),
])


def channel_shelf(slug, ids):
    head = ('<h2 class="shelf-title"><a href="/channels/%s/"><img class="shelf-logo" src="x.webp" alt="x"></a></h2>\n'
            '    <a class="shelf-all" href="/channels/%s/">See All</a>' % (slug, slug))
    return shelf(head, ids)


class Featured(unittest.TestCase):
    def feed(self):
        by = {"ch-a": [clip("a%d" % d, "ch-a", d) for d in range(19, 4, -1)],
              "ch-b": [clip("b%d" % d, "ch-b", d) for d in range(18, 10, -1)] + [clip("md-1", "ch-b", 19)],
              "ch-nilstar": [clip("star", "ch-nilstar", 19)]}
        return rr.network_feed(by)

    def test_rewrites_only_the_new_this_week_rail(self):
        out, note = rr.refresh_featured(FEATURED, self.feed(), NOW)
        self.assertNotIn("old-1", out)
        self.assertIn("/watch/a19/", out)
        # the hero and the other rail are untouched
        self.assertTrue(out.startswith('<section class="hero"><a href="/watch/hero-1/">hero</a></section>'))
        self.assertTrue(out.endswith(shelf('<h2 class="shelf-title">Media Day</h2>', ["md-1"])))
        self.assertIn("18 cards", note)

    def test_skips_clips_shown_elsewhere_and_nil_star(self):
        out, _ = rr.refresh_featured(FEATURED, self.feed(), NOW)
        rail = out.split("New This Week")[1].split("Media Day")[0]
        self.assertNotIn("/watch/md-1/", rail)
        self.assertNotIn("/watch/star/", rail)

    def test_newest_first_with_just_added_tag(self):
        out, _ = rr.refresh_featured(FEATURED, self.feed(), NOW)
        rail = out.split("New This Week")[1]
        self.assertLess(rail.index("/watch/a19/"), rail.index("/watch/b18/"))
        self.assertIn('<span class="tile-tag">Just Added</span>', rail)

    def test_short_feed_keeps_current_cards(self):
        feed = rr.network_feed({"ch-a": [clip("a1", "ch-a", 1)]})
        out, note = rr.refresh_featured(FEATURED, feed, NOW)
        self.assertEqual(out, FEATURED)
        self.assertIn("kept", note)

    def test_missing_rail_is_an_error(self):
        with self.assertRaises(ValueError):
            rr.refresh_featured("<html></html>", self.feed(), NOW)

    def test_spread_caps_each_channel(self):
        by = {"ch-a": [clip("a%d" % d, "ch-a", d) for d in range(19, 0, -1)],
              "ch-b": [clip("b%d" % d, "ch-b", d) for d in range(5, 0, -1)]}
        newest, spread = rr.featured_picks(rr.network_feed(by), set(), NOW)
        self.assertEqual([i["id"] for i in newest][:2], ["a19", "a18"])
        # first pass: two per channel inside the window, then looser passes fill
        self.assertEqual([i["channelId"] for i in spread[:4]], ["ch-a", "ch-a", "ch-b", "ch-b"])
        self.assertEqual(len(spread), rr.FEATURED_SPREAD)


class Channels(unittest.TestCase):
    PAGE = "\n".join([
        shelf('<h2 class="shelf-title">Local Channels</h2>', []),
        channel_shelf("atv", ["old-a"]),
        channel_shelf("truebluetv", ["old-t"]),
    ])

    def test_each_channel_rail_gets_its_newest_clips(self):
        by = {"ch-atv": [clip("a%d" % d, "ch-atv", d) for d in range(19, 0, -1)],
              "ch-trueblue": [clip("t%d" % d, "ch-trueblue", d) for d in range(19, 9, -1)]}
        out, notes = rr.refresh_channels(self.PAGE, by, NOW)
        self.assertNotIn("old-a", out)
        self.assertNotIn("old-t", out)          # ch-trueblue maps to /channels/truebluetv/
        a_rail = out.split("/channels/atv/")[2].split("</section>")[0]
        self.assertEqual(a_rail.count("reel-cell"), rr.HUB.get("count", 12))
        self.assertLess(a_rail.index("/watch/a19/"), a_rail.index("/watch/a18/"))
        self.assertIn("New Episode", a_rail)
        self.assertTrue(out.startswith(shelf('<h2 class="shelf-title">Local Channels</h2>', [])))

    def test_thin_channel_keeps_current_cards(self):
        by = {"ch-atv": [clip("a1", "ch-atv", 1)], "ch-trueblue": []}
        out, notes = rr.refresh_channels(self.PAGE, by, NOW)
        self.assertEqual(out, self.PAGE)
        self.assertTrue(all("kept" in n for n in notes))

    def test_page_without_channel_rails_is_an_error(self):
        with self.assertRaises(ValueError):
            rr.refresh_channels("<html></html>", {}, NOW)


class Cards(unittest.TestCase):
    def test_titles_are_cleaned_and_escaped(self):
        cell = rr.reel_cell({"id": "x1", "title": 'Big "win" - #tag @me & more', "duration": 75})
        self.assertIn('aria-label="Big &quot;win&quot;, &amp; more"', cell)
        self.assertIn('<span class="dur">1:15</span>', cell)
        self.assertIn(rr.DEV_CDN + "/video/x1/poster", cell)


class ApiFailure(unittest.TestCase):
    def test_unreadable_api_changes_nothing(self):
        def boom(url):
            raise OSError("offline")
        orig = rr.fetch_json
        rr.fetch_json = boom
        try:
            self.assertEqual(rr.main(["x", "/nonexistent-root", "--api", "http://x"]), 0)
        finally:
            rr.fetch_json = orig


if __name__ == "__main__":
    unittest.main()
