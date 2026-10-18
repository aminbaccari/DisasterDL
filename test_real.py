"""Detailed step-by-step test of the Vision Agent.

Usage:
    python test_real.py path/to/image.jpg
    python test_real.py                     # runs built-in 3-image suite
"""

import sys
from pathlib import Path

from src.agents.vision_agent import run
from src.config import settings
from src.schemas import VisionInput

ROOT = Path(__file__).parent

SEP  = "=" * 62
SEP2 = "-" * 62


def test_image(image_path: str, label: str = "") -> None:
    tag = f"  [{label}]" if label else ""
    print(f"\n{SEP}")
    print(f"IMAGE{tag}: {image_path}")
    print(f"VLM provider: {settings.vlm_provider}"
          + (f" ({settings.groq_model})" if settings.vlm_provider == "groq" else f" ({settings.vlm_model})"))
    print(SEP)

    if not Path(image_path).exists():
        print("  ERROR: image not found.")
        return

    result = run(VisionInput(image_path=image_path))

    # ── STEP 1 — TTA variants ──────────────────────────────────────
    print("\nSTEP 1 — Test-Time Augmentation (3 variants)")
    print(SEP2)
    for v in result.consistency.variant_results:
        print(f"  Variant : {v.variant_name}")
        print(f"  Class   : {v.predicted_class.value}")
        print(f"  Evidence: {', '.join(v.visible_evidence)}")
        print(f"  Desc    : {v.raw_description}")
        print()

    # ── STEP 2 — Consistency ───────────────────────────────────────
    print("STEP 2 — Visual Consistency Module")
    print(SEP2)
    c = result.consistency
    print(f"  Majority class  : {c.majority_class.value}")
    print(f"  Agreement score : {c.agreement_score:.2f}  (threshold: 0.67)")
    print(f"  All agree       : {c.all_agree}")
    if c.disagreements:
        print("  Disagreements:")
        for d in c.disagreements:
            print(f"    • {d}")
    else:
        print("  Disagreements   : none")

    # ── STEP 3 — Reliability ───────────────────────────────────────
    print()
    print("STEP 3 — Reliability Layer")
    print(SEP2)
    print(f"  Status : {result.reliability_status.value.upper()}")
    if result.reliability_notes:
        for note in result.reliability_notes:
            print(f"  Note   : {note}")
    else:
        print("  Notes  : none — prediction is stable")

    # ── STEP 4 — DINOv2 similarity (when enabled) ─────────────────
    d = result.dinov2_signal
    if d is not None:
        print()
        print("STEP 4 — DINOv2 Visual Similarity")
        print(SEP2)
        print(f"  Embedding dim   : {d.embedding_dim}")
        print(f"  Mode            : {'shadow (logging only)' if d.shadow_mode else 'active'}")
        print(f"  Mean top-5 sim  : {d.mean_top5_similarity:.4f}" if d.mean_top5_similarity is not None else "  Mean top-5 sim  : n/a (no store)")
        if d.nearest_neighbors:
            print("  Nearest neighbors:")
            for i, nn in enumerate(d.nearest_neighbors, 1):
                name = nn.image_path.split("\\")[-1].split("/")[-1]
                print(f"    {i}. {nn.cosine_similarity:.4f}  {name}")
        else:
            print("  Nearest neighbors: none (store not loaded)")
        if d.note:
            print(f"  Note            : {d.note}")

    # ── FINAL OUTPUT ───────────────────────────────────────────────
    print()
    print("FINAL OUTPUT")
    print(SEP2)
    print(f"  predicted_class : {result.predicted_class.value}")
    print(f"  description     : {result.description}")
    print(f"  visible_evidence: {', '.join(result.visible_evidence)}")
    print(f"  reliability     : {result.reliability_status.value}")
    if result.error:
        print(f"  error           : {result.error}")
    print()


if len(sys.argv) > 1:
    test_image(sys.argv[1])
else:
    print("Running built-in 3-image suite via llava-phi3 + Ollama")
    test_image(str(ROOT / "data/Fire/fire_image0001.jpg"),   label="FIRE")
    test_image(str(ROOT / "data/Flood/flood_image0001.jpg"), label="FLOOD")
    test_image(str(ROOT / "data/Normal/image_5990.png"),     label="NORMAL")
    print("Done.")
