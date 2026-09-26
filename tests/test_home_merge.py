"""Home documents are appended to the company ledger; existing rows stay."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import bootstrap, config as config_module
from app.db import engine as engine_module
from app.db.models import Account, Document, User
from app.domain.enums import AccountType
from app.services import account_service, auth_service, document_service, master_data
from app.services.home_merge import merge_home_file
from tests.test_unpost_and_purge import _post


def _book(folder: Path):
    folder.mkdir()
    cfg = config_module.AppConfig(data_dir=folder, sqlite_path=folder / "ledger.sqlite3")
    bootstrap.start(cfg)
    return cfg


def test_home_work_is_added_without_replacing_company(tmp_path: Path) -> None:
    company = _book(tmp_path / "company")
    with Session(engine_module.get_engine()) as session:
        _post(session, "company-a")
        _post(session, "company-b")
        kept_name = session.execute(select(Account.name).where(Account.code == "1001")).scalar_one()
        session.commit()
    engine_module.dispose()

    home = _book(tmp_path / "home")
    with Session(engine_module.get_engine()) as session:
        _post(session, "home-dup")
        fresh = _post(session, "home-fresh")
        session.execute(update(Document).where(Document.id == fresh.id).values(number=4))
        parent = session.execute(select(Account).where(Account.level == 1)).scalar()
        account_service.create(
            session, code="9999", name="حساب خانه", parent_id=parent.id, user_id=None,
        )
        session.execute(update(Account).where(Account.code == "1001").values(name="نام عوض‌شده در خانه"))
        session.commit()
    engine_module.dispose()

    engine_module.init_engine(company)
    try:
        report = merge_home_file(home.sqlite_path, company)
        assert report.added_documents == 2
        assert report.rejected == []
        assert any("home-dup" in line and "1" in line for line in report.renumbered)
        assert "9999" in report.created_codes
        with Session(engine_module.get_engine()) as session:
            descriptions = set(session.execute(select(Document.description)).scalars())
            assert descriptions == {"company-a", "company-b", "home-dup", "home-fresh"}
            company_a = session.execute(select(Document).where(Document.description == "company-a")).scalar_one()
            assert company_a.number == 1
            renamed = session.execute(select(Account.name).where(Account.code == "1001")).scalar_one()
            assert renamed == kept_name
            fresh_row = session.execute(select(Document).where(Document.description == "home-fresh")).scalar_one()
            assert fresh_row.number == 4
            dup = session.execute(select(Document).where(Document.description == "home-dup")).scalar_one()
            assert dup.number != 1
    finally:
        engine_module.dispose()


def test_merge_does_not_steal_a_free_home_number_or_repeat(tmp_path: Path) -> None:
    company = _book(tmp_path / "company")
    with Session(engine_module.get_engine()) as session:
        _post(session, "company-a")
        _post(session, "company-b")
        session.commit()
    engine_module.dispose()

    home = _book(tmp_path / "home")
    with Session(engine_module.get_engine()) as session:
        _post(session, "home-dup")
        fresh = _post(session, "home-fresh")
        session.execute(update(Document).where(Document.id == fresh.id).values(number=3))
        auth_service.create_user(session, username="home-only", display_name="خانه", password="secret", user_id=None)
        session.commit()
    engine_module.dispose()
    before = home.sqlite_path.read_bytes()

    engine_module.init_engine(company)
    try:
        report = merge_home_file(home.sqlite_path, company)
        assert report.added_documents == 2
        with Session(engine_module.get_engine()) as session:
            fresh_row = session.execute(select(Document).where(Document.description == "home-fresh")).scalar_one()
            dup = session.execute(select(Document).where(Document.description == "home-dup")).scalar_one()
            assert fresh_row.number == 3
            assert dup.number == 4
            year = master_data.current_fiscal_year(session)
            assert document_service.next_number_preview(session, year) == 5
            names = set(session.execute(select(Document.description)).scalars())
            assert session.execute(select(User.username).where(User.username == "home-only")).scalar_one_or_none() is None
            assert names == {"company-a", "company-b", "home-dup", "home-fresh"}
        again = merge_home_file(home.sqlite_path, company)
        assert again.added_documents == 0
        with Session(engine_module.get_engine()) as session:
            assert session.execute(select(Document)).scalars().all().__len__() == 4
    finally:
        engine_module.dispose()
    assert home.sqlite_path.read_bytes() == before


def test_merge_rejects_documents_in_a_closed_year(tmp_path: Path) -> None:
    company = _book(tmp_path / "company")
    with Session(engine_module.get_engine()) as session:
        _post(session, "company-a")
        year = master_data.current_fiscal_year(session)
        master_data.set_year_closed(session, year, True, user_id=None)
        session.commit()
    engine_module.dispose()
    home = _book(tmp_path / "home")
    with Session(engine_module.get_engine()) as session:
        _post(session, "home-closed")
        account_service.create(
            session, code="8800", name="کل خانه", account_type=AccountType.ASSET, user_id=None,
        )
        session.commit()
    engine_module.dispose()
    engine_module.init_engine(company)
    try:
        report = merge_home_file(home.sqlite_path, company)
        assert report.added_documents == 0
        assert report.rejected
        with Session(engine_module.get_engine()) as session:
            descriptions = set(session.execute(select(Document.description)).scalars())
            assert descriptions == {"company-a"}
            assert session.execute(select(Account.id).where(Account.code == "8800")).scalar_one_or_none() is not None
    finally:
        engine_module.dispose()
