"""Allow the same معین code under different کل accounts.

Revision ID: moein_code_repeat
Revises: tafsili_link
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types  # noqa: F401

revision: str = "moein_code_repeat"
down_revision: Union[str, None] = "tafsili_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_constraint("uq_accounts_code", type_="unique")
    op.create_index(
        "uq_accounts_kol_code",
        "accounts",
        ["code"],
        unique=True,
        sqlite_where=sa.text("parent_id IS NULL"),
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index(
        "uq_accounts_moein_code",
        "accounts",
        ["parent_id", "code"],
        unique=True,
        sqlite_where=sa.text("parent_id IS NOT NULL"),
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_accounts_moein_code", table_name="accounts")
    op.drop_index("uq_accounts_kol_code", table_name="accounts")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.create_unique_constraint("uq_accounts_code", ["code"])
