"""Add persistent people controls, feedback learning, and rich media metadata.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("images", sa.Column("ocr_language", sa.String(length=100), nullable=True))
    op.add_column("images", sa.Column("ocr_layout", sa.JSON(), nullable=True))
    op.add_column("images", sa.Column("document_type", sa.String(length=50), nullable=True))
    op.add_column(
        "images",
        sa.Column("media_kind", sa.String(length=30), nullable=False, server_default="PHOTO"),
    )
    op.add_column("images", sa.Column("frame_count", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("images", sa.Column("duration_seconds", sa.Float(), nullable=True))
    op.add_column("images", sa.Column("processing_device", sa.String(length=80), nullable=True))
    op.create_index("ix_images_document_type", "images", ["document_type"])
    op.create_index("ix_images_media_kind", "images", ["media_kind"])

    op.create_table(
        "people",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_people_user_id", "people", ["user_id"])
    op.create_index("ix_people_ignored", "people", ["ignored"])
    op.create_index("ix_people_user_ignored", "people", ["user_id", "ignored"])

    op.create_table(
        "face_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("face_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="automatic"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["face_id"], ["detected_faces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("face_id"),
    )
    op.create_index("ix_face_assignments_user_id", "face_assignments", ["user_id"])
    op.create_index("ix_face_assignments_person_id", "face_assignments", ["person_id"])
    op.create_index("ix_face_assignments_face_id", "face_assignments", ["face_id"])

    op.create_table(
        "face_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("first_face_id", sa.Uuid(), nullable=False),
        sa.Column("second_face_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_type", sa.String(length=20), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["first_face_id"], ["detected_faces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["second_face_id"], ["detected_faces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("first_face_id", "second_face_id", name="uq_face_feedback_pair"),
    )
    op.create_index("ix_face_feedback_user_id", "face_feedback", ["user_id"])
    op.create_index("ix_face_feedback_first_face_id", "face_feedback", ["first_face_id"])
    op.create_index("ix_face_feedback_second_face_id", "face_feedback", ["second_face_id"])
    op.create_index("ix_face_feedback_feedback_type", "face_feedback", ["feedback_type"])
    op.create_index("ix_face_feedback_user_type", "face_feedback", ["user_id", "feedback_type"])


def downgrade() -> None:
    op.drop_table("face_feedback")
    op.drop_table("face_assignments")
    op.drop_table("people")
    op.drop_index("ix_images_media_kind", table_name="images")
    op.drop_index("ix_images_document_type", table_name="images")
    op.drop_column("images", "processing_device")
    op.drop_column("images", "duration_seconds")
    op.drop_column("images", "frame_count")
    op.drop_column("images", "media_kind")
    op.drop_column("images", "document_type")
    op.drop_column("images", "ocr_layout")
    op.drop_column("images", "ocr_language")
