import unittest

from c64renamer import compilation
from c64renamer.parsers.base import NameCandidate, ParsedFile
from pathlib import Path


def _parsed(*names, source="disk-name"):
    p = ParsedFile(path=Path("x.d64"), fmt="d64")
    p.candidates = [NameCandidate(n, source) for n in names]
    return p


class CompilationTests(unittest.TestCase):
    def test_keyword_compilation(self):
        self.assertTrue(compilation.detect(_parsed("GAMES COMPILATION")).is_compilation)
        self.assertTrue(compilation.detect(_parsed("THE HIT PACK")).is_compilation)

    def test_n_in_one(self):
        self.assertTrue(compilation.detect(_parsed("4 IN 1")).is_compilation)
        self.assertTrue(compilation.detect(_parsed("10-in-1 MEGA")).is_compilation)

    def test_n_games(self):
        self.assertTrue(compilation.detect(_parsed("5 GAMES")).is_compilation)

    def test_plain_game_is_not_compilation(self):
        self.assertFalse(compilation.detect(_parsed("COMMANDO")).is_compilation)
        # "1942" or "gunship" must not trip the numeric rules
        self.assertFalse(compilation.detect(_parsed("1942")).is_compilation)

    def test_entry_threshold_opt_in(self):
        many = _parsed(*[f"GAME{i}" for i in range(12)], source="dir-entry")
        self.assertFalse(compilation.detect(many, entry_threshold=0).is_compilation)
        self.assertTrue(compilation.detect(many, entry_threshold=10).is_compilation)


if __name__ == "__main__":
    unittest.main()
