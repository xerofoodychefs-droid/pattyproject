import base64
import io
import re
import time
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException, UploadFile
from PIL import Image

MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_URL_LENGTH = 500
ALLOWED_FORMATS = {
    "JPEG": "jpg",
    "JPG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
}

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "products"
DATA_URL_PATTERN = re.compile(r"^data:(?:image\/[a-zA-Z0-9\+\-\.]+)?;?base64,(.+)$", re.DOTALL | re.IGNORECASE)


def is_base64_image(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    val = value.strip()
    if val.startswith("data:image/") or val.startswith("data:;base64,") or (";base64," in val and val.startswith("data:")):
        return True
    # If the string is very long, has no URL schemes/slashes, and contains base64 chars, test if it looks like raw base64
    if len(val) > 128 and not (val.startswith("http://") or val.startswith("https://") or val.startswith("/")):
        if re.fullmatch(r"[A-Za-z0-9+/=\r\n]+", val):
            return True
    return False


def _validate_and_save_image_bytes(raw_bytes: bytes) -> str:
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Image data is empty.")
    if len(raw_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Image size exceeds maximum allowed limit of 8MB.")

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.verify()
        fmt = (img.format or "").upper()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupt image data.")

    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format: {fmt}. Supported formats: JPEG, PNG, WEBP, GIF."
        )

    ext = ALLOWED_FORMATS[fmt]
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"prod_{uuid.uuid4().hex[:12]}_{int(time.time())}.{ext}"
    target_path = UPLOAD_DIR / filename

    # Prevent path traversal
    if not target_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid image path.")

    with open(target_path, "wb") as f:
        f.write(raw_bytes)

    return f"/uploads/products/{filename}"


def save_base64_image(data_url_or_b64: str) -> str:
    val = data_url_or_b64.strip()
    match = DATA_URL_PATTERN.match(val)
    if match:
        b64_payload = match.group(1).strip()
    else:
        b64_payload = val

    try:
        raw_bytes = base64.b64decode(b64_payload, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image encoding.")

    return _validate_and_save_image_bytes(raw_bytes)


async def save_uploaded_file(file: UploadFile) -> str:
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    content = await file.read()
    return _validate_and_save_image_bytes(content)


def process_image_url(image_str: Optional[str]) -> Optional[str]:
    if image_str is None:
        return None
    val = image_str.strip()
    if not val:
        return ""

    if is_base64_image(val):
        return save_base64_image(val)

    if len(val) > MAX_URL_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Image URL exceeds maximum length of {MAX_URL_LENGTH} characters."
        )

    return val


def process_images_list(images: Optional[List[str]]) -> Optional[List[str]]:
    if images is None:
        return None
    processed = []
    for img in images:
        if img is not None:
            processed_item = process_image_url(img)
            if processed_item:
                processed.append(processed_item)
    return processed
