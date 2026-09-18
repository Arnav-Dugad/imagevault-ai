from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
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

    storage_provider: Literal["minio", "azure", "s3"] = "minio"
    azure_storage_account_url: str = ""
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "imagevault"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    registration_enabled: bool = True

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
    max_video_upload_bytes: int = 300 * 1024 * 1024
    max_batch_files: int = 20
    allowed_mime_types: set[str] = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/heic",
        "image/heif",
        "image/x-adobe-dng",
        "image/x-canon-cr2",
        "image/x-nikon-nef",
        "image/x-sony-arw",
        "image/x-raw",
        "video/mp4",
        "video/quicktime",
        "video/webm",
        "video/x-matroska",
        "video/x-msvideo",
    }

    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "laion2b_s34b_b79k"
    embedding_dimension: int = 512
    visual_similarity_threshold: float = 0.85
    perceptual_hash_threshold: int = 8
    similarity_candidate_limit: int = 60
    perceptual_prefilter_distance: int = 18
    presigned_url_expire_minutes: int = Field(default=30, ge=1, le=60)
    metrics_port: int = 9101
    semantic_search_timeout_seconds: int = 30
    semantic_search_min_score: float = 0.16
    analysis_version: int = 5
    ai_device: str = "auto"
    media_sample_frames: int = 6
    ocr_languages: str = "eng+hin+mar+ben+tam+tel+guj+pan"
    face_detector_model_path: str = "/opt/imagevault/models/face_detection_yunet_2023mar.onnx"
    face_recognizer_model_path: str = "/opt/imagevault/models/face_recognition_sface_2021dec.onnx"
    face_embedding_model: str = "opencv-sface-2021dec"
    # SFace's official cosine thresholds are far lower than CLIP's. 0.30 is
    # deliberately cross-pose friendly while the clusterer adds centroid and
    # average-link checks to prevent unrelated identities from chaining.
    face_cluster_threshold: float = 0.30
    event_gap_hours: int = 12
    burst_gap_seconds: int = 12

    @model_validator(mode="after")
    def validate_cloud_settings(self):
        if self.storage_provider == "azure":
            if not self.azure_storage_connection_string and not self.azure_storage_account_url:
                raise ValueError("Azure storage requires an account URL or connection string")
            if self.azure_storage_account_url and not self.azure_storage_account_url.startswith("https://"):
                raise ValueError("Azure storage account URL must use HTTPS")
        if self.storage_provider == "s3" and not self.s3_bucket:
            raise ValueError("S3 storage requires S3_BUCKET")
        if self.environment == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("REPLACE_"):
                raise ValueError("Production requires a random JWT_SECRET of at least 32 characters")
            if self.debug:
                raise ValueError("DEBUG must be disabled in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
