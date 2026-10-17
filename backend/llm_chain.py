"""Fallback chain of LLM providers (Gemini, Groq, OpenRouter) behind one function and one endpoint.

Why this exists: the Gemini free tier answered 503 (high demand) and 429 (requests per minute, then per day) during the
first real runs, so a pipeline of six or more calls per incident could not finish. n8n still owns the orchestration. It
calls POST /llm once per agent, and this module only decides WHICH model answers. It is transport reliability, not an agent graph.

LLM_CHAIN in .env lists the models in order, for example
    LLM_CHAIN=gemini:gemini-3.6-flash,groq:llama-3.3-70b-versatile,openrouter:meta-llama/llama-3.3-70b-instruct:free
A model is skipped when its provider key is empty, when it is cooling down after a 429 / 5xx / timeout, or (for an image request)
when it is not known to accept images. The first usable answer wins. When JSON was requested the answer must parse as a JSON
object, otherwise the next model is tried.

The answer has the same shape as a Gemini generateContent answer (candidates[0].content.parts[0].text) so the n8n Parse nodes
did not change, plus "x_llm" with the provider, model and every attempt (status, seconds, reason). Record x_llm in the evidence
log: results from different models are not comparable.

Vision: a request with task "vision" uses its own chain, VISION_CHAIN, so image calls do not compete with text calls for the few
quotas of vision-capable cloud models. Typical value: a local model first, then a hosted one, then cloud models, for example
    VISION_CHAIN=ollama:qwen3-vl:4b,hf:Qwen/Qwen3-VL-8B-Instruct,gemini:gemini-3.6-flash
Every model of VISION_CHAIN is trusted to accept images (the chain is the list the team verified with scripts/llm_ping.py --image).
Without VISION_CHAIN a vision request uses LLM_CHAIN, filtered by the model-name hints below. See docs/VISION_ARCHITECTURE.md.

Providers: gemini, groq, openrouter (cloud, key in .env), hf (Hugging Face Inference Providers, HF_TOKEN) and ollama (a local server, no key,
OLLAMA_BASE_URL, default http://localhost:11434/v1). hf and ollama use the same OpenAI-style request as groq and openrouter.

Nothing here prints or stores API keys.
"""
import base64
import json
import os
import re
import threading
import time

import requests

try:  # use the operating system certificate store when available (some networks re-sign TLS traffic with a local CA)
    import truststore#type:ignore
    truststore.inject_into_ssl()
except ImportError:
    pass

GEMINI_URL = "{base}/v1beta/models/{model}:generateContent"
GEMINI_BASE = "https://generativelanguage.googleapis.com"  # GEMINI_BASE_URL in .env overrides it (used to point the chain at the MOCK Gemini)
OPENAI_STYLE = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "hf": (None, "HF_TOKEN"),        # URL from HF_BASE_URL, see _openai_url
    "ollama": (None, None),          # URL from OLLAMA_BASE_URL, no key
}
KEY_VARS = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY", "hf": "HF_TOKEN", "ollama": None}
HF_BASE = "https://router.huggingface.co/v1"
OLLAMA_BASE = "http://localhost:11434/v1"
LOCAL_PROVIDERS = {"ollama"}  # a local model may need a cold start (loading into memory), so it gets the longer timeout
# Models known to accept an image. Gemini Flash models do. For Groq and OpenRouter the model name decides (checked with scripts/llm_ping.py --image).
VISION_HINTS = ("gemini", "llama-4", "vision", "-vl", "gpt-4o", "pixtral", "qwen2.5-vl", "gemma-3", "gemma-4")

COOLDOWN_RATE_LIMIT = 65       # seconds, a per-minute limit
COOLDOWN_DAILY = 6 * 3600      # seconds, a per-day quota or an exhausted free tier
COOLDOWN_SERVER = 30           # 5xx, timeouts, connection errors
MAX_WAIT = 90                 # seconds: longest wait for a cooling model before giving up
TIMEOUT_TEXT = 45             # seconds per model for a text call
TIMEOUT_IMAGE = 120           # seconds per model for a call with an image
TIMEOUT_LOCAL = 300           # seconds for a local model: the first call loads it into memory (89 s measured for qwen3-vl:4b from a bind mount)
COOLDOWN_BROKEN = 3600         # 400/401/403/404: wrong model name or key, do not retry soon

_LOCK = threading.Lock()
_COOLDOWN = {}  # "provider:model" -> unix time until which the model is skipped


def http_post(url, headers, body, timeout):
    """One HTTP call. Tests replace this function, so no network is needed to test the chain."""
    return requests.post(url, headers=headers, json=body, timeout=timeout)


def parse_chain(text=None, var="LLM_CHAIN"):
    """'gemini:gemini-3.6-flash,groq:llama-3.3-70b-versatile' -> [('gemini', 'gemini-3.6-flash'), ...].
    Model names may contain ':' (OpenRouter ':free', Ollama 'qwen3-vl:4b'): only the first colon separates the provider."""
    text = os.getenv(var, "") if text is None else text
    chain = []
    for item in text.split(","):
        item = item.strip()
        if ":" not in item:
            continue
        provider, model = item.split(":", 1)
        if provider.strip() in KEY_VARS and model.strip():
            chain.append((provider.strip(), model.strip()))
    return chain


def has_key(provider):
    """True when the provider can be called: its key is set, or it needs none (a local server is simply tried)."""
    var = KEY_VARS[provider]
    return True if var is None else bool(os.getenv(var, "").strip())


def vision_chain():
    """The chain for image calls, or [] when VISION_CHAIN is not set (then the text chain is used with the model-name hints)."""
    return parse_chain(var="VISION_CHAIN")


def accepts_image(provider, model):
    if provider == "gemini":
        return True
    return any(h in model.lower() for h in VISION_HINTS)


def cooling(provider, model, now=None):
    with _LOCK:
        return _COOLDOWN.get(f"{provider}:{model}", 0) > (now or time.time())


def cool_down(provider, model, seconds):
    with _LOCK:
        _COOLDOWN[f"{provider}:{model}"] = time.time() + seconds


def reset_cooldowns():
    with _LOCK:
        _COOLDOWN.clear()


def _status_of(chain):
    now = time.time()
    return [{"provider": p, "model": m, "key": has_key(p), "cooling_seconds": max(0, round(_COOLDOWN.get(f"{p}:{m}", 0) - now))} for p, m in chain]


def status():
    """Text chain state without secrets: for each model, key present (or none needed), cooling down or not."""
    return _status_of(parse_chain())


def status_vision():
    """The same for VISION_CHAIN (empty list when it is not set)."""
    return _status_of(vision_chain())


def _retry_seconds(response):
    """Seconds to wait before this model can be tried again, from Retry-After or the Gemini retryDelay field."""
    header = response.headers.get("retry-after") if hasattr(response, "headers") else None
    if header and str(header).replace(".", "", 1).isdigit():
        return float(header)
    try:
        for detail in response.json()["error"].get("details", []):
            if "retryDelay" in detail:
                return float(str(detail["retryDelay"]).rstrip("s"))
    except (ValueError, KeyError, AttributeError, TypeError):
        pass
    return None


def classify(status_code, response=None):
    """(cooldown seconds, short reason) for an unsuccessful answer."""
    text = ""
    try:
        text = response.text[:400].lower() if response is not None else ""
    except AttributeError:
        pass
    if status_code == 429:
        wait = _retry_seconds(response) if response is not None else None
        daily = "perday" in text.replace("_", "").replace(" ", "").replace("-", "") or "per day" in text or "daily" in text or (wait is not None and wait > 600)
        if daily:
            return max(wait or 0, COOLDOWN_DAILY), "daily quota exhausted"
        # a per-minute limit: use the provider's own retry delay when it gives one (Groq: a few seconds), else a minute
        return (wait + 1 if wait else COOLDOWN_RATE_LIMIT), "rate limit"
    if status_code in (500, 502, 503, 504):
        return COOLDOWN_SERVER, f"server error {status_code}"
    return COOLDOWN_BROKEN, f"http {status_code}"


def _gemini_request(model, system, user, json_mode, image):
    parts = [{"text": user}]
    if image:
        parts.append({"inline_data": {"mime_type": image["mime"], "data": image["b64"]}})
    body = {"system_instruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"response_mime_type": "application/json"} if json_mode else {}}
    return GEMINI_URL.format(base=os.getenv("GEMINI_BASE_URL", GEMINI_BASE).rstrip("/"), model=model), {"x-goog-api-key": os.getenv("GEMINI_API_KEY", ""), "Content-Type": "application/json"}, body


def _openai_url(provider):
    """Chat completions URL of an OpenAI-style provider. hf and ollama bases can be changed in .env (a Space, a remote Ollama)."""
    fixed = OPENAI_STYLE[provider][0]
    if fixed:
        return fixed
    base = os.getenv("HF_BASE_URL", HF_BASE) if provider == "hf" else os.getenv("OLLAMA_BASE_URL", OLLAMA_BASE)
    return base.rstrip("/") + "/chat/completions"


def _openai_request(provider, model, system, user, json_mode, image):
    url, key_var = _openai_url(provider), OPENAI_STYLE[provider][1]
    content = [{"type": "text", "text": user}]
    if image:
        content.append({"type": "image_url", "image_url": {"url": f"data:{image['mime']};base64,{image['b64']}"}})
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": content if image else user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json"}
    if key_var:
        headers["Authorization"] = "Bearer " + os.getenv(key_var, "")
    if provider == "openrouter":
        headers["X-Title"] = "DisasterAI"
    return url, headers, body


def _text_of(provider, payload):
    if provider == "gemini":
        return payload["candidates"][0]["content"]["parts"][0]["text"]
    return payload["choices"][0]["message"]["content"]


def clean_json_text(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    return re.sub(r"\s*```$", "", text).strip()


def _complete_once(system, user, json_mode=True, image=None, chain=None, timeout=None, rotate=False, trusted=False):
    """One pass over the chain. image = {"mime": "image/png", "b64": "..."} or None. rotate=True starts at the second usable model
    (n8n sets it on its retry, so a model that just gave an unusable answer is not asked again first).
    trusted=True: every model of the chain is assumed to accept images (VISION_CHAIN), so the model-name check is skipped.

    Returns a Gemini-shaped dict, or {"error": {...}} when every model failed. Both carry "x_llm" with the attempts.
    """
    chain = parse_chain() if chain is None else chain
    # Per-model limit: a slow model must fall through to the next one. 2026-10-16: OpenRouter nemotron took 40 to 208 s per call
    # and made whole runs last up to 348 s. Image calls get longer, the only vision model left on 2026-10-16 needed 80 s.
    timeout = timeout or (TIMEOUT_IMAGE if image else TIMEOUT_TEXT)
    attempts, started, skipped_first = [], time.time(), False
    for provider, model in chain:
        tag = {"provider": provider, "model": model}
        if not has_key(provider):
            attempts.append({**tag, "status": "skipped", "reason": "no key"})
            continue
        if image and not trusted and not accepts_image(provider, model):
            attempts.append({**tag, "status": "skipped", "reason": "no image support"})
            continue
        if cooling(provider, model):
            attempts.append({**tag, "status": "skipped", "reason": "cooling down"})
            continue
        if rotate and not skipped_first:
            skipped_first = True
            attempts.append({**tag, "status": "skipped", "reason": "retry: not the first choice again"})
            continue
        url, headers, body = (_gemini_request(model, system, user, json_mode, image) if provider == "gemini"
                              else _openai_request(provider, model, system, user, json_mode, image))
        t0 = time.time()
        try:
            response = http_post(url, headers, body, max(timeout, TIMEOUT_LOCAL) if provider in LOCAL_PROVIDERS else timeout)
        except requests.RequestException as exc:
            cool_down(provider, model, COOLDOWN_SERVER)
            attempts.append({**tag, "status": "error", "seconds": round(time.time() - t0, 2), "reason": type(exc).__name__})
            continue
        seconds = round(time.time() - t0, 2)
        if response.status_code != 200:
            wait, reason = classify(response.status_code, response)
            cool_down(provider, model, wait)
            attempts.append({**tag, "status": "error", "seconds": seconds, "reason": reason, "http": response.status_code})
            continue
        try:
            text = _text_of(provider, response.json())
        except (KeyError, IndexError, ValueError, TypeError):
            attempts.append({**tag, "status": "error", "seconds": seconds, "reason": "no text in the answer"})
            continue
        if json_mode:
            try:
                if not isinstance(json.loads(clean_json_text(text)), dict):
                    raise ValueError("not an object")
            except ValueError:
                attempts.append({**tag, "status": "error", "seconds": seconds, "reason": "answer is not a JSON object"})
                continue
            text = clean_json_text(text)
        attempts.append({**tag, "status": "ok", "seconds": seconds})
        return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
                "x_llm": {"provider": provider, "model": model, "seconds": round(time.time() - started, 2), "attempts": attempts}}
    reasons = "; ".join(f"{a['provider']}:{a['model']} {a.get('reason', a['status'])}" for a in attempts) or "the chain is empty"
    return {"error": {"code": 503, "message": "every model in the chain failed or was skipped: " + reasons[:600]},
            "x_llm": {"provider": None, "model": None, "seconds": round(time.time() - started, 2), "attempts": attempts}}


def soonest_available(chain, image=None, trusted=False):
    """Seconds until the first model that has a key (and accepts the image) stops cooling down, or None when no model qualifies."""
    now, waits = time.time(), []
    for provider, model in chain:
        if has_key(provider) and not (image and not trusted and not accepts_image(provider, model)):
            waits.append(max(0.0, _COOLDOWN.get(f"{provider}:{model}", 0) - now))
    return min(waits) if waits else None


def complete(system, user, json_mode=True, image=None, chain=None, timeout=None, rotate=False, task="text"):
    """Ask the chain; when every model is cooling down after a per-minute limit, wait for the first one and ask once more.

    2026-10-16: with the free tiers of Groq, OpenRouter and Gemini all limited at once, calls failed instantly and a whole
    pipeline run degraded in 0.2 s. Waiting up to MAX_WAIT seconds turns a per-minute limit into a delay. A daily quota
    (cooldown of hours) is never waited for. x_llm.waited_seconds records the wait.
    """
    trusted = False
    if chain is None:
        if task == "vision" and vision_chain():
            chain, trusted = vision_chain(), True
        else:
            chain = parse_chain()
    answer = _complete_once(system, user, json_mode, image, chain, timeout, rotate, trusted)
    answer["x_llm"]["task"] = task
    if "error" not in answer:
        return answer
    wait = soonest_available(chain, image, trusted)
    if wait is None or wait > MAX_WAIT:
        return answer
    sleep_for = wait + 0.5
    time.sleep(sleep_for)
    second = _complete_once(system, user, json_mode, image, chain, timeout, False, trusted)
    second["x_llm"]["task"] = task
    second["x_llm"]["attempts"] = answer["x_llm"]["attempts"] + [{"status": "waited", "reason": f"all models cooling down, waited {sleep_for:.1f} s"}] + second["x_llm"]["attempts"]
    second["x_llm"]["waited_seconds"] = round(sleep_for, 1)
    return second


def encode_image(raw_bytes, mime):
    return {"mime": mime, "b64": base64.b64encode(raw_bytes).decode("ascii")}
