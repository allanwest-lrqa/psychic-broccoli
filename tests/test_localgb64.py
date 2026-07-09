import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from c64renamer import artwork
from c64renamer.providers.localgb64 import LocalGB64Provider
from c64renamer.providers.base import GameHit


RECORDS = [
    {"title": "Commando", "filename": "Commando.d64", "screenshot": "C/Commando.png"},
    {"title": "5th Gear", "filename": "5thGear.d64", "screenshot": "5/5thGear.gif"},
    {"title": "Impossible Mission", "filename": "IM.d64", "screenshot": ""},
]


class LocalGB64SearchTests(unittest.TestCase):
    def setUp(self):
        self.p = LocalGB64Provider(records=RECORDS)

    def test_available_with_records(self):
        self.assertTrue(self.p.available())

    def test_search_exact(self):
        hits = self.p.search("Commando")
        self.assertTrue(hits)
        self.assertEqual(hits[0].title, "Commando")

    def test_search_with_hack_tag(self):
        # normalize strips "17h" so this still finds "5th Gear".
        hits = self.p.search("5th Gear17h")
        self.assertTrue(hits)
        self.assertEqual(hits[0].title, "5th Gear")

    def test_search_unknown_returns_nothing(self):
        self.assertEqual(self.p.search("Totally Unknown Game Xyz"), [])


class LocalGB64ArtworkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.scr = Path(self._tmp.name) / "Screenshots"
        (self.scr / "C").mkdir(parents=True)
        (self.scr / "C" / "Commando.png").write_bytes(b"PNGDATA")
        self.p = LocalGB64Provider(records=RECORDS, screenshots_dir=self.scr)

    def tearDown(self):
        self._tmp.cleanup()

    def test_resolves_local_screenshot(self):
        hit = GameHit(title="Commando", extra={"screenshot": "C/Commando.png"})
        assets = self.p.artwork(hit)
        self.assertEqual(len(assets), 1)
        self.assertTrue(assets[0].local_path.endswith("Commando.png"))

    def test_download_for_game_copies_local_file(self):
        hit = GameHit(title="Commando", extra={"screenshot": "C/Commando.png"})
        out = Path(self._tmp.name) / "Artwork"
        written = artwork.download_for_game("Commando", self.p, hit, out)
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].is_file())
        self.assertEqual(written[0].read_bytes(), b"PNGDATA")


if __name__ == "__main__":
    unittest.main()
