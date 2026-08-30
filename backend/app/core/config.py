from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = "ImageVault AI"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api"

    database_url: str = "postgresql+asyncpg://imagevault:imagevault@postgres:5432/imagevault"
    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_public_endpoint: str = "localhost:9000"
    minio_region: str = "us-east-1"
    minio_access_key: str = "imagevault"
    minio_secret_key: str = "change-me-in-env"
    minio_bucket: str = "imagevault"
    minio_secure: bool = False
    minio_public_secure: bool = False

    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: str = "http://localhost:5173"
    max_upload_bytes: int = 15 * 1024 * 1024
    max_batch_files: int = 20
    allowed_mime_types: set[str] = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "laion2b_s34b_b79k"
    embedding_dimension: int = 512
    visual_similarity_threshold: float = 0.85
    perceptual_hash_threshold: int = 8
    similarity_candidate_limit: int = 60
    perceptual_prefilter_distance: int = 18
    presigned_url_expire_minutes: int = 30
    metrics_port: int = 9101
    semantic_search_timeout_seconds: int = 30
    semantic_search_min_score: float = 0.16
    analysis_version: int = 4
    face_detector_model_path: str = "/opt/imagevault/models/face_detection_yunet_2023mar.onnx"
    face_recognizer_model_path: str = "/opt/imagevault/models/face_recognition_sface_2021dec.onnx"
    face_embedding_model: str = "opencv-sface-2021dec"
    # SFace's official cosine thresholds are far lower than CLIP's. 0.30 is
    # deliberately cross-pose friendly while the clusterer adds centroid and
    # average-link checks to prevent unrelated identities from chaining.
    face_cluster_threshold: float = 0.30
    event_gap_hours: int = 12
    burst_gap_seconds: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
