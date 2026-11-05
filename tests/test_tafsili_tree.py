from __future__ import annotations

import re
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import seed
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
