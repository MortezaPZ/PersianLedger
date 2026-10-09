"""Link a معین to a specific tafsili, not only its group.

Revision ID: tafsili_link
Revises: attachment_blobs
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types  # noqa: F401

revision: str = "tafsili_link"
down_revision: Union[str, None] = "attachment_blobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("account_tafsili_rules") as batch_op:
        batch_op.add_column(sa.Column("tafsili_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_account_tafsili_rules_tafsili_id_tafsilis"),
            "tafsilis",
            ["tafsili_id"],
            ["id"],
        )
        batch_op.drop_constraint(
            "uq_account_tafsili_rules_account_id_tafsili_group_id_slot",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_account_tafsili_rules_account_id_tafsili_group_id_slot_tafsili_id"),
            ["account_id", "tafsili_group_id", "slot", "tafsili_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("account_tafsili_rules") as batch_op:
        batch_op.drop_constraint(
            batch_op.f("uq_account_tafsili_rules_account_id_tafsili_group_id_slot_tafsili_id"),
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_account_tafsili_rules_account_id_tafsili_group_id_slot",
            ["account_id", "tafsili_group_id", "slot"],
        )
        batch_op.drop_constraint(
            batch_op.f("fk_account_tafsili_rules_tafsili_id_tafsilis"),
            type_="foreignkey",
        )
        batch_op.drop_column("tafsili_id")
