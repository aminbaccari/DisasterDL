"""One tiny Gemini call to check that GEMINI_API_KEY and GEMINI_MODEL from .env work. Prints the status, never the key.

    python scripts/gemini_ping.py [model]
"""
import os
import sys
import time

import requests
from dotenv import load_dotenv

try:  # use the operating system certificate store (some networks re-sign TLS traffic with a local CA)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

load_dotenv()
key = os.getenv("GEMINI_API_KEY", "")
model = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GEMINI_MODEL", "")  # optional model override, .env is not changed
if not key or not model:
    sys.exit("GEMINI_API_KEY or GEMINI_MODEL is not set in .env")
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
started = time.time()
r = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                  json={"contents": [{"role": "user", "parts": [{"text": "Reply with the single word OK."}]}]}, timeout=60)
print("model:", model, "| http:", r.status_code, "| seconds:", round(time.time() - started, 1))
try:
    body = r.json()
    if r.status_code == 200:
        print("answer:", body["candidates"][0]["content"]["parts"][0]["text"].strip()[:40])
        print("usage:", body.get("usageMetadata"))
    else:
        print("error:", str(body.get("error", body))[:300])
except Exception as exc:  # noqa: BLE001
    print("could not read the answer:", exc, r.text[:200])
