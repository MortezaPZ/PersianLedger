from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
import pytest
from PySide6.QtCore import Qt
from sqlalchemy import create_engine, select, text

from app.db import seed
from app.db.base import Base
from app.db.models import Account, AccountTafsiliRule, Currency, Tafsili, TafsiliGroup
from app.domain.errors import ValidationError
from app.services import document_service, master_data


def _balanced_input(session, first_account, *, tafsili1_id=None, tafsili2_id=None):
    year = master_data.current_fiscal_year(session)
    currency = session.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
    other = session.execute(select(Account).where(Account.code == "3001")).scalar_one()
    return document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=year.start_date_g,
        date_j=year.start_date_j,
        lines=[
            document_service.LineInput(
                first_account.id,
                currency.id,
                Decimal("10"),
                Decimal(0),
                tafsili1_id,
                tafsili2_id,
            ),
            document_service.LineInput(other.id, currency.id, Decimal(0), Decimal("10")),
        ],
    )


def test_tafsili_parent_child_relationship_and_legacy_root(db_session):
    seed.seed_base(db_session)
    group = db_session.execute(
        select(TafsiliGroup).where(TafsiliGroup.code == "20")
    ).scalar_one()
    legacy = db_session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    parent = Tafsili(code="90001", name="واحد اصلی", group_id=group.id)
    child = Tafsili(code="90002", name="واحد فرعی", group_id=group.id, parent=parent)
    db_session.add_all([parent, child])
    db_session.flush()
    db_session.expire_all()

    loaded_parent = db_session.get(Tafsili, parent.id)
    assert loaded_parent.parent_id is None
    assert loaded_parent.children[0].id == child.id
    assert db_session.get(Tafsili, child.id).parent.id == parent.id
    assert legacy.parent_id is None


def test_document_rejects_non_leaf_account_with_required_message(db_session):
    seed.seed_base(db_session)
    kol = db_session.execute(select(Account).where(Account.code == "1")).scalar_one()

    with pytest.raises(ValidationError, match=re.escape("حساب نهایی نیست. حساب باید در پایین‌ترین سطح خود باشد.")):
        document_service.validate(db_session, _balanced_input(db_session, kol))


def test_document_rejects_non_leaf_tafsili_with_required_message(db_session):
    seed.seed_base(db_session)
    account = db_session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
    parent = Tafsili(code="90011", name="صندوق‌های شرکت", group_id=group.id)
    child = Tafsili(code="90012", name="صندوق شعبه", group_id=group.id, parent=parent)
    db_session.add_all([parent, child])
    db_session.flush()

    with pytest.raises(
        ValidationError,
        match=re.escape("تفصیلی نهایی نیست. در سند حسابداری فقط تفصیلی در پایین‌ترین سطح مجاز است."),
    ):
        document_service.validate(db_session, _balanced_input(db_session, account, tafsili1_id=parent.id))


def test_document_rejects_tafsili2_when_account_has_no_tafsili2_rule(db_session):
    seed.seed_base(db_session)
    account = db_session.execute(select(Account).where(Account.code == "3001")).scalar_one()
    tafsili = db_session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()

    with pytest.raises(ValidationError, match=re.escape("خطا: حساب طبق تعریف فاقد تفصیلی ۲ است.")):
        document_service.validate(db_session, _balanced_input(db_session, account, tafsili2_id=tafsili.id))


def test_specific_parent_rule_allows_descendant_leaf(db_session):
    seed.seed_base(db_session)
    account = db_session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
    parent = Tafsili(code="90021", name="خزانه", group_id=group.id)
    leaf = Tafsili(code="90022", name="صندوق شعبه", group_id=group.id, parent=parent)
    db_session.add_all([parent, leaf])
    db_session.flush()
    account.tafsili_rules[:] = [AccountTafsiliRule(tafsili_group_id=group.id, tafsili_id=parent.id, slot=1)]
    db_session.flush()

    document_service.validate(db_session, _balanced_input(db_session, account, tafsili1_id=leaf.id))


def test_migration_keeps_existing_tafsilis_as_root_nodes(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "moein_code_repeat")

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO tafsili_groups (id, code, name, is_active) VALUES (1, '20', 'صندوق‌ها', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO tafsilis (id, code, name, group_id, is_active, row_version) "
                    "VALUES (1, '1101', 'صندوق اصلی', 1, 1, 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO currencies (id, code, name, symbol, decimals, sort_order, is_active, is_locked) "
                    "VALUES (1, 'IRR', 'ریال', 'ریال', 0, 1, 1, 0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO accounts (id, code, name, level, account_type, nature, is_postable, "
                    "tafsili1_required, tafsili2_required, is_active, row_version) "
                    "VALUES (1, '1001', 'صندوق', 2, 'ASSET', 'BOTH', 1, 0, 0, 1, 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO fiscal_years (id, title, start_date_g, end_date_g, start_date_j, end_date_j, is_closed) "
                    "VALUES (1, '1405', '2026-03-21', '2027-03-20', '1405-01-01', '1405-12-29', 0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO documents (id, fiscal_year_id, number, doc_type, date_g, date_j, description, "
                    "status, is_reversed, created_at, row_version) "
                    "VALUES (1, 1, 1, 'GENERAL', '2026-03-21', '1405-01-01', 'قدیمی', 'POSTED', 0, "
                    "'2026-03-21 00:00:00', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO document_lines (id, document_id, line_no, account_id, tafsili1_id, currency_id, debit, credit) "
                    "VALUES (1, 1, 1, 1, 1, 1, 125, 0)"
                )
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
            tafsili = connection.execute(text("SELECT code, name, parent_id FROM tafsilis WHERE id = 1")).one()
            line = connection.execute(text("SELECT tafsili1_id, debit FROM document_lines WHERE id = 1")).one()
            broken_links = connection.execute(text("PRAGMA foreign_key_check")).all()
        assert diff == []
        assert tafsili == ("1101", "صندوق اصلی", None)
        assert line == (1, 125)
        assert broken_links == []

        command.downgrade(config, "moein_code_repeat")
        with engine.connect() as connection:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(tafsilis)"))}
            line_after_downgrade = connection.execute(
                text("SELECT tafsili1_id, debit FROM document_lines WHERE id = 1")
            ).one()
        assert "parent_id" not in columns
        assert line_after_downgrade == (1, 125)
    finally:
        engine.dispose()


def test_tafsili_register_renders_the_parent_child_tree(qapp, tmp_path):
    from app import bootstrap, config as config_module
    from app.ui.context import AppContext
    from app.ui.views.tafsili_view import TafsiliView

    data_dir = tmp_path / "ui-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = config_module.AppConfig(data_dir=data_dir, sqlite_path=data_dir / "ledger.sqlite3")
    context = AppContext(bootstrap.start(cfg))
    group_id = context.refdata.groups[0].id
    with context.session() as db:
        parent = master_data.create_tafsili(db, code="94001", name="گروه اصلی", group_id=group_id)
        child = master_data.create_tafsili(
            db, code="94002", name="تفصیلی نهایی", group_id=group_id, parent_id=parent.id
        )
        parent_id, child_id = parent.id, child.id
    context.reload_refdata()
    view = TafsiliView(context)

    def find_item(item_id):
        def walk(node):
            if node.data(0, Qt.UserRole) == item_id:
                return node
            for index in range(node.childCount()):
                found = walk(node.child(index))
                if found:
                    return found
            return None

        for index in range(view.tree.topLevelItemCount()):
            found = walk(view.tree.topLevelItem(index))
            if found:
                return found
        return None

    parent_item = find_item(parent_id)
    child_item = find_item(child_id)
    assert parent_item is not None
    assert child_item is not None
    assert child_item.parent() is parent_item
    view.close()
