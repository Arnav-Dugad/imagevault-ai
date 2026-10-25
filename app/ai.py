"""Free AI that runs inside ImageVault itself: no paid API, no internet needed after setup.

  CLIP  (OpenAI, MIT license)        turns a photo or a sentence into 512 numbers describing its
                                     meaning; used for smart search and "same subject" suggestions
  YuNet (OpenCV Zoo, MIT license)    finds faces in a photo
  SFace (OpenCV Zoo, Apache 2.0)     turns a face into 128 numbers; the same person gives similar numbers
  PP-OCR + CRNN (OpenCV Zoo, Apache 2.0)  find and read English text in photos (signs, receipts)
  PP-OCRv3 Hindi + Tamil (PaddleOCR, Apache 2.0)  read Devanagari and Tamil text, e.g. Indian station boards

The models (about 245 MB) are downloaded once into the models folder and checked against a
SHA-256 fingerprint, so a changed or corrupted file is never used.
Set IMAGEVAULT_AI=off to turn all of this off.
"""

import hashlib
import logging
import os
import threading
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import data_dir, env

log = logging.getLogger("imagevault")
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")  # hide OpenCV's technical warnings in the worker window

_CLIP = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/d15189d7028b43f1d3e65039190477f6af591c2a"
_ZOO = "https://github.com/opencv/opencv_zoo/raw/48b10fa505aeb51fbd127fc60a5c660040e823b7/models"
_PADDLE = "https://huggingface.co/monkt/paddleocr-onnx/resolve/7b02d0a30a07ba2b92ad1ff5a8941ae2c633de65/languages"
MODELS = {  # file name: (download URL, SHA-256)
    "clip-vision.onnx": (f"{_CLIP}/onnx/vision_model_quantized.onnx",
                         "583fd1110a514667812fee7d684952aaf82a99b959760c8d7dca7e0ab9839299"),
    "clip-text.onnx": (f"{_CLIP}/onnx/text_model_quantized.onnx",
                       "73baab855d406190da9faa498cfedf65f15cf309f4cc7385b7b032e6d08e5c3a"),
    "clip-tokenizer.json": (f"{_CLIP}/tokenizer.json",
                            "f7f3b7af117d467b58374797691a6438d3e6b9e9cef800dfd5dced7f697a90cd"),
    "yunet.onnx": (f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                   "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "sface.onnx": (f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
                   "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
    "text-detect.onnx": (f"{_ZOO}/text_detection_ppocr/text_detection_en_ppocrv3_2023may.onnx",
                         "03f550c6b406fda8bf54bd8327815f6c7e2edd98cea02348c93d879254366587"),
    "text-read.onnx": (f"{_ZOO}/text_recognition_crnn/text_recognition_CRNN_EN_2021sep.onnx",
                       "a84b1f6e11a65c2d733cb0cc1f014aae3f99051e3f11447dc282faa678eee544"),
    "text-read-hindi.onnx": (f"{_PADDLE}/hindi/rec.onnx",
                             "43df175fa3c877fbf7bcc4e5bd1e203e24ec450cd3ea96c9e802c86e39a4d4cf"),
    "text-read-hindi.txt": (f"{_PADDLE}/hindi/dict.txt",
                            "b5f1be6d8bbff1a19fb96c5d4ca96a423380234bb7d2ce0e07b5838adb4d18ea"),
    "text-read-tamil.onnx": (f"{_PADDLE}/tamil/rec.onnx",
                             "fba9a00af746c8f3ef4f091cf966880222cd7245a60f6a953670593630c0ca4f"),
    "text-read-tamil.txt": (f"{_PADDLE}/tamil/dict.txt",
                            "e93e694814afd9ff1e918b6f4bb4267fb4c65a9344ee5d7464f9135b90c0a270"),
}

CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
FACE_MIN_SCORE = 0.9    # how sure YuNet must be that it found a face
FACE_MIN_PIXELS = 32    # smaller faces are too blurry to recognise reliably
FACE_MAX_SIDE = 1600    # photos are shrunk to this size before looking for faces
TEXT_SIDE = 960         # photos are shrunk to this size before looking for text
TEXT_MIN_CONFIDENCE = 0.85  # words the reader is less sure about are mostly noise, so they're dropped
TEXT_MAX_WORDS = 60     # text areas looked at per photo; keeps busy street photos quick to analyse
TEXT_MAX_READS = 200    # words read per photo (a full page of text has more; 200 is plenty to find it)
TEXT_SURE = 0.97        # English words read this confidently are not tried in Hindi or Tamil
TEXT_MAX_INDIAN = 20    # ...and only the 20 clearest text areas are, so busy street photos stay quick
TEXT_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"
WORD_GAP = 10           # in a line straightened to 32 px high, a gap this wide (px) separates two words
SCRIPTS = {"hindi": (0x0900, 0x097F), "tamil": (0x0B80, 0x0BFF)}  # Unicode blocks: Devanagari, Tamil

_download_lock = threading.Lock()
_face_lock = threading.Lock()  # OpenCV's face detector is not safe to share between threads
_text_lock = threading.Lock()


def enabled() -> bool:
    return env("IMAGEVAULT_AI", "on").lower() not in ("off", "false", "0", "no")


def model_dir() -> Path:
    path = Path(env("IMAGEVAULT_MODEL_DIR") or data_dir() / "models")
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_ready() -> bool:
    return all((model_dir() / name).exists() for name in MODELS)


def download_models() -> None:
    """Download any missing model file (once) and verify it."""
    with _download_lock:
        for name, (url, sha256) in MODELS.items():
            target = model_dir() / name
            if target.exists():
                continue
            log.info("Downloading AI model %s", name)
            partial = target.with_suffix(".part")
            digest = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=120) as response, open(partial, "wb") as out:
                while chunk := response.read(1 << 20):
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != sha256:
                partial.unlink(missing_ok=True)
                raise RuntimeError(f"Downloaded {name} does not match its expected fingerprint")
            partial.replace(target)


def _session(name: str):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.enable_cpu_mem_arena = False  # keeps memory use low on small App Service plans
    return ort.InferenceSession(str(model_dir() / name), options, providers=["CPUExecutionProvider"])


@lru_cache(maxsize=1)
def _clip_vision():
    return _session("clip-vision.onnx")


@lru_cache(maxsize=1)
def _clip_text():
    from tokenizers import Tokenizer

    return _session("clip-text.onnx"), Tokenizer.from_file(str(model_dir() / "clip-tokenizer.json"))


@lru_cache(maxsize=1)
def _face_models():
    import cv2

    cv2.setNumThreads(1)  # OpenCV's own thread pool can hang inside a web server; one CPU is plenty here
    detector = cv2.FaceDetectorYN.create(str(model_dir() / "yunet.onnx"), "", (320, 320), FACE_MIN_SCORE)
    recognizer = cv2.FaceRecognizerSF.create(str(model_dir() / "sface.onnx"), "")
    return detector, recognizer


def _normalize(vector: np.ndarray) -> np.ndarray:
    return (vector / np.linalg.norm(vector)).astype(np.float32)


def image_embedding(image: Image.Image) -> np.ndarray:
    """CLIP: 512 numbers describing what the photo shows."""
    width, height = image.size
    scale = 224 / min(width, height)  # resize the short side to 224, then crop the centre square
    image = image.resize((max(224, round(width * scale)), max(224, round(height * scale))), Image.Resampling.BICUBIC)
    left, top = (image.width - 224) // 2, (image.height - 224) // 2
    pixels = np.asarray(image.crop((left, top, left + 224, top + 224)), dtype=np.float32) / 255
    pixels = ((pixels - CLIP_MEAN) / CLIP_STD).transpose(2, 0, 1)[None]
    return _normalize(_clip_vision().run(None, {"pixel_values": pixels})[0][0])


def text_embedding(text: str) -> np.ndarray:
    """CLIP: 512 numbers describing a sentence, comparable with image embeddings."""
    session, tokenizer = _clip_text()
    ids = tokenizer.encode(text.lower()).ids[:77]
    return _normalize(session.run(None, {"input_ids": np.array([ids], dtype=np.int64)})[0][0])


@dataclass
class Face:
    box: tuple[float, float, float, float]  # x, y, width, height as fractions of the photo
    embedding: np.ndarray                    # 128 numbers; the same person gives similar numbers


def find_faces(image: Image.Image) -> list[Face]:
    import cv2

    bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    scale = min(1.0, FACE_MAX_SIDE / max(bgr.shape[:2]))
    if scale < 1:
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    height, width = bgr.shape[:2]
    faces = []
    with _face_lock:
        detector, recognizer = _face_models()
        detector.setInputSize((width, height))
        _, found = detector.detect(bgr)
        for row in found if found is not None else []:
            x, y, w, h = (float(v) for v in row[:4])
            if min(w, h) < FACE_MIN_PIXELS:
                continue
            feature = recognizer.feature(recognizer.alignCrop(bgr, row))[0]
            box = (max(0.0, x / width), max(0.0, y / height), min(1.0, w / width), min(1.0, h / height))
            faces.append(Face(box, _normalize(feature)))
    return faces


@lru_cache(maxsize=1)
def _text_models():
    import cv2

    cv2.setNumThreads(1)
    detector = cv2.dnn_TextDetectionModel_DB(cv2.dnn.readNet(str(model_dir() / "text-detect.onnx")))
    detector.setBinaryThreshold(0.3)
    detector.setPolygonThreshold(0.5)
    detector.setUnclipRatio(2.0)
    detector.setMaxCandidates(200)
    return detector


@lru_cache(maxsize=1)
def _english_reader():
    return _session("text-read.onnx")  # ONNX Runtime reads these about 7x faster than OpenCV's DNN module


def _read_words(images: list[np.ndarray]) -> list[tuple[str, float]]:
    """CRNN reads word images (grey). Returns each text and how sure it is (0..1)."""
    import cv2

    session = _english_reader()
    name = session.get_inputs()[0].name
    results = []
    for image in images:
        pixels = (cv2.resize(image, (100, 32)).astype(np.float32) - 127.5) / 127.5
        scores = session.run(None, {name: pixels[None, None]})[0][:, 0, :]  # positions x (blank + 36 characters)
        probabilities = np.exp(scores - scores.max(axis=1, keepdims=True))
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        chars, sure, previous = [], [], 0
        for position, best in enumerate(probabilities.argmax(axis=1)):
            if best and best != previous:  # CTC: skip blanks and repeated characters
                chars.append(TEXT_CHARS[best - 1])
                sure.append(probabilities[position, best])
            previous = best
        results.append(("".join(chars), float(np.mean(sure)) if sure else 0.0))
    return results


def _indian_readers() -> dict:
    """PaddleOCR readers for Hindi (Devanagari) and Tamil, each with its list of characters."""
    readers = {}
    for language in SCRIPTS:
        chars = (model_dir() / f"text-read-{language}.txt").read_text(encoding="utf-8").splitlines() + [" "]
        readers[language] = (_session(f"text-read-{language}.onnx"), chars)
    return readers


def _read_indian(session, chars: list[str], word: np.ndarray) -> tuple[str, float]:
    """Read one straightened word image (colour, any size) with a PaddleOCR reader."""
    import cv2

    height, width = word.shape[:2]
    pixels = cv2.resize(word, (max(16, min(960, round(48 * width / height))), 48)).astype(np.float32) / 255
    probabilities = session.run(None, {"x": ((pixels - 0.5) / 0.5).transpose(2, 0, 1)[None]})[0][0]
    text, sure, previous = [], [], 0
    for position, best in enumerate(probabilities.argmax(axis=1)):
        if best and best != previous:
            text.append(chars[best - 1])
            sure.append(probabilities[position, best])
        previous = best
    return "".join(text).strip(), float(np.mean(sure)) if sure else 0.0


def _in_script(text: str, language: str) -> bool:
    """Mostly letters of that language's script (so a Hindi reader's guess at English text is ignored)."""
    low, high = SCRIPTS[language]
    letters = [c for c in text if not c.isspace()]
    return len(letters) >= 2 and sum(low <= ord(c) <= high for c in letters) / len(letters) >= 0.6


@dataclass
class Word:
    text: str
    box: tuple[float, float, float, float]  # x, y, width, height as fractions of the photo


def _word_gaps(line: np.ndarray) -> list[tuple[int, int]]:
    """Split a straightened line of text (32 px high) into words at the gaps between them.
    The English reader reads one word at a time, so "TOTAL 14.21 CASH" must be cut into three."""
    import cv2

    _, binary = cv2.threshold(line, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = binary == 0 if (binary == 0).mean() < 0.5 else binary == 255  # dark text on light, or light on dark
    used = ink.sum(axis=0) > 1
    words, start, gap = [], None, 0
    for x, has_ink in enumerate(used):
        if has_ink:
            if start is None:
                start = x
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= WORD_GAP:  # a space this wide ends a word
                words.append((start, x - gap + 1))
                start, gap = None, 0
    if start is not None:
        words.append((start, len(used) - gap))
    pad = 4
    words = [(max(0, a - pad), min(len(used), b + pad)) for a, b in words if b - a >= 6]
    return words or [(0, len(used))]


def _box_part(corners: np.ndarray, start: float, end: float) -> np.ndarray:
    """The corners of part of a text area, from `start` to `end` along the line (0..1).
    Corner order: bottom-left, top-left, top-right, bottom-right."""
    top, bottom = corners[2] - corners[1], corners[3] - corners[0]
    return np.array([corners[1] + start * top, corners[1] + end * top,
                     corners[0] + start * bottom, corners[0] + end * bottom])


def read_text(image: Image.Image) -> list[Word]:
    """Words written in the photo (English, Hindi or Tamil), with where they are, for search and highlighting."""
    import cv2

    bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    scale = TEXT_SIDE / max(height, width)
    size = (max(32, round(width * scale / 32) * 32), max(32, round(height * scale / 32) * 32))
    grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    words: list[Word] = []

    def add(text: str, points: np.ndarray) -> None:
        if text and all(text != word.text for word in words):
            xs, ys = np.clip(points[:, 0] / width, 0, 1), np.clip(points[:, 1] / height, 0, 1)
            words.append(Word(text, (float(xs.min()), float(ys.min()),
                                     float(xs.max() - xs.min()), float(ys.max() - ys.min()))))

    with _text_lock:
        detector = _text_models()
        indian = _indian_readers()
        detector.setInputParams(1.0 / 255.0, size, (122.67891434, 116.66876762, 104.00698793))
        boxes, scores = detector.detect(cv2.resize(bgr, size))
        ranked = sorted(zip(boxes, scores), key=lambda b: b[1], reverse=True)[:TEXT_MAX_WORDS]
        clearest = {id(box) for box, _ in ranked[:TEXT_MAX_INDIAN]}  # Hindi/Tamil are tried on these only

        # Pass 1: straighten each text area at 32 px high and cut it into words.
        areas, crops = [], []
        for box, _ in sorted(ranked, key=lambda b: (min(p[1] for p in b[0]), min(p[0] for p in b[0]))):
            corners = (np.array(box, dtype=np.float32) * [width / size[0], height / size[1]]).astype(np.float32)
            w = int(max(np.linalg.norm(corners[2] - corners[1]), np.linalg.norm(corners[3] - corners[0])))
            h = int(max(np.linalg.norm(corners[0] - corners[1]), np.linalg.norm(corners[3] - corners[2])))
            if w < 8 or h < 8:
                continue
            length = max(32, round(32 * w / h))
            flat = np.array([[0, 31], [0, 0], [length - 1, 0], [length - 1, 31]], dtype=np.float32)
            line = cv2.warpPerspective(grey, cv2.getPerspectiveTransform(corners, flat), (length, 32))
            parts = [(a / length, b / length, len(crops) + i) for i, (a, b) in enumerate(_word_gaps(line))]
            crops += [line[:, round(a * length):round(b * length)] for a, b, _ in parts]
            areas.append((box, corners, w, h, parts))

        # Pass 2: the English reader reads every word in one batch.
        readings = _read_words(crops[:TEXT_MAX_READS])

        # Pass 3: keep the confident words. Hindi and Tamil read whole lines where English found little.
        for box, corners, w, h, parts in areas:
            english = [(readings[i][1], readings[i][0], a, b) for a, b, i in parts if i < len(readings)
                       and len(readings[i][0]) >= 3 and readings[i][1] >= TEXT_MIN_CONFIDENCE]
            sure = max((e[0] for e in english), default=0.0)
            best = None
            if len(english) < 2 and sure < TEXT_SURE and id(box) in clearest:
                straight = np.array([[0, h - 1], [0, 0], [w - 1, 0], [w - 1, h - 1]], dtype=np.float32)
                colour = cv2.warpPerspective(bgr, cv2.getPerspectiveTransform(corners, straight), (w, h))
                for language, (session, chars) in indian.items():
                    text, confidence = _read_indian(session, chars, colour)
                    text = "".join(text.split())
                    if confidence >= TEXT_MIN_CONFIDENCE and confidence > max(sure, best[0] if best else 0) \
                            and _in_script(text, language):
                        best = (confidence, text)
            if best:
                add(best[1], _box_part(corners, 0, 1))
            else:
                for _, text, a, b in english:
                    add(text, _box_part(corners, a, b))
    return words


def to_bytes(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def from_bytes(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)
