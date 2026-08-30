import math
import time
from io import BytesIO
from threading import Lock

from PIL import Image as PillowImage
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
            tensor = self.preprocess(image).unsqueeze(0).to(self.device)
        with self.torch.no_grad():
            embedding = self.model.encode_image(tensor)
            embedding /= embedding.norm(dim=-1, keepdim=True)
        duration = time.perf_counter() - started
        INFERENCE_DURATION.observe(duration)
        vector = normalize_vector(embedding[0].cpu().float().tolist())
        return vector, duration, self.device


embedder = ClipEmbedder()
