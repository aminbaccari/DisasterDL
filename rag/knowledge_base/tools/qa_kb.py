"""Quality and consistency tests for the DisasterAI knowledge base.

Usage:
  python qa_kb.py --sources-dir <folder with the 4 PDFs> --cache-dir <folder for extracted text> --out <report folder>

Tests (all are run, results are reported as they come out):
  T1 provenance      every anchor phrase is found on the cited PDF page (OCR for image-only pages)
  T2 numbers         every number in an entry text appears on the cited pages
  T3 consistency     topics that appear in two or more sources are either reconciled or declared as agreements
  T4 scope           no phone numbers, URLs or foreign-only institutions leak into the text
  T5 self-contained  length and no references to other places in the source
  T6 duplicates      near-duplicate entries
  T7 coverage        needs tags versus a checklist, known gaps reported
  T8 retrieval       lexical proxy (TF-IDF), hit@k and MRR on natural queries. Not the embedding model.
  T9 structure       ids, fields, language, audience
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict

from kb_data import ENTRIES, CONFLICTS, AGREEMENTS, TEAM_NOTES
from qa_queries import QUERIES
from sources_data import SOURCES


# ---------- text helpers ----------
def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"(\d)[.,](\d)", r"\1dec\2", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def numbers_in(s):
    return set(re.findall(r"\d+(?:dec\d+)?", norm(s)))


# ---------- source text ----------
UNVERIFIED = set()  # (source, page) pairs that could not be OCR-checked in this run (only with --allow-missing-ocr)


def load_pages(sources_dir, cache_dir, allow_missing_ocr=False):
    os.makedirs(cache_dir, exist_ok=True)
    pages = {}
    for key, meta in SOURCES.items():
        pdf = os.path.join(sources_dir, meta["file"])
        if not os.path.exists(pdf):
            sys.exit(f"missing source file: {pdf}")
        if meta.get("kind") == "web":  # saved web page: main text in a utf-8 file, treated as one page
            txt = open(pdf, encoding="utf-8").read()
            pages[key] = {"layout": [txt], "raw": [txt], "ocr": {}}
            continue
        layout = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout.split("\f")
        raw = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True, check=True).stdout.split("\f")
        if layout and not layout[-1].strip():
            layout = layout[:-1]
        if raw and not raw[-1].strip():
            raw = raw[:-1]
        d = {"layout": layout, "raw": raw, "ocr": {}}
        for p in meta["ocr_pages"]:
            cache = os.path.join(cache_dir, f"{key}_p{p}.ocr.txt")
            if os.path.exists(cache):
                d["ocr"][p] = open(cache, encoding="utf-8").read()
                continue
            if allow_missing_ocr and not (shutil.which("tesseract") and shutil.which("pdftoppm")):
                UNVERIFIED.add((key, p))
                continue
            png = os.path.join(cache_dir, f"{key}_p{p}")
            subprocess.run(["pdftoppm", "-r", "260", "-png", "-f", str(p), "-l", str(p), "-singlefile", pdf, png], check=True)
            txt = subprocess.run(["tesseract", png + ".png", "-", "--psm", "3"], capture_output=True, text=True).stdout
            open(cache, "w", encoding="utf-8").write(txt)
            d["ocr"][p] = txt
        pages[key] = d
    return pages


def page_norm(pages, src, page):
    d = pages[src]
    parts = []
    for kind in ("layout", "raw"):
        if page - 1 < len(d[kind]):
            parts.append(d[kind][page - 1])
    if page in d["ocr"]:
        parts.append(d["ocr"][page])
    return norm(" ".join(parts)), parts


def page_numbers(pages, src, page):
    # numbers from the page, computed per text variant so that tokens are real tokens
    d = pages[src]
    out = set()
    for kind in ("layout", "raw"):
        if page - 1 < len(d[kind]):
            out |= numbers_in(d[kind][page - 1])
    if page in d["ocr"]:
        out |= numbers_in(d["ocr"][page])
    return out


# ---------- tests ----------
def t1_provenance(pages):
    fails, n = [], 0
    for e in ENTRIES:
        for src, page, anchors in e["sources"]:
            if (src, page) in UNVERIFIED:
                continue
            ptxt, _ = page_norm(pages, src, page)
            for a in anchors:
                n += 1
                if norm(a) not in ptxt:
                    fails.append(f"{e['id']} {src} p{page}: anchor not found: {a!r}")
    return n, fails


def anchor_window_numbers(pages, src, page, anchors, width=500):
    """Numbers found within `width` characters of each anchor on the page (normalised text, all text variants)."""
    d = pages[src]
    variants = []
    for kind in ("layout", "raw"):
        if page - 1 < len(d[kind]):
            variants.append(norm(d[kind][page - 1]))
    if page in d["ocr"]:
        variants.append(norm(d["ocr"][page]))
    found = set()
    for a in anchors:
        na = norm(a)
        for v in variants:
            i = v.find(na)
            if i >= 0:
                found |= set(re.findall(r"\d+(?:dec\d+)?", v[max(0, i - width): i + len(na) + width]))
    return found


def t2_numbers(pages):
    """Every number in an entry must appear within 500 characters of one of the entry's anchors on the cited page.
    Document names such as FEMA P-2055-2 are not counted as numbers."""
    fails, n = [], 0
    for e in ENTRIES:
        allowed = set()
        if any((src, page) in UNVERIFIED for src, page, _ in e["sources"]):
            continue  # numbers cannot be checked without the OCR text
        for src, page, anchors in e["sources"]:
            allowed |= anchor_window_numbers(pages, src, page, anchors)
        text = re.sub(r"P-2055(-2)?", "", e["text"])
        text = re.sub(r"ATC-(20|45)(-1)?", "", text)
        for tok in sorted(numbers_in(text)):
            n += 1
            if tok not in allowed:
                fails.append(f"{e['id']}: number {tok.replace('dec', '.')} is not near any anchor on the cited pages")
    return n, fails


GROUPS = [  # (topic, group name, regex)
    ("flood", "vehicle", r"voiture|vehicle|\bdriv"),
    ("flood", "light", r"candle|bougie|flashlight|lampe de poche|lantern"),
    ("flood", "utilities", r"electric|electricit|electrocut|\bgas\b|\bgaz\b"),
    ("flood", "stay_go", r"evacuat|shelter|\babri\b|higher ground|\betage\b|upper floor"),
    ("flood", "mold", r"\bmold\b"),
    ("flood", "co", r"carbon monoxide"),
    ("flood", "contamination", r"contaminat|blackwater|sewage"),
    ("structural", "cordon_distance", r"1\.5|hinge|cordon distance"),
    ("fire", "smoke_shelter", r"stay indoors|shelter in place|shelter-in-place"),
    ("fire", "stay_go_fire", r"evacuat|leave immediately|leave if|abri|shelter in a|sheltering in"),
    ("fire", "smoke_protection", r"n95|damp cloth|linge humide|respirator"),
    ("fire", "defensible_space", r"defensible|fire-resistant zone|30 feet|debroussaill|débroussaill|clear(ing)? (the )?vegetation"),
    ("fire", "return_after", r"return home|safe to return|go back|re-enter|retourner|se rendre sur les lieux|ne me rends pas"),
    ("fire", "report_fire", r"report (any )?smoke|signaler|l'alerte|you are trapped|call the emergency"),
]


def t3_consistency(pages):
    results, fails = [], []
    by_id = {e["id"]: e for e in ENTRIES}
    group_to_conflict = {c["group"]: cid for cid, c in CONFLICTS.items()}
    for topic, name, rx in GROUPS:
        members = [e for e in ENTRIES if e["topic"] == topic and re.search(rx, e["text"].lower()) and not e["meta"]]
        srcs = sorted({s[0] for e in members for s in e["sources"]})
        row = dict(group=name, topic=topic, entries=[e["id"] for e in members], sources=srcs, status="", detail="")
        if len(srcs) < 2:
            row["status"] = "single source"
        elif name in group_to_conflict:
            cid = group_to_conflict[name]
            c = CONFLICTS[cid]
            r = by_id.get(c["resolver"])
            problems = []
            if r is None:
                problems.append("resolver entry missing")
            else:
                if r["resolves"] != cid if "resolves" in r else True:
                    problems.append("resolver entry does not declare resolves=" + cid)
                low = r["text"].lower()
                for must in c["must_contain"]:
                    if must.lower() not in low:
                        problems.append(f"resolver text lacks {must!r}")
                rsrc = {s[0] for s in r["sources"]}
                need = {s[0] for e in members if e["id"] != r["id"] for s in e["sources"]}
                if name in ("vehicle", "light", "stay_go"):
                    pass  # source sets checked below with the explicit expectation
                missing = need - rsrc if name in ("light", "utilities", "vehicle", "stay_go", "cordon_distance") else set()
                if name == "stay_go":
                    missing = {"RC", "FALC"} - rsrc
                if name == "vehicle":
                    missing = {"RC", "FALC"} - rsrc
                if name == "light":
                    missing = {"RC", "FALC"} - rsrc
                if name == "utilities":
                    missing = {"RC", "FALC", "P2055"} - rsrc
                if name == "cordon_distance":
                    missing = {"P2055", "P2055-2"} - rsrc
                missing |= set(c.get("must_cite", [])) - rsrc
                if missing:
                    problems.append("resolver does not cite " + ", ".join(sorted(missing)))
            if name == "light":
                for e in members:
                    if e["id"] != c["resolver"] and re.search(r"candle|bougie", e["text"].lower()):
                        problems.append(f"{e['id']} mentions a candle outside the resolver")
            row["status"] = "reconciled" if not problems else "FAIL"
            row["detail"] = f"{cid}: {c['summary']}" + ("" if not problems else " | " + "; ".join(problems))
            if problems:
                fails.append(f"{name}: " + "; ".join(problems))
        elif name in AGREEMENTS:
            a = AGREEMENTS[name]
            problems = []
            for eid in a["entries"]:
                e = by_id[eid]
                for num in a["numbers"]:
                    for src, page, _ in e["sources"]:
                        if (src, page) in UNVERIFIED:
                            continue
                        if num not in page_numbers(pages, src, page):
                            problems.append(f"{eid}: {num} not on {src} p{page}")
                    if num not in numbers_in(e["text"]):
                        problems.append(f"{eid}: {num} missing from text")
            row["status"] = "agreement" if not problems else "FAIL"
            row["detail"] = a["summary"] + ("" if not problems else " | " + "; ".join(problems))
            if problems:
                fails.append(f"{name}: " + "; ".join(problems))
        else:
            row["status"] = "FAIL"
            row["detail"] = "appears in several sources with no reconciliation or agreement record"
            fails.append(f"{name}: appears in {srcs} with no record")
        results.append(row)
    # safety rule: any text telling people to stay indoors must carry the smoke-only caveat
    for e in ENTRIES:
        if re.search(r"stay indoors", e["text"].lower()) and "flames" not in e["text"].lower():
            fails.append(f"{e['id']}: stay-indoors advice without the flames caveat")
    return results, fails


BANNED = [
    (r"(?<!\d)(911|112|198|114)(?!\d)", "emergency number"),
    (r"1-800|800-\d{3}-\d{4}", "US phone number"),
    (r"https?://|www\.|\.gov\b|\.org\b|\.fr\b", "url"),
    (r"vigicrues|meteo-france|meteo france|coast guard|flood map|drra|stafford|\bibc\b|\bbric\b|good samaritan|\bahj\b|calbo", "foreign-only institution"),
]


def t4_scope():
    fails = []
    for e in ENTRIES:
        low = norm(e["text"]) if False else e["text"].lower()
        low2 = unicodedata.normalize("NFKD", low)
        low2 = "".join(c for c in low2 if not unicodedata.combining(c))
        tn_only = {s[0] for s in e["sources"]} == {"ONPC"}  # the Tunisian source: its own number 198 is kept
        for rx, label in BANNED:
            if re.search(rx, low2):
                if tn_only and label == "emergency number" and set(re.findall(rx, low2)) == {"198"}:
                    continue
                fails.append(f"{e['id']}: {label} found ({rx})")
        if re.search(r"tunisia", low2) and "does not apply in tunisia" not in low2 and not tn_only:
            fails.append(f"{e['id']}: mentions Tunisia without the disclaimer wording")
    return fails


REFERENCES = r"\b(see above|see below|see also|as mentioned|as noted|as described|ibid|figure \d|table \d|section \d|chapter \d)\b|\bvoir\b|ci-dessus|ci-dessous"
TOPIC_WORDS = {
    "flood": r"flood|inond|crue|water|eau",
    "structural": r"building|collapse|cordon|placard|explosion|gas|chemical|aftershock|earthquake|debris|falling|parapet",
    "fire": r"fire|burn|smoke|soot|wildfire|explosi|\bfeu|incendie|fum[ée]|flamme|braise",
}


def t5_self_contained():
    fails, lengths = [], []
    for e in ENTRIES:
        words = len(e["text"].split())
        lengths.append(words)
        if not 20 <= words <= 170:
            fails.append(f"{e['id']}: {words} words")
        if re.search(REFERENCES, e["text"].lower()):
            fails.append(f"{e['id']}: references another place ({re.search(REFERENCES, e['text'].lower()).group(0)})")
        if not re.search(TOPIC_WORDS[e["topic"]], e["text"].lower()):
            fails.append(f"{e['id']}: does not name its subject")
    return lengths, fails


def stem(w):
    return re.sub(r"(ing|ed|es|ez|er|e|s|x)$", "", w) if len(w) > 4 else w


def tokens(s):
    s = norm(s)
    return [stem(w) for w in s.split() if len(w) > 2]


def tfidf(docs):
    df = Counter()
    toks = [tokens(d) for d in docs]
    for t in toks:
        df.update(set(t))
    n = len(docs)
    idf = {w: (1 + __import__("math").log((1 + n) / (1 + c))) for w, c in df.items()}
    vecs = []
    for t in toks:
        tf = Counter(t)
        v = {w: (1 + __import__("math").log(c)) * idf[w] for w, c in tf.items()}
        nrm = sum(x * x for x in v.values()) ** 0.5 or 1
        vecs.append({w: x / nrm for w, x in v.items()})
    return vecs, idf


def cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0) for w, x in a.items())


ALLOWED_OVERLAP = {frozenset(p) for p in [
    ("FL-12", "FL-17"), ("FL-14", "FL-04"), ("FL-14", "FL-05"), ("FL-13", "FL-07"), ("FL-13", "FL-03"),
    ("ST-07", "ST-08"), ("ST-07", "ST-22"), ("ST-10", "ST-11"),
]}


def t6_duplicates():
    vecs, _ = tfidf([e["title"] + ". " + e["text"] for e in ENTRIES])
    pairs, fails = [], []
    for i in range(len(ENTRIES)):
        for j in range(i + 1, len(ENTRIES)):
            if ENTRIES[i]["lang"] != ENTRIES[j]["lang"]:
                continue
            c = cos(vecs[i], vecs[j])
            if c >= 0.35:
                pairs.append((round(c, 2), ENTRIES[i]["id"], ENTRIES[j]["id"]))
            if c >= 0.60 and frozenset((ENTRIES[i]["id"], ENTRIES[j]["id"])) not in ALLOWED_OVERLAP:
                fails.append(f"{ENTRIES[i]['id']} and {ENTRIES[j]['id']}: cosine {c:.2f}")
    return sorted(pairs, reverse=True), fails


REQUIRED_NEEDS = {
    "flood": ["before", "during", "after", "evacuate", "vehicle", "power", "gas", "health", "mold", "kit", "shelter",
              "roads_blocked", "rising_water", "vulnerable_people", "electrocution", "cleanup", "basement", "children"],
    "structural": ["cordon", "distance", "collapse", "trapped_people", "entry", "gas", "placard", "aftershock",
                   "building_safety", "falling_hazard", "limits", "explosion", "hazmat", "authority", "adjacent_buildings"],
    "fire": ["limits", "flames_approaching", "smoke", "shelter", "health", "after", "building_safety",
             "evacuate", "prevention", "defensible_space", "home_protection", "reporting", "tunisia_context", "return"],
}
KNOWN_GAPS = {
    "flood": ["what to do if water reaches the upper floor or you are trapped (no source gives it)",
              "Tunisian warning services and emergency numbers (no Tunisian source supplied)",
              "after-flood advice is in English only (the French source has none)"],
    "structural": ["search and rescue and what bystanders should do for trapped people (sources only say do not enter an obviously unsafe building and call emergency personnel from outside)",
                   "cordon distance for a tall building whose damage point is unknown",
                   "no French-language structural source, and cordon material is written for earthquakes"],
    "fire": ["what to do when flames are approaching and you cannot leave (the sources say leave when told and shelter in a cleared house until rescue, and give no further steps)",
             "no distance for the cleared zone in the French source, and Tunisian clearing rules are not covered",
             "Tunisian guidance is one news report of an ONPC communique (prevention and reporting only, no evacuation or protection steps), the original ONPC document was not found",
             "firefighting by residents is not covered by any source"],
}


def t7_coverage():
    fails, matrix = [], {}
    for topic, needs in REQUIRED_NEEDS.items():
        have = defaultdict(list)
        for e in ENTRIES:
            if e["topic"] == topic:
                for n in e["needs"]:
                    have[n].append(e["id"])
        matrix[topic] = {n: have.get(n, []) for n in needs}
        for n in needs:
            if not have.get(n):
                fails.append(f"{topic}: no entry for need {n!r}")
    return matrix, fails


def t8_retrieval():
    by_topic = defaultdict(list)
    for e in ENTRIES:
        by_topic[e["topic"]].append(e)
    rows, hits = [], Counter()
    rr = []
    for qid, topic, lang, q, expected in QUERIES:
        pool = by_topic[topic]
        docs = [e["title"] + ". " + e["text"] for e in pool]
        vecs, idf = tfidf(docs + [q])
        qv = vecs[-1]
        scored = sorted(((cos(qv, vecs[i]), pool[i]["id"]) for i in range(len(pool))), reverse=True)
        ranked = [s[1] for s in scored]
        rank = next((i + 1 for i, r in enumerate(ranked) if r in expected), None)
        for k in (1, 3, 5):
            if rank and rank <= k:
                hits[k] += 1
        rr.append(1 / rank if rank else 0)
        rows.append(dict(qid=qid, topic=topic, lang=lang, query=q, expected=expected, top3=ranked[:3], rank=rank))
    n = len(QUERIES)
    summary = {f"hit@{k}": round(hits[k] / n, 2) for k in (1, 3, 5)}
    summary["mrr"] = round(sum(rr) / n, 2)
    summary["n"] = n
    return rows, summary


def t9_structure():
    fails = []
    ids = [e["id"] for e in ENTRIES]
    for i, c in Counter(ids).items():
        if c > 1:
            fails.append(f"duplicate id {i}")
    for e in ENTRIES:
        for f in ("id", "lang", "title", "text", "sources", "needs", "audience"):
            if not e.get(f):
                fails.append(f"{e.get('id')}: missing {f}")
        src_langs = {SOURCES[s[0]]["lang"] for s in e["sources"]}
        if len(src_langs) == 1 and e["lang"] not in src_langs and not e["id"].startswith(("FL-23",)) and not e.get("translation_of"):
            fails.append(f"{e['id']}: language {e['lang']} but source language {src_langs}")
        if e.get("translation_of"):
            ref = next((x for x in ENTRIES if x["id"] == e["translation_of"]), None)
            if ref is None or ref["lang"] == e["lang"] or ref["sources"] != e["sources"] or ref["needs"] != e["needs"]:
                fails.append(f"{e['id']}: translation_of {e['translation_of']} is missing, in the same language, or has different sources or needs")
        if e["audience"] not in ("public", "professional"):
            fails.append(f"{e['id']}: bad audience")
        prefix = {"flood": "FL-", "structural": "ST-", "fire": "FI-"}[e["topic"]]
        if not e["id"].startswith(prefix):
            fails.append(f"{e['id']}: wrong prefix for topic {e['topic']}")
        for s in e["sources"]:
            if s[0] not in SOURCES:
                fails.append(f"{e['id']}: unknown source {s[0]}")
            elif SOURCES[s[0]].get("journalism") and "La Presse" not in e["text"]:
                fails.append(f"{e['id']}: cites a news report but the text does not say it is reported by La Presse")
    for eid, notes in TEAM_NOTES.items():
        e = next((x for x in ENTRIES if x["id"] == eid), None)
        if e is None:
            fails.append(f"team note for unknown entry {eid}")
            continue
        for n in notes:
            if n not in e["text"]:
                fails.append(f"{eid}: declared team note not in text: {n[:50]!r}")
    return fails


def selftest(pages):
    """Inject known faults and check that the tests catch them. Returns [(fault, caught)]."""
    import copy
    out = []

    def run(name, mutate, test, ocr_entry=None):
        if ocr_entry and any((s[0], s[1]) in UNVERIFIED for e in ENTRIES if e["id"] == ocr_entry for s in e["sources"]):
            out.append((name, None))  # the fault lives on an OCR-only page that could not be checked in this run
            return
        saved = copy.deepcopy(ENTRIES)
        by = {e["id"]: e for e in ENTRIES}
        mutate(by)
        caught = bool(test())
        ENTRIES[:] = saved
        out.append((name, caught))

    run("number changed (30 cm to 50 cm)", lambda by: by["FL-04"].update(text=by["FL-04"]["text"].replace("30", "50")), lambda: t2_numbers(pages)[1], ocr_entry="FL-04")
    run("cordon factor changed (1.5 to 2.5)", lambda by: by["ST-07"].update(text=by["ST-07"]["text"].replace("1.5", "2.5")), lambda: t2_numbers(pages)[1])
    run("anchor cited on the wrong page", lambda by: by["FL-04"].update(sources=[("RC", 2, by["FL-04"]["sources"][0][2])]), lambda: t1_provenance(pages)[1], ocr_entry="FL-04")
    run("invented sentence cited as anchor", lambda by: by["ST-03"]["sources"].append(("P2055", 29, ["all buildings must be evacuated within one hour"])), lambda: t1_provenance(pages)[1])
    run("emergency number injected", lambda by: by["FL-16"].update(text=by["FL-16"]["text"] + " Call 198."), lambda: t4_scope())
    run("url injected", lambda by: by["FL-16"].update(text=by["FL-16"]["text"] + " Visit www.redcross.org"), lambda: t4_scope())
    run("candle added to the kit entry", lambda by: by["FL-10"].update(text=by["FL-10"]["text"] + " Une bougie avec des allumettes."), lambda: t3_consistency(pages)[1])
    run("reconciliation entry loses a source", lambda by: by["FL-14"].update(sources=[by["FL-14"]["sources"][0]]), lambda: t3_consistency(pages)[1])
    run("stay-indoors advice without the flames caveat", lambda by: by["FI-05"].update(text=by["FI-05"]["text"].replace("flames", "fire")), lambda: t3_consistency(pages)[1])
    run("duplicate entry added", lambda by: ENTRIES.append(dict(by["FL-16"], id="FL-99")), lambda: t6_duplicates()[1])
    run("a required need removed (gas, structural)", lambda by: [e.update(needs=[n for n in e["needs"] if n != "gas"]) for e in ENTRIES if e["topic"] == "structural"], lambda: t7_coverage()[1])
    run("news report entry loses its La Presse attribution", lambda by: by["FI-12"].update(text=by["FI-12"]["text"].replace("La Presse", "la presse locale")), lambda: t9_structure())
    run("foreign emergency number 112 added to the Tunisian entry", lambda by: by["FI-12"].update(text=by["FI-12"]["text"] + " Appelez le 112."), lambda: t4_scope())
    run("number changed in a French translation (30 to 50)", lambda by: by["FI-23"].update(text=by["FI-23"]["text"].replace("30", "50")), lambda: t2_numbers(pages)[1])
    run("translation points to a missing entry", lambda by: by["FI-23"].update(translation_of="FI-99"), lambda: t9_structure())
    run("entry with a missing field", lambda by: by["ST-01"].update(audience=""), lambda: t9_structure())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources-dir", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-missing-ocr", action="store_true",
                    help="skip (and report) the OCR-only pages when tesseract or pdftoppm is not installed")
    ap.add_argument("--selftest", action="store_true", help="also inject known faults and check they are caught")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    pages = load_pages(args.sources_dir, args.cache_dir, args.allow_missing_ocr)
    res = {}
    n1, f1 = t1_provenance(pages)
    n2, f2 = t2_numbers(pages)
    r3, f3 = t3_consistency(pages)
    f4 = t4_scope()
    lengths, f5 = t5_self_contained()
    pairs, f6 = t6_duplicates()
    matrix, f7 = t7_coverage()
    rows8, sum8 = t8_retrieval()
    f9 = t9_structure()
    selftest_rows = selftest(pages) if args.selftest else []
    res.update(dict(
        T1=dict(checked=n1, fails=f1), T2=dict(checked=n2, fails=f2), T3=dict(groups=r3, fails=f3), T4=dict(fails=f4),
        T5=dict(min=min(lengths), max=max(lengths), mean=round(sum(lengths) / len(lengths), 1), fails=f5),
        T6=dict(similar_pairs=pairs, fails=f6), T7=dict(matrix=matrix, fails=f7, known_gaps=KNOWN_GAPS),
        T8=dict(rows=rows8, summary=sum8), T9=dict(fails=f9),
        selftest=selftest_rows, unverified_pages=sorted(f"{k} p{p}" for k, p in UNVERIFIED),
        counts=dict(entries=len(ENTRIES), by_topic=dict(Counter(e["topic"] for e in ENTRIES))),
    ))
    json.dump(res, open(os.path.join(args.out, "qa_results.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    total_fail = 0
    for k in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T9"):
        f = res[k]["fails"]
        total_fail += len(f)
        print(f"{k}: {'PASS' if not f else 'FAIL (' + str(len(f)) + ')'}")
        for x in f:
            print("   -", x)
    print("T3 groups:")
    for r in r3:
        print(f"   {r['topic']}/{r['group']}: {r['status']} {r['sources']}")
    print("T8 retrieval proxy:", sum8)
    for r in rows8:
        if not r["rank"] or r["rank"] > 3:
            print("   miss/low:", r["qid"], r["query"], "expected", r["expected"], "top3", r["top3"], "rank", r["rank"])
    if selftest_rows:
        ran = [(n, c) for n, c in selftest_rows if c is not None]
        print("selftest:", sum(c for _, c in ran), "of", len(ran), "injected faults caught,", len(selftest_rows) - len(ran), "skipped (OCR page unavailable)")
        for name, c in selftest_rows:
            if c is False:
                print("   NOT caught:", name)
    if UNVERIFIED:
        print("NOT re-verified in this run (no OCR available):", ", ".join(res["unverified_pages"]))
    print("entries:", res["counts"])
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
