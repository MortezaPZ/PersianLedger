"""Add users.role

Revision ID: user_role
Revises: 5879b0c1dc53
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types  # noqa: F401

revision: str = "user_role"
down_revision: Union[str, None] = "5879b0c1dc53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=24), nullable=False, server_default="ACCOUNTANT")
        )
    op.execute("UPDATE users SET role='ADMIN' WHERE is_admin = TRUE")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
