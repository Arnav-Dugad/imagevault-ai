import math
import re
from dataclasses import dataclass

from PIL import Image as PillowImage, ImageFilter, ImageStat

from app.core.config import get_settings


@dataclass(frozen=True)
class QualityMetrics:
    blur: float
    exposure: float
    resolution: float
    screenshot: float | None
    overall: float


@dataclass(frozen=True)
class OcrResult:
    text: str
    language: str | None
    layout: list[dict]
    document_type: str | None


# Each visual label is contrastively compared with an explicit negative. This
# is much less trigger-happy than accepting the three nearest CLIP prompts.
SEMANTIC_LABEL_PROMPTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "selfie": (
        (
            "a smartphone selfie taken at arm's length by the person in the picture",
            "a casual front-camera selfie with a face close to the lens",
        ),
        (
            "a professionally posed portrait photographed by another person",
            "a full-body event photograph taken from a distance",
        ),
    ),
    "landscape": (
        (
            "a wide landscape photograph of scenery, mountains, beach, or countryside",
            "an outdoor scenic vista with a distant horizon",
        ),
        ("a close-up portrait of a person", "a document or screenshot"),
    ),
    "food": (
        ("a photograph focused on food, a prepared meal, dessert, or drink",),
        ("a photograph with no food or drinks",),
    ),
    "pet": (
        ("a photograph focused on a pet dog, cat, or domestic animal",),
        ("a photograph with no animal",),
    ),
    "vehicle": (
        ("a photograph prominently containing a car, motorcycle, truck, or vehicle",),
        ("a photograph with no vehicle",),
    ),
    "product": (
        ("a clean product photograph focused on an object for sale",),
        ("a candid photograph of people or scenery",),
    ),
    "architecture": (
        ("an architectural photograph focused on a building or interior design",),
        ("a close-up photograph of a person",),
    ),
    "nature": (
        ("a nature photograph focused on plants, trees, wildlife, or flowers",),
        ("an indoor portrait or document",),
    ),
    "night": (
        ("a night photograph taken after dark with nighttime lighting",),
        ("a bright daytime photograph",),
    ),
    "art": (
        ("a photograph of artwork, an illustration, painting, or drawing",),
        ("an ordinary camera photograph with no artwork",),
    ),
    "meme": (
        ("an internet meme with a picture and a large humorous caption",),
        ("an ordinary photograph without caption text",),
    ),
}


def clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _pillow_sharpness(grayscale: PillowImage.Image) -> float:
    """Dependency-light fallback used by API-only development environments."""
    denoised = grayscale.filter(ImageFilter.GaussianBlur(0.65))
    edges = denoised.filter(ImageFilter.FIND_EDGES)
    edge_rms = ImageStat.Stat(edges).rms[0]
    contrast = ImageStat.Stat(grayscale).stddev[0]
    edge_score = 1.0 - math.exp(-max(0.0, edge_rms - 3.0) / 22.0)
    contrast_score = 1.0 - math.exp(-contrast / 72.0)
    return clamp(edge_score * 0.88 + contrast_score * 0.12)


def _opencv_sharpness(grayscale: PillowImage.Image) -> float:
    import cv2
    import numpy as np

    gray = np.asarray(grayscale, dtype=np.uint8)
    denoised = cv2.GaussianBlur(gray, (0, 0), 0.55)
    laplacian = np.abs(cv2.Laplacian(denoised, cv2.CV_32F, ksize=3))
    if min(laplacian.shape) > 16:
        laplacian = laplacian[4:-4, 4:-4]
    laplacian = np.minimum(laplacian, np.percentile(laplacian, 99.0))
    laplacian_rms = float(np.sqrt(np.mean(np.square(laplacian))))

    sobel_x = cv2.Sobel(denoised, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(denoised, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(sobel_x, sobel_y)
    gradient = np.minimum(gradient, np.percentile(gradient, 99.0))
    gradient_rms = float(np.sqrt(np.mean(np.square(gradient))))
    edge_density = float(np.mean(gradient >= 32.0))

    fine_blur = cv2.GaussianBlur(gray, (0, 0), 0.8)
    coarse_blur = cv2.GaussianBlur(gray, (0, 0), 2.4)
    fine_energy = float(np.mean(cv2.absdiff(gray, fine_blur)))
    coarse_energy = float(np.mean(cv2.absdiff(gray, coarse_blur)))
    fine_ratio = fine_energy / max(0.1, coarse_energy)

    laplacian_score = 1.0 - math.exp(-laplacian_rms / 24.0)
    gradient_score = 1.0 - math.exp(-gradient_rms / 72.0)
    ratio_score = clamp((fine_ratio - 0.14) / 0.42)
    density_score = clamp(edge_density / 0.22)
    raw = (
        laplacian_score * 0.31
        + gradient_score * 0.27
        + ratio_score * 0.29
        + density_score * 0.13
    )

    # JPEG block boundaries can create huge Laplacian values in a visibly soft
    # image. Penalize boundary energy that is unusually stronger every 8 px.
    if gray.shape[1] >= 32 and gray.shape[0] >= 32:
        vertical = np.abs(np.diff(gray.astype(np.float32), axis=1))
        horizontal = np.abs(np.diff(gray.astype(np.float32), axis=0))
        v_boundary = float(np.mean(vertical[:, 7::8])) if vertical[:, 7::8].size else 0.0
        h_boundary = float(np.mean(horizontal[7::8, :])) if horizontal[7::8, :].size else 0.0
        v_regular = float(np.mean(vertical[:, 3::8])) if vertical[:, 3::8].size else 0.0
        h_regular = float(np.mean(horizontal[3::8, :])) if horizontal[3::8, :].size else 0.0
        block_ratio = (v_boundary + h_boundary) / max(0.5, v_regular + h_regular)
        raw *= 1.0 - min(0.28, max(0.0, block_ratio - 1.18) * 0.22)
    return clamp(raw)


def quality_metrics(
    image: PillowImage.Image,
    *,
    is_screenshot: bool = False,
    ocr_text: str = "",
) -> QualityMetrics:
    rgb = image.convert("RGB")
    sample = rgb.copy()
    sample.thumbnail((1200, 1200), PillowImage.Resampling.LANCZOS)
    grayscale = sample.convert("L")

    if min(grayscale.size) < 16:
        raw_sharpness = 0.0
    else:
        try:
            raw_sharpness = _opencv_sharpness(grayscale)
        except (ImportError, AttributeError, ValueError):
            raw_sharpness = _pillow_sharpness(grayscale)

    megapixels = (rgb.width * rgb.height) / 1_000_000
    resolution = clamp(math.log1p(megapixels) / math.log1p(12.0))
    short_edge_progress = clamp((min(rgb.size) - 120.0) / 960.0)
    # A tiny compressed web image cannot honestly be reported as perfectly
    # sharp, even when block boundaries or a silhouette create strong edges.
    sharpness_cap = 0.42 + 0.56 * math.sqrt(
        max(0.0, short_edge_progress * 0.72 + resolution * 0.28)
    )
    blur = clamp(min(raw_sharpness, sharpness_cap))

    histogram = grayscale.histogram()
    pixels = max(1, sum(histogram))
    clipped = (sum(histogram[:5]) + sum(histogram[251:])) / pixels
    mean = ImageStat.Stat(grayscale).mean[0]
    midtone = clamp(1.0 - max(0.0, abs(mean - 127.5) - 24.0) / 103.5)
    middle_fraction = sum(histogram[48:208]) / pixels
    exposure = clamp(
        midtone * 0.62
        + (1.0 - min(1.0, clipped * 4.0)) * 0.30
        + middle_fraction * 0.08
    )
    if is_screenshot or len(ocr_text.strip()) >= 80:
        exposure = max(exposure, clamp(0.72 + (1.0 - min(1.0, clipped * 3.0)) * 0.18))

    overall = clamp(blur * 0.46 + exposure * 0.24 + resolution * 0.30)
    screenshot = None
    if is_screenshot:
        readable_text = min(1.0, len(ocr_text.strip()) / 180.0)
        screenshot = clamp(blur * 0.38 + exposure * 0.22 + resolution * 0.18 + readable_text * 0.22)
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


def _ocr_language(image: PillowImage.Image, pytesseract: object) -> str:
    configured = get_settings().ocr_languages.split("+")
    try:
        available = set(pytesseract.get_languages(config=""))
    except (RuntimeError, OSError):
        available = {"eng"}
    usable = [language for language in configured if language in available]
    if not usable:
        return "eng" if "eng" in available else next(iter(available), "eng")
    script = "Latin"
    if min(image.size) >= 160:
        try:
            osd = pytesseract.image_to_osd(
                image,
                output_type=pytesseract.Output.DICT,
                timeout=6,
            )
            script = str(osd.get("script") or "Latin")
        except (RuntimeError, OSError):
            pass
    script_languages = {
        "Latin": ["eng"],
        "Devanagari": ["hin", "mar", "eng"],
        "Bengali": ["ben", "eng"],
        "Tamil": ["tam", "eng"],
        "Telugu": ["tel", "eng"],
        "Gujarati": ["guj", "eng"],
        "Gurmukhi": ["pan", "eng"],
    }
    selected = [language for language in script_languages.get(script, usable) if language in usable]
    return "+".join(selected or usable[:3])


def _document_type(text: str, layout: list[dict]) -> str | None:
    lowered = text.casefold()
    words = set(re.findall(r"[\w₹$€£]+", lowered))
    if "receipt" in words and len({"subtotal", "tax", "total", "payment", "change"}.intersection(words)) >= 2:
        return "receipt"
    if ("invoice" in words or "bill" in words) and len({"subtotal", "tax", "total", "amount"}.intersection(words)) >= 2:
        return "invoice"
    if len({"resume", "experience", "education", "skills", "curriculum"}.intersection(words)) >= 2:
        return "resume"
    if len({"statement", "account", "balance", "transaction", "credit", "debit"}.intersection(words)) >= 3:
        return "statement"
    if len(layout) >= 12 or len(text.strip()) >= 100:
        return "document"
    return None


def extract_ocr_layout(image: PillowImage.Image) -> OcrResult:
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
        language = _ocr_language(working, pytesseract)
        data = pytesseract.image_to_data(
            working,
            lang=language,
            config="--oem 1 --psm 11",
            timeout=12,
            output_type=pytesseract.Output.DICT,
        )
        words: list[dict] = []
        lines: dict[tuple[int, int, int], list[str]] = {}
        for index, raw_text in enumerate(data.get("text", [])):
            value = re.sub(r"[ \t]+", " ", str(raw_text)).strip()
            try:
                confidence = float(data["conf"][index])
            except (KeyError, TypeError, ValueError, IndexError):
                confidence = -1
            if not value or confidence < 25:
                continue
            line_key = (
                int(data.get("block_num", [0])[index]),
                int(data.get("par_num", [0])[index]),
                int(data.get("line_num", [0])[index]),
            )
            lines.setdefault(line_key, []).append(value)
            if len(words) < 1200:
                words.append(
                    {
                        "text": value,
                        "confidence": round(confidence / 100.0, 3),
                        "x": int(data["left"][index]),
                        "y": int(data["top"][index]),
                        "width": int(data["width"][index]),
                        "height": int(data["height"][index]),
                        "block": line_key[0],
                        "paragraph": line_key[1],
                        "line": line_key[2],
                    }
                )
        text = "\n".join(" ".join(values) for values in lines.values()).strip()[:20_000]
        return OcrResult(text, language, words, _document_type(text, words))
    except (ImportError, RuntimeError, OSError):
        return OcrResult("", None, [], None)


def extract_ocr(image: PillowImage.Image) -> str:
    """Compatibility wrapper for callers that only need searchable text."""
    return extract_ocr_layout(image).text


def merge_smart_labels(
    semantic_evidence: dict[str, float],
    *,
    is_screenshot: bool,
    ocr_text: str,
    face_boxes: list[dict[str, int]],
    image_size: tuple[int, int],
    filename: str = "",
    camera_model: str | None = None,
) -> list[str]:
    labels: list[str] = []

    def add(label: str) -> None:
        if label not in labels:
            labels.append(label)

    lowered = ocr_text.casefold()
    normalized_filename = filename.casefold()
    if is_screenshot:
        add("screenshot")

    receipt_words = sum(
        bool(re.search(rf"\b{token}\b", lowered))
        for token in ("total", "subtotal", "tax", "invoice", "receipt", "amount", "payment")
    )
    if receipt_words >= 2 and len(ocr_text.strip()) >= 12:
        add("receipt")
    elif len(ocr_text.strip()) >= 90 and not is_screenshot:
        add("document")

    face_count = len(face_boxes)
    if face_count > 1:
        add("people")
    elif face_count == 1:
        add("portrait")
        box = face_boxes[0]
        image_area = max(1, image_size[0] * image_size[1])
        face_area = box.get("width", 0) * box.get("height", 0) / image_area
        explicit_selfie = "selfie" in normalized_filename or "front" in (camera_model or "").casefold()
        model_selfie = semantic_evidence.get("selfie", 0.0) >= 0.86 and face_area >= 0.08
        if not is_screenshot and (explicit_selfie or model_selfie):
            add("selfie")

    if (
        semantic_evidence.get("meme", 0.0) >= 0.76
        and 12 <= len(ocr_text.strip()) < 500
        and not is_screenshot
        and "document" not in labels
    ):
        add("meme")

    aspect_ratio = image_size[0] / max(1, image_size[1])
    thresholds = {
        "landscape": 0.68,
        "food": 0.70,
        "pet": 0.69,
        "vehicle": 0.69,
        "product": 0.72,
        "architecture": 0.70,
        "nature": 0.70,
        "night": 0.72,
        "art": 0.72,
    }
    for label, confidence in sorted(
        semantic_evidence.items(), key=lambda item: item[1], reverse=True
    ):
        if label not in thresholds or confidence < thresholds[label]:
            continue
        if label == "landscape" and aspect_ratio < 1.08:
            continue
        add(label)
    return labels[:5]
