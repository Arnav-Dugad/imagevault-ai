"""Free AI that runs inside ImageVault itself: no paid API, no internet needed after setup.

  CLIP  (OpenAI, MIT license)        turns a photo or a sentence into 512 numbers describing its
                                     meaning; used for smart search and "same subject" suggestions
  YuNet (OpenCV Zoo, MIT license)    finds faces in a photo
  SFace (OpenCV Zoo, Apache 2.0)     turns a face into 128 numbers; the same person gives similar numbers
  PP-OCRv3 text detector (OpenCV Zoo, Apache 2.0)  finds where text is written in a photo
  PaddleOCR readers (Apache 2.0)     read the text: English (PP-OCRv5), Hindi, Tamil, Telugu and Kannada
                                     (PP-OCRv3). Kannada was converted to ONNX for this project (see the
                                     "models-1" release on GitHub); the others come from monkt/paddleocr-onnx.
  OpenCV's QR code reader            reads QR codes (no model to download)

The models (about 235 MB) are downloaded once into the models folder and checked against a
SHA-256 fingerprint, so a changed or corrupted file is never used.
Set IMAGEVAULT_AI=off to turn all of this off.
"""

import hashlib
import logging
import os
import re
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
_RELEASE = "https://github.com/Arnav-Dugad/imagevault-ai/releases/download/models-1"
_PADDLE_DICTS = "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/ppocr/utils/dict"
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
    "text-read-english.onnx": (f"{_PADDLE}/english/rec.onnx",
                               "4e16deb22c4da6468bdca539b2cd3c8687825538b67109177c47d359ab994cd7"),
    "text-read-english.txt": (f"{_PADDLE}/english/dict.txt",
                              "e025a66d31f327ba0c232e03f407ae8d105e1e709e7ccb3f408aa778c24e70d6"),
    "text-read-hindi.onnx": (f"{_PADDLE}/hindi/rec.onnx",
                             "43df175fa3c877fbf7bcc4e5bd1e203e24ec450cd3ea96c9e802c86e39a4d4cf"),
    "text-read-hindi.txt": (f"{_PADDLE}/hindi/dict.txt",
                            "b5f1be6d8bbff1a19fb96c5d4ca96a423380234bb7d2ce0e07b5838adb4d18ea"),
    "text-read-tamil.onnx": (f"{_PADDLE}/tamil/rec.onnx",
                             "fba9a00af746c8f3ef4f091cf966880222cd7245a60f6a953670593630c0ca4f"),
    "text-read-tamil.txt": (f"{_PADDLE}/tamil/dict.txt",
                            "e93e694814afd9ff1e918b6f4bb4267fb4c65a9344ee5d7464f9135b90c0a270"),
    "text-read-telugu.onnx": (f"{_PADDLE}/telugu/rec.onnx",
                              "669946d9ad4de93e8d1b13f7e72c59cc2cc2de91bb24e22aad7503a6cc5757ee"),
    "text-read-telugu.txt": (f"{_PADDLE}/telugu/dict.txt",
                             "ee9946a60d7701977474e89883694a4ca20eaa3868a23334bf7940dcd008f0f9"),
    "text-read-kannada.onnx": (f"{_RELEASE}/text-read-kannada.onnx",
                               "240d0edc4493d0e1411874fb1c704df28f7ffc2430131eafc715eaf593bf7ed8"),
    "text-read-kannada.txt": (f"{_PADDLE_DICTS}/ka_dict.txt",
                              "fad3f765943275eec2134a6fbc9b52785426641104d4e7db3a159dc73f341dde"),
}

CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
FACE_MIN_SCORE = 0.9    # how sure YuNet must be that it found a face
FACE_MIN_PIXELS = 32    # smaller faces are too blurry to recognise reliably
FACE_MAX_SIDE = 1600    # photos are shrunk to this size before looking for faces
FACE_RETRY_SIDE = 640   # a close-up face filling the photo is only found at a smaller size
TEXT_SIDE = 960         # photos are shrunk to this size before looking for text
TEXT_MIN_CONFIDENCE = 0.85  # lines the reader is less sure about are mostly noise, so they're dropped
TEXT_MAX_LINES = 80     # text areas read per photo; keeps busy street photos quick to analyse
TEXT_SURE = 0.97        # English read this confidently is not tried in the Indian languages
TEXT_MAX_INDIAN = 20    # ...and only the 20 clearest text areas are, so busy street photos stay quick
SCRIPTS = {"hindi": (0x0900, 0x097F), "tamil": (0x0B80, 0x0BFF), "telugu": (0x0C00, 0x0C7F),  # Unicode blocks
           "kannada": (0x0C80, 0x0CFF)}

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
    return _detect_faces(image, FACE_MAX_SIDE) or _detect_faces(image, FACE_RETRY_SIDE)


def _detect_faces(image: Image.Image, max_side: int) -> list[Face]:
    import cv2

    bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    scale = min(1.0, max_side / max(bgr.shape[:2]))
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
def _readers() -> dict:
    """The PaddleOCR text readers, each with its list of characters (plus a space at the end)."""
    readers = {}
    for language in ("english", *SCRIPTS):
        chars = (model_dir() / f"text-read-{language}.txt").read_text(encoding="utf-8").splitlines() + [" "]
        readers[language] = (_session(f"text-read-{language}.onnx"), chars)
    return readers


def _read_line(session, chars: list[str], line: np.ndarray) -> tuple[str, float, list[float]]:
    """Read one straightened line of text (colour image). Returns the text, how sure the reader is (0..1),
    and where along the line (0..1) each character is."""
    import cv2

    height, width = line.shape[:2]
    pixels = cv2.resize(line, (max(16, min(1600, round(48 * width / height))), 48)).astype(np.float32) / 255
    probabilities = session.run(None, {"x": ((pixels - 0.5) / 0.5).transpose(2, 0, 1)[None]})[0][0]
    text, sure, where, previous = [], [], [], 0
    for position, best in enumerate(probabilities.argmax(axis=1)):
        if best and best != previous:  # CTC: skip blanks and repeated characters
            text.append(chars[best - 1])
            sure.append(probabilities[position, best])
            where.append((position + 0.5) / len(probabilities))
        previous = best
    return "".join(text), float(np.mean(sure)) if sure else 0.0, where


def _in_script(text: str, language: str) -> bool:
    """Mostly letters of that language's script (so a guess at text in another script is ignored)."""
    low, high = SCRIPTS[language]
    letters = [c for c in text if not c.isspace()]
    in_script = [c for c in letters if low <= ord(c) <= high]
    # At least 3 different letters: a row of light bulbs can look like "ంంంం" to the Telugu reader.
    return len(set(in_script)) >= 3 and len(in_script) / len(letters) >= 0.8


_VOWEL_SIGN_I = re.compile("\u093f([\u0915-\u0939\u0958-\u095f]\u093c?)")


def _logical_order(word: str) -> str:
    """The Hindi reader gives the vowel sign "ि" where it is drawn, before its consonant ("िटकट"), but
    it is typed (and stored in Unicode) after it ("टिकट"), so search needs it moved."""
    return _VOWEL_SIGN_I.sub("\\1\u093f", word)


def _split_words(text: str, where: list[float], step: float) -> list[tuple[str, float, float]]:
    """Cut a line into words, with where each one starts and ends along the line (0..1)."""
    words, current = [], []
    for char, at in zip(list(text) + [" "], where + [1.0]):
        if char.isspace():
            if current and any(c.isalnum() for c, _ in current):
                words.append(("".join(c for c, _ in current), max(0.0, current[0][1] - step),
                              min(1.0, current[-1][1] + step)))
            current = []
        else:
            current.append((char, at))
    return words


@dataclass
class Word:
    text: str
    box: tuple[float, float, float, float]  # x, y, width, height as fractions of the photo
    line: int = 0                           # which line of text it belongs to


def _box_part(corners: np.ndarray, start: float, end: float) -> np.ndarray:
    """The corners of part of a text area, from `start` to `end` along the line (0..1).
    Corner order: bottom-left, top-left, top-right, bottom-right."""
    top, bottom = corners[2] - corners[1], corners[3] - corners[0]
    return np.array([corners[1] + start * top, corners[1] + end * top,
                     corners[0] + start * bottom, corners[0] + end * bottom])


@dataclass
class QrCode:
    text: str
    box: tuple[float, float, float, float]  # x, y, width, height as fractions of the photo


def read_qr_codes(image: Image.Image) -> list[QrCode]:
    """QR codes in the photo (links, Wi-Fi details, payment codes...), with where they are."""
    import cv2

    bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    scale = min(1.0, 1600 / max(bgr.shape[:2]))
    if scale < 1:
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    height, width = bgr.shape[:2]
    try:
        found, texts, corners, _ = cv2.QRCodeDetector().detectAndDecodeMulti(bgr)
    except cv2.error:
        return []
    codes = []
    for text, points in zip(texts if found else [], corners if found else []):
        if text:
            xs, ys = np.clip(points[:, 0] / width, 0, 1), np.clip(points[:, 1] / height, 0, 1)
            codes.append(QrCode(text, (float(xs.min()), float(ys.min()), float(xs.max() - xs.min()),
                                       float(ys.max() - ys.min()))))
    return codes


def read_text(image: Image.Image) -> list[Word]:
    """Words written in the photo (English, Hindi, Tamil or Telugu), with where they are and which line
    they're on, for search, highlighting and copying."""
    import cv2

    bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    scale = TEXT_SIDE / max(height, width)
    size = (max(32, round(width * scale / 32) * 32), max(32, round(height * scale / 32) * 32))
    words: list[Word] = []
    with _text_lock:
        detector = _text_models()
        readers = _readers()
        detector.setInputParams(1.0 / 255.0, size, (122.67891434, 116.66876762, 104.00698793))
        boxes, scores = detector.detect(cv2.resize(bgr, size))
        ranked = sorted(zip(boxes, scores), key=lambda b: b[1], reverse=True)[:TEXT_MAX_LINES]
        clearest = {id(box) for box, _ in ranked[:TEXT_MAX_INDIAN]}  # Indian languages are tried on these only
        line = 0
        for box, _ in sorted(ranked, key=lambda b: (min(p[1] for p in b[0]), min(p[0] for p in b[0]))):
            corners = (np.array(box, dtype=np.float32) * [width / size[0], height / size[1]]).astype(np.float32)
            w = int(max(np.linalg.norm(corners[2] - corners[1]), np.linalg.norm(corners[3] - corners[0])))
            h = int(max(np.linalg.norm(corners[0] - corners[1]), np.linalg.norm(corners[3] - corners[2])))
            if w < 8 or h < 8:
                continue
            straight = np.array([[0, h - 1], [0, 0], [w - 1, 0], [w - 1, h - 1]], dtype=np.float32)
            area = cv2.warpPerspective(bgr, cv2.getPerspectiveTransform(corners, straight), (w, h))
            # English first; Indian languages read the line too unless English is already very sure.
            text, sure, where = _read_line(*readers["english"], area)
            best = (sure, text, where) if sure >= TEXT_MIN_CONFIDENCE and sum(c.isalnum() for c in text) >= 2 \
                else (0.0, "", [])
            english_words = sum(len(w) >= 3 and w.isascii() and w.isalpha() for w in text.split())
            if sure < TEXT_SURE and english_words < 2 and id(box) in clearest:
                for language in SCRIPTS:
                    text, sure, where = _read_line(*readers[language], area)
                    if sure >= TEXT_MIN_CONFIDENCE and sure > best[0] and _in_script(text, language):
                        best = (sure, text, where)
            if not best[1]:
                continue
            step = 0.6 * (best[2][1] - best[2][0]) if len(best[2]) > 1 else 0.05
            for word, start, end in _split_words(best[1], best[2], step):
                points = _box_part(corners, start, end)
                xs, ys = np.clip(points[:, 0] / width, 0, 1), np.clip(points[:, 1] / height, 0, 1)
                words.append(Word(_logical_order(word), (float(xs.min()), float(ys.min()), float(xs.max() - xs.min()),
                                         float(ys.max() - ys.min())), line))
            line += 1
    return words


def to_bytes(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def from_bytes(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)
