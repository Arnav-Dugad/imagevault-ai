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
    if not math.isfinite(magnitude) or magnitude == 0:
        raise ValueError("Cannot normalize a zero or non-finite vector")
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
        requested = settings.ai_device.casefold()
        cuda_available = torch.cuda.is_available()
        self.device = "cuda" if requested in {"auto", "cuda"} and cuda_available else "cpu"
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
            redis.set("imagevault:worker:device", self.device, ex=3600)
            redis.close()
        except Exception:
            pass

    def _fallback_to_cpu(self) -> None:
        if self.device != "cuda":
            return
        self.model.to("cpu")
        self.device = "cpu"
        self.torch.cuda.empty_cache()
        try:
            redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
            redis.set("imagevault:worker:device", "cpu-fallback", ex=3600)
            redis.close()
        except Exception:
            pass

    def image_embedding_frames(
        self, images: Sequence[PillowImage.Image]
    ) -> tuple[list[float], float, str]:
        self._load()
        started = time.perf_counter()
        views: list[PillowImage.Image] = []
        for source in images:
            image = source.convert("RGB")
            full_frame = ImageOps.pad(
                image,
                (384, 384),
                method=PillowImage.Resampling.LANCZOS,
                color=(127, 127, 127),
            )
            views.extend([image, full_frame, ImageOps.mirror(full_frame)])

        def infer() -> object:
            tensor = self.torch.stack([self.preprocess(view) for view in views]).to(self.device)
            with self.torch.no_grad():
                view_embeddings = self.model.encode_image(tensor)
                view_embeddings /= view_embeddings.norm(dim=-1, keepdim=True)
                combined = view_embeddings.mean(dim=0, keepdim=True)
                combined /= combined.norm(dim=-1, keepdim=True)
            return combined

        try:
            embedding = infer()
        except RuntimeError:
            if self.device != "cuda":
                raise
            self._fallback_to_cpu()
            embedding = infer()
        duration = time.perf_counter() - started
        INFERENCE_DURATION.observe(duration)
        vector = normalize_vector(embedding[0].cpu().float().tolist())
        return vector, duration, self.device

    def image_embedding(self, data: bytes) -> tuple[list[float], float, str]:
        with PillowImage.open(BytesIO(data)) as source:
            image = source.convert("RGB")
        return self.image_embedding_frames([image])

    def text_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load()
        def infer() -> object:
            tokens = self.tokenizer(list(texts)).to(self.device)
            with self.torch.no_grad():
                result = self.model.encode_text(tokens)
                result /= result.norm(dim=-1, keepdim=True)
            return result

        try:
            embeddings = infer()
        except RuntimeError:
            if self.device != "cuda":
                raise
            self._fallback_to_cpu()
            embeddings = infer()
        return [normalize_vector(row) for row in embeddings.cpu().float().tolist()]

    def text_embedding(self, text: str) -> list[float]:
        return self.text_embeddings([text])[0]


embedder = ClipEmbedder()
