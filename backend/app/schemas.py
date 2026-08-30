from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DuplicateType, ProcessingStatus


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ImageSummary(BaseModel):
    id: UUID
    batch_id: UUID | None
    original_filename: str
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    sha256: str
    perceptual_hash: str | None
    status: ProcessingStatus
    exact_duplicate_of_id: UUID | None
    created_at: datetime
    processed_at: datetime | None
    thumbnail_url: str | None = None
    original_url: str | None = None
    best_similarity: float | None = None
    blur_score: float | None = None
    exposure_score: float | None = None
    resolution_score: float | None = None
    screenshot_quality_score: float | None = None
    quality_score: float | None = None
    is_screenshot: bool = False
    smart_labels: list[str] = Field(default_factory=list)
    face_count: int = 0


class SimilarImage(BaseModel):
    image: ImageSummary
    similarity_score: float
    classification: str
    match_type: DuplicateType
    phash_distance: int | None = None
    clip_score: float | None = None
    perceptual_score: float | None = None
    color_score: float | None = None
    aspect_score: float | None = None
    reasons: list[str] = Field(default_factory=list)


class ImageDetail(ImageSummary):
    object_key: str
    thumbnail_key: str | None
    error_message: str | None
    exif_timestamp: datetime | None
    camera_model: str | None
    ocr_text: str | None
    exact_duplicate_of: ImageSummary | None = None
    similar_images: list[SimilarImage] = Field(default_factory=list)


class ImageListResponse(BaseModel):
    items: list[ImageSummary]
    total: int
    page: int
    page_size: int
    pages: int


class UploadItem(BaseModel):
    image: ImageSummary
    exact_duplicate: bool
    matched_filename: str | None = None
    message: str


class UploadResponse(BaseModel):
    batch_id: UUID
    items: list[UploadItem]


class ReindexResponse(BaseModel):
    queued: int
    message: str


class BulkDeleteRequest(BaseModel):
    image_ids: list[UUID] = Field(min_length=1, max_length=100)
    confirm: bool = False


class BulkDeleteResponse(BaseModel):
    deleted: int
    recovered_bytes: int
    message: str


class SmartAlbum(BaseModel):
    id: str
    title: str
    subtitle: str
    cover: ImageSummary
    images: list[ImageSummary]
    image_count: int
    best_image_id: UUID | None = None


class SmartAlbumsResponse(BaseModel):
    items: list[SmartAlbum]
    total: int


class DuplicateCandidate(BaseModel):
    image: ImageSummary
    similarity_score: float
    match_type: DuplicateType
    classification: str
    phash_distance: int | None = None
    clip_score: float | None = None
    perceptual_score: float | None = None
    color_score: float | None = None
    aspect_score: float | None = None
    reasons: list[str] = Field(default_factory=list)
    same_batch: bool = False


class DuplicateGroup(BaseModel):
    group_id: str
    original: ImageSummary
    candidates: list[DuplicateCandidate]
    recoverable_bytes: int
    highest_similarity: float = 0
    all_same_batch: bool = False


class DuplicateReviewResponse(BaseModel):
    groups: list[DuplicateGroup]
    batch_id: UUID | None = None
    total_groups: int
    exact_duplicates: int
    similar_images: int
    recoverable_bytes: int
    processing_images: int
    total_images_scanned: int


class DashboardMetric(BaseModel):
    value: int
    change_percent: float | None = None


class TimeSeriesPoint(BaseModel):
    label: str
    uploads: int
    duplicates: int


class DistributionPoint(BaseModel):
    name: str
    value: int


class DashboardResponse(BaseModel):
    total_images: int
    unique_images: int
    exact_duplicates: int
    similar_images: int
    storage_used: int
    potential_savings: int
    processing_images: int
    uploads_over_time: list[TimeSeriesPoint]
    format_distribution: list[DistributionPoint]
    recent_images: list[ImageSummary]


class ComponentHealth(BaseModel):
    status: str
    detail: str | None = None


class SystemStatusResponse(BaseModel):
    status: str
    version: str
    api: ComponentHealth
    database: ComponentHealth
    object_storage: ComponentHealth
    worker: ComponentHealth
    embedding_model: ComponentHealth
    pending_jobs: int
    queue_size: int | None = None


class MessageResponse(BaseModel):
    message: str
