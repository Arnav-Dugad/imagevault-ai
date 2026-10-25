"""Free AI that runs inside ImageVault itself: no paid API, no internet needed after setup.

  CLIP  (OpenAI, MIT license)        turns a photo or a sentence into 512 numbers describing its
                                     meaning; used for smart search and "same subject" suggestions
  YuNet (OpenCV Zoo, MIT license)    finds faces in a photo
  SFace (OpenCV Zoo, Apache 2.0)     turns a face into 128 numbers; the same person gives similar numbers

The models (about 190 MB) are downloaded once into the models folder and checked against a
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
}

CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
FACE_MIN_SCORE = 0.9    # how sure YuNet must be that it found a face
FACE_MIN_PIXELS = 32    # smaller faces are too blurry to recognise reliably
FACE_MAX_SIDE = 1600    # photos are shrunk to this size before looking for faces

_download_lock = threading.Lock()
_face_lock = threading.Lock()  # OpenCV's face detector is not safe to share between threads


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


def to_bytes(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def from_bytes(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)
