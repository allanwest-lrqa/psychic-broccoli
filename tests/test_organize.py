import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from c64renamer import organize
from c64renamer.organize import OrganizeConfig
from tests import fixtures


class BucketTests(unittest.TestCase):
    def test_letter_digit_article(self):
        self.assertEqual(organize.bucket_for("Arkanoid"), "A")
        self.assertEqual(organize.bucket_for("1942"), "0-9")
        self.assertEqual(organize.bucket_for("The Great Giana Sisters"), "G")
        self.assertEqual(organize.bucket_for("!Explode"), "E")


class OrganizeDirectoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.src = Path(self._tmp.name) / "src"
        self.out = Path(self._tmp.name) / "out"
        self.src.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, data):
        p = self.src / name
        p.write_bytes(data)
        return p

    def test_copy_layout_offline(self):
        self._write("cart.crt", fixtures.make_crt("International Karate"))
        self._write("Commando.d64", fixtures.make_d64("COMMANDO", ["COMMANDO"]))
        self._write("tape.t64", fixtures.make_t64("BRUCE LEE", ["BRUCE LEE"]))
        self._write("mixed.crt", fixtures.make_crt("GAMES COMPILATION"))

        cfg = OrganizeConfig(output_dir=self.out, apply=True)  # no providers
        outcomes = organize.organize_directory(self.src, [], cfg)

        self.assertTrue((self.out / "Cartridges" / "I" / "International Karate.crt").exists())
        self.assertTrue((self.out / "Disks" / "C" / "Commando.d64").exists())
        self.assertTrue((self.out / "Tapes" / "B" / "Bruce Lee.t64").exists())
        # compilation set aside
        comp = list((self.out / "Compilations").rglob("*.crt"))
        self.assertEqual(len(comp), 1)
        # originals untouched (copy, not move)
        self.assertTrue((self.src / "cart.crt").exists())

    def test_multidisk_grouped_and_named(self):
        self._write("Maniac Mansion (Disk 1 of 2).d64",
                    fixtures.make_d64("MANIAC MANSION", ["MANIAC"]))
        self._write("Maniac Mansion (Disk 2 of 2).d64",
                    fixtures.make_d64("MANIAC MANSION", ["MANIAC"]))
        cfg = OrganizeConfig(output_dir=self.out, apply=True)
        organize.organize_directory(self.src, [], cfg)
        d = self.out / "Disks" / "M"
        self.assertTrue((d / "Maniac Mansion (Disk 1 of 2).d64").exists())
        self.assertTrue((d / "Maniac Mansion (Disk 2 of 2).d64").exists())

    def test_dry_run_writes_nothing(self):
        self._write("cart.crt", fixtures.make_crt("International Karate"))
        cfg = OrganizeConfig(output_dir=self.out, apply=False)
        outcomes = organize.organize_directory(self.src, [], cfg)
        self.assertFalse(self.out.exists())
        self.assertEqual(outcomes[0].action, organize.WOULD_COPY)

    def test_move_action(self):
        self._write("cart.crt", fixtures.make_crt("International Karate"))
        cfg = OrganizeConfig(output_dir=self.out, apply=True, action="move")
        organize.organize_directory(self.src, [], cfg)
        self.assertFalse((self.src / "cart.crt").exists())
        self.assertTrue((self.out / "Cartridges" / "I" / "International Karate.crt").exists())


if __name__ == "__main__":
    unittest.main()
