"""Add parent-child hierarchy to tafsili accounts.

Revision ID: tafsili_tree
Revises: moein_code_repeat
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "tafsili_tree"
down_revision: Union[str, None] = "moein_code_repeat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable so every existing tafsili remains a valid root after upgrade.
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if is_sqlite:
        # SQLite cannot ALTER a table to add a foreign key. Disable FK checks
        # while Alembic copies this table, which has existing document-line FKs.
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("tafsilis", recreate="always" if is_sqlite else "auto") as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tafsilis_parent_id_tafsilis", "tafsilis", ["parent_id"], ["id"]
        )
    if is_sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")
    op.create_index("ix_tafsilis_parent_id", "tafsilis", ["parent_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if is_sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    op.drop_index("ix_tafsilis_parent_id", table_name="tafsilis")
    with op.batch_alter_table("tafsilis") as batch_op:
        batch_op.drop_constraint("fk_tafsilis_parent_id_tafsilis", type_="foreignkey")
        batch_op.drop_column("parent_id")
    if is_sqlite:
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")
