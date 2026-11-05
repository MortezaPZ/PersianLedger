from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from sqlalchemy import text

from app.config import AppConfig
from app.db import migrate
from app.db.engine import build_engine


_ROOT = Path(__file__).resolve().parents[1]
_FINANCIAL_TABLES = (
    "tafsili_groups", "tafsili_group_members", "currencies", "accounts",
    "account_tafsili_rules", "fiscal_years", "documents", "document_lines",
)


def _tree_database(tmp_path: Path, name: str = "ledger.sqlite3"):
    folder = tmp_path / name.removesuffix(".sqlite3")
    folder.mkdir(parents=True)
    database = folder / name
    url = f"sqlite:///{database.as_posix()}"
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "moein_code_repeat")
    engine = build_engine(url)
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
    command.upgrade(cfg, "tafsili_tree")
    app_cfg = AppConfig(data_dir=folder, sqlite_path=database, backup_dir_override=folder / "backups")
    return cfg, app_cfg, engine


def _financial_snapshot(engine) -> dict[str, list[tuple]]:
    with engine.connect() as connection:
        result = {
            table: [tuple(row) for row in connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1")]
            for table in _FINANCIAL_TABLES
        }
        result["tafsilis"] = [tuple(row) for row in connection.exec_driver_sql(
            "SELECT id,code,name,group_id,phone,national_id,address,note,is_active,row_version FROM tafsilis ORDER BY id"
        )]
        return result


def _mutex_exists(engine) -> bool:
    with engine.connect() as connection:
        return connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tafsili_tree_mutex'"
        ).first() is not None


def _fail_before_mutex_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise RuntimeError("injected immediately after mutex CREATE")

    monkeypatch.setattr(Operations, "bulk_insert", fail)


def test_direct_alembic_mutex_failure_rolls_back_ddl_and_retry_succeeds(tmp_path, monkeypatch):
    cfg, _app_cfg, engine = _tree_database(tmp_path)
    try:
        before = _financial_snapshot(engine)
        _fail_before_mutex_seed(monkeypatch)
        with pytest.raises(RuntimeError, match="immediately after mutex CREATE"):
            command.upgrade(cfg, "head")
        assert not _mutex_exists(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "tafsili_tree"
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        monkeypatch.undo()
        command.upgrade(cfg, "head")
        assert _financial_snapshot(engine) == before
        assert _mutex_exists(engine)
    finally:
        engine.dispose()


def test_process_exit_during_mutex_migration_rolls_back_and_startup_recovers(tmp_path):
    cfg, app_cfg, engine = _tree_database(tmp_path)
    before = _financial_snapshot(engine)
    engine.dispose()
    script = r'''
import os
from alembic.operations import Operations
from app.config import AppConfig
from app.db.engine import build_engine
from app.db.migrate import upgrade_to_head

database = os.environ["MUTEX_TEST_DATABASE"]
folder = os.path.dirname(database)
cfg = AppConfig(data_dir=folder, sqlite_path=database, backup_dir_override=os.path.join(folder, "backups"))
original = Operations.bulk_insert
def stop_after_create(self, table, rows, *args, **kwargs):
    os._exit(73)
Operations.bulk_insert = stop_after_create
engine = build_engine(cfg.database_url())
upgrade_to_head(engine, cfg)
'''
    env = os.environ.copy()
    env["MUTEX_TEST_DATABASE"] = str(app_cfg.sqlite_path)
    process = subprocess.Popen(
        [sys.executable, "-c", script], cwd=_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=45)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
        pytest.fail(f"mutex crash subprocess timed out; stdout={stdout!r}; stderr={stderr!r}")
    assert process.returncode == 73, (stdout, stderr)

    recovered_engine = build_engine(app_cfg.database_url())
    try:
        assert not _mutex_exists(recovered_engine)
        result = migrate.upgrade_to_head(recovered_engine, app_cfg)
        assert result.applied
        assert _financial_snapshot(recovered_engine) == before
        with recovered_engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert connection.exec_driver_sql("SELECT id,revision FROM tafsili_tree_mutex").all() == [(1, 0)]
    finally:
        recovered_engine.dispose()


def test_startup_recovers_valid_empty_mutex_remnant_and_preserves_financial_rows(tmp_path):
    _cfg, app_cfg, engine = _tree_database(tmp_path)
    try:
        before = _financial_snapshot(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE tafsili_tree_mutex (id INTEGER NOT NULL, revision INTEGER DEFAULT 0 NOT NULL, "
                "CONSTRAINT pk_tafsili_tree_mutex PRIMARY KEY (id))"
            )
        engine.dispose()
        engine = build_engine(app_cfg.database_url())
        result = migrate.upgrade_to_head(engine, app_cfg)
        assert result.applied
        assert _financial_snapshot(engine) == before
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "tafsili_tree_mutex"
            assert connection.exec_driver_sql("SELECT id,revision FROM tafsili_tree_mutex").all() == [(1, 0)]
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert list(app_cfg.backup_dir.glob("pre-upgrade-mutex-recovery-*.sqlite3"))
    finally:
        engine.dispose()


def test_failed_startup_recovery_restores_clean_snapshot_and_next_retry_succeeds(tmp_path, monkeypatch):
    _cfg, app_cfg, engine = _tree_database(tmp_path)
    try:
        before = _financial_snapshot(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE tafsili_tree_mutex (id INTEGER NOT NULL, revision INTEGER DEFAULT 0 NOT NULL, "
                "CONSTRAINT pk_tafsili_tree_mutex PRIMARY KEY (id))"
            )
        engine.dispose()
        engine = build_engine(app_cfg.database_url())
        _fail_before_mutex_seed(monkeypatch)
        with pytest.raises(RuntimeError, match="immediately after mutex CREATE"):
            migrate.upgrade_to_head(engine, app_cfg)
        monkeypatch.undo()
        engine = build_engine(app_cfg.database_url())
        assert not _mutex_exists(engine)
        assert _financial_snapshot(engine) == before
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "tafsili_tree"
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        result = migrate.upgrade_to_head(engine, app_cfg)
        assert result.applied
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT id,revision FROM tafsili_tree_mutex").all() == [(1, 0)]
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        engine.dispose()


def test_startup_refuses_unrecognized_mutex_remnant_without_deleting_it(tmp_path):
    _cfg, app_cfg, engine = _tree_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE tafsili_tree_mutex (unexpected TEXT)")
            connection.exec_driver_sql("INSERT INTO tafsili_tree_mutex VALUES ('keep')")
        with pytest.raises(RuntimeError, match="مطابقت ندارد"):
            migrate.upgrade_to_head(engine, app_cfg)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT * FROM tafsili_tree_mutex").all() == [("keep",)]
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "tafsili_tree"
    finally:
        engine.dispose()


def test_caller_transaction_is_neither_committed_rolled_back_nor_fk_modified(tmp_path, monkeypatch):
    cfg, _app_cfg, engine = _tree_database(tmp_path)
    try:
        with engine.connect() as connection:
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
            transaction = connection.begin()
            connection.exec_driver_sql(
                "INSERT INTO app_settings(key,value) VALUES ('caller_owned','pending')"
            )
            assert connection.connection.driver_connection.in_transaction
            cfg.attributes["connection"] = connection
            _fail_before_mutex_seed(monkeypatch)
            with pytest.raises(RuntimeError, match="immediately after mutex CREATE"):
                command.upgrade(cfg, "head")
            assert transaction.is_active
            assert connection.in_transaction()
            assert connection.connection.driver_connection.in_transaction
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 0
            assert connection.exec_driver_sql(
                "SELECT value FROM app_settings WHERE key='caller_owned'"
            ).scalar_one() == "pending"
            connection.rollback()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            cfg.attributes.pop("connection", None)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM app_settings WHERE key='caller_owned'"
            ).scalar_one() == 0
            assert not _mutex_exists(engine)
    finally:
        engine.dispose()


def test_seeded_mutex_with_old_revision_is_validated_then_stamped(tmp_path):
    _cfg, app_cfg, engine = _tree_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE tafsili_tree_mutex (id INTEGER NOT NULL, revision INTEGER DEFAULT 0 NOT NULL, "
                "CONSTRAINT pk_tafsili_tree_mutex PRIMARY KEY (id))"
            )
            connection.exec_driver_sql("INSERT INTO tafsili_tree_mutex(id,revision) VALUES (1,4)")
        engine.dispose()
        engine = build_engine(app_cfg.database_url())
        result = migrate.upgrade_to_head(engine, app_cfg)
        assert result.applied
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "tafsili_tree_mutex"
            assert connection.exec_driver_sql("SELECT id,revision FROM tafsili_tree_mutex").all() == [(1, 4)]
    finally:
        engine.dispose()


def test_head_revision_without_valid_mutex_is_rejected(tmp_path):
    cfg, app_cfg, engine = _tree_database(tmp_path)
    try:
        command.upgrade(cfg, "head")
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE tafsili_tree_mutex")
        with pytest.raises(RuntimeError, match="جدول mutex سالم نیست"):
            migrate.upgrade_to_head(engine, app_cfg)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "tafsili_tree_mutex"
    finally:
        engine.dispose()


def test_mutex_migration_roundtrip_preserves_financial_rows(tmp_path):
    cfg, _app_cfg, engine = _tree_database(tmp_path)
    try:
        before = _financial_snapshot(engine)
        command.upgrade(cfg, "head")
        with engine.begin() as connection:
            connection.exec_driver_sql("UPDATE tafsilis SET parent_id=1 WHERE id=2")
            connection.exec_driver_sql("UPDATE tafsilis SET parent_id=2 WHERE id=3")
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        command.downgrade(cfg, "moein_code_repeat")
        assert _financial_snapshot(engine) == before
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        command.upgrade(cfg, "head")
        assert _financial_snapshot(engine) == before
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    finally:
        engine.dispose()
