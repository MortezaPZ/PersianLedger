"""Open the database, bring the schema to head, make sure base data exists."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from app import config as config_module
from app.config import AppConfig
from app.db import engine as engine_module
from app.db import migrate, seed


@dataclass
class Startup:
    config: AppConfig
    engine: Engine
    migration: migrate.MigrationResult
    seeded: bool


def start(cfg: AppConfig | None = None, with_demo: bool = False) -> Startup:
    cfg = cfg or config_module.load()
    engine = engine_module.init_engine(cfg)
    result = migrate.upgrade_to_head(engine, cfg)
    seeded = False
    with engine_module.new_session() as session:
        if seed.is_empty(session):
            seed.seed_base(session)
            seeded = True
            if with_demo:
                seed.seed_demo(session)
            # The employer asks for this worked example in every round of
            # feedback, so a plain install has to show it too -- not just --demo.
            seed.seed_project_example(session)
    return Startup(cfg, engine, result, seeded)
