"""Batch accuracy evaluation for the Vision Agent.

Randomly samples N images per class from data/Fire, data/Flood, data/Normal,
runs the full pipeline (TTA + consistency + reliability), and prints a report.

Usage:
    python eval_batch.py          # 5 per class (15 images, ~10-20 min)
    python eval_batch.py 10       # 10 per class
    python eval_batch.py 3        # quick smoke-test (3 per class)
"""

import random
import sys
import time
from pathlib import Path

from src.agents.vision_agent import run
from src.schemas import DisasterClass, VisionInput

ROOT = Path(__file__).parent
SEED = 42
SEP  = "=" * 66
SEP2 = "-" * 66

CLASSES = {
    "fire":  (ROOT / "data" / "Fire",   DisasterClass.FIRE),
    "flood": (ROOT / "data" / "Flood",  DisasterClass.FLOOD),
    "normal":(ROOT / "data" / "Normal", DisasterClass.NORMAL),
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MIN_DIM = 128  # Ollama rejects very small images

N_PER_CLASS = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def sample_images(folder: Path, n: int) -> list[Path]:
    from PIL import Image as _PIL
    candidates = []
    for f in folder.iterdir():
        if f.suffix.lower() not in IMAGE_EXTS:
            continue
        try:
            with _PIL.open(f) as img:
                w, h = img.size
            if w >= MIN_DIM and h >= MIN_DIM:
                candidates.append(f)
        except Exception:
            pass
    random.seed(SEED)
    return random.sample(candidates, min(n, len(candidates)))


def run_evaluation():
    results = []  # (label, predicted, reliability, image_name, elapsed)

    total = N_PER_CLASS * len(CLASSES)
    done  = 0

    print(SEP)
    print(f"  DisasterAI — Vision Agent Batch Evaluation")
    print(f"  {N_PER_CLASS} images/class × {len(CLASSES)} classes = {total} images")
    print(SEP)

    for label, (folder, gt_class) in CLASSES.items():
        images = sample_images(folder, N_PER_CLASS)
        print(f"\n[{label.upper()}]  {len(images)} images from {folder.name}/")
        print(SEP2)

        for img_path in images:
            done += 1
            t0 = time.time()
            try:
                out = run(VisionInput(image_path=str(img_path)))
                elapsed = time.time() - t0
                pred = out.predicted_class
                correct = (pred == gt_class)
                mark = "✓" if correct else "✗"
                results.append({
                    "label": label,
                    "gt": gt_class,
                    "pred": pred,
                    "reliability": out.reliability_status,
                    "agreement": out.consistency.agreement_score,
                    "image": img_path.name,
                    "elapsed": elapsed,
                    "correct": correct,
                })
                print(
                    f"  [{done:02d}/{total}] {mark}  "
                    f"gt={label:<6}  pred={pred.value:<9}  "
                    f"rel={out.reliability_status.value:<10}  "
                    f"agree={out.consistency.agreement_score:.2f}  "
                    f"({elapsed:.1f}s)  {img_path.name}"
                )
            except Exception as exc:
                elapsed = time.time() - t0
                print(f"  [{done:02d}/{total}] ERROR: {img_path.name}: {exc}")
                results.append({
                    "label": label, "gt": gt_class, "pred": None,
                    "reliability": None, "agreement": 0.0,
                    "image": img_path.name, "elapsed": elapsed, "correct": False,
                })

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  RESULTS SUMMARY")
    print(SEP)

    overall_correct = 0
    overall_total   = 0

    for label, (_, gt_class) in CLASSES.items():
        class_results = [r for r in results if r["label"] == label]
        correct  = sum(1 for r in class_results if r["correct"])
        total_c  = len(class_results)
        acc      = correct / total_c * 100 if total_c else 0
        reliable = sum(1 for r in class_results if r["reliability"] and r["reliability"].value == "reliable")
        uncertain_pred = sum(1 for r in class_results if r["pred"] == DisasterClass.UNCERTAIN)
        overall_correct += correct
        overall_total   += total_c
        print(
            f"  {label.upper():<6}  acc={acc:5.1f}%  ({correct}/{total_c})  "
            f"reliable={reliable}/{total_c}  uncertain_out={uncertain_pred}"
        )

    overall_acc = overall_correct / overall_total * 100 if overall_total else 0
    print(SEP2)
    print(f"  OVERALL acc={overall_acc:.1f}%  ({overall_correct}/{overall_total})")

    # ── Per-class confusion breakdown ─────────────────────────────────────
    print(f"\n{SEP}")
    print("  CONFUSION BREAKDOWN (rows=ground_truth, cols=predicted)")
    print(SEP2)
    all_classes = ["fire", "flood", "normal", "uncertain"]
    header = f"  {'gt':>8} | " + " ".join(f"{c:>9}" for c in all_classes)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for label in ["fire", "flood", "normal"]:
        row_results = [r for r in results if r["label"] == label]
        row = f"  {label:>8} | "
        for pc in all_classes:
            count = sum(
                1 for r in row_results
                if r["pred"] is not None and r["pred"].value == pc
            )
            row += f"{count:>9} "
        print(row)

    # ── Reliability breakdown ─────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  RELIABILITY BREAKDOWN")
    print(SEP2)
    for status in ["reliable", "unreliable", "uncertain"]:
        group = [r for r in results if r["reliability"] and r["reliability"].value == status]
        correct_in_group = sum(1 for r in group if r["correct"])
        print(
            f"  {status:<10}  count={len(group):>3}  "
            f"correct_in_group={correct_in_group}/{len(group)}"
            + (f"  ({correct_in_group/len(group)*100:.0f}%)" if group else "")
        )

    avg_time = sum(r["elapsed"] for r in results) / len(results) if results else 0
    total_time = sum(r["elapsed"] for r in results)
    print(f"\n  Total time: {total_time:.1f}s  |  Avg per image: {avg_time:.1f}s")
    print(SEP)


if __name__ == "__main__":
    run_evaluation()
