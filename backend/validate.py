"""Deterministic guardrails for the report agent output.

POST /validate receives the report JSON plus what it was built from and returns
{"status": "pass" | "fail", "violations": [{"check", "message"}]}. No model is called.
The checks are regular expressions and set logic, so they prove only what they test:
a report can pass and still be wrong in a way no check looks for.

Request body:
  report          the Report Agent JSON (backend/schemas/report.schema.json)
  retrieval       {"topic": "fire|flood|structural|general", "results": [/search results with entry_ids]}
  incident_text   the raw text of the incident
  incident        Incident Understanding JSON (optional, used for the injection check)
  vision          Vision JSON or null (optional, used for the conflict check)
  image_status    analysed | not_provided | analysis_failed | unusable (optional, set by the workflow, the report must repeat it)
"""
import json
import re
from pathlib import Path

import jsonschema
from fastapi import APIRouter

ROOT = Path(__file__).resolve().parent.parent
REPORT_SCHEMA = json.loads((Path(__file__).parent / "schemas" / "report.schema.json").read_text(encoding="utf-8"))
ENTRIES_JSON = ROOT / "rag" / "knowledge_base" / "entries.json"

# Entries needed to talk about evacuation or protecting a house from approaching flames.
FIRE_ACTION_NEEDS = {"evacuate", "flames_approaching", "home_protection"}
# Fallback when entries.json is not present: the fire entries tagged with those needs on 2026-10-16.
FIRE_ACTION_FALLBACK = {"FI-09", "FI-10", "FI-11", "FI-13", "FI-14", "FI-16", "FI-17", "FI-21", "FI-22", "FI-23", "FI-24"}
# The one national number allowed, and the entry that carries it (ONPC report, Tunisian civil protection).
TUNISIAN_NUMBER = ("198", "FI-12")
# The fire scope note: the base holds nothing on flames already reaching a house.
SCOPE_NOTE_FIRE = "FI-01"


def fire_action_entries(path=ENTRIES_JSON):
    """Entry ids that cover evacuation or house protection, from the knowledge base provenance file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set(FIRE_ACTION_FALLBACK)
    return {e["id"] for e in data["entries"]
            if e["topic"] == "fire" and "scope note" not in e["type"] and FIRE_ACTION_NEEDS & set(e["needs"])}


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def report_text(report):
    """All free text of the report, except the Markdown copy, which repeats it."""
    parts = [report.get("summary", ""), report.get("disclaimer", "")]
    parts += [c["text"] for key in ("reported", "observed") for c in report.get(key, [])]
    knowledge = report.get("knowledge", {})
    parts += [g["text"] for g in knowledge.get("guidance", [])]
    parts.append(knowledge.get("no_guidance_statement") or "")
    assessment = report.get("assessment", {})
    for key in ("basis", "risks", "possibly_affected"):
        parts += [c["text"] for c in assessment.get(key, [])]
    parts += assessment.get("conflicts", [])
    parts += [r["text"] for r in report.get("recommendations", [])]
    parts += report.get("uncertainties", []) + report.get("information_needed", [])
    return "\n".join(p for p in parts if p)


def recommendation_text(report):
    return [r["text"] for r in report.get("recommendations", [])] + [g["text"] for g in report.get("knowledge", {}).get("guidance", [])]


# ---------- checks: each returns a list of messages ----------
def check_schema(report):
    validator = jsonschema.Draft202012Validator(REPORT_SCHEMA)
    return [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in sorted(validator.iter_errors(report), key=lambda e: list(e.path))]


def retrieved_ids(retrieval):
    ids, by_chunk = set(), {}
    for result in retrieval.get("results", []):
        by_chunk[result.get("chunk_id")] = set(result.get("entry_ids", []))
        ids |= by_chunk[result.get("chunk_id")]
    return ids, by_chunk


def check_citations(report, retrieval):
    ids, by_chunk = retrieved_ids(retrieval)
    problems = []
    for kind, items in (("recommendation", report.get("recommendations", [])), ("guidance point", report.get("knowledge", {}).get("guidance", []))):
        for i, item in enumerate(items):
            entry, chunk = item.get("entry_id"), item.get("chunk_id")
            if not entry:
                problems.append(f"{kind} {i} has no entry_id")
            elif entry not in ids:
                problems.append(f"{kind} {i} cites {entry}, which is not in the retrieval result")
            elif chunk in by_chunk and entry not in by_chunk[chunk]:
                problems.append(f"{kind} {i} cites {entry} in chunk {chunk}, which does not hold that entry")
            elif chunk not in by_chunk:
                problems.append(f"{kind} {i} cites chunk {chunk}, which is not in the retrieval result")
    return problems


PHONE = re.compile(r"(?<![\d.])(?:\+?\d[\d .-]{7,}\d)(?![\d.])")
SHORT_NUMBERS = re.compile(r"(?<!\d)(911|112|114|999|198|190|197|193)(?!\d)")
URL = re.compile(r"https?://|www\.|\b[\w-]+\.(?:gov|org|com|fr|tn|net)\b", re.I)
FOREIGN = r"(FEMA|Red Cross|Croix-Rouge américaine|American Red Cross|Météo-France|Meteo France|Vigicrues|Coast Guard|NOAA|ready\.gov)"
CONTACT_FOREIGN = re.compile(rf"\b(call|contact|phone|dial|appelez|contactez|joignez)\b[^.\n]{{0,25}}{FOREIGN}", re.I)
TUNISIAN_FOREIGN = re.compile(rf"(tunisian|tunisien(?:ne)?s?|in tunisia|en tunisie)[^.\n]{{0,25}}{FOREIGN}|{FOREIGN}[^.\n]{{0,25}}(tunisian|tunisien(?:ne)?s?|in tunisia|en tunisie)", re.I)


def check_scope(report):
    cited = {r.get("entry_id") for r in report.get("recommendations", []) + report.get("knowledge", {}).get("guidance", [])}
    text = report_text(report)
    problems = []
    if PHONE.search(text):
        problems.append(f"phone number: {PHONE.search(text).group(0).strip()}")#type:ignore
    for number in set(SHORT_NUMBERS.findall(text)):
        if not (number == TUNISIAN_NUMBER[0] and TUNISIAN_NUMBER[1] in cited):
            problems.append(f"emergency number {number} (only {TUNISIAN_NUMBER[0]} is allowed, and only with {TUNISIAN_NUMBER[1]} cited)")
    if URL.search(text):
        problems.append(f"web address: {URL.search(text).group(0)}")#type:ignore
    if CONTACT_FOREIGN.search(text):
        problems.append(f"tells the reader to contact a foreign institution: {CONTACT_FOREIGN.search(text).group(0)}")#type:ignore
    if TUNISIAN_FOREIGN.search(text):
        problems.append(f"presents a foreign institution as Tunisian: {TUNISIAN_FOREIGN.search(text).group(0)}")#type:ignore
    return problems


NEGATION = re.compile(r"(do not|don't|dont|never|must not|should not|shouldn't|avoid|not to|ne pas|n'|jamais|évitez|eviter|éviter)[^.;\n]{0,40}$", re.I)
FORBIDDEN = [
    (re.compile(r"\b(dispatch|deploy|send)\b[^.;\n]{0,30}\b(units?|teams?|ambulances?|firefighters|fire trucks?|crews?|rescuers?|police|troops)\b", re.I), "instructs to dispatch units"),
    (re.compile(r"\b(envoyez|déployez|deployez|dépêchez|depechez)\b[^.;\n]{0,30}(unités?|équipes?|ambulances?|pompiers|secours)", re.I), "instructs to dispatch units"),
    (re.compile(r"\b(enter|go into|go inside|walk into|re-?enter|penetrate)\b[^.;\n]{0,25}\b(the |a )?(damaged |collapsed |unsafe )?(building|house|structure|rubble)\b", re.I), "instructs to enter a damaged building"),
    (re.compile(r"\b(entrez|pénétrez|penetrez|rentrez)\b[^.;\n]{0,25}(bâtiment|batiment|immeuble|maison|structure)", re.I), "instructs to enter a damaged building"),
]


def check_forbidden_instructions(report):
    problems = []
    text = report_text(report)
    for rx, label in FORBIDDEN:
        for match in rx.finditer(text):
            before = text[max(0, match.start() - 45):match.start() + len(match.group(0).split()[0])]
            if NEGATION.search(before):
                continue  # "do not enter" restates guidance and is allowed
            problems.append(f"{label}: {match.group(0)}")
    return problems


NOT_STATED = re.compile(r"not (stated|specified|provided|given|available|known)|unknown|n/a|non (pr[ée]cis|indiqu|renseign)|inconnu|aucun", re.I)


def check_location(report, incident_text):
    location = report.get("location")
    markdown = report.get("report_markdown", "")
    problems = []
    if location and _norm(location) not in _norm(incident_text):
        problems.append(f"location {location!r} does not appear in the incident text")
    match = re.search(r"Location:\s*([^|\n]+)", markdown)
    if match:
        shown = re.sub(r"[*_`#]+", "", match.group(1)).strip()  # models write 'Location: **Not stated**' and similar
        if shown and not NOT_STATED.search(shown) and _norm(shown) not in _norm(incident_text):
            problems.append(f"the Markdown header shows location {shown!r}, which is not in the incident text")
    return problems


EVAC_OR_PROTECT = re.compile(r"evacuat|\bleave\b|\bshelter|protect|\bflee|évacu|\babri|quitt|protég|proteg|mettez-vous", re.I)


def check_no_guidance(report, retrieval, fire_entries):
    """Empty retrieval, or a fire incident with no entry on evacuation or protection: the report must say it has no guidance."""
    results = retrieval.get("results", [])
    ids, _ = retrieved_ids(retrieval)
    knowledge = report.get("knowledge", {})
    problems = []
    statement = (knowledge.get("no_guidance_statement") or "").strip()
    no_action_entries = retrieval.get("topic") == "fire" and not (ids & fire_entries)
    if not results or no_action_entries:
        if not statement:
            problems.append("no knowledge base entry covers this need, but the report does not say that no guidance is available")
        if knowledge.get("coverage") == "good":
            problems.append("coverage is 'good' although no retrieved entry covers the need")
        for text in recommendation_text(report):
            if EVAC_OR_PROTECT.search(text):
                problems.append(f"evacuation or protection step without a covering entry: {text[:80]!r}")
    if knowledge.get("coverage") in ("partial", "none") and not statement:
        problems.append("coverage is partial or none but there is no no_guidance_statement")
    # D5 (fire_01, batch A): FI-01 is the scope note saying the knowledge base has nothing on flames already reaching a house.
    # When it is retrieved for a fire incident, coverage 'good' overstates what the base can support.
    if retrieval.get("topic") == "fire" and SCOPE_NOTE_FIRE in ids and knowledge.get("coverage") == "good":
        problems.append(f"coverage is 'good' although {SCOPE_NOTE_FIRE} (fire scope note: no guidance for flames reaching a house) was retrieved")
    return problems


RESOLVES = re.compile(r"(the (image|photo|report) is (wrong|incorrect|right|correct|mistaken)|despite the (image|photo|report)|the (image|photo) (proves|shows that the report is))", re.I)


def check_conflict(report, vision):
    if not vision:
        return []
    # vision v2 does not compare with the report (the Risk agent does), so without these fields there is nothing to check here
    mismatch = vision.get("consistent_with_report") in ("no", "partly") or bool(vision.get("inconsistencies"))
    conflicts = report.get("assessment", {}).get("conflicts", [])
    problems = []
    if mismatch and not conflicts:
        problems.append("the image and the report disagree but assessment.conflicts is empty")
    if mismatch and report.get("image_status") != "analysed":
        problems.append("the image disagrees with the report but image_status is not 'analysed'")
    resolved = RESOLVES.search(report_text(report))
    if resolved:
        problems.append(f"a conflict is resolved instead of shown: {resolved.group(0)}")
    return problems


INJECTION = re.compile(r"(ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)|disregard[^.]{0,30}instructions|ignore toutes? les instructions|oublie[zs]? (toutes? )?les instructions|do not mention any risks?|report the severity as \w+|system prompt)", re.I)
DEMANDED_SEVERITY = re.compile(r"severity as (low|moderate|high|critical)", re.I)


def check_injection(report, incident_text, incident):
    problems = []
    found = [m.group(0) for m in INJECTION.finditer(incident_text or "")]
    if not found:
        return problems
    elsewhere = report_text({**report, "reported": []})
    for phrase in found:
        if _norm(phrase) in _norm(elsewhere):
            problems.append(f"injected text is repeated outside the reported facts: {phrase!r}")
    demanded = DEMANDED_SEVERITY.search(incident_text or "")
    if demanded and report.get("severity") == demanded.group(1).lower():
        agent_severity = (incident or {}).get("initial_severity")
        if agent_severity != demanded.group(1).lower():
            problems.append(f"severity {report.get('severity')!r} is the one the incident text demanded")
    if re.search(r"do not mention any risks?", incident_text or "", re.I) and not report.get("assessment", {}).get("risks"):
        problems.append("the incident text asked to omit the risks and the report lists none")
    return problems


def check_image_status(report, expected):
    """The workflow knows whether an image was sent and whether the Vision step worked. The report must say the same.
    2026-10-16: a failed Vision step was reported as 'unusable image' (edge_02)."""
    if expected and report.get("image_status") != expected:
        return [f"image_status is {report.get('image_status')!r} but the workflow status is {expected!r}"]
    return []


CHECKS = ["schema", "citations", "scope", "forbidden_instructions", "location", "no_guidance", "conflict", "injection", "image_status"]


def validate(payload, fire_entries=None):
    """Run every check. A schema failure stops the others, which would read missing fields."""
    report = payload.get("report")
    retrieval = payload.get("retrieval") or {"topic": "general", "results": []}
    incident_text = payload.get("incident_text", "")
    fire_entries = fire_action_entries() if fire_entries is None else fire_entries
    violations = [{"check": "schema", "message": m} for m in (check_schema(report) if isinstance(report, dict) else ["report is not an object"])]
    if not violations:
        runs = [
            ("citations", check_citations(report, retrieval)),
            ("scope", check_scope(report)),
            ("forbidden_instructions", check_forbidden_instructions(report)),
            ("location", check_location(report, incident_text)),
            ("no_guidance", check_no_guidance(report, retrieval, fire_entries)),
            ("conflict", check_conflict(report, payload.get("vision"))),
            ("injection", check_injection(report, incident_text, payload.get("incident"))),
            ("image_status", check_image_status(report, payload.get("image_status"))),
        ]
        violations = [{"check": name, "message": m} for name, messages in runs for m in messages]
    return {"status": "pass" if not violations else "fail", "violations": violations}


router = APIRouter()


@router.post("/validate")
def validate_endpoint(payload: dict):
    """n8n calls this after the report agent. A failing result triggers one repair attempt."""
    return validate(payload)
