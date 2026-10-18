"""Build embedding store from a percentage of the dataset.

Usage:
    python build_partial_store.py 10     # 10% of each class
    python build_partial_store.py 50     # 50%
"""
import random, sys, time
from pathlib import Path
from PIL import Image
from src.vision.dinov2_encoder import DINOv2Encoder
from src.vision.similarity import EmbeddingStore

ROOT = Path(__file__).parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
MIN_DIM = 128
PERCENT = int(sys.argv[1]) if len(sys.argv) > 1 else 10
SEED = 42
OUT = ROOT / "embeddings" / "store.npz"

print(f"Building store with {PERCENT}% of each class...")
encoder = DINOv2Encoder.get()
store   = EmbeddingStore()
t0      = time.time()

for class_dir in ["Fire", "Flood", "Normal"]:
    folder = ROOT / "data" / class_dir
    imgs = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS]
    random.seed(SEED)
    n = max(1, int(len(imgs) * PERCENT / 100))
    sample = random.sample(imgs, n)
    ok = 0
    for p in sample:
        try:
            with Image.open(p) as img:
                w, h = img.size
                if w < MIN_DIM or h < MIN_DIM:
                    continue
                emb = encoder.encode(img)
            store.add(str(p), emb)
            ok += 1
            if ok % 50 == 0:
                elapsed = time.time() - t0
                print(f"  {class_dir}: {ok}/{n}  ({elapsed:.0f}s elapsed)")
        except Exception as e:
            print(f"  skip {p.name}: {e}")
    print(f"  {class_dir}: {ok}/{n} done")

store.save(OUT)
print(f"\nStore saved → {OUT}  ({store.size()} embeddings)  ({time.time()-t0:.0f}s total)")
