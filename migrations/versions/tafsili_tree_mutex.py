"""Add a database row to serialize concurrent tafsili tree edits.

Revision ID: tafsili_tree_mutex
Revises: tafsili_tree
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "tafsili_tree_mutex"
down_revision: Union[str, None] = "tafsili_tree"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tafsili_tree_mutex",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "tafsili_tree_mutex",
            sa.column("id", sa.Integer()),
            sa.column("revision", sa.Integer()),
        ),
        [{"id": 1, "revision": 0}],
    )


def downgrade() -> None:
    op.drop_table("tafsili_tree_mutex")
