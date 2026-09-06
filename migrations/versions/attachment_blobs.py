"""Create attachment_blobs.

Revision ID: attachment_blobs
Revises: user_role
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types  # noqa: F401

revision: str = "attachment_blobs"
down_revision: Union[str, None] = "user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachment_blobs",
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("sha256", name=op.f("pk_attachment_blobs")),
    )


def downgrade() -> None:
    op.drop_table("attachment_blobs")
