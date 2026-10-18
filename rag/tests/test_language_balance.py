"""D12: balance_by_language keeps slots for each language. Offline, no index."""
import unittest

from rag.store import balance_by_language


def c(i, lang, score):
    return {"chunk_id": i, "language": lang, "score": score}


class TestBalance(unittest.TestCase):
    def pool(self):
        # five French chunks all above two English ones: the D12 situation
        return [c("f1", "fr", 0.90), c("f2", "fr", 0.88), c("f3", "fr", 0.86), c("f4", "fr", 0.85), c("f5", "fr", 0.84), c("e1", "en", 0.80), c("e2", "en", 0.78)]

    def test_english_entry_survives_in_top_5(self):
        ids = [x["chunk_id"] for x in balance_by_language(self.pool(), 5)]
        self.assertIn("e1", ids)
        self.assertIn("e2", ids)
        self.assertEqual(len(ids), 5)

    def test_result_is_sorted_by_score(self):
        scores = [x["score"] for x in balance_by_language(self.pool(), 5)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_k_1_is_unchanged(self):
        self.assertEqual([x["chunk_id"] for x in balance_by_language(self.pool(), 1)], ["f1"])

    def test_single_language_pool_is_unchanged(self):
        pool = [c("f1", "fr", 0.9), c("f2", "fr", 0.8), c("f3", "fr", 0.7)]
        self.assertEqual([x["chunk_id"] for x in balance_by_language(pool, 3)], ["f1", "f2", "f3"])

    def test_fewer_candidates_than_k(self):
        self.assertEqual(len(balance_by_language(self.pool()[:3], 5)), 3)

    def test_best_result_stays_first_when_it_is_in_the_majority_language(self):
        self.assertEqual(balance_by_language(self.pool(), 4)[0]["chunk_id"], "f1")


if __name__ == "__main__":
    unittest.main()
