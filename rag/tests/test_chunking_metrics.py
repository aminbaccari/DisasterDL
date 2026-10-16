import unittest

from rag import chunking, metrics


class TestFixedChunking(unittest.TestCase):
    def test_short_text_gives_one_chunk(self):
        self.assertEqual(len(chunking.chunk_fixed("a b c", size=10, overlap=2)), 1)

    def test_empty_text(self):
        self.assertEqual(chunking.chunk_fixed("   ", size=10, overlap=2), [])

    def test_overlap_is_shared(self):
        text = " ".join(f"w{i}" for i in range(25))
        chunks = chunking.chunk_fixed(text, size=10, overlap=3)
        first, second = chunks[0].split(), chunks[1].split()
        self.assertEqual(first[-3:], second[:3])

    def test_no_words_lost(self):
        text = " ".join(f"w{i}" for i in range(95))
        chunks = chunking.chunk_fixed(text, size=20, overlap=5)
        covered = set(" ".join(chunks).split())
        self.assertEqual(covered, set(text.split()))

    def test_bad_overlap(self):
        with self.assertRaises(ValueError):
            chunking.chunk_fixed("a b c", size=5, overlap=5)


class TestSections(unittest.TestCase):
    def test_heading_detection(self):
        self.assertTrue(chunking.is_heading("## Before a flood"))
        self.assertTrue(chunking.is_heading("DURING A FLOOD"))
        self.assertTrue(chunking.is_heading("2.1 Evacuation"))
        self.assertFalse(chunking.is_heading("Move to higher ground immediately."))
        self.assertFalse(chunking.is_heading(""))

    def test_sections_keep_heading(self):
        body = "word " * 40
        text = f"## Before\n{body}\n## During\n{body}"
        chunks, last = chunking.chunk_sections(text, max_words=100, overlap=10, min_words=30)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0][1].startswith("Before."))
        self.assertTrue(chunks[1][1].startswith("During."))
        self.assertEqual(last, "During")

    def test_short_sections_merge(self):
        text = "## A\nfew words here\n## B\nfew more words here"
        chunks, _ = chunking.chunk_sections(text, max_words=100, overlap=10, min_words=30)
        self.assertEqual(len(chunks), 1)

    def test_heading_carries_across_pages(self):
        body = "word " * 40
        pages = [(1, f"## Evacuation\n{body}"), (2, body)]
        chunks = chunking.chunk_document(pages, "section", size=100, overlap=10, min_words=30)
        self.assertEqual([c.page for c in chunks], [1, 2])
        self.assertEqual(chunks[1].section, "Evacuation")

    def test_unknown_strategy(self):
        with self.assertRaises(ValueError):
            chunking.chunk_document([(1, "text")], "magic")


class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.results = [
            {"source": "a.pdf", "text": "unrelated text"},
            {"source": "b.pdf", "text": "Move to higher ground at once"},
            {"source": "b.pdf", "text": "other"},
        ]

    def test_source_only_hit(self):
        self.assertEqual(metrics.first_hit_rank(self.results, "b.pdf"), 2)

    def test_phrase_must_match(self):
        self.assertEqual(metrics.first_hit_rank(self.results, "b.pdf", "higher ground"), 2)
        self.assertIsNone(metrics.first_hit_rank(self.results, "b.pdf", "evacuate by boat"))

    def test_no_hit(self):
        self.assertIsNone(metrics.first_hit_rank(self.results, "c.pdf"))

    def test_summary(self):
        s = metrics.summarize([1, 3, None, 2], ks=(1, 3))
        self.assertAlmostEqual(s["hit@1"], 0.25)
        self.assertAlmostEqual(s["hit@3"], 0.75)
        self.assertAlmostEqual(s["mrr"], (1 + 1 / 3 + 0 + 1 / 2) / 4)

    def test_empty_summary(self):
        self.assertEqual(metrics.summarize([]), {"n_queries": 0})


if __name__ == "__main__":
    unittest.main()


class TestEntryIdMatching(unittest.TestCase):
    def fixed_chunk(self):
        return {"source": "fire_kb.md", "section": "",
                "text": "Origin: US. ## FI-09 Under a wildfire warning Leave if told. ## FI-10 Before a wildfire sign up"}

    def section_chunk(self):
        return {"source": "fire_kb.md", "section": "FI-13 Leave when told", "text": "FI-13 Leave when told. Two kinds of advice"}

    def test_ids_from_fixed_and_section_chunks(self):
        self.assertEqual(metrics.entry_ids(self.fixed_chunk()), ["FI-09", "FI-10"])
        self.assertEqual(metrics.entry_ids(self.section_chunk()), ["FI-13"])

    def test_id_in_the_body_does_not_count(self):
        chunk = {"source": "fire_kb.md", "section": "FI-21 Titre", "text": "FI-21 Titre. Type: French translation of FI-09."}
        self.assertEqual(metrics.entry_ids(chunk), ["FI-21"])

    def test_hit_on_any_listed_entry(self):
        self.assertTrue(metrics.is_hit(self.fixed_chunk(), expected_entry_ids=["FI-10", "FI-99"]))
        self.assertFalse(metrics.is_hit(self.section_chunk(), expected_entry_ids=["FI-09"]))

    def test_entry_id_wins_over_source(self):
        # source does not match but the entry does: the entry id decides
        self.assertTrue(metrics.is_hit(self.section_chunk(), "other.md", "", ["FI-13"]))

    def test_rank_with_entry_ids(self):
        results = [self.section_chunk(), self.fixed_chunk()]
        self.assertEqual(metrics.first_hit_rank(results, expected_entry_ids=["FI-10"]), 2)
        self.assertIsNone(metrics.first_hit_rank(results, expected_entry_ids=["FL-01"]))

    def test_old_source_and_phrase_matching_still_works(self):
        self.assertTrue(metrics.is_hit(self.fixed_chunk(), "fire_kb.md", "leave if told"))
        self.assertFalse(metrics.is_hit(self.fixed_chunk(), "flood_kb.md"))
