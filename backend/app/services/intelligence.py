import math
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PillowImage, ImageFilter, ImageStat


@dataclass(frozen=True)
class QualityMetrics:
    blur: float
    exposure: float
    resolution: float
    screenshot: float | None
    overall: float


@dataclass(frozen=True)
class FaceCrop:
    bounding_box: dict[str, int]
    confidence: float
    image: PillowImage.Image


SEMANTIC_LABELS = {
    "document": "a photo or scan of a document page with printed text",
    "selfie": "a selfie photograph of one person looking at the camera",
    "portrait": "a portrait photograph of a person",
    "landscape": "a wide landscape, nature, mountain, beach, or outdoor scene",
    "receipt": "a receipt, invoice, bill, or shopping payment slip",
    "meme": "an internet meme with a picture and prominent caption text",
    "screenshot": "a computer, phone, website, app, or chat screenshot",
    "food": "a photograph of food, a meal, or a drink",
    "pet": "a photograph of a pet, dog, or cat",
    "vehicle": "a photograph containing a car, motorcycle, truck, or vehicle",
    "product": "a product photograph of an object for sale",
    "people": "a photograph containing a group of people",
}


def clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def quality_metrics(
    image: PillowImage.Image,
    *,
    is_screenshot: bool = False,
    ocr_text: str = "",
) -> QualityMetrics:
    rgb = image.convert("RGB")
    sample = rgb.copy()
    sample.thumbnail((768, 768), PillowImage.Resampling.LANCZOS)
    grayscale = sample.convert("L")

    edge_variance = ImageStat.Stat(grayscale.filter(ImageFilter.FIND_EDGES)).var[0]
    blur = clamp(math.log1p(edge_variance) / math.log1p(1800.0))

    histogram = grayscale.histogram()
    pixels = max(1, sum(histogram))
    clipped = (sum(histogram[:8]) + sum(histogram[248:])) / pixels
    mean = ImageStat.Stat(grayscale).mean[0]
    balance = 1.0 - abs(mean - 127.5) / 127.5
    # Preserve contrast-heavy documents and screenshots: intentional black text
    # and white paper should not be treated like a blown-out camera exposure.
    exposure = clamp(balance * (1.0 - min(0.75, clipped * 1.8)))

    megapixels = (rgb.width * rgb.height) / 1_000_000
    resolution = clamp(math.log1p(megapixels) / math.log1p(12.0))
    overall = clamp(blur * 0.45 + exposure * 0.25 + resolution * 0.30)

    screenshot = None
    if is_screenshot:
        readable_text = min(1.0, len(ocr_text.strip()) / 180.0)
        screenshot = clamp(blur * 0.45 + exposure * 0.25 + resolution * 0.15 + readable_text * 0.15)
    return QualityMetrics(blur, exposure, resolution, screenshot, overall)


def looks_like_screenshot(
    image: PillowImage.Image,
    *,
    filename: str,
    camera_model: str | None,
    ocr_text: str,
) -> bool:
    normalized_name = filename.casefold()
    if any(token in normalized_name for token in ("screenshot", "screen shot", "screencap")):
        return True
    if camera_model:
        return False
    ratio = max(image.width, image.height) / max(1, min(image.width, image.height))
    common_ratio = any(abs(ratio - value) < 0.035 for value in (16 / 9, 19.5 / 9, 20 / 9, 4 / 3))
    text_density = len(re.sub(r"\s+", "", ocr_text)) / max(1, image.width * image.height)
    return common_ratio and text_density >= 0.00012


def extract_ocr(image: PillowImage.Image) -> str:
    try:
        import pytesseract

        rgb = image.convert("RGB")
        working = rgb.copy()
        if max(working.size) > 2400:
            working.thumbnail((2400, 2400), PillowImage.Resampling.LANCZOS)
        elif max(working.size) < 900:
            scale = min(2.0, 900 / max(working.size))
            working = working.resize(
                (round(working.width * scale), round(working.height * scale)),
                PillowImage.Resampling.LANCZOS,
            )
        text = pytesseract.image_to_string(
            working,
            lang="eng",
            config="--oem 1 --psm 11",
            timeout=12,
        )
        return re.sub(r"[ \t]+", " ", text).strip()[:20_000]
    except (ImportError, RuntimeError, OSError):
        return ""


def detect_faces(image: PillowImage.Image, limit: int = 10) -> list[FaceCrop]:
    try:
        import cv2
        import numpy as np

        rgb = image.convert("RGB")
        scale = min(1.0, 1600 / max(rgb.size))
        working = rgb.resize(
            (round(rgb.width * scale), round(rgb.height * scale)),
            PillowImage.Resampling.LANCZOS,
        )
        pixels = np.asarray(working)
        gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
        gray = cv2.equalizeHist(gray)
        cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
        classifier = cv2.CascadeClassifier(cascade_path)
        if classifier.empty():
            return []
        minimum = max(36, min(working.size) // 14)
        rectangles, _, weights = classifier.detectMultiScale3(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(minimum, minimum),
            outputRejectLevels=True,
        )
        ranked = sorted(
            zip(rectangles, weights, strict=True), key=lambda item: float(item[1]), reverse=True
        )[:limit]
        results: list[FaceCrop] = []
        for (x, y, width, height), weight in ranked:
            left = max(0, round(x / scale))
            top = max(0, round(y / scale))
            right = min(rgb.width, round((x + width) / scale))
            bottom = min(rgb.height, round((y + height) / scale))
            padding_x = round((right - left) * 0.22)
            padding_y = round((bottom - top) * 0.28)
            crop_box = (
                max(0, left - padding_x),
                max(0, top - padding_y),
                min(rgb.width, right + padding_x),
                min(rgb.height, bottom + padding_y),
            )
            results.append(
                FaceCrop(
                    bounding_box={"x": left, "y": top, "width": right - left, "height": bottom - top},
                    confidence=clamp(0.55 + min(0.44, max(0.0, float(weight)) / 20.0)),
                    image=rgb.crop(crop_box),
                )
            )
        return results
    except (ImportError, AttributeError, ValueError, OSError):
        return []


def merge_smart_labels(
    semantic_labels: list[str],
    *,
    is_screenshot: bool,
    ocr_text: str,
    face_count: int,
) -> list[str]:
    labels: list[str] = []

    def add(label: str) -> None:
        if label not in labels:
            labels.append(label)

    if is_screenshot:
        add("screenshot")
    lowered = ocr_text.casefold()
    receipt_words = sum(
        token in lowered
        for token in ("total", "subtotal", "tax", "invoice", "receipt", "amount", "payment")
    )
    if receipt_words >= 2:
        add("receipt")
    elif len(ocr_text.strip()) >= 100:
        add("document")
    if face_count == 1:
        add("portrait")
    elif face_count > 1:
        add("people")
    for label in semantic_labels:
        add(label)
    return labels[:5]
