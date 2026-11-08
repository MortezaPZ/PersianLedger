from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from queue import Queue
from threading import Barrier, Thread

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
import pytest
from PySide6.QtCore import Qt
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import seed
from app.db.base import Base
from app.db.models import Account, AccountTafsiliRule, Currency, Tafsili, TafsiliGroup
from app.db.engine import build_engine
from app.domain.errors import ConcurrencyError, ValidationError
from app.services import document_service, master_data
from app.ui.refdata import RefData
from app.ui.widgets.line_grid import (
    CLEAR_TAFSILI,
    COL_ACCOUNT,
    COL_T1,
    COL_T2,
    LineGridModel,
    TafsiliDelegate,
)
from app.ui.widgets.tree_picker import TreePickerDialog


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


def test_document_rejects_same_tafsili_in_both_slots(db_session):
    seed.seed_base(db_session)
    account = db_session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
    tafsili = db_session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    account.tafsili_rules.append(AccountTafsiliRule(tafsili_group_id=group.id, slot=2))
    db_session.flush()

    with pytest.raises(
        ValidationError,
        match=re.escape("ردیف 1: یک تفصیلی را نمی‌توان هم‌زمان در جایگاه‌های ۱ و ۲ ثبت کرد."),
    ):
        document_service.validate(
            db_session,
            _balanced_input(
                db_session,
                account,
                tafsili1_id=tafsili.id,
                tafsili2_id=tafsili.id,
            ),
        )


def test_document_line_picker_blocks_duplicate_between_tafsili_slots(db_session, qapp):
    seed.seed_base(db_session)
    account = db_session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
    tafsili = db_session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    account.tafsili_rules.append(AccountTafsiliRule(tafsili_group_id=group.id, slot=2))
    db_session.flush()

    refdata = RefData.load(db_session)
    model = LineGridModel(refdata)
    account_index = model.index(0, COL_ACCOUNT)
    assert model.setData(account_index, account.id)
    first_index = model.index(0, COL_T1)
    second_index = model.index(0, COL_T2)
    assert model.setData(first_index, tafsili.id)

    second_delegate = TafsiliDelegate(2)
    second_combo = second_delegate.createEditor(None, None, second_index)
    offered_in_second = {second_combo.itemData(i) for i in range(second_combo.count())}
    assert tafsili.id not in offered_in_second
    assert tafsili.id not in {ident for ident, _label, _parent, _selectable in second_delegate.tree_choices(second_index)}
    assert not model.setData(second_index, tafsili.id)
    assert model.rows[0].tafsili2_id is None

    assert model.setData(first_index, None)
    assert model.setData(second_index, tafsili.id)
    first_delegate = TafsiliDelegate(1)
    first_combo = first_delegate.createEditor(None, None, first_index)
    offered_in_first = {first_combo.itemData(i) for i in range(first_combo.count())}
    assert tafsili.id not in offered_in_first
    assert tafsili.id not in {ident for ident, _label, _parent, _selectable in first_delegate.tree_choices(first_index)}
    assert not model.setData(first_index, tafsili.id)
    assert model.rows[0].tafsili1_id is None

    model.rows[0].tafsili1_id = tafsili.id
    model.rows[0].tafsili2_id = tafsili.id
    legacy_duplicate = second_delegate.createEditor(None, None, second_index)
    duplicate_index = legacy_duplicate.findData(tafsili.id)
    assert duplicate_index >= 0
    assert not legacy_duplicate.model().item(duplicate_index).isEnabled()
    second_delegate.setModelData(legacy_duplicate, model, second_index)
    assert model.rows[0].tafsili2_id == tafsili.id
    legacy_duplicate.setCurrentIndex(legacy_duplicate.findData(CLEAR_TAFSILI))
    second_delegate.setModelData(legacy_duplicate, model, second_index)
    assert model.rows[0].tafsili2_id is None


@pytest.mark.parametrize("slot,column", [(1, COL_T1), (2, COL_T2)])
def test_document_tafsili_picker_stays_disabled_until_account_is_selected(db_session, qapp, slot, column):
    seed.seed_base(db_session)
    account = db_session.execute(select(Account).where(Account.code == "1001")).scalar_one()
    tafsili = db_session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
    if slot == 2:
        group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
        account.tafsili_rules.append(AccountTafsiliRule(tafsili_group_id=group.id, slot=slot))
        db_session.flush()
    model = LineGridModel(RefData.load(db_session))
    account_index = model.index(0, COL_ACCOUNT)
    tafsili_index = model.index(0, column)
    delegate = TafsiliDelegate(slot)

    assert not model.flags(tafsili_index) & Qt.ItemIsEditable
    assert not model.setData(tafsili_index, tafsili.id)
    assert delegate.tree_choices(tafsili_index) == []
    editor = delegate.createEditor(None, None, tafsili_index)
    assert not editor.isEnabled()
    assert "ابتدا سرفصل" in editor.currentText()
    editor.close()

    assert model.setData(account_index, account.id)
    assert model.flags(tafsili_index) & Qt.ItemIsEditable
    choices = {ident: selectable for ident, _label, _parent, selectable in delegate.tree_choices(tafsili_index)}
    assert choices[tafsili.id]
    assert model.setData(tafsili_index, tafsili.id)


def test_tree_picker_search_keeps_matching_paths_and_hides_unrelated_nodes(qapp):
    dialog = TreePickerDialog(
        "انتخاب از درخت",
        [
            (1, "حساب‌های اصلی", None, False),
            (2, "دارایی‌ها", 1, False),
            (3, "صندوق شعبه مرکزی", 2, True),
            (4, "بدهی‌ها", 1, False),
            (5, "وام بلندمدت", 4, True),
        ],
    )
    root = dialog.tree.topLevelItem(0)
    assets, debts = root.child(0), root.child(1)
    branch, loan = assets.child(0), debts.child(0)

    dialog.search.setText("شعبه مرکزی")

    assert not root.isHidden()
    assert not assets.isHidden()
    assert not branch.isHidden()
    assert root.isExpanded() and assets.isExpanded()
    assert debts.isHidden() and loan.isHidden()
    dialog.tree.setCurrentItem(branch)
    assert dialog.selected_id == 3
    dialog.search.clear()
    assert not debts.isHidden() and not loan.isHidden()
    dialog.close()


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


def test_tafsili_parent_rejects_self_and_deep_cycles(db_session):
    seed.seed_base(db_session)
    group = db_session.execute(select(TafsiliGroup).where(TafsiliGroup.code == "20")).scalar_one()
    root = master_data.create_tafsili(db_session, code="90101", name="ریشه", group_id=group.id)
    branch = master_data.create_tafsili(
        db_session, code="90102", name="شاخه", group_id=group.id, parent_id=root.id
    )
    leaf = master_data.create_tafsili(
        db_session, code="90103", name="برگ", group_id=group.id, parent_id=branch.id
    )

    with pytest.raises(ValidationError, match="چرخه"):
        master_data.update_tafsili(db_session, root, parent_id=root.id)
    with pytest.raises(ValidationError, match="چرخه"):
        master_data.update_tafsili(db_session, root, parent_id=leaf.id)

    assert root.parent_id is None
    assert branch.parent_id == root.id
    assert leaf.parent_id == branch.id


def test_tafsili_reparent_rechecks_stale_ancestry_in_independent_sessions(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'stale-tree.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as setup:
            group = master_data.create_tafsili_group(setup, code="98", name="ممیزی")
            node_a = master_data.create_tafsili(setup, code="981", name="A", group_id=group.id)
            node_b = master_data.create_tafsili(setup, code="982", name="B", group_id=group.id)
            node_a_id, node_b_id = node_a.id, node_b.id
            setup.commit()

        with Session(engine, expire_on_commit=False) as first, Session(engine, expire_on_commit=False) as second:
            first_a = first.get(Tafsili, node_a_id)
            second_a = second.get(Tafsili, node_a_id)
            second_b = second.get(Tafsili, node_b_id)
            master_data.update_tafsili(first, first_a, parent_id=node_b_id)
            first.commit()

            with pytest.raises(ValidationError, match="چرخه"):
                master_data.update_tafsili(second, second_b, parent_id=second_a.id)
            second.rollback()

        with Session(engine) as verify:
            assert verify.get(Tafsili, node_a_id).parent_id == node_b_id
            assert verify.get(Tafsili, node_b_id).parent_id is None
    finally:
        engine.dispose()


def test_competing_reparents_are_serialized_by_database_state(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'racing-tree.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as setup:
            group = master_data.create_tafsili_group(setup, code="97", name="رقابت")
            node_a = master_data.create_tafsili(setup, code="971", name="A", group_id=group.id)
            node_b = master_data.create_tafsili(setup, code="972", name="B", group_id=group.id)
            node_a_id, node_b_id = node_a.id, node_b.id
            setup.commit()

        start = Barrier(2)
        outcomes: Queue[str] = Queue()

        def reparent(target_id: int, parent_id: int) -> None:
            with Session(engine, expire_on_commit=False) as session:
                item = session.get(Tafsili, target_id)
                session.get(Tafsili, parent_id)
                start.wait(timeout=10)
                try:
                    master_data.update_tafsili(session, item, parent_id=parent_id)
                    session.commit()
                    outcomes.put("committed")
                except ValidationError:
                    session.rollback()
                    outcomes.put("cycle-rejected")
                except ConcurrencyError:
                    session.rollback()
                    outcomes.put("conflict-rejected")

        workers = [
            Thread(target=reparent, args=(node_a_id, node_b_id)),
            Thread(target=reparent, args=(node_b_id, node_a_id)),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)
        assert all(not worker.is_alive() for worker in workers)
        results = [outcomes.get_nowait(), outcomes.get_nowait()]
        assert results.count("committed") == 1
        assert results.count("cycle-rejected") + results.count("conflict-rejected") == 1

        with Session(engine) as verify:
            final_a = verify.get(Tafsili, node_a_id)
            final_b = verify.get(Tafsili, node_b_id)
            assert not (final_a.parent_id == node_b_id and final_b.parent_id == node_a_id)
    finally:
        engine.dispose()


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


def test_tafsili_tree_migration_round_trip_preserves_financial_data(tmp_path):
    database = tmp_path / "financial-round-trip.sqlite3"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "moein_code_repeat")

    engine = build_engine(f"sqlite:///{database.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tafsili_groups(id,code,name,is_active) "
                    "VALUES (1,'20','اشخاص',1),(2,'30','پروژه',1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO tafsilis(id,code,name,group_id,is_active,row_version) "
                    "VALUES (1,'1101','شخص اصلی',1,1,1),(2,'1102','زیرمجموعه',1,1,1)"
                )
            )
            connection.execute(text("INSERT INTO tafsili_group_members(tafsili_id,group_id) VALUES (2,2)"))
            connection.execute(
                text(
                    "INSERT INTO currencies(id,code,name,symbol,decimals,sort_order,is_active,is_locked) "
                    "VALUES (1,'IRR','ریال','ریال',0,1,1,0),(2,'USD','دلار','$',2,2,1,0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO accounts(id,code,name,level,account_type,nature,is_postable,tafsili1_required,"
                    "tafsili2_required,is_active,row_version) "
                    "VALUES (1,'1001','حساب آزمایشی',2,'ASSET','BOTH',1,1,1,1,1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO account_tafsili_rules(id,account_id,tafsili_group_id,tafsili_id,slot) "
                    "VALUES (1,1,1,1,1),(2,1,1,2,2)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO fiscal_years(id,title,start_date_g,end_date_g,start_date_j,end_date_j,is_closed) "
                    "VALUES (1,'1405','2026-03-21','2027-03-20','1405-01-01','1405-12-29',0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO documents(id,fiscal_year_id,number,doc_type,date_g,date_j,description,status,"
                    "is_reversed,created_at,row_version) VALUES "
                    "(1,1,1,'GENERAL','2026-03-21','1405-01-01','سند قطعی','POSTED',0,'2026-03-21 00:00:00',1),"
                    "(2,1,2,'GENERAL','2026-03-22','1405-01-02','سند پیش‌نویس','DRAFT',0,'2026-03-22 00:00:00',1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO document_lines(id,document_id,line_no,account_id,tafsili1_id,tafsili2_id,"
                    "currency_id,debit,credit) VALUES "
                    "(1,1,1,1,1,2,1,125,0),(2,2,1,1,2,1,2,0,250)"
                )
            )

        def financial_snapshot(connection):
            queries = (
                "SELECT id,code,name,symbol,decimals FROM currencies ORDER BY id",
                "SELECT id,status,number FROM documents ORDER BY id",
                "SELECT id,document_id,tafsili1_id,tafsili2_id,currency_id,debit,credit "
                "FROM document_lines ORDER BY id",
                "SELECT tafsili_id,group_id FROM tafsili_group_members ORDER BY tafsili_id,group_id",
                "SELECT id,account_id,tafsili_group_id,tafsili_id,slot FROM account_tafsili_rules ORDER BY id",
            )
            return tuple(tuple(connection.execute(text(query)).all()) for query in queries)

        with engine.connect() as connection:
            before = financial_snapshot(connection)
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []

        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(text("UPDATE tafsilis SET parent_id=1 WHERE id=2"))
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert connection.execute(text("SELECT parent_id FROM tafsilis WHERE id=2")).scalar_one() == 1

        command.downgrade(config, "moein_code_repeat")
        with engine.connect() as connection:
            assert financial_snapshot(connection) == before
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tafsilis)")}
            assert "parent_id" not in columns
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tafsili_tree_mutex'"
            ).scalar_one() == 0

        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert financial_snapshot(connection) == before
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert connection.execute(
                text("SELECT parent_id FROM tafsilis WHERE id IN (1,2) ORDER BY id")
            ).all() == [(None,), (None,)]
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "tafsili_tree_mutex"
            assert connection.exec_driver_sql(
                "SELECT id, revision FROM tafsili_tree_mutex"
            ).all() == [(1, 0)]
    finally:
        engine.dispose()


def _legacy_migration_database(tmp_path):
    database = tmp_path / "retained-connection.sqlite3"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "moein_code_repeat")
    return config, build_engine(config.get_main_option("sqlalchemy.url"))


def test_retained_sqlite_connection_restores_foreign_keys_across_upgrade_downgrade(tmp_path):
    config, engine = _legacy_migration_database(tmp_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.commit()
            config.attributes["connection"] = connection

            command.upgrade(config, "head")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.rollback()

            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(
                    "INSERT INTO tafsili_groups(id,code,name,is_active) VALUES(1,'20','test',1)"
                )
                connection.exec_driver_sql(
                    "INSERT INTO tafsilis(id,code,name,parent_id,group_id,is_active,row_version) "
                    "VALUES(1,'test','test',999,1,1,1)"
                )
            connection.rollback()

            command.downgrade(config, "moein_code_repeat")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.rollback()
            command.upgrade(config, "head")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        engine.dispose()


def test_sqlite_migration_failure_restores_foreign_keys_on_retained_connection(tmp_path, monkeypatch):
    config, engine = _legacy_migration_database(tmp_path)
    try:
        with engine.connect() as connection:
            connection.commit()
            config.attributes["connection"] = connection
            original_run_migrations = MigrationContext.run_migrations

            def fail_migration(self, *args, **kwargs):
                original_run_migrations(self, *args, **kwargs)
                raise RuntimeError("injected migration failure")

            monkeypatch.setattr(MigrationContext, "run_migrations", fail_migration)
            with pytest.raises(RuntimeError, match="injected migration failure"):
                command.upgrade(config, "head")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.rollback()
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tafsilis)")}
            assert "parent_id" not in columns
            tables = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert "tafsili_tree_mutex" not in tables
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == "moein_code_repeat"
            )
    finally:
        engine.dispose()


def test_sqlite_migration_respects_active_callers_transaction(tmp_path):
    database = tmp_path / "caller-transaction.sqlite3"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    url = f"sqlite:///{database.as_posix()}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "tafsili_link")
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(
                "INSERT INTO app_settings(key,value) VALUES ('caller_transaction','pending')"
            )
            assert connection.in_transaction()
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            config.attributes["connection"] = connection
            command.upgrade(config, "moein_code_repeat")
            assert connection.in_transaction()
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.rollback()
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == "tafsili_link"
            )
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM app_settings WHERE key='caller_transaction'"
            ).scalar_one() == 0
    finally:
        engine.dispose()


def test_sqlite_tree_migration_refuses_active_foreign_key_transaction_without_changes(tmp_path):
    config, engine = _legacy_migration_database(tmp_path)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
            assert connection.in_transaction()
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            config.attributes["connection"] = connection

            with pytest.raises(RuntimeError, match="no migration was run"):
                command.upgrade(config, "head")

            assert connection.in_transaction()
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == "moein_code_repeat"
            )
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tafsilis)")}
            assert "parent_id" not in columns
            assert "tafsili_tree_mutex" not in {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            connection.rollback()

            command.upgrade(config, "head")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.rollback()
            connection.exec_driver_sql("SELECT 1")
            assert connection.in_transaction()

            with pytest.raises(RuntimeError, match="no migration was run"):
                command.downgrade(config, "moein_code_repeat")

            assert connection.in_transaction()
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == "tafsili_tree_mutex"
            )
            assert "parent_id" in {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(tafsilis)")
            }
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            connection.rollback()
    finally:
        engine.dispose()


def test_tafsili_register_renders_the_parent_child_tree(qapp, tmp_path):
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

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
    view.resize(1100, 700)
    view.show()
    qapp.processEvents()

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
    assert not parent_item.isExpanded()
    branch = view.tree.visualItemRect(parent_item)
    assert branch.isValid()
    disclosure_x = None
    for x in range(view.tree.viewport().width()):
        QTest.mouseClick(view.tree.viewport(), Qt.LeftButton, pos=QPoint(x, branch.center().y()))
        qapp.processEvents()
        if parent_item.isExpanded():
            disclosure_x = x
            break
    assert disclosure_x is not None
    assert parent_item.isExpanded()
    QTest.qWait(500)
    branch = view.tree.visualItemRect(parent_item)
    QTest.mouseClick(
        view.tree.viewport(),
        Qt.LeftButton,
        pos=QPoint(disclosure_x, branch.center().y()),
    )
    qapp.processEvents()
    assert not parent_item.isExpanded()
    assert "QTreeWidget::branch:has-children:closed" in qapp.styleSheet()
    assert "QTreeWidget::branch:has-children:open" in qapp.styleSheet()
    assert not parent_item.icon(0).isNull()
    assert not child_item.icon(0).isNull()
    assert view.tree.contextMenuPolicy() == Qt.CustomContextMenu
    assert "::branch:has-siblings" in view.tree.styleSheet()
    assert "والد" not in view.hint and "فرزند" not in view.hint
    from app.ui.views.tafsili_view import _tree_language

    translated = _tree_language("تفصیلی والد انتخاب‌شده یافت نشد.")
    assert "والد" not in translated and "فرزند" not in translated
    assert "شاخهٔ بالاتر" in translated
    from PySide6.QtWidgets import QLabel, QPushButton
    from app.ui.views.tafsili_view import TafsiliDialog

    dialog = TafsiliDialog(context)
    dialog_labels = [label.text() for label in dialog.findChildren(QLabel)]
    visible_labels = dialog_labels + [button.text() for button in view.findChildren(QPushButton)]
    assert "شاخهٔ بالاتر" in dialog_labels
    assert not any("والد" in label or "فرزند" in label for label in visible_labels)
    dialog.close()
    view.close()
