import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from c64renamer import renamer
from c64renamer.config import Config
from c64renamer.providers.base import ArtworkAsset, GameHit
from tests import fixtures


class FakeProvider:
    """Offline provider returning canned hits for known queries."""

    name = "fake"

    def __init__(self, table):
        self.table = table  # {query_substring: canonical_title}

    def available(self):
        return True

    def search(self, query):
        hits = []
        for needle, title in self.table.items():
            if needle.lower() in query.lower():
                hits.append(GameHit(title=title, game_id="1",
                                    url="http://example/game/1"))
        return hits

    def artwork(self, hit):
        return [ArtworkAsset("http://example/cover.jpg", "cover", "front")]


class RenamerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.provider = FakeProvider({"commando": "Commando"})

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_dry_run_does_not_rename(self):
        path = self._write("x.crt", fixtures.make_crt("COMMANDO"))
        config = Config(apply=False, download_artwork=False)
        outcome = renamer.process_file(path, [self.provider], config)
        self.assertEqual(outcome.status, renamer.WOULD_RENAME)
        self.assertEqual(outcome.title, "Commando")
        self.assertTrue(path.exists())  # untouched

    def test_apply_renames_high_confidence(self):
        path = self._write("x.crt", fixtures.make_crt("COMMANDO"))
        config = Config(apply=True, download_artwork=False)
        outcome = renamer.process_file(path, [self.provider], config)
        self.assertEqual(outcome.status, renamer.RENAMED)
        self.assertFalse(path.exists())
        self.assertTrue((self.dir / "Commando.crt").exists())

    def test_low_confidence_is_left_untouched(self):
        path = self._write("x.crt", fixtures.make_crt("SOME UNKNOWN THING"))
        config = Config(apply=True, download_artwork=False)
        outcome = renamer.process_file(path, [self.provider], config)
        self.assertEqual(outcome.status, renamer.UNMATCHED)
        self.assertTrue(path.exists())

    def test_no_providers_skips(self):
        path = self._write("x.crt", fixtures.make_crt("COMMANDO"))
        config = Config(apply=True)
        outcome = renamer.process_file(path, [], config)
        self.assertEqual(outcome.status, renamer.SKIPPED)

    def test_collision_gets_suffix(self):
        self._write("Commando.crt", fixtures.make_crt("Commando"))
        path = self._write("other.crt", fixtures.make_crt("COMMANDO"))
        config = Config(apply=True, download_artwork=False)
        outcome = renamer.process_file(path, [self.provider], config)
        self.assertEqual(outcome.status, renamer.RENAMED)
        self.assertEqual(outcome.new_path.name, "Commando (2).crt")

    def test_process_directory_scans_supported_files(self):
        self._write("a.crt", fixtures.make_crt("COMMANDO"))
        self._write("readme.txt", b"not a game")
        config = Config(apply=False, download_artwork=False)
        outcomes = renamer.process_directory(self.dir, [self.provider], config)
        self.assertEqual(len(outcomes), 1)


if __name__ == "__main__":
    unittest.main()
