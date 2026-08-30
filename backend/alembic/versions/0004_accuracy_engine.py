"""Version intelligence results and identify dedicated face embeddings.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "images",
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_images_analysis_version", "images", ["analysis_version"])
    op.add_column(
        "detected_faces",
        sa.Column("embedding_model", sa.String(length=80), nullable=False, server_default="legacy"),
    )


def downgrade() -> None:
    op.drop_column("detected_faces", "embedding_model")
    op.drop_index("ix_images_analysis_version", table_name="images")
    op.drop_column("images", "analysis_version")
