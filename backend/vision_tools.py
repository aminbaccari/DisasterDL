"""Stateless tools for the three-view (TTA) vision path. They make NO model call and keep NO state.

Orchestration stays in n8n (repo rule): n8n decides whether there is an image, calls /llm once per view, retries, sets analysis_failed, and
decides what is degraded. Python only does the deterministic work that n8n cannot do well:

    POST /vision/variants   image -> three views of it (original, mirrored, contrast-adjusted)
    POST /vision/merge      the vision answers of the views -> one answer plus a reliability block

Merge rules (written down so that they can be tested and argued with):
  * only answers that n8n already validated are passed in; a view that failed is simply not in the list;
  * image_usable: at least half of the views say usable;
  * observations: one per category, kept when at least two views have that category (when there are two or more answers); a category seen by
    one view only goes to reliability.unstable_categories, not to the observations. With one answer nothing can be compared: everything is kept;
  * confidence of a kept observation: the highest among the views that saw it; when only two of three views agree it is capped at "medium";
  * description: from the view named first in PREFER that saw the category (the mirrored view says "on the left" for what is on the right);
  * visible_text: kept when at least two views read it (all of it with one answer); quality_issues and not_determinable: union;
  * consistent_with_report and inconsistencies are NOT merged: the prompt for this path (vision v2) does not see the report.
"""
import base64
import io

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError
from pydantic import BaseModel

router = APIRouter()

PREFER = ["original", "contrast", "flip"]          # which view's wording is used for a merged observation
RANK = {"low": 0, "medium": 1, "high": 2}
NAMES = {0: "low", 1: "medium", 2: "high"}
MAX_PIXELS = 40_000_000                            # refuse decompression bombs
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


class ImageError(ValueError):
    pass


def _open(data):
    try:
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            raise ImageError("the image is too large (more than 40 million pixels)")
        img.load()
        return ImageOps.exif_transpose(img)
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageError(f"could not read the image: {str(exc)[:120]}")


def _encode(img, mime):
    fmt = FORMATS.get(mime, "JPEG")
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out = io.BytesIO()
    save_kwargs = {"quality": 90} if fmt in ("JPEG", "WEBP") else {}
    img.save(out, format=fmt, **save_kwargs)
    return out.getvalue()


def make_variants(data, mime="image/jpeg"):
    """Three views as [{name, image_b64, image_mime}]. The original is returned byte for byte; the others are re-encoded in the same format.

    Raises ImageError for something that is not a readable image."""
    img = _open(data)
    flipped = ImageOps.mirror(img)
    contrast = ImageEnhance.Brightness(ImageEnhance.Contrast(img.convert("RGB") if img.mode not in ("RGB", "L") else img).enhance(1.15)).enhance(1.05)
    views = [("original", data), ("flip", _encode(flipped, mime)), ("contrast", _encode(contrast, mime))]
    return [{"name": n, "image_b64": base64.b64encode(b).decode("ascii"), "image_mime": mime} for n, b in views]


def _best_by_category(result):
    best = {}
    for o in result.get("observations", []) or []:
        if not isinstance(o, dict):
            continue
        c = o.get("category")
        if c not in best or RANK.get(o.get("confidence"), 0) > RANK.get(best[c].get("confidence"), 0):
            best[c] = o
    return best


def _norm(text):
    return " ".join(str(text).lower().split())


def merge(answers, requested=None):
    """answers: [{name, result}] (result = a validated vision answer) or plain results. Returns the merged answer with a reliability block.

    Raises ValueError when there is no answer to merge."""
    items = []
    for i, a in enumerate(answers or []):
        if isinstance(a, dict) and "result" in a:
            items.append((a.get("name") or f"view{i}", a["result"]))
        else:
            items.append((f"view{i}", a))
    items = [(n, r) for n, r in items if isinstance(r, dict)]
    if not items:
        raise ValueError("no answer to merge")
    items.sort(key=lambda x: PREFER.index(x[0]) if x[0] in PREFER else len(PREFER))
    n = len(items)
    results = [r for _, r in items]

    usable_votes = sum(1 for r in results if r.get("image_usable") is True)
    usable = usable_votes * 2 >= n
    quality = []
    for r in results:
        for q in r.get("quality_issues", []) or []:
            if _norm(q) not in [_norm(x) for x in quality]:
                quality.append(q)
    not_det = []
    for r in results:
        for x in r.get("not_determinable", []) or []:
            if _norm(x) not in [_norm(y) for y in not_det]:
                not_det.append(x)

    per_view = [_best_by_category(r) for r in results]
    seen = []
    for best in per_view:
        for c in best:
            if c not in seen:
                seen.append(c)
    observations, unstable, supports = [], [], {}
    for c in seen:
        holders = [best[c] for best in per_view if c in best]     # in PREFER order
        support = len(holders)
        supports[c] = support
        if n >= 2 and support < 2:
            unstable.append({"category": c, "support": support})
            continue
        top = max(RANK.get(h.get("confidence"), 0) for h in holders)
        if n >= 3 and support < n:
            top = min(top, RANK["medium"])
            unstable.append({"category": c, "support": support})
        observations.append({"category": c, "description": holders[0].get("description", ""), "confidence": NAMES[top]})

    texts = {}
    for r in results:
        for t in r.get("visible_text", []) or []:
            key = _norm(t)
            texts.setdefault(key, [t, 0])[1] += 1
    visible = [v[0] for v in texts.values() if n < 2 or v[1] >= 2]

    agreement = None
    if n >= 2 and seen:
        agreement = round(sum(supports[c] / n for c in seen) / len(seen), 3)

    merged = {"image_usable": usable, "quality_issues": quality, "scene_summary": results[0].get("scene_summary", ""),
              "observations": observations if usable else [], "visible_text": visible, "not_determinable": not_det,
              "reliability": {"variants_used": n, "variants_requested": requested or n, "usable_votes": f"{usable_votes}/{n}",
                              "category_agreement_score": agreement, "unstable_categories": unstable}}
    return merged


# ---------------------------------------------------------------- HTTP tools (included in rag/service.py)
class VariantsRequest(BaseModel):
    image_b64: str
    image_mime: str = "image/jpeg"


class MergeRequest(BaseModel):
    answers: list
    requested: int | None = None


@router.post("/vision/variants")
def variants_endpoint(req: VariantsRequest):
    try:
        data = base64.b64decode(req.image_b64, validate=False)
        return {"variants": make_variants(data, req.image_mime)}
    except ImageError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except (ValueError, TypeError) as exc:
        return JSONResponse(status_code=400, content={"error": f"could not read the image: {str(exc)[:120]}"})


@router.post("/vision/merge")
def merge_endpoint(req: MergeRequest):
    try:
        return {"merged": merge(req.answers, req.requested)}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
