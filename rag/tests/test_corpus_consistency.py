"""Corpus consistency: French translations point at real English entries, SOURCES.md lists every file, evaluation files only name existing entries. Offline."""
import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = ROOT / "rag" / "corpus"


def entry_ids(lang):
    ids = {}
    for path in sorted((CORPUS / lang).glob("*_kb.md")):
        for m in re.finditer(r"(?m)^## ([A-Z]{2}-\d+) ", path.read_text(encoding="utf-8")):
            ids[m.group(1)] = path
    return ids


class TestCorpus(unittest.TestCase):
    def test_no_entry_id_is_used_twice_across_the_corpus(self):
        seen = {}
        for lang in ("en", "fr"):
            for path in sorted((CORPUS / lang).glob("*_kb.md")):
                for m in re.finditer(r"(?m)^## ([A-Z]{2}-\d+) ", path.read_text(encoding="utf-8")):
                    self.assertNotIn(m.group(1), seen, f"{m.group(1)} appears in {seen.get(m.group(1))} and {path}")
                    seen[m.group(1)] = path

    def test_every_translation_points_at_an_english_entry(self):
        english = entry_ids("en")
        found = 0
        for path in (CORPUS / "fr").glob("*_kb.md"):
            for m in re.finditer(r"French translation by the project team of ([A-Z]{2}-\d+)", path.read_text(encoding="utf-8")):
                found += 1
                self.assertIn(m.group(1), english, f"{path.name}: translation of unknown entry {m.group(1)}")
        self.assertGreaterEqual(found, 19)  # FI-21..26, FL-27..33, ST-27..32

    def test_translations_are_marked_as_unreviewed(self):
        for path in (CORPUS / "fr").glob("*_kb.md"):
            text = path.read_text(encoding="utf-8")
            for block in re.split(r"(?m)^## ", text)[1:]:
                if "French translation by the project team" in block and block.startswith(("FL-", "ST-")):
                    self.assertIn("Not reviewed by a French reader", block, block[:40])

    def test_every_corpus_file_is_listed_in_sources(self):
        sources = (CORPUS / "SOURCES.md").read_text(encoding="utf-8")
        for lang in ("en", "fr"):
            for path in (CORPUS / lang).glob("*_kb.md"):
                self.assertIn(f"{lang}/{path.name}", sources)

    def test_evaluation_files_only_name_existing_entries(self):
        known = set(entry_ids("en")) | set(entry_ids("fr"))
        wanted = {}
        for name in ("queries_v2.csv", "queries_v3.csv", "queries_v4.csv"):
            with open(ROOT / "rag" / "eval" / name, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    for i in (row["expected_entry_id"] or "").split("|"):
                        if i:
                            wanted[i] = name
        for case in json.loads((ROOT / "rag" / "eval" / "incident_cases_v1.json").read_text(encoding="utf-8"))["cases"]:
            for need in case["needs"]:
                for i in need["any_of"]:
                    wanted[i] = case["id"]
        missing = {i: where for i, where in wanted.items() if i not in known}
        self.assertEqual(missing, {})


if __name__ == "__main__":
    unittest.main()
