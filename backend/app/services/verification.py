"""Conservative spatial verification for resized/recompressed still images.

CLIP describes content; it cannot establish that two files depict the same shot.
Compare aligned pixels at two scales before giving a near-duplicate label.
"""
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps


def spatial_similarity(first: bytes, second: bytes) -> float:
    scores = []
    with Image.open(BytesIO(first)) as left, Image.open(BytesIO(second)) as right:
        left = ImageOps.exif_transpose(left).convert("RGB")
        right = ImageOps.exif_transpose(right).convert("RGB")
        for size in (32, 96):
            a = np.asarray(left.resize((size, size), Image.Resampling.LANCZOS), dtype=float) / 255
            b = np.asarray(right.resize((size, size), Image.Resampling.LANCZOS), dtype=float) / 255
            # Blank backgrounds have weak fingerprints. Require
            # texture instead of assigning them a confident duplicate label.
            if min(a.std(axis=(0, 1)).max(), b.std(axis=(0, 1)).max()) < 0.04:
                return 0.0
            centered_a, centered_b = a - a.mean(), b - b.mean()
            correlation = float(np.sum(centered_a * centered_b) / np.sqrt(
                np.sum(centered_a ** 2) * np.sum(centered_b ** 2)
            ))
            error = float(np.sqrt(np.mean((a - b) ** 2)))
            # Both spatial agreement and small pixel error must hold; the
            # returned score is a heuristic, never a probability of correctness.
            scores.append(min(max(0.0, correlation), max(0.0, 1 - error)))
    return min(scores)
