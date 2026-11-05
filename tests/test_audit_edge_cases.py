"""Independent adversarial audit of d27aee3; failures are intentionally visible.
Only test code is added. No production behavior or expected failure is patched.
"""
from __future__ import annotations

import re
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from app.db import seed
from app.db.base import Base
from app.db.models import Account, AccountTafsiliRule, Currency, Tafsili, TafsiliGroup
from app.domain.errors import InUseError, ValidationError
from app.services import document_service, master_data
from app.ui.refdata import RefData
import datetime as dt
from sqlalchemy import select
from app.db.models import Account, Currency, Document, DocumentLine, Tafsili, TafsiliGroup
from app.domain.enums import DocumentStatus, DocumentType
from app.services import master_data
from app.services.report_service import StatementFilter, account_statement, tafsili_descendant_ids, tafsili_moein_matrix
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from app.db.engine import build_engine
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QDialog, QStyleOptionViewItem
from app import bootstrap, config as config_module
from app.db.models import Account, AccountTafsiliRule, Tafsili, TafsiliGroup
from app.ui.context import AppContext
from app.ui.views.document_entry_view import DocumentEntryView
from app.ui.views.tafsili_view import TafsiliView
from app.ui.widgets.line_grid import (
    AccountDelegate, COL_ACCOUNT, COL_T1, COL_T2, LineGridModel, LineRow,
    TafsiliDelegate, TreePickerCombo,
)
from app.ui.widgets.tree_picker import TreePickerDialog


@pytest.fixture
def domain_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        seed.seed_base(session)
        yield session
    engine.dispose()


def _domain_account(session):
    return session.scalar(select(Account).where(Account.code == "3002"))


def _domain_input(session, account, slot=None, tafsili_id=None):
    year = master_data.current_fiscal_year(session)
    currency = session.scalar(select(Currency).where(Currency.code == "IRR"))
    counter = session.scalar(select(Account).where(Account.code == "3001"))
    line = document_service.LineInput(account.id, currency.id, Decimal("10"), Decimal(0))
    if slot:
        setattr(line, f"tafsili{slot}_id", tafsili_id)
    return document_service.DocumentInput(
        fiscal_year_id=year.id,
        date_g=year.start_date_g,
        date_j=year.start_date_j,
        lines=[line, document_service.LineInput(counter.id, currency.id, Decimal(0), Decimal("10"))],
    )


def _domain_tree(session, *, cross_group=False):
    group = session.scalar(select(TafsiliGroup).where(TafsiliGroup.code == "10"))
    other = session.scalar(select(TafsiliGroup).where(TafsiliGroup.code == "40"))
    root = master_data.create_tafsili(session, code="99101", name="ریشه", group_id=group.id)
    middle = master_data.create_tafsili(session, code="99102", name="میانی", group_id=(other if cross_group else group).id, parent_id=root.id)
    leaf = master_data.create_tafsili(session, code="99103", name="برگ", group_id=(other if cross_group else group).id, parent_id=middle.id)
    return root, middle, leaf


@pytest.mark.parametrize("parent_position", [0, 2], ids=["self", "deep-descendant"])
def test_audit_domain_rejects_self_and_deep_cycles(domain_session, parent_position):
    root, middle, leaf = _domain_tree(domain_session)
    proposed = [root, middle, leaf][parent_position]
    with pytest.raises(ValidationError, match="چرخه"):
        master_data.update_tafsili(domain_session, root, parent_id=proposed.id)
    assert root.parent_id is None
    assert middle.parent_id == root.id
    assert leaf.parent_id == middle.id


def test_audit_domain_rejects_missing_parent(domain_session):
    root, _, _ = _domain_tree(domain_session)
    with pytest.raises(ValidationError, match="والد انتخاب‌شده یافت نشد"):
        master_data.update_tafsili(domain_session, root, parent_id=999999)


def test_audit_domain_rejects_deleting_node_with_children(domain_session):
    root, middle, leaf = _domain_tree(domain_session)
    with pytest.raises(InUseError, match="فرزند دارد"):
        master_data.delete_tafsili(domain_session, middle)
    assert domain_session.get(Tafsili, middle.id) is middle
    assert domain_session.get(Tafsili, leaf.id).parent_id == middle.id


@pytest.mark.parametrize("slot", [1, 2])
@pytest.mark.parametrize("posted", [False, True], ids=["draft", "posted"])
def test_audit_domain_rejects_deleting_used_leaf(domain_session, slot, posted):
    _, _, leaf = _domain_tree(domain_session)
    account = _domain_account(domain_session)
    account.tafsili_rules[:] = [AccountTafsiliRule(tafsili_group_id=leaf.group_id, slot=slot)]
    data = _domain_input(domain_session, account, slot, leaf.id)
    document = document_service.save_draft(domain_session, data)
    if posted:
        document_service.post(domain_session, document)
    assert master_data.tafsili_in_use(domain_session, leaf.id)
    with pytest.raises(InUseError, match="سند دارد"):
        master_data.delete_tafsili(domain_session, leaf)
    assert domain_session.get(Tafsili, leaf.id) is leaf


@pytest.mark.parametrize("slot", [1, 2])
@pytest.mark.parametrize("inactive_position", [0, 1], ids=["root", "middle"])
def test_audit_domain_inactive_ancestor_excludes_leaf_and_rejects_post(domain_session, slot, inactive_position):
    root, middle, leaf = _domain_tree(domain_session)
    account = _domain_account(domain_session)
    account.tafsili_rules[:] = [AccountTafsiliRule(tafsili_group_id=root.group_id, slot=slot)]
    data = _domain_input(domain_session, account, slot, leaf.id)
    document_service.validate(domain_session, data)
    master_data.update_tafsili(domain_session, [root, middle][inactive_position], is_active=False)
    refs = RefData.load(domain_session)
    assert leaf.id not in {item.id for item in refs.final_tafsilis()}
    assert leaf.id not in {item.id for item in refs.tafsilis_for(account.id, slot)}
    with pytest.raises(ValidationError, match="والد آن غیرفعال"):
        document_service.save_and_post(domain_session, data)


@pytest.mark.parametrize("slot", [1, 2])
def test_audit_domain_rejects_parent_tafsili_in_either_slot(domain_session, slot):
    root, _, _ = _domain_tree(domain_session)
    account = _domain_account(domain_session)
    account.tafsili_rules[:] = [AccountTafsiliRule(tafsili_group_id=root.group_id, slot=slot)]
    with pytest.raises(ValidationError) as result:
        document_service.validate(domain_session, _domain_input(domain_session, account, slot, root.id))
    assert str(result.value) == "تفصیلی نهایی نیست. در سند حسابداری فقط تفصیلی در پایین‌ترین سطح مجاز است."


def test_audit_domain_rejects_level_two_account_with_children(domain_session):
    account = _domain_account(domain_session)
    domain_session.add(Account(code="99199", name="فرزند معین", parent=account, level=2, account_type=account.account_type, is_postable=True))
    domain_session.flush()
    with pytest.raises(ValidationError) as result:
        document_service.validate(domain_session, _domain_input(domain_session, account))
    assert str(result.value) == "حساب نهایی نیست. حساب باید در پایین‌ترین سطح خود باشد."


@pytest.mark.parametrize("slot", [1, 2])
@pytest.mark.parametrize("specific", [False, True], ids=["ancestor-group", "ancestor-id"])
def test_audit_domain_inherits_deep_parent_permissions_across_groups(domain_session, slot, specific):
    root, _, leaf = _domain_tree(domain_session, cross_group=True)
    account = _domain_account(domain_session)
    account.tafsili_rules[:] = [AccountTafsiliRule(tafsili_group_id=root.group_id, tafsili_id=root.id if specific else None, slot=slot)]
    document_service.validate(domain_session, _domain_input(domain_session, account, slot, leaf.id))
    refs = RefData.load(domain_session)
    assert leaf.id in {item.id for item in refs.tafsilis_for(account.id, slot)}
    assert root.id not in {item.id for item in refs.tafsilis_for(account.id, slot)}


@pytest.mark.parametrize("slot", [1, 2])
def test_audit_domain_specific_parent_does_not_authorize_unrelated_leaf(domain_session, slot):
    root, _, _ = _domain_tree(domain_session)
    unrelated = domain_session.scalar(select(Tafsili).where(Tafsili.code == "2101"))
    account = _domain_account(domain_session)
    account.tafsili_rules[:] = [AccountTafsiliRule(tafsili_group_id=root.group_id, tafsili_id=root.id, slot=slot)]
    with pytest.raises(ValidationError, match="وصل نیست"):
        document_service.validate(domain_session, _domain_input(domain_session, account, slot, unrelated.id))
    assert unrelated.id not in {item.id for item in RefData.load(domain_session).tafsilis_for(account.id, slot)}


def test_audit_domain_slot_two_without_rules_has_exact_error(domain_session):
    account = _domain_account(domain_session)
    account.tafsili_rules[:] = [rule for rule in account.tafsili_rules if rule.slot != 2]
    leaf = domain_session.scalar(select(Tafsili).where(Tafsili.code == "3101"))
    with pytest.raises(ValidationError) as result:
        document_service.validate(domain_session, _domain_input(domain_session, account, 2, leaf.id))
    assert str(result.value) == "خطا: حساب طبق تعریف فاقد تفصیلی ۲ است."


def _audit_matrix_tree(session):
    seed.seed_base(session)
    group = session.execute(select(TafsiliGroup).where(TafsiliGroup.code == '20')).scalar_one()
    root = Tafsili(code='95001', name='audit root', group_id=group.id)
    branch = Tafsili(code='95002', name='audit branch', group_id=group.id, parent=root)
    leaf = Tafsili(code='95003', name='audit leaf', group_id=group.id, parent=branch)
    sibling = Tafsili(code='95004', name='audit sibling', group_id=group.id, parent=root)
    outside = Tafsili(code='95005', name='audit outside', group_id=group.id)
    session.add_all([root, branch, leaf, sibling, outside])
    session.flush()
    account = session.execute(select(Account).where(Account.code == '1001')).scalar_one()
    currencies = {c.code: c for c in session.execute(select(Currency)).scalars()}
    return master_data.current_fiscal_year(session), account, currencies, root, branch, leaf, sibling, outside


def _audit_matrix_line(session, year, account, currency, day, amount, first=None, second=None, status=DocumentStatus.POSTED):
    doc = Document(fiscal_year_id=year.id, doc_type=DocumentType.GENERAL, date_g=day,
                   date_j=year.start_date_j, description='audit matrix', status=status)
    line = DocumentLine(line_no=1, account_id=account.id, currency_id=currency.id,
                        tafsili1_id=first.id if first else None,
                        tafsili2_id=second.id if second else None,
                        debit=max(Decimal(str(amount)), Decimal(0)),
                        credit=max(-Decimal(str(amount)), Decimal(0)))
    doc.lines.append(line)
    session.add(doc)
    session.flush()
    return line.id


def test_audit_matrix_both_slots_count_once_and_statement_matches(db_session):
    year, account, currencies, root, branch, leaf, sibling, outside = _audit_matrix_tree(db_session)
    day = year.start_date_g
    ids = {
        _audit_matrix_line(db_session, year, account, currencies['IRR'], day, 2, first=root),
        _audit_matrix_line(db_session, year, account, currencies['IRR'], day, 3, second=leaf),
        _audit_matrix_line(db_session, year, account, currencies['IRR'], day, 5, first=leaf, second=leaf),
        _audit_matrix_line(db_session, year, account, currencies['IRR'], day, -7, first=leaf, second=sibling),
    }
    _audit_matrix_line(db_session, year, account, currencies['IRR'], day, 100, first=outside)
    descendants = tafsili_descendant_ids(db_session, root.id)
    assert set(descendants) == {root.id, branch.id, leaf.id, sibling.id}
    assert len(descendants) == len(set(descendants))
    matrix = tafsili_moein_matrix(db_session, root.id, day, day, [currencies['IRR'].id])
    totals = matrix.rows[0].amounts[currencies['IRR'].id]
    assert (totals.debit_turnover, totals.credit_turnover, totals.debit_balance, totals.credit_balance) == (Decimal(10), Decimal(7), Decimal(3), Decimal(0))
    statement = account_statement(db_session, StatementFilter(account_id=account.id, tafsili_ids=descendants,
                                 date_from=day, date_to=day, include_drafts=False, include_opening=True))
    assert {row.line_id for row in statement.rows if not row.is_opening} == ids
    assert statement.closing[currencies['IRR'].id] == Decimal(3)


def test_audit_matrix_exact_boundaries_drafts_and_currency_isolation(db_session):
    year, account, currencies, root, branch, leaf, sibling, outside = _audit_matrix_tree(db_session)
    start = year.start_date_g + dt.timedelta(days=10)
    end = start + dt.timedelta(days=2)
    for offset, amount in [(-1, 11), (0, 13), (2, -5), (3, 101)]:
        _audit_matrix_line(db_session, year, account, currencies['IRR'], start + dt.timedelta(days=offset), amount, second=leaf)
    _audit_matrix_line(db_session, year, account, currencies['IRR'], start, 1000, first=leaf, status=DocumentStatus.DRAFT)
    _audit_matrix_line(db_session, year, account, currencies['USD'], start - dt.timedelta(days=1), -9, first=sibling)
    _audit_matrix_line(db_session, year, account, currencies['USD'], start, Decimal('2.25'), second=leaf)
    matrix = tafsili_moein_matrix(db_session, root.id, start, end, None)
    totals = matrix.rows[0].amounts
    irr, usd = totals[currencies['IRR'].id], totals[currencies['USD'].id]
    assert (irr.debit_turnover, irr.credit_turnover, irr.debit_balance, irr.credit_balance) == (Decimal(13), Decimal(5), Decimal(19), Decimal(0))
    assert (usd.debit_turnover, usd.credit_turnover, usd.debit_balance, usd.credit_balance) == (Decimal('2.25'), Decimal(0), Decimal(0), Decimal('6.75'))
    only_usd = tafsili_moein_matrix(db_session, root.id, start, end, [currencies['USD'].id])
    assert set(only_usd.rows[0].amounts) == {currencies['USD'].id}
    assert [column.id for column in only_usd.currencies] == [currencies['USD'].id]
    statement = account_statement(db_session, StatementFilter(account_id=account.id,
                                 tafsili_ids=tafsili_descendant_ids(db_session, root.id), date_from=start, date_to=end,
                                 include_drafts=False, include_opening=True))
    assert statement.closing == {currencies['IRR'].id: Decimal(19), currencies['USD'].id: Decimal('-6.75')}


@pytest.mark.parametrize('changed_filter', ['unchanged', 'tafsili', 'date', 'currency'])
def test_audit_matrix_drilldown_uses_rendered_report_filters(qapp, tmp_path, monkeypatch, changed_filter):
    from app import bootstrap, config as config_module
    from app.ui.context import AppContext
    from app.ui.views import tafsili_moein_matrix_view as module
    from app.domain import jalali
    from PySide6.QtCore import Qt
    data_dir = tmp_path / 'matrix-audit-ui'
    data_dir.mkdir()
    cfg = config_module.AppConfig(data_dir=data_dir, sqlite_path=data_dir / 'ledger.sqlite3')
    context = AppContext(bootstrap.start(cfg))
    with context.session() as db:
        year, account, currencies, root, branch, leaf, sibling, outside = _audit_matrix_tree(db)
        day = year.start_date_g + dt.timedelta(days=5)
        expected_line = _audit_matrix_line(db, year, account, currencies['IRR'], day, 10, second=leaf)
        _audit_matrix_line(db, year, account, currencies['IRR'], day, 99, first=outside)
        root_id, outside_id, irr_id = root.id, outside.id, currencies['IRR'].id
    context.reload_refdata()
    view = module.TafsiliMoeinMatrixView(context)
    errors = []
    monkeypatch.setattr(view, 'report_error', lambda exc: errors.append(str(exc)))
    view.tafsili.setCurrentIndex(view.tafsili.findData(root_id))
    for i in range(view.currency_list.count()):
        item = view.currency_list.item(i)
        item.setCheckState(Qt.Checked if item.data(Qt.UserRole) == irr_id else Qt.Unchecked)
    view.run()
    assert not errors
    assert view._result.rows[0].amounts[irr_id].debit_balance == Decimal(10)
    captured = []
    real_statement = module.account_statement
    def capture(db, flt):
        result = real_statement(db, flt)
        captured.append(result)
        return result
    monkeypatch.setattr(module, 'account_statement', capture)
    monkeypatch.setattr(module.QDialog, 'exec', lambda self: 0)
    if changed_filter == 'tafsili':
        view.tafsili.setCurrentIndex(view.tafsili.findData(outside_id))
    elif changed_filter == 'date':
        view.to_date.setText(jalali.to_jalali(day - dt.timedelta(days=1)).strftime('%Y-%m-%d'))
    elif changed_filter == 'currency':
        for i in range(view.currency_list.count()):
            item = view.currency_list.item(i)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) != irr_id else Qt.Unchecked)
    view.show_statement(view.model.index(0, 0))
    view.close()
    assert not errors
    assert len(captured) == 1
    assert {row.line_id for row in captured[0].rows if not row.is_opening} == {expected_line}
    assert captured[0].closing == {irr_id: Decimal(10)}


def test_audit_matrix_cumulative_balance_includes_prior_fiscal_year(db_session):
    from app.db.models import FiscalYear
    year, account, currencies, root, branch, leaf, sibling, outside = _audit_matrix_tree(db_session)
    prior_day = year.start_date_g - dt.timedelta(days=1)
    previous = FiscalYear(title='audit previous', start_date_g=prior_day - dt.timedelta(days=360),
                          end_date_g=prior_day, start_date_j='1403-01-01', end_date_j='1403-12-29')
    db_session.add(previous)
    db_session.flush()
    _audit_matrix_line(db_session, previous, account, currencies['IRR'], prior_day, 7, second=leaf)
    _audit_matrix_line(db_session, year, account, currencies['IRR'], year.start_date_g, 3, first=leaf)
    result = tafsili_moein_matrix(db_session, root.id, year.start_date_g, year.start_date_g, [currencies['IRR'].id])
    amounts = result.rows[0].amounts[currencies['IRR'].id]
    assert amounts.debit_turnover == Decimal(3)
    assert amounts.debit_balance == Decimal(10)
    statement = account_statement(db_session, StatementFilter(account_id=account.id,
                                 tafsili_ids=tafsili_descendant_ids(db_session, root.id),
                                 date_from=year.start_date_g, date_to=year.start_date_g,
                                 include_drafts=False, include_opening=True))
    assert len([row for row in statement.rows if row.is_opening]) == 1
    assert statement.closing[currencies['IRR'].id] == Decimal(10)


_AUDIT_REPO = Path(__file__).resolve().parents[1]


def _audit_legacy_migration_database(tmp_path):
    database = tmp_path / "legacy-audit.sqlite3"
    config = Config(str(_AUDIT_REPO / "alembic.ini"))
    config.set_main_option("script_location", str(_AUDIT_REPO / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "moein_code_repeat")
    engine = build_engine(config.get_main_option("sqlalchemy.url"))
    statements = [
        "INSERT INTO tafsili_groups(id,code,name,is_active) VALUES(1,'20','home',1),(2,'30','secondary',1)",
        "INSERT INTO tafsilis(id,code,name,group_id,is_active,row_version) VALUES(1,'9001','root',1,1,3),(2,'9002','child',1,1,4),(3,'9003','leaf',1,1,5)",
        "INSERT INTO tafsili_group_members(tafsili_id,group_id) VALUES(1,2),(2,2),(3,2)",
        "INSERT INTO currencies(id,code,name,symbol,decimals,sort_order,is_active,is_locked) VALUES(1,'IRR','rial','IRR',0,1,1,0),(2,'USD','dollar','$',2,2,1,0)",
        "INSERT INTO accounts(id,code,name,level,account_type,nature,is_postable,tafsili1_required,tafsili2_required,is_active,row_version) VALUES(1,'1001','cash',2,'ASSET','BOTH',1,0,0,1,1)",
        "INSERT INTO account_tafsili_rules(id,account_id,tafsili_group_id,tafsili_id,slot) VALUES(1,1,1,1,1),(2,1,2,2,2)",
        "INSERT INTO fiscal_years(id,title,start_date_g,end_date_g,start_date_j,end_date_j,is_closed) VALUES(1,'1405','2026-03-21','2027-03-20','1405-01-01','1405-12-29',0)",
        "INSERT INTO documents(id,fiscal_year_id,number,doc_type,date_g,date_j,description,status,is_reversed,created_at,row_version) VALUES(1,1,1,'GENERAL','2026-03-21','1405-01-01','posted','POSTED',0,'2026-03-21 00:00:00',3),(2,1,NULL,'GENERAL','2026-03-22','1405-01-02','draft','DRAFT',0,'2026-03-22 00:00:00',7)",
        "INSERT INTO document_lines(id,document_id,line_no,account_id,tafsili1_id,tafsili2_id,currency_id,debit,credit,description) VALUES(1,1,1,1,1,2,1,12345,0,'both'),(2,1,2,1,2,3,1,0,12345,'balance'),(3,2,1,1,NULL,3,2,19.25,0,'USD'),(4,2,2,1,3,NULL,2,0,19.25,'USD-balance')",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    return config, engine


def _audit_historical_rows(engine):
    tables = (
        "tafsili_groups", "tafsili_group_members", "currencies", "accounts",
        "account_tafsili_rules", "fiscal_years", "documents", "document_lines",
    )
    with engine.connect() as connection:
        result = {
            table: [tuple(row) for row in connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1")]
            for table in tables
        }
        result["tafsilis"] = [tuple(row) for row in connection.exec_driver_sql(
            "SELECT id,code,name,group_id,phone,national_id,address,note,is_active,row_version FROM tafsilis ORDER BY id"
        )]
        return result


def test_audit_migration_restores_foreign_keys_on_retained_connection(tmp_path):
    config, engine = _audit_legacy_migration_database(tmp_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.commit()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            # Enforcement must survive the migration when env.py reuses a caller's connection.
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()


def test_audit_populated_migration_roundtrip_preserves_historical_records(tmp_path):
    config, engine = _audit_legacy_migration_database(tmp_path)
    try:
        historical = _audit_historical_rows(engine)
        command.upgrade(config, "head")
        with engine.begin() as connection:
            assert connection.exec_driver_sql("SELECT id,parent_id FROM tafsilis ORDER BY id").all() == [(1,None),(2,None),(3,None)]
            connection.execute(text("UPDATE tafsilis SET parent_id=1 WHERE id=2"))
            connection.execute(text("UPDATE tafsilis SET parent_id=2 WHERE id=3"))
        for direction, revision in (("downgrade", "moein_code_repeat"), ("upgrade", "head")):
            getattr(command, direction)(config, revision)
            assert _audit_historical_rows(engine) == historical
            with engine.connect() as connection:
                assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
                assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        with engine.connect() as connection:
            # Downgrade removes hierarchy metadata by design; amounts and old references survive.
            assert connection.exec_driver_sql("SELECT id,parent_id FROM tafsilis ORDER BY id").all() == [(1,None),(2,None),(3,None)]
    finally:
        engine.dispose()


@pytest.fixture
def audit_ui_context(tmp_path, qapp):
    data = tmp_path / 'audit-ui'
    data.mkdir()
    context = AppContext(bootstrap.start(config_module.AppConfig(
        data_dir=data, sqlite_path=data / 'ledger.sqlite3')))
    with context.session() as db:
        group = db.execute(select(TafsiliGroup).where(TafsiliGroup.code == '20')).scalar_one()
        root = master_data.create_tafsili(db, code='99101', name='ریشه ممیزی', group_id=group.id)
        branch = master_data.create_tafsili(db, code='99102', name='شاخه ممیزی', group_id=group.id, parent_id=root.id)
        leaf = master_data.create_tafsili(db, code='99103', name='برگ ممیزی', group_id=group.id, parent_id=branch.id)
        account = db.execute(select(Account).where(Account.code == '1001')).scalar_one()
        account.tafsili_rules[:] = [AccountTafsiliRule(tafsili_group_id=group.id, tafsili_id=root.id, slot=slot) for slot in (1, 2)]
        ids = SimpleNamespace(root=root.id, branch=branch.id, leaf=leaf.id, account=account.id)
    context.reload_refdata()
    yield context, ids


def test_audit_tree_picker_blocks_parent_and_accepts_leaf(qapp):
    dialog = TreePickerDialog('ممیزی', [(1, 'ریشه', None, False), (2, 'شاخه', 1, False), (3, 'برگ', 2, True)])
    root = dialog.tree.topLevelItem(0)
    branch, leaf = root.child(0), root.child(0).child(0)
    for node in (root, branch):
        dialog.tree.setCurrentItem(node)
        assert dialog.selected_id is None
        assert not dialog.ok_button.isEnabled()
        assert node.foreground(0).color() == dialog.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        dialog.tree.itemDoubleClicked.emit(node, 0)
        assert dialog.result() == 0
    dialog.tree.setCurrentItem(leaf)
    assert dialog.selected_id == 3
    assert dialog.ok_button.isEnabled()
    dialog.tree.itemDoubleClicked.emit(leaf, 0)
    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.close()


@pytest.mark.parametrize('slot,column', [(1, COL_T1), (2, COL_T2)])
def test_audit_tafsili_combo_and_tree_expose_only_eligible_leaves(audit_ui_context, slot, column):
    context, ids = audit_ui_context
    model = LineGridModel(context.refdata)
    model.set_rows([LineRow(account_id=ids.account)])
    delegate = TafsiliDelegate(slot)
    index = model.index(0, column)
    choices = {ident: (parent, selectable) for ident, _label, parent, selectable in delegate.tree_choices(index)}
    assert choices[ids.root] == (None, False)
    assert choices[ids.branch] == (ids.root, False)
    assert choices[ids.leaf] == (ids.branch, True)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), index)
    assert isinstance(editor, TreePickerCombo)
    assert editor.findData(ids.root) == -1
    assert editor.findData(ids.branch) == -1
    assert editor.findData(ids.leaf) >= 0
    editor.close()


def test_audit_account_tree_disables_nonleaf_accounts(audit_ui_context):
    context, _ids = audit_ui_context
    model = LineGridModel(context.refdata)
    delegate = AccountDelegate()
    choices = delegate.tree_choices(model.index(0, COL_ACCOUNT))
    assert choices
    for ident, _label, _parent, selectable in choices:
        account = context.refdata.account_by_id[ident]
        assert selectable == (account in context.refdata.postable)
        if account.children or account.level == 1:
            assert not selectable


def test_audit_register_three_levels_and_double_click_edit(audit_ui_context, qapp):
    context, ids = audit_ui_context
    view = TafsiliView(context)
    nodes = {}
    def visit(node):
        nodes[node.data(0, Qt.UserRole)] = node
        for position in range(node.childCount()):
            visit(node.child(position))
    for position in range(view.tree.topLevelItemCount()):
        visit(view.tree.topLevelItem(position))
    assert nodes[ids.branch].parent() is nodes[ids.root]
    assert nodes[ids.leaf].parent() is nodes[ids.branch]
    view.tree.setCurrentItem(nodes[ids.leaf])
    with patch('app.ui.views.tafsili_view.TafsiliDialog') as dialog:
        dialog.return_value.exec.return_value = 0
        view.tree.doubleClicked.emit(view.tree.indexFromItem(nodes[ids.leaf]))
        assert dialog.call_count == 1
        assert dialog.call_args.args[2].id == ids.leaf
    view.close()


def test_audit_active_row_status_updates_account_and_both_slots(audit_ui_context, qapp):
    context, ids = audit_ui_context
    view = DocumentEntryView(context)
    account = context.refdata.account_by_id[ids.account]
    leaf = context.refdata.tafsili_by_id[ids.leaf]
    other = next(item for item in context.refdata.tafsilis if not item.children and item.id != leaf.id)
    view.model.set_rows([LineRow(ids.account, leaf.id, other.id), LineRow()])
    view.table.setCurrentIndex(view.model.index(0, COL_ACCOUNT))
    qapp.processEvents()
    assert f'حساب: {account.posting_display}' in view.balance.text()
    assert f'تفصیلی ۱: {leaf.display}' in view.balance.text()
    assert f'تفصیلی ۲: {other.display}' in view.balance.text()
    view.table.setCurrentIndex(view.model.index(1, COL_ACCOUNT))
    qapp.processEvents()
    assert 'حساب: — | تفصیلی ۱: — | تفصیلی ۲: —' in view.balance.text()
    assert leaf.display not in view.balance.text()
    view.close()


def test_audit_concurrent_reparenting_rejects_cycle_with_cached_ancestry(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'concurrent-tree.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as setup:
            group = master_data.create_tafsili_group(setup, code="99", name="ممیزی")
            node_a = master_data.create_tafsili(setup, code="991", name="A", group_id=group.id)
            node_b = master_data.create_tafsili(setup, code="992", name="B", group_id=group.id)
            node_a_id, node_b_id = node_a.id, node_b.id
            setup.commit()

        with Session(engine, expire_on_commit=False) as first, Session(engine, expire_on_commit=False) as second:
            first_a = first.get(Tafsili, node_a_id)
            first_b = first.get(Tafsili, node_b_id)
            second_a = second.get(Tafsili, node_a_id)
            second_b = second.get(Tafsili, node_b_id)
            assert first_a.parent is first_b.parent is None
            assert second_a.parent is second_b.parent is None

            master_data.update_tafsili(first, first_a, parent_id=node_b_id)
            first.commit()
            assert second_a.parent is None

            # A stale session must not commit a reverse edge to the new ancestor.
            with pytest.raises(ValidationError, match="چرخه|ساختار"):
                master_data.update_tafsili(second, second_b, parent_id=node_a_id)
                second.commit()
    finally:
        engine.dispose()
