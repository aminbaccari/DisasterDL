"""Generate the n8n workflow JSON from the versioned prompt files.

    python scripts/build_workflow.py                      # writes n8n/workflows/disasterai.json and disasterai_error.json
    python scripts/build_workflow.py --pace-seconds 13    # optional wait before every model call

The prompts in prompts/ stay the single source of truth: this script reads the system prompt and the user message
template of each agent from its markdown file and writes them into the nodes. The prompt file used by each agent is in
PROMPTS below and its version is recorded in the node names ("Prompt risk v2") and in the response (prompt_versions).
No API key is in the JSON, nor in n8n. Every model call goes to POST /llm of the RAG service (backend/llm_chain.py), which tries the models
listed in LLM_CHAIN in .env in order (Gemini, Groq, OpenRouter) and falls back on rate limits, server errors and unusable JSON.
"""
import argparse
import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# agent -> prompt file, relative to prompts/. Changing a version means changing this table and rebuilding.
PROMPTS = {
    "incident": "incident_understanding/v3.md",
    "vision": "vision/v1.md",
    "rag_queries": "rag_query/v1.md",
    "knowledge": "rag_query/v2_synthesis.md",
    "risk": "risk_assessment/v2.md",
    "report": "report/v4.md",
}
VERSIONS = {agent: re.search(r"v\d+", Path(path).stem).group(0) for agent, path in PROMPTS.items()}

# placeholders of the user message templates -> JavaScript expressions evaluated in the Set node of that agent
CTX = "$('Assemble context').first().json"
PLACEHOLDERS = {
    "incident": {"incident_text": "$('Normalise input').first().json.incident_text"},
    "vision": {"incident_text": "$('Normalise input').first().json.incident_text"},
    "rag_queries": {"incident_json": "JSON.stringify((({_degraded, ...r}) => r)($('Incident ready').first().json))"},
    "knowledge": {"incident_json": "JSON.stringify((({_degraded, ...r}) => r)($('Incident ready').first().json))",
                  "passages_json": "JSON.stringify($('Merge passages').first().json.passages)"},
    "risk": {"incident_json": f"JSON.stringify({CTX}.incident)", "vision_json_or_null": f"JSON.stringify({CTX}.vision)",
             "knowledge_json": f"JSON.stringify({CTX}.knowledge)"},
    "report": {"output_language": f"{CTX}.output_language", "generated_at": f"{CTX}.generated_at", "image_status": f"{CTX}.image_status",
               "incident_json": f"JSON.stringify({CTX}.incident)", "vision_json_or_null": f"JSON.stringify({CTX}.vision)",
               "knowledge_json": f"JSON.stringify({CTX}.knowledge)", "risk_json": "JSON.stringify($('Risk ready').first().json.risk)"},
}


# ---------- reading the prompt files ----------
def blocks(text):
    return re.findall(r"~~~\n(.*?)\n~~~", text, re.S)


def read_prompt(agent):
    """Return (system prompt, user template) from a prompt markdown file."""
    text = (ROOT / "prompts" / PROMPTS[agent]).read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n")
    system_part, _, user_part = text.partition("## User message template")
    system = blocks(system_part.partition("## System prompt")[2])[0]
    if "EXAMPLE1_JSON" in system:  # incident prompt: the two example lines are listed after the prompt
        for label in ("EXAMPLE1_JSON", "EXAMPLE2_JSON"):
            example = blocks(system_part.partition(f"{label}:")[2])[0]
            system = system.replace(label, example, 1)
    user = blocks(user_part)[0] if blocks(user_part) else ""
    return system, user


def user_expression(agent, template):
    """Turn '<incident_report>\\n{{incident_text}}\\n</incident_report>' into an n8n expression that concatenates JS values."""
    parts, last = [], 0
    for match in re.finditer(r"\{\{(\w+)\}\}", template):
        parts.append(json.dumps(template[last:match.start()]))
        parts.append("(" + PLACEHOLDERS[agent][match.group(1)] + ")")
        last = match.end()
    parts.append(json.dumps(template[last:]))
    return "={{ " + " + ".join(parts) + " }}"


# ---------- JavaScript used in the Code nodes ----------
READ_MODEL = r"""
// Text of a Gemini answer, or the reason it could not be read.
function readModel(j) {
  const tag = RETRIED ? '(after one retry) ' : '';
  if (j.error) return { err: tag + 'Gemini request failed: ' + String(j.error.message || JSON.stringify(j.error)).slice(0, 300) };
  let t;
  try { t = j.candidates[0].content.parts[0].text; } catch (e) {
    return { err: tag + 'no text in the Gemini answer' + (j.promptFeedback ? ' (' + JSON.stringify(j.promptFeedback).slice(0, 150) + ')' : '') };
  }
  t = String(t).trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  try { return { value: JSON.parse(t) }; } catch (e) { return { err: tag + 'invalid JSON from the model: ' + t.slice(0, 120) }; }
}
"""

NORMALISE = r"""
const item = $input.first();
const body = item.json.body || {};
const text = String(body.incident_text || '').trim();
const lang = String(body.output_language || 'en').trim().toLowerCase() === 'fr' ? 'fr' : 'en';
let image_b64 = null, image_mime = null, image_note = null;
const supported = ['image/png', 'image/jpeg', 'image/webp', 'image/heic', 'image/heif'];
if (item.binary && item.binary.image) {
  const mime = item.binary.image.mimeType;
  if (supported.includes(mime)) {
    const buf = await this.helpers.getBinaryDataBuffer(0, 'image');
    image_b64 = buf.toString('base64');
    image_mime = mime;
  } else {
    image_note = 'Unsupported image type: ' + mime;
  }
}
if (!image_b64 && !image_note && body.image) image_note = 'The image field arrived as text, not as a file: send the part with its own Content-Type (for example image/jpeg). The Vision step was skipped.';
const valid = text.length >= 3;
return [{ json: { valid, reason: valid ? null : 'incident_text is missing or too short', incident_text: text, output_language: lang,
  has_image: image_b64 !== null, image_b64, image_mime, image_note, generated_at: new Date().toISOString() } }];
"""

REJECT = r"""
const n = $input.first().json;
return [{ json: { status: 'rejected', error: n.reason, incident_type: null, severity: null, report_markdown: '', degraded_steps: [], prompt_versions: PV } }];
"""

PARSE_INCIDENT = READ_MODEL + r"""
const norm = $('Normalise input').first().json;
const ENUMS = {
  incident_type: ['forest_fire', 'flood', 'structural_emergency', 'other', 'unclear'],
  type_confidence: ['high', 'medium', 'low'],
  initial_severity: ['low', 'moderate', 'high', 'critical', 'unknown'],
  people_at_risk_mentioned: ['yes', 'no', 'unknown'],
  language: ['en', 'fr', 'ar', 'other'],
};
function problem(o) {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return 'the answer is not a JSON object';
  for (const [k, allowed] of Object.entries(ENUMS)) if (!allowed.includes(o[k])) return k + ' has an invalid value: ' + JSON.stringify(o[k]);
  if (!Array.isArray(o.reported_facts) || !Array.isArray(o.missing_information)) return 'reported_facts or missing_information is not a list';
  if (!o.location || typeof o.location !== 'object') return 'location is missing';
  return null;
}
const r = readModel($input.first().json);
let out = r.value, degraded = [];
const why = r.err || problem(out);
if (why) {
  degraded.push({ step: 'incident understanding', reason: why });
  out = { incident_type: 'unclear', type_confidence: 'low', location: { text: null, precision: 'unknown' }, reported_facts: [norm.incident_text],
    initial_severity: 'unknown', severity_reason: 'Fallback: the Incident Understanding step failed', people_at_risk_mentioned: 'unknown',
    missing_information: ['Everything: the report could not be analysed automatically'], language: norm.output_language, rag_topic: 'general', notes: null, parse_error: true };
}
// The topic follows the type by rule (prompts/README.md), whatever the model wrote.
out.rag_topic = { forest_fire: 'fire', flood: 'flood', structural_emergency: 'structural' }[out.incident_type] || 'general';
return [{ json: { ...out, _degraded: degraded, _failed: !!why } }];
"""

NEEDS_INFO = r"""
const inc = $input.first().json;
const norm = $('Normalise input').first().json;
const fr = norm.output_language === 'fr';
const missing = (inc.missing_information || []);
const image = norm.has_image
  ? (fr ? 'Image : une image a été reçue mais n\'a pas été analysée, le rapport est trop vague pour la comparer.' : 'Image: an image was received but not analysed, the report is too vague to compare it with.')
  : (fr ? 'Image : aucune image n\'a été fournie.' : 'Image: no image was provided.');
const search = fr ? 'Base de connaissances : aucune recherche effectuée, le type d\'incident n\'est pas clair.' : 'Knowledge base: no search was made, the incident type is unclear.';
const md = fr
  ? '# Informations supplémentaires nécessaires\n\nLe rapport ne permet pas de classer l\'incident ni d\'évaluer sa gravité. Aucune hypothèse n\'a été faite.\n\n' + image + '\n' + search + '\n\n' + missing.map(m => '- ' + m).join('\n')
  : '# More information needed\n\nThe report does not allow the incident to be classified or its severity to be assessed. Nothing was guessed.\n\n' + image + '\n' + search + '\n\n' + missing.map(m => '- ' + m).join('\n');
return [{ json: { status: inc.parse_error ? 'degraded' : 'needs_more_information', incident_type: inc.incident_type, severity: 'undetermined', report_markdown: md,
  missing_information: missing, report: null, validation: null, degraded_steps: inc._degraded || [], prompt_versions: PV } }];
"""

NO_IMAGE = r"""
const n = $('Normalise input').first().json;
return [{ json: { vision: null, vision_status: 'not_provided', vision_skipped: n.image_note || 'No image was provided', degraded_a: n.image_note ? [{ step: 'vision', reason: n.image_note }] : [] } }];
"""

PARSE_VISION = READ_MODEL + r"""
const CATS = ['smoke', 'flames', 'flood_water', 'structural_damage', 'infrastructure', 'vehicles', 'people', 'vegetation', 'other'];
function problem(o) {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return 'the answer is not a JSON object';
  if (typeof o.image_usable !== 'boolean') return 'image_usable is not a boolean';
  if (!Array.isArray(o.observations) || !Array.isArray(o.not_determinable) || ('inconsistencies' in o && !Array.isArray(o.inconsistencies))) return 'observations, not_determinable or inconsistencies is not a list';
  if ('consistent_with_report' in o && !['yes', 'partly', 'no', 'cannot_tell'].includes(o.consistent_with_report)) return 'consistent_with_report has an invalid value';
  if (o.observations.some(x => !CATS.includes(x.category) || !['high', 'medium', 'low'].includes(x.confidence))) return 'an observation has an invalid category or confidence';
  return null;
}
const r = readModel($input.first().json);
const why = r.err || problem(r.value);
if (why) {
  // The step failed: this is not an unusable image. vision stays null (nothing was analysed) and the status says why.
  return [{ json: { vision: null, vision_status: 'analysis_failed', degraded_a: [{ step: 'vision', reason: why }], _failed: true } }];
}
return [{ json: { vision: r.value, vision_status: r.value.image_usable ? 'analysed' : 'unusable', degraded_a: [], _failed: false } }];
"""

PARSE_QUERIES = READ_MODEL + r"""
const inc = $('Incident ready').first().json;
const r = readModel($input.first().json);
let queries = r.value && Array.isArray(r.value.queries) ? r.value.queries.filter(q => q && typeof q.text === 'string' && q.text.length > 2).slice(0, 3) : [];
const degraded = [];
if (!queries.length) {
  degraded.push({ step: 'RAG queries', reason: r.err || 'no usable queries in the answer; used the incident facts as the query' });
  queries = [{ text: (inc.reported_facts || []).join('. ').slice(0, 200), language: inc.language === 'fr' ? 'fr' : 'en', need: 'fallback' }];
}
return [{ json: { queries, degraded_b: degraded, _failed: degraded.length > 0 } }];
"""

SPLIT_QUERIES = r"""
const topic = $('Incident ready').first().json.rag_topic;
const q = $input.first().json.queries;
return q.map(x => ({ json: { query: x.text, topic } }));
"""

MERGE_PASSAGES = r"""
const topic = $('Incident ready').first().json.rag_topic;
const degraded = [...($('Queries ready').first().json.degraded_b || [])];
const best = {};
for (const item of $input.all()) {
  const j = item.json;
  if (j.error || !Array.isArray(j.results)) { degraded.push({ step: 'RAG search', reason: 'search failed: ' + String((j.error && j.error.message) || 'no results field').slice(0, 200) }); continue; }
  for (const r of j.results) if (!best[r.chunk_id] || r.score > best[r.chunk_id].score) best[r.chunk_id] = r;
}
const passages = Object.values(best).sort((a, b) => b.score - a.score).slice(0, 8);
return [{ json: { passages, retrieval: { topic, results: passages }, degraded_b: degraded } }];
"""

KNOWLEDGE_NONE = r"""
const topic = $('Incident ready').first().json.rag_topic;
const j = $input.first().json;
const reason = topic === 'general' ? 'No retrieval for this incident type' : ((j.degraded_b || []).some(d => d.step === 'RAG search') ? 'The knowledge base search failed' : 'No passages retrieved');
return [{ json: { knowledge: { relevant_guidance: [], ignored_chunks: [], coverage: 'none', gaps: [reason] },
  retrieval: { topic, results: [] }, degraded_b: j.degraded_b || [] } }];
"""

PARSE_KNOWLEDGE = READ_MODEL + r"""
const merged = $('Merge passages').first().json;
const entries = {};
for (const p of merged.passages) entries[p.chunk_id] = p.entry_ids || [];
const r = readModel($input.first().json);
const degraded = [...(merged.degraded_b || [])];
let k = r.value;
const bad = !k || typeof k !== 'object' || !Array.isArray(k.relevant_guidance) || !['good', 'partial', 'none'].includes(k.coverage) || !Array.isArray(k.gaps);
if (r.err || bad) {
  degraded.push({ step: 'knowledge synthesis', reason: r.err || 'the answer does not match the knowledge contract' });
  k = { relevant_guidance: [], ignored_chunks: [], coverage: 'none', gaps: ['The knowledge synthesis step failed'] };
} else {
  // A point is kept only if it cites an entry that the cited chunk really holds.
  const kept = k.relevant_guidance.filter(g => g && g.citation && (entries[g.citation.chunk_id] || []).includes(g.citation.entry_id));
  if (kept.length !== k.relevant_guidance.length) degraded.push({ step: 'knowledge synthesis', reason: (k.relevant_guidance.length - kept.length) + ' guidance point(s) removed: the cited entry is not in the cited chunk' });
  k.relevant_guidance = kept;
  if (!kept.length) k.coverage = 'none';
  // D5: FI-01 is the fire scope note (the base has nothing on flames already reaching a house). Coverage 'good' would overstate what it can support.
  // Cap it here, before the report agent writes, so that /validate does not have to send a complete report through the repair pass for it.
  const topic = $('Incident ready').first().json.rag_topic;
  const hasScopeNote = merged.passages.some(p => (p.entry_ids || []).includes('FI-01'));
  if (topic === 'fire' && hasScopeNote && k.coverage === 'good') {
    k.coverage = 'partial';
    k.gaps = [...(k.gaps || []), 'FI-01: the knowledge base has no guidance for flames that already reach a house'];
  }
}
return [{ json: { knowledge: k, retrieval: merged.retrieval, degraded_b: degraded, _failed: !!(r.err || bad) } }];
"""

ASSEMBLE = r"""
const m = $input.first().json;
const inc = $('Incident ready').first().json;
const norm = $('Normalise input').first().json;
const { _degraded, ...incident } = inc;
return [{ json: { incident, vision: m.vision === undefined ? null : m.vision, image_status: m.vision_status || 'not_provided', knowledge: m.knowledge, retrieval: m.retrieval,
  output_language: norm.output_language, generated_at: norm.generated_at, incident_text: norm.incident_text,
  degraded: [...(_degraded || []), ...(m.degraded_a || []), ...(m.degraded_b || [])] } }];
"""

PARSE_RISK = READ_MODEL + r"""
const ctx = $('Assemble context').first().json;
const ids = new Set(); const byChunk = {};
for (const p of ctx.retrieval.results) { byChunk[p.chunk_id] = p.entry_ids || []; for (const e of byChunk[p.chunk_id]) ids.add(e); }
const SEV = ['low', 'moderate', 'high', 'critical', 'undetermined'];
const r = readModel($input.first().json);
const degraded = [];
let risk = r.value;
const bad = !risk || typeof risk !== 'object' || !SEV.includes(risk.severity) || !Array.isArray(risk.considerations) || !Array.isArray(risk.uncertainties) || !Array.isArray(risk.conflicts_between_sources);
if (r.err || bad) {
  degraded.push({ step: 'risk assessment', reason: r.err || 'the answer does not match the risk contract' });
  risk = { severity: 'undetermined', severity_basis: [], main_risks: [], possibly_affected: [], conflicts_between_sources: [], considerations: [],
    uncertainties: ['The risk assessment step failed, no severity could be assessed'], information_needed: ctx.incident.missing_information || [] };
} else {
  const kept = risk.considerations.filter(c => c && c.citation && (byChunk[c.citation.chunk_id] || []).includes(c.citation.entry_id));
  if (kept.length !== risk.considerations.length) degraded.push({ step: 'risk assessment', reason: (risk.considerations.length - kept.length) + ' consideration(s) removed: the cited entry is not in the cited chunk' });
  risk.considerations = kept;
}
return [{ json: { risk, degraded_c: degraded, _failed: !!(r.err || bad) } }];
"""

PARSE_REPORT = READ_MODEL + r"""
const r = readModel($input.first().json);
if (r.err || !r.value || typeof r.value !== 'object' || Array.isArray(r.value)) {
  return [{ json: { report: null, degraded_d: [{ step: 'report', reason: r.err || 'the answer is not a JSON object' }], _failed: true } }];
}
return [{ json: { report: r.value, degraded_d: [], _failed: false } }];
"""

READY_JS = r"""
// Which model answered this step: from x_llm of the /llm call that produced the parsed result.
const j = $input.first().json;
const retried = $('LLM: LABEL (retry)').isExecuted;
const call = $(retried ? 'LLM: LABEL (retry)' : 'LLM: LABEL').first().json;
const x = call.x_llm || null;
j._llm = x ? { step: 'LABEL', provider: x.provider, model: x.model, seconds: x.seconds, failed_attempts: (x.attempts || []).filter(a => a.status === 'error').map(a => a.provider + ':' + a.model + ' ' + a.reason) }
           : { step: 'LABEL', provider: null, model: null, error: String((call.error && call.error.message) || 'no x_llm in the answer').slice(0, 150) };
return [{ json: j }];
"""

BUILD_RESPONSE = r"""
// SOURCE is the Parse node whose report is returned, VALIDATION the node that validated it.
const ctx = $('Assemble context').first().json;
const risk = $('Risk ready').first().json;
let parsed = $(SOURCE).first().json;
const v = VALIDATION ? $input.first().json : null;
let validation = !v ? { status: 'not_run', violations: [], repaired: REPAIRED }
  : (v.error ? { status: 'unavailable', violations: [{ check: 'validate', message: 'the /validate service did not answer: ' + String(v.error.message || '').slice(0, 150) }], repaired: REPAIRED }
  : { status: v.status, violations: v.violations || [], repaired: REPAIRED });
// D6: when the repair pass ran, keep what the FIRST validation said, so the reason for the repair is not lost.
if (REPAIRED) { try { validation.first_violations = $('Validate report').first().json.violations || []; } catch (e) { validation.first_violations = []; } }
const degraded = [...ctx.degraded, ...(risk.degraded_c || [])];
// 2026-10-18 (real run, edge_03): the repair model fixed the one problem and dropped four required fields, and the broken report was returned.
// The repair pass must never make the answer worse: when the repaired report fails more checks than the original, or breaks the schema where the original did not, keep the original.
if (REPAIRED && validation.status !== 'pass') {
  let first = null, original = null;
  try { first = $('Validate report').first().json; original = $('Report ready').first().json; } catch (e) { first = null; }
  if (first && !first.error && original && original.report) {
    const was = first.violations || [], now = validation.violations || [];
    const schemaBroke = now.some(x => x.check === 'schema') && !was.some(x => x.check === 'schema');
    if (schemaBroke || now.length > was.length) {
      degraded.push({ step: 'repair', reason: 'the repaired report failed ' + now.length + ' check(s) against ' + was.length + ' for the original, so the original report is returned' });
      validation = { status: first.status, violations: was, repaired: true, repair_discarded: true, repair_violations: now, first_violations: was };
      parsed = original;
    }
  }
}
degraded.push(...(parsed.degraded_d || []));
if (!parsed.report) {
  return [{ json: { status: 'degraded', incident_type: ctx.incident.incident_type, severity: risk.risk.severity, report_markdown: '', report: null, risk: risk.risk,
    validation, degraded_steps: degraded, knowledge_coverage: ctx.knowledge.coverage, prompt_versions: PV } }];
}
const status = validation.status !== 'pass' ? 'flagged' : (degraded.length ? 'degraded' : 'ok');
if (validation.status !== 'pass') degraded.push({ step: 'validation', reason: validation.violations.map(x => x.check + ': ' + x.message).join(' | ').slice(0, 600) || validation.status });
const ids = [...new Set(ctx.retrieval.results.flatMap(r => r.entry_ids || []))];
const models = [];
for (const n of ['Incident ready', 'Vision ready', 'Queries ready', 'Knowledge ready', 'Risk ready', 'Report ready', 'Repaired report ready']) {
  let node; try { node = $(n); if (!node.isExecuted) continue; } catch (e) { continue; }
  const l = node.first().json._llm; if (l) models.push(l);
}
return [{ json: { status, incident_type: ctx.incident.incident_type, severity: parsed.report.severity || risk.risk.severity,
  report_markdown: parsed.report.report_markdown || '', report: parsed.report, validation, degraded_steps: degraded,
  knowledge_coverage: ctx.knowledge.coverage, retrieved_entry_ids: ids, models_used: models, prompt_versions: PV } }];
"""


def with_pv(js, versions, retried=False):
    return "const PV = " + json.dumps(versions) + ";\nconst RETRIED = " + ("true" if retried else "false") + ";\n" + js


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "disasterai/" + name))


class Builder:
    def __init__(self):
        self.nodes, self.connections = [], {}

    def add(self, name, type_, version, params, x, y, **extra):
        node = {"parameters": params, "id": uid(name), "name": name, "type": type_, "typeVersion": version, "position": [x, y]}
        node.update(extra)
        self.nodes.append(node)
        return name

    def link(self, a, b, out=0, inp=0):
        outs = self.connections.setdefault(a, {"main": []})["main"]
        while len(outs) <= out:
            outs.append([])
        outs[out].append({"node": b, "type": "main", "index": inp})

    # --- node helpers ---
    def code(self, name, js, x, y, versions, retried=False):
        return self.add(name, "n8n-nodes-base.code", 2, {"jsCode": with_pv(js, versions, retried)}, x, y)

    def if_(self, name, left_expr, x, y):
        cond = {"id": uid(name + "/cond"), "leftValue": left_expr, "rightValue": "",
                "operator": {"type": "boolean", "operation": "true", "singleValue": True}}
        params = {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2}, "conditions": [cond], "combinator": "and"}, "options": {}}
        return self.add(name, "n8n-nodes-base.if", 2.2, params, x, y)

    def prompt(self, agent, x, y, user_expr=None, name=None):
        system, template = read_prompt(agent)
        name = name or f"Prompt {agent.replace('_', ' ')} {VERSIONS[agent]}"
        assignments = [
            {"id": uid(name + "/system"), "name": "system", "value": system, "type": "string"},
            {"id": uid(name + "/user"), "name": "user", "value": user_expr or user_expression(agent, template), "type": "string"},
            {"id": uid(name + "/version"), "name": "prompt_file", "value": "prompts/" + PROMPTS[agent], "type": "string"},
        ]
        return self.add(name, "n8n-nodes-base.set", 3.4, {"mode": "manual", "assignments": {"assignments": assignments}, "includeOtherFields": False, "options": {}}, x, y)

    pace_seconds = 0

    def gemini(self, name, x, y, json_out=True, image=False, src="$json", retry=False):
        """HTTP node calling the model chain. With pacing on, a Wait node goes first. Returns (entry node, HTTP node)."""
        entry = None
        if self.pace_seconds:
            entry = self.add(f"Pace before {name}", "n8n-nodes-base.wait", 1.1, {"resume": "timeInterval", "amount": self.pace_seconds, "unit": "seconds"}, x - 130, y + 60,
                             webhookId=uid("wait/" + name))
        http = self._gemini_http(name, x, y, json_out, image, src, retry)
        if entry:
            self.link(entry, http)
        return (entry or http), http

    def _gemini_http(self, name, x, y, json_out=True, image=False, src="$json", retry=False):
        """POST /llm: the chain picks the model. The retry node sends retry: true so the model that just failed is not asked first again."""
        # an image call is a vision task: /llm then uses VISION_CHAIN (a local or hosted vision model) when it is set
        img = (", task: 'vision', image_b64: $('Normalise input').first().json.image_b64, image_mime: $('Normalise input').first().json.image_mime" if image else "")
        body = ("={{ JSON.stringify({ system: " + src + ".system, user: " + src + ".user, json: " + ("true" if json_out else "false") + ", retry: " + ("true" if retry else "false") + img + " }) }}")
        params = {"method": "POST", "url": "={{ $('Config').first().json.rag_url + '/llm' }}", "sendBody": True, "specifyBody": "json", "jsonBody": body, "options": {"timeout": 600000}}
        return self.add(name, "n8n-nodes-base.httpRequest", 4.2, params, x, y, onError="continueRegularOutput")

    def http_json(self, name, url_expr, body_expr, x, y, timeout=30000):
        params = {"method": "POST", "url": url_expr, "sendBody": True, "specifyBody": "json", "jsonBody": body_expr, "options": {"timeout": timeout}}
        return self.add(name, "n8n-nodes-base.httpRequest", 4.2, params, x, y, retryOnFail=True, maxTries=2, waitBetweenTries=2000, onError="continueRegularOutput")

    def respond(self, name, x, y, code=200):
        return self.add(name, "n8n-nodes-base.respondToWebhook", 1.1, {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}", "options": {"responseCode": code}}, x, y)


def chain(b, label, prompt_name, parse_js, x, y, versions, ready_name, image=False, json_out=True):
    """Model call through /llm (which already falls back across providers), parse, and one more call when the answer is still unusable.

    Nodes: LLM: <label>, Parse <label>, <label> answer usable?, LLM: <label> (retry), Parse <label> (retry), <ready_name>.
    Everything downstream reads the result from <ready_name>, whichever path produced it. <ready_name> adds _llm: the provider and
    model that answered (from the x_llm field of /llm), so every result can be attributed to a model.
    """
    entry, g = b.gemini(f"LLM: {label}", x, y, json_out=json_out, image=image)
    p = b.code(f"Parse {label}", parse_js, x + 260, y, versions)
    ok = b.if_(f"{label}: answer usable?", "={{ !$json._failed }}", x + 520, y)
    entry2, g2 = b.gemini(f"LLM: {label} (retry)", x + 780, y + 140, json_out=json_out, image=image, src=f"$('{prompt_name}').first().json", retry=True)
    p2 = b.code(f"Parse {label} (retry)", parse_js, x + 1040, y + 140, versions, retried=True)
    ready = b.code(ready_name, READY_JS.replace("LABEL", label), x + 1300, y, versions)
    b.link(g, p)
    b.link(p, ok)
    b.link(ok, ready, 0)
    b.link(ok, entry2, 1)
    b.link(g2, p2)
    b.link(p2, ready)
    return entry, ready


def build(args):
    v = VERSIONS
    b = Builder()
    X = 260  # column width
    L = b.link

    # 1. entry, input checks
    b.add("Incident received", "n8n-nodes-base.webhook", 2, {"httpMethod": "POST", "path": args.path, "responseMode": "responseNode", "options": {}}, 0, 300, webhookId=uid("webhook/" + args.workflow_id))
    cfg = [{"id": uid("cfg/" + k), "name": k, "value": val, "type": "string"} for k, val in (("rag_url", args.rag_url.rstrip("/")),)]
    b.code("Normalise input", NORMALISE, X, 300, v)
    b.add("Config", "n8n-nodes-base.set", 3.4, {"mode": "manual", "assignments": {"assignments": cfg}, "includeOtherFields": True, "options": {}}, 2 * X, 300)
    b.if_("Valid input?", "={{ $json.valid }}", 3 * X, 300)
    b.code("Reject input", REJECT, 4 * X, 480, v)
    b.respond("Respond 400", 5 * X, 480, 400)
    L("Incident received", "Normalise input"); L("Normalise input", "Config"); L("Config", "Valid input?")
    L("Valid input?", "Prompt incident " + v["incident"], 0); L("Valid input?", "Reject input", 1); L("Reject input", "Respond 400")

    # 2. incident understanding
    b.prompt("incident", 4 * X, 300)
    first, ready = chain(b, "incident", "Prompt incident " + v["incident"], PARSE_INCIDENT, 5 * X, 300, v, "Incident ready")
    L("Prompt incident " + v["incident"], first)
    b.if_("Enough to assess?", "={{ $json.incident_type !== 'unclear' }}", 10 * X, 300)
    b.code("Ask for missing information", NEEDS_INFO, 11 * X, 480, v)
    b.respond("Respond needs more information", 12 * X, 480)
    L(ready, "Enough to assess?"); L("Enough to assess?", "Ask for missing information", 1); L("Ask for missing information", "Respond needs more information")

    # 3a. vision branch
    b.if_("Has image?", "={{ $('Normalise input').first().json.has_image }}", 11 * X, 120)
    b.prompt("vision", 12 * X, 40)
    vfirst, vready = chain(b, "vision", "Prompt vision " + v["vision"], PARSE_VISION, 13 * X, 40, v, "Vision ready", image=True)
    b.code("No image: vision skipped", NO_IMAGE, 12 * X, 200, v)
    L("Enough to assess?", "Has image?", 0); L("Has image?", "Prompt vision " + v["vision"], 0); L("Has image?", "No image: vision skipped", 1)
    L("Prompt vision " + v["vision"], vfirst)

    # 3b. knowledge branch
    b.prompt("rag_queries", 11 * X, 700)
    qfirst, qready = chain(b, "RAG queries", "Prompt rag queries " + v["rag_queries"], PARSE_QUERIES, 12 * X, 700, v, "Queries ready")
    b.if_("Topic searchable?", "={{ $('Incident ready').first().json.rag_topic !== 'general' }}", 17 * X, 700)
    b.code("Split queries", SPLIT_QUERIES, 18 * X, 640, v)
    b.http_json("RAG search", "={{ $('Config').first().json.rag_url + '/search' }}",
                "={{ JSON.stringify({ query: $json.query, k: 4, topic: $json.topic, strategy: 'section', balance_languages: true }) }}", 19 * X, 640)
    b.code("Merge passages", MERGE_PASSAGES, 20 * X, 640, v)
    b.if_("Any passages?", "={{ $json.passages.length > 0 }}", 21 * X, 640)
    b.prompt("knowledge", 22 * X, 580)
    kfirst, kready = chain(b, "knowledge", "Prompt knowledge " + v["knowledge"], PARSE_KNOWLEDGE, 23 * X, 580, v, "Knowledge ready")
    b.code("Knowledge: none", KNOWLEDGE_NONE, 22 * X, 800, v)
    L("Enough to assess?", "Prompt rag queries " + v["rag_queries"], 0); L("Prompt rag queries " + v["rag_queries"], qfirst); L(qready, "Topic searchable?")
    L("Topic searchable?", "Split queries", 0); L("Topic searchable?", "Knowledge: none", 1)
    L("Split queries", "RAG search"); L("RAG search", "Merge passages"); L("Merge passages", "Any passages?")
    L("Any passages?", "Prompt knowledge " + v["knowledge"], 0); L("Any passages?", "Knowledge: none", 1); L("Prompt knowledge " + v["knowledge"], kfirst)

    # 4. merge, risk, report
    b.add("Wait for both branches", "n8n-nodes-base.merge", 3.2, {"mode": "combine", "combineBy": "combineByPosition", "options": {}}, 29 * X, 300)
    b.code("Assemble context", ASSEMBLE, 30 * X, 300, v)
    L(vready, "Wait for both branches", 0, 0); L("No image: vision skipped", "Wait for both branches", 0, 0)
    L(kready, "Wait for both branches", 0, 1); L("Knowledge: none", "Wait for both branches", 0, 1)
    L("Wait for both branches", "Assemble context")
    b.prompt("risk", 31 * X, 300)
    rfirst, rready = chain(b, "risk", "Prompt risk " + v["risk"], PARSE_RISK, 32 * X, 300, v, "Risk ready")
    L("Assemble context", "Prompt risk " + v["risk"]); L("Prompt risk " + v["risk"], rfirst)
    b.prompt("report", 37 * X, 300)
    pfirst, pready = chain(b, "report", "Prompt report " + v["report"], PARSE_REPORT, 38 * X, 300, v, "Report ready")
    L(rready, "Prompt report " + v["report"]); L("Prompt report " + v["report"], pfirst)
    b.if_("Report produced?", "={{ $json.report !== null }}", 43 * X, 300)
    validate_body = ("={{ JSON.stringify({ report: $json.report, retrieval: $('Assemble context').first().json.retrieval, incident_text: $('Assemble context').first().json.incident_text, "
                     "incident: $('Assemble context').first().json.incident, vision: $('Assemble context').first().json.vision, image_status: $('Assemble context').first().json.image_status }) }}")
    b.http_json("Validate report", "={{ $('Config').first().json.rag_url + '/validate' }}", validate_body, 44 * X, 220)
    b.if_("Validation passed?", "={{ $json.status === 'pass' }}", 45 * X, 220)
    b.code("Build response", "const SOURCE = 'Report ready', VALIDATION = true, REPAIRED = false;\n" + BUILD_RESPONSE, 46 * X, 140, v)
    b.respond("Respond", 47 * X, 140)
    L(pready, "Report produced?"); L("Report produced?", "Validate report", 0); L("Validate report", "Validation passed?")
    L("Validation passed?", "Build response", 0); L("Build response", "Respond")

    # repair path: one more pass through the report agent with the failed checks
    repair_user = ("={{ $('Prompt report " + v["report"] + "').first().json.user + '\\n\\nYour previous answer failed these automatic checks. Fix only what they name, keep everything else, and return the full JSON object again.\\n<failed_checks>\\n' "
                   "+ JSON.stringify($json.violations || $json.error || 'validation service unavailable') + '\\n</failed_checks>\\n<previous_answer>\\n' + JSON.stringify($('Report ready').first().json.report) + '\\n</previous_answer>' }}")
    b.prompt("report", 46 * X, 460, user_expr=repair_user, name="Prompt report repair " + v["report"])
    xfirst, xready = chain(b, "repaired report", "Prompt report repair " + v["report"], PARSE_REPORT, 47 * X, 460, v, "Repaired report ready")
    b.http_json("Validate repaired report", "={{ $('Config').first().json.rag_url + '/validate' }}", validate_body, 52 * X, 460)
    b.code("Build response (after repair)", "const SOURCE = 'Repaired report ready', VALIDATION = true, REPAIRED = true;\n" + BUILD_RESPONSE, 53 * X, 460, v)
    b.respond("Respond after repair", 54 * X, 460)
    L("Validation passed?", "Prompt report repair " + v["report"], 1); L("Prompt report repair " + v["report"], xfirst)
    L(xready, "Validate repaired report"); L("Validate repaired report", "Build response (after repair)"); L("Build response (after repair)", "Respond after repair")

    # the report agent failed even after its retry: degraded response, never silent
    b.code("Degraded response", "const SOURCE = 'Report ready', VALIDATION = false, REPAIRED = false;\n" + BUILD_RESPONSE, 44 * X, 600, v)
    b.respond("Respond degraded", 45 * X, 600)
    L("Report produced?", "Degraded response", 1); L("Degraded response", "Respond degraded")

    return {
        "name": args.workflow_name, "nodes": b.nodes, "connections": b.connections, "active": False,
        "settings": {"executionOrder": "v1", "errorWorkflow": "disasterai-error", "saveDataErrorExecution": "all", "saveDataSuccessExecution": "all"},
        "pinData": {}, "meta": {"disasterai": {"prompt_versions": VERSIONS, "prompt_files": PROMPTS, "generated_by": "scripts/build_workflow.py",
                                               "rag_url": args.rag_url, "llm": "POST /llm, models from LLM_CHAIN in .env", "pace_seconds": args.pace_seconds}},
        "id": args.workflow_id, "tags": [],
    }


ERROR_JS = r"""
// Global error workflow: keep a readable line per failed execution (visible in the Executions tab of this workflow).
const e = $input.first().json;
return [{ json: { when: new Date().toISOString(), workflow: e.workflow && e.workflow.name, execution_id: e.execution && e.execution.id,
  failed_node: e.execution && e.execution.lastNodeExecuted, message: e.execution && e.execution.error && e.execution.error.message } }];
"""


def build_error_workflow():
    b = Builder()
    b.add("Error Trigger", "n8n-nodes-base.errorTrigger", 1, {}, 0, 0)
    b.code("Log failure", ERROR_JS, 260, 0, VERSIONS)
    b.link("Error Trigger", "Log failure")
    return {"name": "DisasterAI error workflow", "nodes": b.nodes, "connections": b.connections, "active": False, "settings": {"executionOrder": "v1"},
            "pinData": {}, "id": "disasterai-error", "tags": [], "meta": {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rag-url", default="http://host.docker.internal:8010")
    parser.add_argument("--path", default="incident", help="webhook path")
    parser.add_argument("--workflow-id", default="disasterai-pipeline", help="n8n workflow id (use another id to keep several variants side by side)")
    parser.add_argument("--workflow-name", default="DisasterAI pipeline")
    parser.add_argument("--out-name", default="disasterai.json", help="file name written in --out-dir")
    parser.add_argument("--prompt", action="append", default=[], metavar="AGENT=FILE",
                        help="use another prompt file for one agent, for before and after tests, for example --prompt incident=incident_understanding/v1.md --prompt report=report/v3.md")
    parser.add_argument("--pace-seconds", type=int, default=0,
                        help="wait this long before every model call. Default 0: the chain already moves to the next model on a rate limit.")
    parser.add_argument("--out-dir", default=str(ROOT / "n8n" / "workflows"))
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    Builder.pace_seconds = args.pace_seconds
    for item in args.prompt:
        agent, _, path = item.partition("=")
        if agent not in PROMPTS or not (ROOT / "prompts" / path).exists():
            raise SystemExit(f"--prompt {item}: unknown agent or file not found under prompts/")
        PROMPTS[agent] = path
        VERSIONS[agent] = re.search(r"v\d+", Path(path).stem).group(0)
    main_wf = build(args)
    (out / args.out_name).write_text(json.dumps(main_wf, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "disasterai_error.json").write_text(json.dumps(build_error_workflow(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(main_wf['nodes'])} nodes to {out / args.out_name} (prompt versions: {VERSIONS})")


if __name__ == "__main__":
    main()
