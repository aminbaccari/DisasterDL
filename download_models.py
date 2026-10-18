"""One-time script to pull required Ollama models.

Usage:
    python download_models.py
"""

import subprocess
import sys

MODEL = "llava-phi3"

print(f"Pulling {MODEL} via Ollama (~2.9 GB) …")
result = subprocess.run(["ollama", "pull", MODEL], check=False)
if result.returncode == 0:
    print("Done. Model is ready.")
else:
    print("Failed. Make sure Ollama is installed: https://ollama.com")
    sys.exit(1)
