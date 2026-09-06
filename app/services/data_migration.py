from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.config import AppConfig
from app.db import engine as engine_module
from app.db import migrate as migrate_module
from app.db.base import Base
from app.services import attachment_service


@dataclass
class MigrationReport:
    table_counts: dict[str, tuple[int, int]] = field(default_factory=dict)
    debit_credit: dict[str, tuple[object, object, object, object]] = field(default_factory=dict)
    mismatches: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return not self.mismatches


def cfg_from_pg_url(url: str) -> AppConfig:
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    return AppConfig(
        backend="postgresql",
        pg_host=parsed.hostname or "localhost",
        pg_port=parsed.port or 5432,
        pg_database=(parsed.path or "/").lstrip("/"),
        pg_user=parsed.username or "postgres",
        pg_password=parsed.password or "",
    )


def migrate(
    sqlite_path: Path,
    pg_url: str,
    replace: bool = False,
    attachments_dir: Path | None = None,
    progress=None,
) -> MigrationReport:
    src_cfg = AppConfig(backend="sqlite", sqlite_path=Path(sqlite_path), data_dir=Path(sqlite_path).parent)
    if attachments_dir:
        src_cfg.attachments_dir_override = Path(attachments_dir)
    dst_cfg = cfg_from_pg_url(pg_url)
    src_engine = engine_module.build_engine(src_cfg.database_url())
    dst_engine = engine_module.build_engine(pg_url)
    report = MigrationReport()
    try:
        migrate_module.upgrade_to_head(src_engine, src_cfg)
        migrate_module.upgrade_to_head(dst_engine, dst_cfg)
        with dst_engine.connect() as conn:
            docs = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar_one()
            accounts = conn.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one()
            users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        if (docs or accounts or users) and not replace:
            report.mismatches.append("target is not empty; pass replace=True")
            return report
        if replace:
            tables = [t.name for t in reversed(Base.metadata.sorted_tables) if t.name != "alembic_version"]
            with dst_engine.begin() as conn:
                conn.execute(text("TRUNCATE {} RESTART IDENTITY CASCADE".format(", ".join(tables))))
        skip = {"alembic_version"}
        with src_engine.connect() as src, dst_engine.begin() as dst:
            for table in Base.metadata.sorted_tables:
                if table.name in skip:
                    continue
                if progress:
                    progress(table.name)
                rows = list(src.execute(table.select()).mappings())
                if rows:
                    for i in range(0, len(rows), 500):
                        dst.execute(table.insert(), [dict(r) for r in rows[i : i + 500]])
                dst_count = dst.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar_one()
                report.table_counts[table.name] = (len(rows), int(dst_count))
                if len(rows) != int(dst_count):
                    report.mismatches.append(f"{table.name}: {len(rows)} vs {dst_count}")
            for table in Base.metadata.sorted_tables:
                pk = table.primary_key.columns
                if len(pk) != 1:
                    continue
                col = list(pk)[0]
                if col.name != "id":
                    continue
                if getattr(col.type, "python_type", None) is not int:
                    continue
                dst.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table.name}','id'), "
                        f"COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM {table.name}"
                    )
                )
        with dst_engine.begin() as dst:
            from sqlalchemy.orm import Session

            session = Session(bind=dst)
            if attachments_dir:
                src_cfg.data_dir = Path(attachments_dir).parent
                attachment_service.import_legacy_files(session, src_cfg)
            session.flush()
            session.commit()
            session.close()
        _verify(src_engine, dst_engine, report)
    finally:
        src_engine.dispose()
        dst_engine.dispose()
    return report


def _verify(src: Engine, dst: Engine, report: MigrationReport) -> None:
    with src.connect() as a, dst.connect() as b:
        for table in Base.metadata.sorted_tables:
            if table.name == "alembic_version":
                continue
            sa_ = a.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar_one()
            sb_ = b.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar_one()
            if sa_ != sb_:
                report.mismatches.append(f"count {table.name}: {sa_} vs {sb_}")
        if inspect(src).has_table("document_lines"):
            q = text(
                "SELECT c.code, SUM(debit), SUM(credit) FROM document_lines dl "
                "JOIN currencies c ON c.id = dl.currency_id GROUP BY c.code"
            )
            left = {row[0]: (row[1], row[2]) for row in a.execute(q)}
            right = {row[0]: (row[1], row[2]) for row in b.execute(q)}
            if left != right:
                report.mismatches.append(f"sums {left} vs {right}")
            report.debit_credit = {k: (v[0], v[1], right.get(k, (0, 0))[0], right.get(k, (0, 0))[1]) for k, v in left.items()}
