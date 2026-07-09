import unittest

from c64renamer import multidisk


class DiskInfoTests(unittest.TestCase):
    def test_disk_of_total(self):
        info = multidisk.parse_disk_info("Maniac Mansion (Disk 1 of 2)")
        self.assertEqual(info.base, "Maniac Mansion")
        self.assertEqual(info.index, 1)
        self.assertEqual(info.total, 2)
        self.assertTrue(info.is_multi)

    def test_side_letter(self):
        info = multidisk.parse_disk_info("Zak McKracken [Side B]")
        self.assertEqual(info.base, "Zak McKracken")
        self.assertEqual(info.index, 2)  # B -> 2
        self.assertEqual(info.kind, "side")

    def test_short_form(self):
        info = multidisk.parse_disk_info("Bards Tale (d2)")
        self.assertEqual(info.index, 2)
        self.assertEqual(info.base, "Bards Tale")

    def test_single_disk(self):
        info = multidisk.parse_disk_info("Arkanoid")
        self.assertFalse(info.is_multi)
        self.assertEqual(info.base, "Arkanoid")

    def test_format_name(self):
        info = multidisk.parse_disk_info("Game (Disk 1 of 3)")
        self.assertEqual(multidisk.format_name("Game", info), "Game (Disk 1 of 3)")
        # total inferred from a group when the file itself omitted it
        info2 = multidisk.parse_disk_info("Game (Disk 1)")
        self.assertEqual(
            multidisk.format_name("Game", info2, total_override=2),
            "Game (Disk 1 of 2)")


if __name__ == "__main__":
    unittest.main()
