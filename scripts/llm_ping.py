"""Check the providers and models of the fallback chain with tiny calls. Never prints a key.

    python scripts/llm_ping.py                          # one call per model in LLM_CHAIN (.env)
    python scripts/llm_ping.py --list groq              # model ids the key can see (groq | openrouter | gemini | ollama | hf)
    python scripts/llm_ping.py --task vision --image    # one image call per model of VISION_CHAIN (.env)
    python scripts/llm_ping.py --list openrouter --free # only OpenRouter models whose id ends in :free
    python scripts/llm_ping.py --model groq:llama-3.3-70b-versatile --json --image
    python scripts/llm_ping.py --burst 8 --model groq:llama-3.3-70b-versatile   # 8 calls in a row, shows where rate limits start

--json asks for a JSON object and checks that it parses. --image sends a small generated image (a red square) and asks for its colour,
to learn whether the model really reads images. Results printed here are single observations, not benchmarks.
"""
import argparse
import base64
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from backend import llm_chain  # noqa: E402


def red_square_png(size=48):
    """A valid PNG of a solid red square, built without any image library."""
    row = b"\x00" + b"\xff\x00\x00" * size
    raw = zlib.compress(row * size)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def list_models(provider, free_only):
    var = llm_chain.KEY_VARS[provider]
    key = os.getenv(var, "") if var else ""
    if var and not key:
        sys.exit(f"{var} is empty in .env")
    if provider == "ollama":  # the local server lists what is pulled: GET /api/tags on the same host
        base = os.getenv("OLLAMA_BASE_URL", llm_chain.OLLAMA_BASE).rstrip("/")
        try:
            tags = requests.get(base.removesuffix("/v1") + "/api/tags", timeout=10).json().get("models", [])
        except requests.RequestException as exc:
            sys.exit(f"Ollama is not reachable at {base} ({type(exc).__name__}). Install and start it, see docs/VISION_ARCHITECTURE.md")
        print(f"ollama: {len(tags)} models pulled")
        for m in sorted(t["name"] for t in tags):
            print("  ", m)
        return
    if provider == "hf":
        r = requests.get(os.getenv("HF_BASE_URL", llm_chain.HF_BASE).rstrip("/") + "/models", headers={"Authorization": "Bearer " + key}, timeout=60)
        names = sorted(m["id"] for m in r.json().get("data", [])) if r.status_code == 200 else [f"http {r.status_code}: {r.text[:120]}"]
        print(f"hf: {len(names)} models (hosted by inference providers, check the model page for the provider and price)")
        for n in names[:200]:
            print("  ", n)
        return
    if provider == "gemini":
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key}, timeout=60)
        names = [m["name"].split("/")[1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    else:
        url = {"groq": "https://api.groq.com/openai/v1/models", "openrouter": "https://openrouter.ai/api/v1/models"}[provider]
        r = requests.get(url, headers={"Authorization": "Bearer " + key}, timeout=60)
        if r.status_code != 200:
            sys.exit(f"http {r.status_code}: {r.text[:200]}")
        data = r.json()["data"]
        if provider == "openrouter" and free_only:
            data = [m for m in data if m["id"].endswith(":free")]
        names = [m["id"] + ("  [image input]" if "image" in str(m.get("architecture", {}).get("input_modalities", "")) else "") for m in data]
    print(f"{provider}: {len(names)} models")
    for n in sorted(names):
        print("  ", n)


def ping(provider, model, want_json, want_image, task="text"):
    system = "You are a test endpoint. Follow the user message exactly."
    if want_image:
        user = 'What colour is the square in the image? Answer with one JSON object {"colour": "..."}.' if want_json else "What colour is the square in the image? One word."
        image = llm_chain.encode_image(red_square_png(), "image/png")
    else:
        user = 'Answer with one JSON object {"ok": true}.' if want_json else "Reply with the single word OK."
        image = None
    started = time.time()
    # chain=[(provider, model)] pins the model; a vision ping skips the model-name check like VISION_CHAIN does
    answer = llm_chain._complete_once(system, user, want_json, image, [(provider, model)], 120 if provider in llm_chain.LOCAL_PROVIDERS else 60, False, trusted=task == "vision")         if task == "vision" else llm_chain.complete(system, user, json_mode=want_json, image=image, chain=[(provider, model)], timeout=60)
    attempt = answer["x_llm"]["attempts"][-1] if answer["x_llm"]["attempts"] else {}
    if "error" in answer:
        return {"ok": False, "seconds": round(time.time() - started, 1), "reason": attempt.get("reason", answer["error"]["message"][:100]), "http": attempt.get("http")}
    text = answer["candidates"][0]["content"]["parts"][0]["text"].strip().replace("\n", " ")
    return {"ok": True, "seconds": attempt.get("seconds"), "answer": text[:80]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", choices=["groq", "openrouter", "gemini", "ollama", "hf"])
    parser.add_argument("--task", choices=["text", "vision"], default="text", help="vision: default models come from VISION_CHAIN and are trusted to accept images")
    parser.add_argument("--free", action="store_true")
    parser.add_argument("--model", action="append", help="provider:model, repeatable. Default: LLM_CHAIN")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--burst", type=int, default=1)
    args = parser.parse_args()
    if args.list:
        list_models(args.list, args.free)
        return
    default = llm_chain.vision_chain() if args.task == "vision" else llm_chain.parse_chain()
    models = llm_chain.parse_chain(",".join(args.model)) if args.model else default
    if not models:
        sys.exit("no model: set LLM_CHAIN (or VISION_CHAIN with --task vision) in .env or pass --model provider:model")
    for provider, model in models:
        if not llm_chain.has_key(provider):
            print(f"{provider}:{model}  SKIPPED (no key in .env)")
            continue
        for i in range(args.burst):
            llm_chain.reset_cooldowns()
            result = ping(provider, model, args.json, args.image, args.task)
            tag = f"#{i + 1} " if args.burst > 1 else ""
            print(f"{tag}{provider}:{model}  json={args.json} image={args.image}  ", result)


if __name__ == "__main__":
    main()
