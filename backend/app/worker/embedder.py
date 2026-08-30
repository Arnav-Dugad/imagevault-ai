import math
import time
from io import BytesIO
from threading import Lock
from collections.abc import Sequence

from PIL import Image as PillowImage, ImageOps
from redis import Redis

from app.core.config import get_settings
from app.metrics import INFERENCE_DURATION, MODEL_LOADED


def normalize_vector(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        raise ValueError("Cannot normalize a zero vector")
    return [value / magnitude for value in values]


class ClipEmbedder:
    """Lazy OpenCLIP loader; model weights are cached outside the repository."""

    _instance: "ClipEmbedder | None" = None
    _lock = Lock()

    def __new__(cls) -> "ClipEmbedder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._loaded = False
        return cls._instance

    def _load(self) -> None:
        if self._loaded:
            return
        import open_clip
        import torch

        settings = get_settings()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            settings.clip_model,
            pretrained=settings.clip_pretrained,
            device=self.device,
        )
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer(settings.clip_model)
        self.torch = torch
        self._loaded = True
        MODEL_LOADED.set(1)
        try:
            redis = Redis.from_url(settings.redis_url, decode_responses=True)
            redis.set("imagevault:worker:model", "loaded", ex=3600)
            redis.close()
        except Exception:
            pass

    def image_embedding(self, data: bytes) -> tuple[list[float], float, str]:
        self._load()
        started = time.perf_counter()
        with PillowImage.open(BytesIO(data)) as source:
            image = source.convert("RGB")
            # Combine a normal CLIP crop with a full-frame padded view and its
            # mirror. This retains edge content and makes near-duplicate search
            # more robust to crops, borders, screenshots, and horizontal flips.
            full_frame = ImageOps.pad(
                image,
                (384, 384),
                method=PillowImage.Resampling.LANCZOS,
                color=(127, 127, 127),
            )
            views = [image, full_frame, ImageOps.mirror(full_frame)]
            tensor = self.torch.stack([self.preprocess(view) for view in views]).to(self.device)
        with self.torch.no_grad():
            view_embeddings = self.model.encode_image(tensor)
            view_embeddings /= view_embeddings.norm(dim=-1, keepdim=True)
            embedding = view_embeddings.mean(dim=0, keepdim=True)
            embedding /= embedding.norm(dim=-1, keepdim=True)
        duration = time.perf_counter() - started
        INFERENCE_DURATION.observe(duration)
        vector = normalize_vector(embedding[0].cpu().float().tolist())
        return vector, duration, self.device

    def image_embeddings(self, images: Sequence[PillowImage.Image]) -> list[list[float]]:
        if not images:
            return []
        self._load()
        tensor = self.torch.stack([self.preprocess(image.convert("RGB")) for image in images]).to(
            self.device
        )
        with self.torch.no_grad():
            embeddings = self.model.encode_image(tensor)
            embeddings /= embeddings.norm(dim=-1, keepdim=True)
        return [normalize_vector(row) for row in embeddings.cpu().float().tolist()]

    def text_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load()
        tokens = self.tokenizer(list(texts)).to(self.device)
        with self.torch.no_grad():
            embeddings = self.model.encode_text(tokens)
            embeddings /= embeddings.norm(dim=-1, keepdim=True)
        return [normalize_vector(row) for row in embeddings.cpu().float().tolist()]

    def text_embedding(self, text: str) -> list[float]:
        return self.text_embeddings([text])[0]


embedder = ClipEmbedder()
