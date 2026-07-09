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

    def test_dedupe_same_title(self):
        # Two files, same game name, different bytes -> one kept, one duplicate.
        self._write("ik.crt", fixtures.make_crt("International Karate"))
        self._write("ik2.crt", fixtures.make_crt("International Karate!"))
        cfg = OrganizeConfig(output_dir=self.out, apply=True)
        outs = organize.organize_directory(self.src, [], cfg)
        placed = [o for o in outs if o.action == organize.COPIED]
        dupes = [o for o in outs if o.action == organize.DUPLICATE]
        self.assertEqual(len(placed), 1)
        self.assertEqual(len(dupes), 1)
        crts = list((self.out / "Cartridges").rglob("*.crt"))
        self.assertEqual(len(crts), 1)

    def test_dedupe_identical_content_diff_name(self):
        data = fixtures.make_crt("International Karate")
        self._write("a.crt", data)
        self._write("b.crt", data)  # byte-identical, different filename
        cfg = OrganizeConfig(output_dir=self.out, apply=True)
        outs = organize.organize_directory(self.src, [], cfg)
        self.assertEqual(sum(o.action == organize.DUPLICATE for o in outs), 1)

    def test_allow_duplicates_suffixes(self):
        self._write("ik.crt", fixtures.make_crt("International Karate"))
        self._write("ik2.crt", fixtures.make_crt("International Karate!"))
        cfg = OrganizeConfig(output_dir=self.out, apply=True, dedupe=False)
        organize.organize_directory(self.src, [], cfg)
        crts = sorted(p.name for p in (self.out / "Cartridges").rglob("*.crt"))
        self.assertEqual(len(crts), 2)
        self.assertIn("International Karate (2).crt", crts)

    def test_multidisk_not_treated_as_duplicate(self):
        self._write("Bard (Disk 1 of 2).d64", fixtures.make_d64("BARD", ["BARD"]))
        self._write("Bard (Disk 2 of 2).d64", fixtures.make_d64("BARD", ["BARD"]))
        cfg = OrganizeConfig(output_dir=self.out, apply=True)
        outs = organize.organize_directory(self.src, [], cfg)
        self.assertEqual(sum(o.action == organize.DUPLICATE for o in outs), 0)
        self.assertEqual(len(list((self.out / "Disks").rglob("*.d64"))), 2)

    def test_group_disk_name_uses_game_program(self):
        # Disk name is a cracking group; the real game is a directory entry.
        self._write("fairlight.d64", fixtures.make_d64("FAIRLIGHT", ["COMMANDO"]))
        cfg = OrganizeConfig(output_dir=self.out, apply=True)
        organize.organize_directory(self.src, [], cfg)
        self.assertTrue((self.out / "Disks" / "C" / "Commando.d64").exists())

    def test_group_only_file_is_unidentified(self):
        self._write("fairlight.d64", fixtures.make_d64("FAIRLIGHT", []))
        cfg = OrganizeConfig(output_dir=self.out, apply=True)
        outs = organize.organize_directory(self.src, [], cfg)
        self.assertEqual(outs[0].category, organize.UNIDENTIFIED)

    def test_hack_tag_stripped_from_name(self):
        self._write("5th Gear17h.crt", fixtures.make_crt("5th Gear17h"))
        cfg = OrganizeConfig(output_dir=self.out, apply=True)
        organize.organize_directory(self.src, [], cfg)
        # Title starts with a digit, so it buckets under 0-9.
        self.assertTrue((self.out / "Cartridges" / "0-9" / "5th Gear.crt").exists())

    def test_verify_names_without_provider_is_unidentified(self):
        self._write("cart.crt", fixtures.make_crt("International Karate"))
        cfg = OrganizeConfig(output_dir=self.out, apply=True, verify_names=True)
        outs = organize.organize_directory(self.src, [], cfg)
        self.assertEqual(outs[0].category, organize.UNIDENTIFIED)

    def test_skip_unidentified_ignores_file(self):
        # verify_names makes it unidentified (no provider); skip drops it.
        self._write("cart.crt", fixtures.make_crt("International Karate"))
        cfg = OrganizeConfig(output_dir=self.out, apply=True,
                             verify_names=True, skip_unidentified=True)
        outs = organize.organize_directory(self.src, [], cfg)
        self.assertEqual(outs[0].action, organize.SKIPPED)
        self.assertIsNone(outs[0].dest)
        # Nothing copied anywhere.
        self.assertFalse(self.out.exists())

    def test_artwork_downloaded_in_organize(self):
        from c64renamer.providers.base import GameHit, ArtworkAsset

        class FakeProv:
            name = "fake"
            def available(self): return True
            def search(self, q):
                return [GameHit("International Karate", game_id="1", url="u")]
            def artwork(self, hit):
                return [ArtworkAsset("http://x/c.jpg", "cover", "front")]

        # Monkeypatch the downloader to avoid real network.
        import c64renamer.artwork as art
        calls = {}
        real = art.http.download
        def fake_download(url, dest, timeout=30):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"img")
            calls["n"] = calls.get("n", 0) + 1
            return dest
        art.http.download = fake_download
        try:
            self._write("ik.crt", fixtures.make_crt("International Karate"))
            cfg = OrganizeConfig(output_dir=self.out, apply=True,
                                 download_artwork=True, min_confidence=0.8)
            organize.organize_directory(self.src, [FakeProv()], cfg)
        finally:
            art.http.download = real
        arts = list((self.out / "Artwork").rglob("*.jpg"))
        self.assertTrue(arts)


if __name__ == "__main__":
    unittest.main()
