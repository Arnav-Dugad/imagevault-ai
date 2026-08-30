"""Add local intelligence metadata and private face suggestions.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("images", sa.Column("blur_score", sa.Float(), nullable=True))
    op.add_column("images", sa.Column("exposure_score", sa.Float(), nullable=True))
    op.add_column("images", sa.Column("resolution_score", sa.Float(), nullable=True))
    op.add_column("images", sa.Column("screenshot_quality_score", sa.Float(), nullable=True))
    op.add_column("images", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column(
        "images", sa.Column("is_screenshot", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("images", sa.Column("smart_labels", sa.JSON(), nullable=True))
    op.add_column("images", sa.Column("ocr_text", sa.Text(), nullable=True))
    op.add_column(
        "images", sa.Column("face_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_index("ix_images_quality_score", "images", ["quality_score"])
    op.create_index("ix_images_is_screenshot", "images", ["is_screenshot"])

    op.create_table(
        "detected_faces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("face_index", sa.Integer(), nullable=False),
        sa.Column("bounding_box", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id", "face_index", name="uq_detected_face_index"),
    )
    op.create_index("ix_detected_faces_user_id", "detected_faces", ["user_id"])
    op.create_index("ix_detected_faces_image_id", "detected_faces", ["image_id"])
    op.create_index(
        "ix_detected_faces_embedding_hnsw",
        "detected_faces",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_detected_faces_embedding_hnsw", table_name="detected_faces")
    op.drop_index("ix_detected_faces_image_id", table_name="detected_faces")
    op.drop_index("ix_detected_faces_user_id", table_name="detected_faces")
    op.drop_table("detected_faces")
    op.drop_index("ix_images_is_screenshot", table_name="images")
    op.drop_index("ix_images_quality_score", table_name="images")
    op.drop_column("images", "face_count")
    op.drop_column("images", "ocr_text")
    op.drop_column("images", "smart_labels")
    op.drop_column("images", "is_screenshot")
    op.drop_column("images", "quality_score")
    op.drop_column("images", "screenshot_quality_score")
    op.drop_column("images", "resolution_score")
    op.drop_column("images", "exposure_score")
    op.drop_column("images", "blur_score")
