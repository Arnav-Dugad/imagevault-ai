"""Add multi-signal similarity evidence and upload batches.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("images", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.add_column("images", sa.Column("difference_hash", sa.String(length=32), nullable=True))
    op.add_column("images", sa.Column("wavelet_hash", sa.String(length=32), nullable=True))
    op.add_column("images", sa.Column("color_signature", sa.JSON(), nullable=True))
    op.create_index("ix_images_batch_id", "images", ["batch_id"])

    op.add_column("duplicate_matches", sa.Column("clip_score", sa.Float(), nullable=True))
    op.add_column("duplicate_matches", sa.Column("perceptual_score", sa.Float(), nullable=True))
    op.add_column("duplicate_matches", sa.Column("color_score", sa.Float(), nullable=True))
    op.add_column("duplicate_matches", sa.Column("aspect_score", sa.Float(), nullable=True))
    op.add_column("duplicate_matches", sa.Column("evidence", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("duplicate_matches", "evidence")
    op.drop_column("duplicate_matches", "aspect_score")
    op.drop_column("duplicate_matches", "color_score")
    op.drop_column("duplicate_matches", "perceptual_score")
    op.drop_column("duplicate_matches", "clip_score")
    op.drop_index("ix_images_batch_id", table_name="images")
    op.drop_column("images", "color_signature")
    op.drop_column("images", "wavelet_hash")
    op.drop_column("images", "difference_hash")
    op.drop_column("images", "batch_id")
