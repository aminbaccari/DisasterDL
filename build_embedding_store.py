"""Build a DINOv2 embedding store from a directory of images.

Encodes every image in the target directory (recursively) with the
frozen DINOv2 encoder and saves the result to a compressed .npz file.
The store can then be used by the Vision Agent for nearest-neighbor
similarity analysis.

Usage:
    python build_embedding_store.py                      # encode data/ → embeddings/store.npz
    python build_embedding_store.py data/Fire            # single class
    python build_embedding_store.py data/ embeddings/my_store.npz

Hardware: runs on GPU when available, CPU otherwise.
Time estimate (RTX 2060): ~1–2 s per image for dinov2-small.

Note: the Ollama / LLaVA-Phi3 service does NOT need to be running.
"""

import sys
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
IMG_DIR   = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data"
STORE_OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "embeddings" / "store.npz"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MIN_DIM   = 128  # skip tiny images that Ollama also rejects

print(f"Source : {IMG_DIR}")
print(f"Output : {STORE_OUT}")

# ── Load encoder ─────────────────────────────────────────────────────────────
from src.vision.dinov2_encoder import DINOv2Encoder
from src.vision.similarity import EmbeddingStore
from PIL import Image

encoder = DINOv2Encoder.get()
store   = EmbeddingStore()

# ── Collect images ────────────────────────────────────────────────────────────
all_images = sorted(
    p for p in IMG_DIR.rglob("*") if p.suffix.lower() in IMAGE_EXTS
)
print(f"Found {len(all_images)} images.\n")

errors  = 0
skipped = 0
t_start = time.time()

for i, img_path in enumerate(all_images, 1):
    try:
        with Image.open(img_path) as img:
            w, h = img.size
        if w < MIN_DIM or h < MIN_DIM:
            skipped += 1
            continue
        with Image.open(img_path) as img:
            embedding = encoder.encode(img)
        store.add(str(img_path), embedding)

        if i % 100 == 0 or i == len(all_images):
            elapsed = time.time() - t_start
            rate    = i / elapsed
            eta     = (len(all_images) - i) / rate if rate > 0 else 0
            print(
                f"  [{i:>6}/{len(all_images)}]  "
                f"stored={store.size()}  "
                f"elapsed={elapsed:.0f}s  "
                f"ETA={eta:.0f}s"
            )
    except Exception as exc:
        errors += 1
        print(f"  ERROR {img_path.name}: {exc}")

# ── Save ─────────────────────────────────────────────────────────────────────
store.save(STORE_OUT)

total_time = time.time() - t_start
print(f"\nDone.")
print(f"  Stored  : {store.size()} embeddings")
print(f"  Skipped : {skipped} (too small)")
print(f"  Errors  : {errors}")
print(f"  Time    : {total_time:.1f}s")
print(f"  Output  : {STORE_OUT}")
print(f"\nTo enable in the Vision Agent, add to your .env:")
print(f"  DINOV2_ENABLED=true")
print(f"  DINOV2_STORE_PATH={STORE_OUT}")
