import unittest

from c64renamer import matching


class CleanTitleTests(unittest.TestCase):
    def test_strips_cracker_tags(self):
        self.assertEqual(matching.clean_title("COMMANDO/HTL"), "Commando")
        self.assertEqual(matching.clean_title("GIANA +3"), "Giana")

    def test_strips_brackets(self):
        self.assertEqual(
            matching.clean_title("ZAK MCKRACKEN [E]"), "Zak Mckracken"
        )

    def test_preserves_short_acronyms(self):
        self.assertEqual(matching.clean_title("IK+"), "IK")


class SimilarityTests(unittest.TestCase):
    def test_case_and_spacing_insensitive(self):
        self.assertEqual(
            matching.similarity("IMPOSSIBLE MISSION", "Impossible Mission"), 1.0
        )

    def test_subset_titles_score_high(self):
        score = matching.similarity("GIANA SISTERS", "The Great Giana Sisters")
        self.assertGreater(score, 0.6)

    def test_unrelated_titles_score_low(self):
        self.assertLess(matching.similarity("COMMANDO", "Pac-Man"), 0.6)

    def test_ranking_orders_best_first(self):
        titles = ["Pac-Man", "Commando", "Commando 2"]
        ranked = matching.rank_titles("COMMANDO", titles)
        self.assertEqual(ranked[0][0], "Commando")


if __name__ == "__main__":
    unittest.main()
