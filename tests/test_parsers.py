import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from c64renamer import parsers
from tests import fixtures


class ParserTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name: str, data: bytes) -> Path:
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_d64_reads_disk_and_program_names(self):
        path = self._write(
            "game.d64",
            fixtures.make_d64("COMMANDO", ["COMMANDO", "HISCORE"]),
        )
        parsed = parsers.parse(path)
        self.assertEqual(parsed.fmt, "d64")
        names = parsed.unique_names()
        self.assertIn("COMMANDO", names)
        self.assertIn("HISCORE", names)
        # disk-name and first dir entry are both weighted above later entries.
        self.assertEqual(parsed.best_candidate().name, "COMMANDO")

    def test_t64_reads_container_and_entries(self):
        path = self._write(
            "tape.t64",
            fixtures.make_t64("BRUCE LEE", ["BRUCE LEE"]),
        )
        parsed = parsers.parse(path)
        self.assertEqual(parsed.fmt, "t64")
        self.assertIn("BRUCE LEE", parsed.unique_names())

    def test_crt_reads_cartridge_name(self):
        path = self._write("cart.crt", fixtures.make_crt("International Karate"))
        parsed = parsers.parse(path)
        self.assertEqual(parsed.fmt, "crt")
        self.assertEqual(parsed.best_candidate().name, "International Karate")

    def test_unsupported_extension_raises(self):
        path = self._write("thing.tap", b"\x00" * 10)
        with self.assertRaises(parsers.ParseError):
            parsers.parse(path)

    def test_petscii_padding_is_trimmed(self):
        path = self._write("x.crt", fixtures.make_crt("ZAK"))
        parsed = parsers.parse(path)
        self.assertEqual(parsed.best_candidate().name, "ZAK")


if __name__ == "__main__":
    unittest.main()
