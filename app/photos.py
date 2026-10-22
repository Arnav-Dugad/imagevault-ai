"""Reading photos and deciding which ones are duplicates.

Two checks are used:

1. Exact duplicate - the SHA-256 fingerprint of the file bytes is identical.
2. Similar photo   - the "perceptual hashes" are almost the same. A perceptual
   hash is a 64-bit summary of what the picture looks like, so a resized or
   re-compressed copy gets nearly the same hash even though its bytes differ.
   We count how many of the 64 bits differ (the Hamming distance).
"""

import hashlib
import io
import math
import statistics
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

SUPPORTED_FORMATS = {
    "JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif", "BMP": "image/bmp",
}

# Both hashes must be at most this many bits apart (out of 64) to count as similar.
PHASH_MAX_DISTANCE = 10
DHASH_MAX_DISTANCE = 12
# Photos with very different shapes (for example portrait vs landscape) are never similar.
MAX_ASPECT_DIFFERENCE = 0.15

THUMBNAIL_SIZE = 480


class NotAPhoto(ValueError):
    pass


@dataclass
class PhotoInfo:
    content_type: str
    width: int
    height: int
    sha256: str
    phash: str
    dhash: str
    thumbnail: bytes


def _to_hex(bits: list[bool]) -> str:
    return f"{sum(1 << i for i, bit in enumerate(bits) if bit):016x}"


def difference_hash(image: Image.Image) -> str:
    """dHash: shrink to 9x8 grey pixels and record whether each pixel is brighter than its right neighbour."""
    pixels = list(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).get_flattened_data())
    return _to_hex([pixels[row * 9 + col] > pixels[row * 9 + col + 1] for row in range(8) for col in range(8)])


# Cosine table for the first 8 frequencies of a 32-point DCT (discrete cosine transform).
_COS = [[math.cos(math.pi * k * (2 * n + 1) / 64) for n in range(32)] for k in range(8)]


def perceptual_hash(image: Image.Image) -> str:
    """pHash: shrink to 32x32 grey pixels, keep the 8x8 lowest frequencies (the overall
    shapes and light), and record whether each one is above the median."""
    pixels = list(image.convert("L").resize((32, 32), Image.Resampling.LANCZOS).get_flattened_data())
    rows = [pixels[i * 32:(i + 1) * 32] for i in range(32)]
    partial = [[sum(_COS[u][x] * rows[x][y] for x in range(32)) for y in range(32)] for u in range(8)]
    low = [sum(partial[u][y] * _COS[v][y] for y in range(32)) for u in range(8) for v in range(8)]
    median = statistics.median(low)
    return _to_hex([value > median for value in low])


def analyze(data: bytes) -> PhotoInfo:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise NotAPhoto("This file is not a supported photo (use JPG, PNG, WEBP, GIF or BMP).") from exc
    if image.format not in SUPPORTED_FORMATS:
        raise NotAPhoto(f"{image.format} files are not supported (use JPG, PNG, WEBP, GIF or BMP).")

    content_type = SUPPORTED_FORMATS[image.format]
    image = ImageOps.exif_transpose(image).convert("RGB")  # respect phone camera rotation
    thumbnail = image.copy()
    thumbnail.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
    buffer = io.BytesIO()
    thumbnail.save(buffer, "JPEG", quality=85)

    return PhotoInfo(
        content_type=content_type,
        width=image.width,
        height=image.height,
        sha256=hashlib.sha256(data).hexdigest(),
        phash=perceptual_hash(image),
        dhash=difference_hash(image),
        thumbnail=buffer.getvalue(),
    )


def hash_distance(a: str, b: str) -> int:
    """How many of the 64 bits differ."""
    return (int(a, 16) ^ int(b, 16)).bit_count()


def compare(new: dict, old: dict) -> tuple[str, float] | None:
    """Return ("exact" | "similar", similarity 0..1) or None if the photos are different."""
    if new["sha256"] == old["sha256"]:
        return "exact", 1.0
    aspect_new = new["width"] / new["height"]
    aspect_old = old["width"] / old["height"]
    if abs(aspect_new - aspect_old) / max(aspect_new, aspect_old) > MAX_ASPECT_DIFFERENCE:
        return None
    phash = hash_distance(new["phash"], old["phash"])
    dhash = hash_distance(new["dhash"], old["dhash"])
    if phash <= PHASH_MAX_DISTANCE and dhash <= DHASH_MAX_DISTANCE:
        # Capped below 1.0, because 100% is reserved for byte-for-byte identical files.
        return "similar", min(0.99, round(1 - (phash + dhash) / 128, 3))
    return None
