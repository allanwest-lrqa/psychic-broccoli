import unittest

from c64renamer import groups, matching


class GroupTests(unittest.TestCase):
    def test_known_groups(self):
        self.assertTrue(groups.is_group("FAIRLIGHT"))
        self.assertTrue(groups.is_group("Triad"))
        self.assertTrue(groups.is_group("The OUG-Team"))

    def test_cracking_marker(self):
        self.assertTrue(groups.is_group("German Cracking Service"))
        self.assertTrue(groups.is_group("cracked by someone"))

    def test_real_games_are_not_groups(self):
        self.assertFalse(groups.is_group("Commando"))
        self.assertFalse(groups.is_group("The A-Team"))
        self.assertFalse(groups.is_group("Impossible Mission"))


class JunkStripTests(unittest.TestCase):
    def test_hack_marker_glued(self):
        self.assertEqual(matching.clean_title("5th Gear17h"), "5th Gear")

    def test_hack_marker_spaced(self):
        self.assertEqual(matching.clean_title("5TH GEAR 17H"), "5th Gear")

    def test_plus_and_percent(self):
        self.assertEqual(matching.clean_title("Commando +3"), "Commando")
        self.assertEqual(matching.clean_title("Bomb Jack 100%"), "Bomb Jack")

    def test_trailing_junk_word(self):
        self.assertEqual(matching.clean_title("Commando cr"), "Commando")

    def test_junk_does_not_eat_sequel_number(self):
        # A bare sequel number (no 'h') must be kept.
        self.assertEqual(matching.clean_title("Turrican 2"), "Turrican 2")

    def test_similarity_matches_after_junk(self):
        self.assertEqual(matching.similarity("5th Gear17h", "5th Gear"), 1.0)


if __name__ == "__main__":
    unittest.main()
