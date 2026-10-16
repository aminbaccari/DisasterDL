"""MOCK of the Gemini generateContent endpoint, for offline tests of contracts, schemas and /validate.

Everything this module returns is canned or built by simple templates from the request. It is NOT a language model.
Any result obtained with it must be labelled MOCK. It proves plumbing (request format, JSON shapes, guardrails),
and says nothing about model quality.

Use as a library:   mock_agent("incident", user_text) -> str (JSON or Markdown)
Use as a server:    python -m backend.mock_gemini --port 8020
                    POST /v1beta/models/<any>:generateContent with the same body the n8n nodes send.
"""
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCIDENT_DIR = ROOT / "eval" / "incidents"

# Which agent is calling: a phrase from its system prompt.
SIGNATURES = [
    ("Incident Understanding Agent", "incident"),
    ("Vision Agent", "vision"),
    ("You write search queries", "rag_queries"),
    ("Knowledge Agent", "knowledge"),
    ("Risk Assessment Agent", "risk"),
    ("Report Agent", "report"),
]

NO_GUIDANCE = {
    "en": "No guidance available in the knowledge base for this point. Follow the instructions of the authorities and emergency services.",
    "fr": "Aucune consigne disponible dans la base de connaissances sur ce point. Suivez les instructions des autorités et des services de secours.",
}
DISCLAIMER = {
    "en": "This report is a decision-support output from an AI prototype. It does not replace emergency services and is not an official emergency decision. The severity scale is a working scale of this prototype.",
    "fr": "Ce rapport est une aide à la décision produite par un prototype d'IA. Il ne remplace pas les services d'urgence et ne constitue pas une décision officielle. L'échelle de gravité est une échelle de travail de ce prototype.",
}


def _incident(id_, type_, loc, facts, severity, reason, risk_flag, missing, lang, topic, notes=None, conf="high"):
    return {"incident_type": type_, "type_confidence": conf, "location": {"text": loc, "precision": "area" if loc else "unknown"},
            "reported_facts": facts, "initial_severity": severity, "severity_reason": reason, "people_at_risk_mentioned": risk_flag,
            "missing_information": missing, "language": lang, "rag_topic": topic, "notes": notes}


# Canned Incident Understanding outputs for the six fixed incidents, written by hand from the incident texts.
INCIDENT_OUT = {
    "fire_01": _incident("fire_01", "forest_fire", None,
                         ["Smoke rising from the hills behind the village", "Flames visible near the first houses", "Strong wind blowing toward the village"],
                         "high", "Flames reported near the first houses with a wind blowing toward the village", "unknown",
                         ["Exact location", "Distance between the flames and the houses", "Whether an evacuation has started", "Whether people are trapped or injured"], "en", "fire"),
    "flood_01": _incident("flood_01", "flood", "Nabeul",
                          ["Fortes inondations dans un quartier résidentiel de Nabeul", "Plusieurs routes sont bloquées", "L'eau continue de monter"],
                          "high", "Routes bloquées et eau qui monte dans un quartier résidentiel", "unknown",
                          ["Hauteur d'eau", "Nombre de personnes touchées", "Débit du courant"], "fr", "flood"),
    "structural_01": _incident("structural_01", "structural_emergency", None,
                               ["Part of a five-storey apartment building has collapsed", "Dust covers the street", "Neighbours say some residents may still be inside (second-hand, unconfirmed)"],
                               "critical", "Partial collapse with possibly trapped residents, reported second-hand", "yes",
                               ["Exact location", "Number of residents possibly inside", "Extent of the damage", "Gas or fire hazards"], "en", "structural"),
    "edge_01_vague": _incident("edge_01_vague", "unclear", "près du port",
                               ["Un problème grave est signalé près du port"], "unknown", "Le rapport ne dit pas ce qui s'est passé", "unknown",
                               ["Type d'incident", "Y a-t-il des personnes en danger", "Lieu précis"], "fr", "general", notes="Rapport trop vague pour classer", conf="low"),
    "edge_02_conflict": _incident("edge_02_conflict", "flood", None,
                                  ["Flooding on the main road", "Water is rising quickly"], "high", "Water reported rising quickly on a main road", "unknown",
                                  ["Exact location", "Water depth", "Number of people affected"], "en", "flood"),
    "edge_03_injection": _incident("edge_03_injection", "forest_fire", None,
                                   ["A grass fire is spreading toward a farm"], "high", "Fire reported spreading toward a farm", "unknown",
                                   ["Exact location", "Wind direction and speed", "Whether people are at the farm"], "en", "fire",
                                   notes="The report also contains an instruction addressed to the assistant. It was treated as text, not followed."),
}

VISION_OUT = {
    "fire_01": {"image_usable": True, "quality_issues": [], "scene_summary": "Hillside with a smoke column above vegetation and a few houses in the foreground.",
                "observations": [{"category": "smoke", "description": "A dense smoke column rising from the hillside", "confidence": "high"},
                                 {"category": "flames", "description": "Orange flames at the base of the smoke, on the slope", "confidence": "medium"},
                                 {"category": "infrastructure", "description": "Several houses at the foot of the slope", "confidence": "high"}],
                "visible_text": [], "consistent_with_report": "yes", "inconsistencies": [],
                "not_determinable": ["Wind speed and direction", "Distance between the flames and the houses", "Number of people", "Cause of the fire"]},
    "flood_01": {"image_usable": True, "quality_issues": [], "scene_summary": "Rue résidentielle recouverte d'eau.",
                 "observations": [{"category": "flood_water", "description": "Eau brunâtre couvrant la chaussée", "confidence": "high"},
                                  {"category": "vehicles", "description": "Une voiture partiellement dans l'eau", "confidence": "medium"}],
                 "visible_text": [], "consistent_with_report": "yes", "inconsistencies": [],
                 "not_determinable": ["Hauteur d'eau", "Nombre de personnes", "Sens du courant"]},
    "structural_01": {"image_usable": True, "quality_issues": [], "scene_summary": "Façade d'un immeuble partiellement effondrée avec poussière dans la rue.",
                      "observations": [{"category": "structural_damage", "description": "Partie de la façade et des étages effondrée", "confidence": "high"},
                                       {"category": "other", "description": "Poussière dans la rue", "confidence": "medium"}],
                      "visible_text": [], "consistent_with_report": "yes", "inconsistencies": [],
                      "not_determinable": ["Structural integrity of the rest of the building", "Number of people inside", "Gas leaks"]},
    "edge_02_conflict": {"image_usable": True, "quality_issues": [], "scene_summary": "A dry road with smoke on the horizon.",
                         "observations": [{"category": "smoke", "description": "Smoke on the horizon", "confidence": "medium"},
                                          {"category": "infrastructure", "description": "A dry road surface", "confidence": "high"}],
                         "visible_text": [], "consistent_with_report": "no",
                         "inconsistencies": ["The report says flooding but the image shows a dry road and smoke, no water"],
                         "not_determinable": ["Cause of the smoke", "Location"]},
}

QUERIES_OUT = {
    "en": {"queries": [{"text": "what to do when a hazard threatens people and buildings", "language": "en", "need": "safety actions"},
                       {"text": "evacuation when authorities give an order", "language": "en", "need": "evacuation"},
                       {"text": "consignes de sécurité pour les habitants", "language": "fr", "need": "safety actions"}]},
    "fr": {"queries": [{"text": "que faire quand le danger menace les habitants", "language": "fr", "need": "safety actions"},
                       {"text": "quand quitter les lieux et suivre les consignes", "language": "fr", "need": "evacuation"},
                       {"text": "what to do in an emergency before help arrives", "language": "en", "need": "safety actions"}]},
}
SEVERITY_FOR_RISK = {"unknown": "undetermined"}


def _between(text, tag):
    match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    return match.group(1) if match else ""


def _json(text, tag):
    raw = _between(text, tag)
    try:
        return json.loads(raw)
    except ValueError:
        return None


def incident_id_for(text):
    """Find the fixed incident whose text is in the request, or None."""
    for path in sorted(INCIDENT_DIR.glob("*.json")):
        incident = json.loads(path.read_text(encoding="utf-8"))
        if incident["text"].strip() and incident["text"].strip() in text:
            return incident["id"]
    return None


def mock_incident(user_text):
    key = incident_id_for(user_text)
    if key:
        return INCIDENT_OUT[key]
    return _incident("unknown", "unclear", None, [_between(user_text, "incident_report")[:200]], "unknown", "The report does not say enough", "unknown",
                     ["Type of incident", "Exact location"], "en", "general", notes="Mock: unrecognised text", conf="low")


def mock_vision(user_text):
    return VISION_OUT.get(incident_id_for(user_text)) or {"image_usable": False, "quality_issues": ["Mock: no canned image analysis for this text"],
                                                          "scene_summary": "", "observations": [], "visible_text": [], "consistent_with_report": "cannot_tell",
                                                          "inconsistencies": [], "not_determinable": []}


def mock_queries(user_text):
    incident = _json(user_text, "incident_json") or {}
    return QUERIES_OUT["fr" if incident.get("language") == "fr" else "en"]


def _first_sentence(chunk):
    """Passage text without its heading: the first sentence after 'ID Title. '."""
    text = re.sub(r"^(?:##\s*)?(?:FL|ST|FI)-\d{2}\s+[^.]*\.\s*", "", chunk.get("text", "")).strip()
    return (re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0] or text)[:240]


def mock_knowledge(user_text):
    incident = _json(user_text, "incident_json") or {}
    passages = _json(user_text, "retrieved_passages") or []
    if not passages:
        return {"relevant_guidance": [], "ignored_chunks": [], "coverage": "none", "gaps": ["No passages retrieved"]}
    guidance, used = [], set()
    for chunk in passages:
        if len(guidance) == 2:
            break
        entry = (chunk.get("entry_ids") or [None])[0]
        if entry and chunk["chunk_id"] not in used:
            used.add(chunk["chunk_id"])
            guidance.append({"point": _first_sentence(chunk), "citation": {"chunk_id": chunk["chunk_id"], "source": chunk["source"], "page": chunk.get("page", 1), "entry_id": entry}})
    topic = incident.get("rag_topic")
    gaps = ["What to do when flames are already reaching a house (no entry covers it)"] if topic == "fire" else []
    return {"relevant_guidance": guidance, "ignored_chunks": [c["chunk_id"] for c in passages if c["chunk_id"] not in used],
            "coverage": "partial" if gaps or not guidance else "good", "gaps": gaps}


def mock_risk(user_text):
    incident = _json(user_text, "incident_json") or {}
    vision = _json(user_text, "vision_json")
    knowledge = _json(user_text, "knowledge_json") or {"relevant_guidance": [], "gaps": []}
    severity = SEVERITY_FOR_RISK.get(incident.get("initial_severity"), incident.get("initial_severity", "undetermined"))
    basis = [{"statement": f, "source": "report"} for f in incident.get("reported_facts", [])[:3]]
    if vision and vision.get("image_usable"):
        basis += [{"statement": o["description"], "source": "image"} for o in vision.get("observations", [])[:1]]
    uncertainties = []
    if vision is None:
        uncertainties.append("No image was analysed")
    elif not vision.get("image_usable"):
        uncertainties.append("The image could not be used")
    if not knowledge.get("relevant_guidance"):
        uncertainties.append("No relevant guidance retrieved")
    uncertainties += knowledge.get("gaps", [])
    if not incident.get("location", {}).get("text"):
        uncertainties.append("Location not stated")
    return {
        "severity": severity, "severity_basis": basis,
        "main_risks": [{"risk": incident.get("severity_reason", ""), "basis": "Reported facts", "source": "report"}] if incident.get("incident_type") != "unclear" else [],
        "possibly_affected": [], "conflicts_between_sources": (vision or {}).get("inconsistencies", []),
        "considerations": [{"text": "Responders may wish to weigh: " + g["point"], "citation": g["citation"]} for g in knowledge.get("relevant_guidance", [])[:1]],
        "uncertainties": uncertainties, "information_needed": incident.get("missing_information", [])[:4],
    }


def mock_report(user_text):
    lang = "fr" if re.search(r"output_language:\s*fr", user_text) else "en"
    incident = _json(user_text, "incident_json") or {}
    vision = _json(user_text, "vision_json")
    knowledge = _json(user_text, "knowledge_json") or {"relevant_guidance": [], "gaps": [], "coverage": "none"}
    risk = _json(user_text, "risk_json") or {}
    location = incident.get("location", {}).get("text")
    guidance = [{"text": g["point"], "entry_id": g["citation"]["entry_id"], "chunk_id": g["citation"]["chunk_id"], "source": "knowledge_base"} for g in knowledge.get("relevant_guidance", [])]
    needs_statement = knowledge.get("coverage") in ("partial", "none") or bool(knowledge.get("gaps"))
    status = "not_provided" if vision is None else ("analysed" if vision.get("image_usable") else "unusable")
    report = {
        "language": lang, "location": location, "severity": risk.get("severity", "undetermined"),
        "summary": "; ".join(incident.get("reported_facts", [])[:2]) or ("Rapport trop vague." if lang == "fr" else "The report is too vague."),
        "reported": [{"text": f, "source": "report"} for f in incident.get("reported_facts", [])],
        "image_status": status,
        "observed": [{"text": o["description"], "confidence": o["confidence"], "source": "image"} for o in (vision or {}).get("observations", [])],
        "knowledge": {"coverage": knowledge.get("coverage", "none"), "guidance": guidance, "no_guidance_statement": NO_GUIDANCE[lang] if needs_statement else None},
        "assessment": {"basis": [{"text": b["statement"], "source": b["source"]} for b in risk.get("severity_basis", [])],
                       "risks": [{"text": r["risk"], "source": r["source"]} for r in risk.get("main_risks", [])],
                       "possibly_affected": [{"text": a["element"], "source": a["source"]} for a in risk.get("possibly_affected", [])],
                       "conflicts": risk.get("conflicts_between_sources", [])},
        "recommendations": [{"text": c["text"], "entry_id": c["citation"]["entry_id"], "chunk_id": c["citation"]["chunk_id"], "source": "knowledge_base"} for c in risk.get("considerations", [])],
        "uncertainties": risk.get("uncertainties", []), "information_needed": risk.get("information_needed", []), "disclaimer": DISCLAIMER[lang],
    }
    notes = "Aucune image fournie." if lang == "fr" else "No image was provided."
    report["report_markdown"] = (
        f"# Preliminary incident assessment\nIncident type: {incident.get('incident_type')} | Location: {location or 'Not stated'} | Severity (system assessment): {report['severity']}\n\n"
        f"## Summary\n{report['summary']}\n\n## 2. What was observed in the image\n{'; '.join(o['text'] for o in report['observed']) or notes}\n\n"
        f"## 3. Relevant information from the knowledge base\nCoverage: {report['knowledge']['coverage']}\n"
        + "".join(f"- {g['text']} ({g['entry_id']})\n" for g in guidance) + (NO_GUIDANCE[lang] + "\n" if needs_statement else "")
        + f"\n## About this report\n{DISCLAIMER[lang]}\n")
    return report


AGENTS = {"incident": mock_incident, "vision": mock_vision, "rag_queries": mock_queries, "knowledge": mock_knowledge, "risk": mock_risk, "report": mock_report}


def mock_agent(agent, user_text):
    """Canned or templated answer of one agent, as the text the model would return."""
    return json.dumps(AGENTS[agent](user_text), ensure_ascii=False)


def agent_for_system(system_text):
    for phrase, agent in SIGNATURES:
        if phrase in system_text:
            return agent
    return None


MODE = "normal"  # normal | invalid_json | http500 | bad_report | bad_report_always (set with --mode, to exercise the workflow failure paths)


def handle_generate(body):
    """Answer a generateContent request body like the Gemini API does (candidates[0].content.parts[0].text)."""
    system = "".join(p.get("text", "") for p in body.get("system_instruction", {}).get("parts", [])) if isinstance(body.get("system_instruction", {}).get("parts"), list) \
        else body.get("system_instruction", {}).get("parts", {}).get("text", "")
    user = "\n".join(p.get("text", "") for c in body.get("contents", []) for p in c.get("parts", []) if "text" in p)
    agent = agent_for_system(system)
    if agent is None:
        return {"error": {"code": 400, "message": "MOCK: unknown agent"}}
    if MODE == "http500":
        return {"error": {"code": 500, "message": "MOCK: simulated Gemini failure"}}
    text = mock_agent(agent, user)
    if MODE == "invalid_json":
        text = "Sorry, here is the answer: this is not JSON"
    elif agent == "report" and (MODE == "bad_report_always" or (MODE == "bad_report" and "<failed_checks>" not in user)):
        report = json.loads(text)
        report["location"] = "Sfax"  # invented place, /validate must catch it
        text = json.dumps(report, ensure_ascii=False)
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": {"mock": True}}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        answer = handle_generate(body)
        data = json.dumps(answer, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if "candidates" in answer else answer["error"]["code"])
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--mode", default="normal", choices=["normal", "invalid_json", "http500", "bad_report", "bad_report_always"])
    args = parser.parse_args()
    MODE = args.mode
    print(f"MOCK Gemini endpoint on http://localhost:{args.port} (not a language model)")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
