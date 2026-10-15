"""Environment check for DisasterAI.

Run from the project root:
    python scripts/check_env.py
    python scripts/check_env.py --skip-embeddings
"""
import argparse
import os
import sys

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("FAIL  missing packages. Run: pip install -r requirements.txt")
    sys.exit(1)

load_dotenv()

results = []


def report(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"{status}  {name}" + (f"  ({detail})" if detail else ""))
    results.append(ok)


def check_python():
    ok = sys.version_info >= (3, 10)
    report("Python 3.10 or newer", ok, sys.version.split()[0])


def check_env_file():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    report("GEMINI_API_KEY set in .env", bool(key))
    return key


def check_gemini(key):
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not key or not model:
        report("Gemini text call", False, "missing key or GEMINI_MODEL")
        return
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": "Reply with the single word: ready"}]}]}
    try:
        r = requests.post(url, json=body, headers={"x-goog-api-key": key}, timeout=30)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            report("Gemini text call", True, f"model={model}, reply={text[:30]!r}")
        else:
            report("Gemini text call", False, f"HTTP {r.status_code}: {r.text[:150]}")
    except Exception as e:
        report("Gemini text call", False, str(e)[:150])


def check_n8n():
    base = os.getenv("N8N_URL", "http://localhost:5678").rstrip("/")
    try:
        r = requests.get(f"{base}/healthz", timeout=5)
        report("n8n reachable", r.status_code == 200, f"{base}, HTTP {r.status_code}")
    except Exception as e:
        report("n8n reachable", False, f"{base}: run 'docker compose up -d' ({str(e)[:80]})")


def check_embeddings():
    name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(name)
        vecs = model.encode(["query: flood response", "query: inondation"])
        report("Embedding model loads", True, f"{name}, dim={vecs.shape[1]}")
    except Exception as e:
        report("Embedding model loads", False, str(e)[:150])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-embeddings", action="store_true")
    args = parser.parse_args()

    check_python()
    key = check_env_file()
    check_gemini(key)
    check_n8n()
    if args.skip_embeddings:
        print("SKIP  Embedding model (--skip-embeddings)")
    else:
        check_embeddings()

    print()
    if all(results):
        print("All checks passed.")
    else:
        print("Some checks failed. Fix them before moving on.")
        sys.exit(1)


if __name__ == "__main__":
    main()
