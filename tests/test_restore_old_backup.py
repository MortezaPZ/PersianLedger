"""An older SQLite backup is upgraded on restore, and a failed upgrade rolls back."""
from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest
from alembic import command
from sqlalchemy import select, text, update

from app import config as config_module
from app.db import engine as engine_module
from app.db import migrate
from app.services import backup_service
from app.services.backup_service import BackupError


def _stamp_old_backup(folder: Path) -> Path:
    folder.mkdir()
    cfg = config_module.AppConfig(data_dir=folder, sqlite_path=folder / "old.sqlite3")
    engine = engine_module.build_engine(cfg.database_url())
    alembic_cfg = migrate.alembic_config(cfg.database_url())
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
        connection.execute(
            text(
                "INSERT INTO fiscal_years (title, start_date_g, end_date_g, start_date_j, end_date_j, is_closed) "
                "VALUES ('1404', '2025-03-21', '2026-03-20', '1404/01/01', '1404/12/29', 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO documents (fiscal_year_id, number, doc_type, date_g, date_j, description, status, "
                "is_reversed, created_at, row_version) "
                "VALUES (1, 1, 'GENERAL', '2025-04-01', '1404/01/12', 'old-invoice', 'POSTED', 0, "
                "'2026-01-01T00:00:00', 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO currencies (code, name, symbol, decimals, sort_order, is_active, is_locked) "
                "VALUES ('IRR', 'ریال', 'ریال', 0, 0, 1, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO accounts (code, name, parent_id, group_id, level, account_type, nature, "
                "is_postable, tafsili1_required, tafsili2_required, is_active, row_version) "
                "VALUES ('1', 'دارایی', NULL, 1, 1, 'ASSET', 'DEBIT', 0, 0, 0, 1, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO accounts (code, name, parent_id, group_id, level, account_type, nature, "
                "is_postable, tafsili1_required, tafsili2_required, is_active, row_version) "
                "VALUES ('101', 'صندوق', 1, 1, 2, 'ASSET', 'DEBIT', 1, 0, 0, 1, 1)"
            )
        )
        connection.execute(
            text("INSERT INTO account_currencies (account_id, currency_id) VALUES (2, 1)")
        )
        connection.execute(
            text(
                "INSERT INTO document_lines (document_id, line_no, account_id, currency_id, debit, credit) "
                "VALUES (1, 1, 2, 1, 10, 0)"
            )
        )
        # Simulate the temporary table left behind by a failed 0.7.4 batch migration.
        connection.execute(text("CREATE TABLE _alembic_tmp_accounts AS SELECT * FROM accounts"))
    engine.dispose()
    return cfg.sqlite_path


def _live(folder: Path):
    folder.mkdir()
    cfg = config_module.AppConfig(data_dir=folder, sqlite_path=folder / "ledger.sqlite3")
    engine = engine_module.init_engine(cfg)
    migrate.upgrade_to_head(engine, cfg)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (username, display_name, password_hash, is_active, is_admin, role, created_at) "
                "VALUES ('current', 'جاری', 'x', 1, 1, 'ADMIN', '2026-01-01T00:00:00')"
            )
        )
    return cfg, engine


def test_restore_upgrades_old_backup(tmp_path: Path) -> None:
    source = _stamp_old_backup(tmp_path / "old")
    cfg, engine = _live(tmp_path / "live")
    result = backup_service.restore(engine, cfg, source, user_id=None)
    assert result.documents == 1
    assert result.posted == 1
    check = engine_module.build_engine(cfg.database_url())
    try:
        with check.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            role = connection.execute(text("SELECT role FROM users WHERE username='boss'")).scalar()
            description = connection.execute(text("SELECT description FROM documents")).scalar()
            current = connection.execute(text("SELECT COUNT(*) FROM users WHERE username='current'")).scalar()
            accounts = connection.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
            lines = connection.execute(text("SELECT COUNT(*) FROM document_lines")).scalar()
            stale_tables = connection.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE name='_alembic_tmp_accounts'")
            ).scalar()
        assert revision == migrate.head_revision(cfg.database_url())
        assert role == "ADMIN"
        assert description == "old-invoice"
        assert accounts == 2
        assert lines == 1
        assert stale_tables == 0
        assert current == 0
    finally:
        check.dispose()
        engine_module.dispose()


def test_failed_upgrade_restores_previous_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _stamp_old_backup(tmp_path / "old")
    cfg, engine = _live(tmp_path / "live")

    def boom(*_args, **_kwargs):
        raise RuntimeError("migration broke")

    monkeypatch.setattr(migrate, "upgrade_to_head", boom)
    with pytest.raises(BackupError, match="دیتابیس فعلی تغییر نکرد"):
        backup_service.restore(engine, cfg, source, user_id=None)
    check = engine_module.build_engine(cfg.database_url())
    try:
        with check.connect() as connection:
            username = connection.execute(text("SELECT username FROM users")).scalar()
        assert username == "current"
    finally:
        check.dispose()
        engine_module.dispose()


def test_current_schema_cleans_leftover_alembic_batch_table(tmp_path: Path) -> None:
    cfg, engine = _live(tmp_path / "live")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE _alembic_tmp_accounts AS SELECT * FROM accounts"
        )

    result = migrate.upgrade_to_head(engine, cfg)

    assert result.applied
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE name='_alembic_tmp_accounts'")
        ).scalar() == 0
    assert migrate.upgrade_to_head(engine, cfg).applied is False


def test_restore_refuses_newer_schema_and_keeps_live_data(tmp_path: Path) -> None:
    source = _stamp_old_backup(tmp_path / "old")
    cfg, engine = _live(tmp_path / "live")
    conn = sqlite3.connect(source)
    try:
        conn.execute("UPDATE alembic_version SET version_num = 'not-a-real-revision'")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(BackupError, match="دیتابیس فعلی تغییر نکرد"):
        backup_service.restore(engine, cfg, source, user_id=None)
    check = engine_module.build_engine(cfg.database_url())
    try:
        with check.connect() as connection:
            username = connection.execute(text("SELECT username FROM users")).scalar()
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert username == "current"
        assert revision == migrate.head_revision(cfg.database_url())
    finally:
        check.dispose()
        engine_module.dispose()
