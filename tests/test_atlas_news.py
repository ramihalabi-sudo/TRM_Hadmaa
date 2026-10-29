"""Detector Atlas news: watcher events become news items; read state is kept in the settings."""
import unittest

import _common  # noqa: F401  (puts the project on sys.path)
from trm4 import atlas_news as NEWS

FEED = {
    "last_checked": "2026-10-26T07:06:16Z",
    "catalog": [{"id": "rec-1", "manufacturer": "SCD", "model": "Blackbird", "band": "MWIR", "technology": "XBn",
                 "width": 1920, "height": 1536, "pitch_um": 10}],
    "events": [
        {"id": "evt-old", "kind": "new_listing", "manufacturer": "LYNRED", "model": "MEGALINK",
         "detected_at": "2026-10-20T12:59:22Z", "record_id": None, "specs": {},
         "status": "Unclassified candidate - review"},
        {"id": "evt-new", "kind": "new_listing", "manufacturer": "SCD", "model": "Blackbird",
         "detected_at": "2026-10-25T06:00:00Z", "record_id": "rec-1", "band": None, "specs": {},
         "status": "Catalogued - review"},
        {"kind": "broken"},
    ],
}


class AtlasNews(unittest.TestCase):
    def test_items_newest_first_with_record(self):
        items = NEWS.items(FEED)
        self.assertEqual([it["id"] for it in items], ["evt-new", "evt-old"])
        self.assertEqual(items[0]["band"], "MWIR")
        self.assertIn("1920x1536", NEWS.details(items[0]))
        self.assertIn("10 um pitch", NEWS.details(items[0]))
        self.assertEqual(NEWS.title(items[1]), "LYNRED MEGALINK")

    def test_read_state(self):
        items, settings = NEWS.items(FEED), {}
        self.assertEqual(len(NEWS.unread(items, settings)), 2)
        NEWS.mark_read(settings, ["evt-old"])
        self.assertEqual([it["id"] for it in NEWS.unread(items, settings)], ["evt-new"])
        NEWS.mark_read(settings, ["evt-old"], read=False)
        self.assertEqual(len(NEWS.unread(items, settings)), 2)

    def test_no_events(self):
        self.assertEqual(NEWS.items({"catalog": [], "events": []}), [])


if __name__ == "__main__":
    unittest.main()
