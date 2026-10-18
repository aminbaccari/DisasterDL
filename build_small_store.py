"""Quick build: 10 images per class → embeddings/store.npz for pipeline testing."""
import random
from pathlib import Path
from PIL import Image
from src.vision.dinov2_encoder import DINOv2Encoder
from src.vision.similarity import EmbeddingStore

ROOT = Path(__file__).parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
MIN_DIM = 128
N = 10
SEED = 42

encoder = DINOv2Encoder.get()
store   = EmbeddingStore()

for class_dir in ["Fire", "Flood", "Normal"]:
    folder = ROOT / "data" / class_dir
    imgs = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS]
    random.seed(SEED)
    sample = random.sample(imgs, min(N, len(imgs)))
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
        except Exception as e:
            print(f"  skip {p.name}: {e}")
    print(f"  {class_dir}: {ok} embeddings added")

out = ROOT / "embeddings" / "store.npz"
store.save(out)
print(f"\nStore saved → {out}  ({store.size()} embeddings)")
