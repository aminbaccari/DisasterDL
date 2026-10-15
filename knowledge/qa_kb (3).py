"""Builds the knowledge base files from the entries and the QA results.

  python build_kb.py --qa-dir <qa output> --out <folder for knowledge_base> [--corpus-dir <project rag/corpus>]
Run qa_kb.py first. This script refuses to build if the QA results contain failures.
"""
import argparse
import datetime
import json
import os
import shutil
import sys

from kb_data import ENTRIES, CONFLICTS, AGREEMENTS, TEAM_NOTES, EXCLUSIONS
from sources_data import SOURCES

TOPIC_TITLES = {"flood": "Floods", "structural": "Structural and urban emergencies", "fire": "Fires"}
TOPIC_INTRO = {
    "flood": ("Knowledge for the flood assistant. Sources: American Red Cross checklist (English, United States), the French easy-to-read guidance "
              "Pluie et inondation (French, France) and FEMA P-2055 (English, United States, building evaluators). Phone numbers, websites and "
              "national services in the sources are not reproduced because they do not apply in Tunisia."),
    "structural": ("Knowledge for structural and urban emergencies. Sources: FEMA P-2055 and FEMA P-2055-2 (English, United States). They are written for "
                   "building safety evaluators and emergency managers, and the cordon material is written for earthquakes. Entries marked professional are "
                   "context for the assistant, not instructions for the public."),
    "fire": ("LIMITED coverage. The four supplied sources contain no wildfire prevention, evacuation or firefighting guidance. This file only holds what "
             "FEMA P-2055 says about buildings after a fire, smoke and soot, and secondary hazards. Do not use it to advise on an approaching fire."),
}


def entry_type(e):
    if e["meta"]:
        return "scope note written by the project team"
    if "resolves" in e:
        if len({s[0] for s in e["sources"]}) < 2:
            return "source passage with a caveat written by the project team"
        return "reconciliation of sources that differ, written by the project team from the cited passages"
    return "taken from the sources"


def source_line(e):
    seen = {}
    for src, page, _ in e["sources"]:
        seen.setdefault(src, []).append(page)
    parts = []
    for src, pages in seen.items():
        m = SOURCES[src]
        ps = sorted(set(pages))
        pg = ", ".join(str(p) for p in ps)
        parts.append(f"{m['short']}, PDF page{'s' if len(ps) > 1 else ''} {pg}")
    return "; ".join(parts)


def render_entry(e):
    juris = sorted({SOURCES[s[0]]["jurisdiction"] for s in e["sources"]})
    lines = [f"## {e['id']} {e['title']}", "", e["text"], ""]
    lines.append(f"{'Basis' if e['meta'] else 'Source'}: {source_line(e)}.")
    lines.append(f"Origin of the sources: {', '.join(juris)}. Audience: {e['audience']}. Type: {entry_type(e)}.")
    for n in TEAM_NOTES.get(e["id"], []):
        if not e["meta"]:
            lines.append(f"Team note, not from the sources: {n}")
    if e["omitted"]:
        lines.append("Left out on purpose: " + "; ".join(e["omitted"]) + ".")
    lines.append("")
    return "\n".join(lines)


def render_topic(topic, entries):
    langs = sorted({e["lang"] for e in entries})
    out = [f"# {TOPIC_TITLES[topic]} knowledge base", "", TOPIC_INTRO[topic], "",
           f"Entries: {len(entries)}. Languages: {', '.join(langs)}. Each entry is self-contained and ends with its source and PDF page.", ""]
    out += [render_entry(e) for e in entries]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qa-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--corpus-dir")
    args = ap.parse_args()

    qa = json.load(open(os.path.join(args.qa_dir, "qa_results.json"), encoding="utf-8"))
    failed = [k for k in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T9") if qa[k]["fails"]]
    if failed:
        sys.exit("QA has failures in " + ", ".join(failed) + ". Fix them before building.")

    os.makedirs(args.out, exist_ok=True)
    for topic in TOPIC_TITLES:
        items = [e for e in ENTRIES if e["topic"] == topic]
        open(os.path.join(args.out, f"{topic}.md"), "w", encoding="utf-8").write(render_topic(topic, items))
    # entries.json (the provenance record)
    rec = []
    for e in ENTRIES:
        rec.append({
            "id": e["id"], "topic": e["topic"], "language": e["lang"], "title": e["title"], "text": e["text"],
            "audience": e["audience"], "type": entry_type(e), "needs": e["needs"], "topic_keys": e["topic_keys"],
            "sources": [{"source": s[0], "file": SOURCES[s[0]]["file"], "pdf_page": s[1], "anchors": s[2]} for s in e["sources"]],
            "team_notes": TEAM_NOTES.get(e["id"], []), "left_out": e["omitted"],
        })
    json.dump({"generated": datetime.date.today().isoformat(), "sources": SOURCES, "entries": rec},
              open(os.path.join(args.out, "entries.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    shutil.copy(os.path.join(args.qa_dir, "qa_results.json"), os.path.join(args.out, "qa_results.json"))
    write_sources(args.out)
    write_qa_report(args.out, qa)
    write_readme(args.out, qa)

    if args.corpus_dir:
        for topic in TOPIC_TITLES:
            for lang in ("en", "fr"):
                items = [e for e in ENTRIES if e["topic"] == topic and e["lang"] == lang]
                d = os.path.join(args.corpus_dir, lang)
                os.makedirs(d, exist_ok=True)
                path = os.path.join(d, f"{topic}_kb.md")
                if items:
                    open(path, "w", encoding="utf-8").write(render_topic(topic, items))
                elif os.path.exists(path):
                    os.remove(path)
    print("built:", sorted(os.listdir(args.out)))


def write_sources(out):
    L = ["# Sources used", "", "Only these four documents were used. They were checked by the team before use (reported by Kay on 2026-10-15). "
         "PDF page numbers are the page positions in the PDF file, which can differ from the printed page numbers.", ""]
    L.append("| Key | File | Title | Publisher | Date | Language |")
    L.append("|-----|------|-------|-----------|------|----------|")
    for k, m in SOURCES.items():
        L.append(f"| {k} | {m['file']} | {m['title']} | {m['publisher']} | {m['date']} | {m['lang']} |")
    L += ["", "Notes:", ""]
    for k, m in SOURCES.items():
        L.append(f"- {k}: {m['note']}")
    L += ["", "No licence is stated in the documents. Use the knowledge base inside the course project and cite the sources. Do not republish it.", ""]
    open(os.path.join(out, "SOURCES_USED.md"), "w", encoding="utf-8").write("\n".join(L))


def write_qa_report(out, qa):
    s8 = qa["T8"]["summary"]
    L = ["# Quality and consistency report", "", f"Run on {datetime.date.today().isoformat()} with qa_kb.py. Results below are the output of that run.", ""]
    L += ["## Results", "", "| Test | What it checks | Result |", "|------|----------------|--------|"]
    n_anchor = qa["T1"]["checked"]
    rows = [
        ("T1 provenance", f"{n_anchor} verbatim anchor phrases are found on the cited PDF page (OCR for the 4 image-only pages)", "pass" if not qa["T1"]["fails"] else "fail"),
        ("T2 numbers", f"{qa['T2']['checked']} numbers in entry texts each appear within 500 characters of an anchor on the cited page", "pass" if not qa["T2"]["fails"] else "fail"),
        ("T3 consistency", f"{len(qa['T3']['groups'])} topics checked across sources, see the table below", "pass" if not qa["T3"]["fails"] else "fail"),
        ("T4 scope", "no phone numbers, URLs or foreign-only institutions in the texts", "pass" if not qa["T4"]["fails"] else "fail"),
        ("T5 self-contained", f"{qa['T5']['min']} to {qa['T5']['max']} words (mean {qa['T5']['mean']}), no references to other places", "pass" if not qa["T5"]["fails"] else "fail"),
        ("T6 duplicates", "no near-duplicate entries (TF-IDF cosine below 0.60 except declared overlaps)", "pass" if not qa["T6"]["fails"] else "fail"),
        ("T7 coverage", "every need on the checklist has at least one entry", "pass" if not qa["T7"]["fails"] else "fail"),
        ("T9 structure", "ids, fields, language, audience, declared team notes", "pass" if not qa["T9"]["fails"] else "fail"),
    ]
    for r in rows:
        L.append("| " + " | ".join(r) + " |")
    L += ["", "## What T1 and T2 do not prove", "",
          "They prove that quoted phrases and numbers exist on the cited page. They do not prove that a paraphrase means the same as the source. "
          "Meaning was checked by reading each entry against its page. Sentences written by the team are listed as team notes in the md files.", ""]
    L += ["## T3 consistency across sources", "",
          "Detection is automatic: a keyword group that appears in entries drawn from two or more sources must be reconciled by a dedicated entry or declared as an agreement.", "",
          "| Topic | Entries | Sources | Status | Detail |", "|-------|---------|---------|--------|--------|"]
    for g in qa["T3"]["groups"]:
        L.append(f"| {g['topic']}/{g['group']} | {', '.join(g['entries'])} | {', '.join(g['sources'])} | {g['status']} | {g['detail']} |")
    L += ["", "Differences found between sources, and how they are handled:", ""]
    for cid, c in CONFLICTS.items():
        L.append(f"- {cid}: {c['summary']} Handled in {c['resolver']}.")
    L += ["", "Agreements confirmed:", ""]
    for k, a in AGREEMENTS.items():
        L.append(f"- {k}: {a['summary']}")
    L += ["", "Rule used when sources differ: the entry keeps both positions with their source, states the stricter safety action, and says when the sources give no answer. "
          "Nothing is added that no source says.", ""]
    L += ["## T8 retrieval proxy (lexical, not the embedding model)", "",
          f"{s8['n']} natural queries (English and French, written after the entries), TF-IDF search inside the topic. "
          f"hit@1 {s8['hit@1']}, hit@3 {s8['hit@3']}, hit@5 {s8['hit@5']}, MRR {s8['mrr']}.", "",
          "This checks that each entry can be found by the words a person would use. It does not replace the embedding evaluation in rag/evaluate.py, "
          "and it cannot test cross-language retrieval. The queries were written by the same person who wrote the entries, so the score is optimistic.", "",
          "| Query | Topic | Language | Expected | Top 3 | Rank |", "|-------|-------|----------|----------|-------|------|"]
    for r in qa["T8"]["rows"]:
        L.append(f"| {r['query']} | {r['topic']} | {r['lang']} | {', '.join(r['expected'])} | {', '.join(r['top3'])} | {r['rank']} |")
    L += ["", "## T7 coverage matrix (needs and the entries that serve them)", ""]
    for topic, m in qa["T7"]["matrix"].items():
        L += [f"### {topic}", "", "| Need | Entries |", "|------|---------|"]
        for need, ids in m.items():
            L.append(f"| {need} | {', '.join(ids)} |")
        L.append("")
    L += ["## Known gaps (not covered by the four sources)", ""]
    for topic, gaps in qa["T7"]["known_gaps"].items():
        L.append(f"- {topic}:")
        for g in gaps:
            L.append(f"  - {g}")
    L += ["", "## Content read but left out", "", "| Where | What | Why |", "|-------|------|-----|"]
    for w, what, why in EXCLUSIONS:
        L.append(f"| {w} | {what} | {why} |")
    if qa.get("selftest"):
        caught = sum(1 for _, c in qa["selftest"] if c)
        L += ["", "## Do the tests catch mistakes?", "",
              f"qa_kb.py --selftest injects known faults into a copy of the entries. {caught} of {len(qa['selftest'])} were caught.", "",
              "| Injected fault | Caught |", "|----------------|--------|"]
        for name, c in qa["selftest"]:
            L.append(f"| {name} | {'yes' if c else 'NO'} |")
    L += ["", "## Iteration log", "",
          "- First run: T1 failed on 2 anchors (both were misquoted, the source wording differed from what had been written), T5 flagged 5 entries (1 too short, 4 caused by a reference pattern that matched ordinary words such as 'above' and 'section loss'). The entries and the pattern were corrected.",
          "- First retrieval proxy run: hit@1 0.76, hit@3 0.92, hit@5 0.97, MRR 0.85 on 38 queries. Misses came from a stemmer that did not match 'mudslide' with 'mudslides' (a flaw in the test tool) and from wording such as 'going back into a house'. The stemmer was fixed and one fire entry was reworded in plain language.",
          "- Number check was first run against the whole page and missed a faked 2.5 because 'Section 2.5' is on the same page. It now looks only near the anchors, and the injected fault is caught.",
          ""]
    open(os.path.join(out, "QA_REPORT.md"), "w", encoding="utf-8").write("\n".join(L))


def write_readme(out, qa):
    c = qa["counts"]["by_topic"]
    L = ["# DisasterAI knowledge base v1", "",
         f"Three md files, one per incident type: flood.md ({c.get('flood', 0)} entries), structural.md ({c.get('structural', 0)}), fire.md ({c.get('fire', 0)}). "
         "Each entry is one self-contained piece of guidance with its source and PDF page, ready to be a retrieval chunk.", "",
         "## Read this first", "",
         "- Sources are the four documents the team selected. None is Tunisian. They come from the United States (Red Cross, FEMA) and France.",
         "- fire.md is limited. No fire document was supplied, so it holds only what FEMA P-2055 says about buildings after a fire and about smoke. "
         "It has no wildfire evacuation or prevention guidance. FI-01 says so, and the assistant must not invent that guidance. Add wildfire sources to fix this.",
         "- structural.md is written for building safety evaluators and the cordon material is for earthquakes. Entries are tagged professional or public. ST-25 states the limit.",
         "- Where sources differ, a reconciliation entry shows both positions and the stricter safety action (FL-12, FL-13, FL-14, FL-22, ST-07, FI-05). See QA_REPORT.md.",
         "- Sentences written by the team, not by a source, are marked 'Team note' in the files and listed in entries.json.",
         "- Phone numbers, websites and national services were removed on purpose. The assistant must not present a foreign number or institution as Tunisian.", "",
         "## Files", "",
         "- flood.md, structural.md, fire.md: the knowledge base",
         "- entries.json: every entry with source, PDF page and the verbatim anchor phrases used in the provenance test",
         "- QA_REPORT.md and qa_results.json: test results, coverage, gaps, exclusions",
         "- SOURCES_USED.md: the four documents",
         "- tools/: scripts that rebuild and test everything (needs the four PDFs, pdftotext, tesseract)", "",
         "## Use in the RAG service", "",
         "Copy flood_kb.md, structural_kb.md and fire_kb.md from rag/corpus/en and rag/corpus/fr (generated by build_kb.py) so the loader gets the language from the folder and the topic from the file name. "
         "The heading of each entry carries its id (for example FL-04), so a citation can name the entry.", "",
         "## Rebuild and re-test", "",
         "python tools/qa_kb.py --sources-dir <folder with the 4 PDFs> --cache-dir <cache> --out <qa folder> --selftest",
         "python tools/build_kb.py --qa-dir <qa folder> --out <output folder> [--corpus-dir rag/corpus]", ""]
    open(os.path.join(out, "README.md"), "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    main()
