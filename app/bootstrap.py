"""Open the database, bring the schema to head, make sure base data exists."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine

from app import config as config_module
from app.config import AppConfig
from app.db import engine as engine_module
from app.db import migrate, seed
from app.db.engine import SCHEMA_LOCK_KEY, advisory_lock


@dataclass
class Startup:
    config: AppConfig
    engine: Engine
    migration: migrate.MigrationResult
    seeded: bool


def start(cfg: AppConfig | None = None, with_demo: bool = False) -> Startup:
    cfg = cfg or config_module.load()
    from app import paths

    if paths.is_frozen() and not paths.is_portable() and cfg.backend == "sqlite":
        from app.previous_data import default_desktop_roots, recall_previous_data

        recall_previous_data(Path(cfg.data_dir), default_desktop_roots())
    engine = engine_module.init_engine(cfg)
    result = migrate.upgrade_to_head(engine, cfg)
    seeded = False
    with engine.connect() as lock_conn, advisory_lock(lock_conn, SCHEMA_LOCK_KEY):
        with engine_module.new_session() as session:
            if seed.is_empty(session):
                seed.seed_base(session)
                seeded = True
                if with_demo:
                    seed.seed_demo(session)
                    seed.seed_project_example(session)
            from app.db.models import AttachmentBlob
            from app.services import attachment_service
            from sqlalchemy import func, select

            empty_blobs = session.execute(select(func.count()).select_from(AttachmentBlob)).scalar_one() == 0
            if empty_blobs:
                attachment_service.import_legacy_files(session, cfg)
    return Startup(cfg, engine, result, seeded)
