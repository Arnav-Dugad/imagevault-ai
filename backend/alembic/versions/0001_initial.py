"""Initial ImageVault schema with pgvector.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_key", sa.String(length=500), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("perceptual_hash", sa.String(length=32), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "PROCESSING", "READY", "EXACT_DUPLICATE", "FAILED",
                name="processingstatus", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("exact_duplicate_of_id", sa.Uuid(), nullable=True),
        sa.Column("exif_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("camera_model", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exact_duplicate_of_id"], ["images.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_images_created_at", "images", ["created_at"])
    op.create_index("ix_images_exact_duplicate_of_id", "images", ["exact_duplicate_of_id"])
    op.create_index("ix_images_perceptual_hash", "images", ["perceptual_hash"])
    op.create_index("ix_images_sha256", "images", ["sha256"])
    op.create_index("ix_images_status", "images", ["status"])
    op.create_index("ix_images_user_id", "images", ["user_id"])
    op.create_index("ix_images_user_created", "images", ["user_id", "created_at"])
    op.create_index("ix_images_user_sha256", "images", ["user_id", "sha256"])
    op.create_index(
        "ix_images_embedding_hnsw",
        "images",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_logs_action", "activity_logs", ["action"])
    op.create_table(
        "duplicate_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_image_id", sa.Uuid(), nullable=False),
        sa.Column("target_image_id", sa.Uuid(), nullable=False),
        sa.Column(
            "match_type",
            sa.Enum("EXACT", "PERCEPTUAL", "VISUAL", name="duplicatetype", native_enum=False),
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("phash_distance", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_image_id"], ["images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_image_id"], ["images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_image_id", "target_image_id", "match_type", name="uq_match_pair"),
    )
    op.create_index("ix_duplicate_matches_source_image_id", "duplicate_matches", ["source_image_id"])
    op.create_index("ix_duplicate_matches_target_image_id", "duplicate_matches", ["target_image_id"])
    op.create_index("ix_duplicate_matches_user_type", "duplicate_matches", ["user_id", "match_type"])
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETE", "FAILED", name="jobstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_jobs_image_id", "processing_jobs", ["image_id"], unique=True)


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_table("duplicate_matches")
    op.drop_table("activity_logs")
    op.drop_table("images")
    op.drop_table("users")
