from __future__ import annotations

import pytest
from sqlalchemy import text

from app import bootstrap, config as config_module
from app.db import engine as engine_module
from app.db import migrate
from app.db.models import User
from app.domain.enums import UserRole
from app.domain.errors import PermissionDeniedError
from app.domain.permissions import Perm
from app.services import auth_service, document_service, master_data
from tests.test_unpost_and_purge import _post


def _user(session, username: str, role: UserRole) -> User:
    return auth_service.create_user(
        session,
        username=username,
        display_name=username,
        password="secret",
        role=role,
    )


def test_roles_enforce_document_actions(db_session):
    session = db_session
    master_data  # seed via seed_base
    from app.db import seed

    seed.seed_base(session)
    admin = _user(session, "admin", UserRole.ADMIN)
    accountant = _user(session, "acc", UserRole.ACCOUNTANT)
    clerk = _user(session, "clerk", UserRole.CLERK)
    viewer = _user(session, "view", UserRole.VIEWER)
    doc = _post(session, "draft-source")
    document_service.unpost(session, doc, user_id=admin.id)
    session.flush()
    with pytest.raises(PermissionDeniedError):
        document_service.post(session, doc, user_id=clerk.id)
    document_service.save_draft(session, document_service.DocumentInput(
        fiscal_year_id=doc.fiscal_year_id,
        date_g=doc.date_g,
        date_j=doc.date_j,
        description="clerk",
        lines=[],
    ), user_id=clerk.id)
    with pytest.raises(PermissionDeniedError):
        document_service.save_draft(session, document_service.DocumentInput(
            fiscal_year_id=doc.fiscal_year_id,
            date_g=doc.date_g,
            date_j=doc.date_j,
            description="nope",
            lines=[],
        ), user_id=viewer.id)
    posted = _post(session, "acc-unpost")
    with pytest.raises(PermissionDeniedError):
        document_service.unpost(session, posted, user_id=accountant.id)
    document_service.unpost(session, posted, user_id=admin.id)
    document_service.save_draft(session, document_service.DocumentInput(
        fiscal_year_id=doc.fiscal_year_id, date_g=doc.date_g, date_j=doc.date_j, description="x", lines=[]
    ), user_id=None)
    inactive = _user(session, "dead", UserRole.ADMIN)
    auth_service.set_active(session, inactive, False, user_id=admin.id)
    with pytest.raises(PermissionDeniedError):
        document_service.save_draft(session, document_service.DocumentInput(
            fiscal_year_id=doc.fiscal_year_id, date_g=doc.date_g, date_j=doc.date_j, description="x", lines=[]
        ), user_id=inactive.id)
    auth_service.set_password(session, clerk, "newpass", user_id=clerk.id)
    with pytest.raises(PermissionDeniedError):
        auth_service.set_password(session, clerk, "other", user_id=accountant.id)
    auth_service.set_password(session, clerk, "adminok", user_id=admin.id)


def test_role_migration_promotes_admin(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")
    engine = engine_module.init_engine(cfg)
    alembic_cfg = migrate.alembic_config(cfg.database_url())
    from alembic import command

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "5879b0c1dc53")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (username, display_name, password_hash, is_active, is_admin, created_at) "
                "VALUES ('boss', 'مدیر', 'x', 1, 1, '2026-01-01T00:00:00')"
            )
        )
    migrate.upgrade_to_head(engine, cfg)
    with engine.connect() as connection:
        role = connection.execute(text("SELECT role FROM users WHERE username='boss'")).scalar()
    assert role == "ADMIN"


def test_permissions_of_admin(db_session):
    from app.db import seed

    seed.seed_base(db_session)
    admin = _user(db_session, "root", UserRole.ADMIN)
    assert Perm.DOC_PURGE in auth_service.permissions_of(admin)
