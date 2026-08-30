import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    FAILED = "FAILED"


class DuplicateType(str, enum.Enum):
    EXACT = "EXACT"
    PERCEPTUAL = "PERCEPTUAL"
    VISUAL = "VISUAL"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    images: Mapped[list["Image"]] = relationship(back_populates="user", cascade="all, delete")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(512).with_variant(JSON(), "sqlite"), nullable=True
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, native_enum=False), default=ProcessingStatus.PENDING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    exact_duplicate_of_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("images.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    exif_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    camera_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="images")
    exact_duplicate_of: Mapped["Image | None"] = relationship(
        remote_side="Image.id", foreign_keys=[exact_duplicate_of_id]
    )
    job: Mapped["ProcessingJob | None"] = relationship(
        back_populates="image", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index("ix_images_user_sha256", "user_id", "sha256"),
        Index("ix_images_user_created", "user_id", "created_at"),
        Index(
            "ix_images_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class DuplicateMatch(Base):
    __tablename__ = "duplicate_matches"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    source_image_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    target_image_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    match_type: Mapped[DuplicateType] = mapped_column(Enum(DuplicateType, native_enum=False))
    similarity_score: Mapped[float] = mapped_column(Float)
    phash_distance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source: Mapped[Image] = relationship(foreign_keys=[source_image_id])
    target: Mapped[Image] = relationship(foreign_keys=[target_image_id])

    __table_args__ = (
        UniqueConstraint("source_image_id", "target_image_id", "match_type", name="uq_match_pair"),
        Index("ix_duplicate_matches_user_type", "user_id", "match_type"),
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    image_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("images.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    image: Mapped[Image] = relationship(back_populates="job")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(100), index=True)
    image_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
