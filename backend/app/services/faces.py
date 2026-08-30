import math
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from PIL import Image as PillowImage

from app.core.config import get_settings


FACE_VECTOR_SIZE = 512


@dataclass(frozen=True)
class FaceAnalysis:
    bounding_box: dict[str, int]
    confidence: float
    embedding: list[float]


def _normalize(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude <= 1e-12:
        raise ValueError("Face model returned an empty embedding")
    normalized = [value / magnitude for value in values]
    if len(normalized) > FACE_VECTOR_SIZE:
        raise ValueError(f"Face embedding has unexpected size {len(normalized)}")
    # SFace emits 128 values. The existing pgvector column is 512-wide because
    # the first implementation stored CLIP features there. Zero-padding keeps
    # cosine similarity mathematically identical without a destructive table
    # rewrite, and the embedding_model column prevents model mixing.
    return normalized + [0.0] * (FACE_VECTOR_SIZE - len(normalized))


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


class FaceEngine:
    """Lazy, local YuNet + SFace detector and identity embedder.

    YuNet supplies five facial landmarks. SFace uses those landmarks to align
    every face before producing its identity vector, making comparisons much
    more stable across pose, crop, expression, and lighting than whole-crop
    CLIP embeddings.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._lock = Lock()

    def _load(self) -> None:
        if self._loaded:
            return
        import cv2

        settings = get_settings()
        detector_path = Path(settings.face_detector_model_path)
        recognizer_path = Path(settings.face_recognizer_model_path)
        missing = [str(path) for path in (detector_path, recognizer_path) if not path.is_file()]
        if missing:
            raise FileNotFoundError("Missing local face model: " + ", ".join(missing))
        self._cv2 = cv2
        self._detector = cv2.FaceDetectorYN.create(
            str(detector_path),
            "",
            (320, 320),
            0.68,
            0.30,
            5000,
        )
        self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
        self._loaded = True

    def analyze(self, image: PillowImage.Image, limit: int = 20) -> list[FaceAnalysis]:
        import numpy as np

        with self._lock:
            self._load()
            rgb = image.convert("RGB")
            longest = max(rgb.size)
            # Upscaling small web images substantially improves detection. Very
            # large photos are capped to keep CPU processing predictable.
            scale = min(3.0, max(1.0, 720.0 / longest), 2000.0 / longest)
            if abs(scale - 1.0) > 0.001:
                working = rgb.resize(
                    (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale))),
                    PillowImage.Resampling.LANCZOS,
                )
            else:
                working = rgb
            pixels = np.ascontiguousarray(np.asarray(working))
            bgr = self._cv2.cvtColor(pixels, self._cv2.COLOR_RGB2BGR)
            self._detector.setInputSize((working.width, working.height))
            _, detected = self._detector.detect(bgr)
            if detected is None:
                return []

            ranked = sorted(detected, key=lambda face: float(face[-1]), reverse=True)
            results: list[FaceAnalysis] = []
            for face in ranked:
                x, y, width, height = (float(value) for value in face[:4])
                original_width, original_height = width / scale, height / scale
                if min(original_width, original_height) < 18:
                    continue
                try:
                    aligned = self._recognizer.alignCrop(bgr, face)
                    feature = self._recognizer.feature(aligned).flatten().astype(float).tolist()
                    embedding = _normalize(feature)
                except self._cv2.error:
                    continue

                left = max(0, round(x / scale))
                top = max(0, round(y / scale))
                right = min(rgb.width, round((x + width) / scale))
                bottom = min(rgb.height, round((y + height) / scale))
                if right <= left or bottom <= top:
                    continue
                detector_confidence = float(face[-1])
                detail_confidence = min(1.0, min(original_width, original_height) / 112.0)
                confidence = _clamp(detector_confidence * (0.58 + 0.42 * detail_confidence))
                results.append(
                    FaceAnalysis(
                        bounding_box={
                            "x": left,
                            "y": top,
                            "width": right - left,
                            "height": bottom - top,
                        },
                        confidence=confidence,
                        embedding=embedding,
                    )
                )
                if len(results) >= limit:
                    break
            return results


face_engine = FaceEngine()
