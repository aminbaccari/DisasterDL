"""Shared image encoding helper for VLM clients."""

import base64
import io

from PIL import Image


def encode_image_b64(image: Image.Image, quality: int = 85) -> str:
    """Convert a PIL image to a base64-encoded JPEG string."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()
