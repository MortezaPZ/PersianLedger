"""Restore must replace the live ledger in the UI, not appear to merge with it."""
from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from app.db import engine as engine_module
from app.db.models import Document
from app.services import backup_service, document_service, master_data
from app.services.backup_service import BackupError
from app.ui.views.document_entry_view import DocumentEntryView
from app.ui.views.document_list_view import DocumentListView
from app.ui.views.settings_view import SettingsView
from tests.test_close_and_restore import _window


def _snapshot_docs(window) -> set[tuple[int, str]]:
    with window.ctx.read_session() as db:
        docs = list(db.execute(select(Document)).scalars())
        return {(d.number, d.description) for d in docs}


def _table_docs(listing: DocumentListView) -> set[tuple[int, str]]:
    out: set[tuple[int, str]] = set()
    for row in range(listing.table.rowCount()):
        number = int(listing.table.item(row, 0).text())
        description = listing.table.item(row, 3).text()
        out.add((number, description))
    return out


def _post_two(window, suffix: str) -> None:
    rd = window.ctx.refdata
    with window.ctx.read_session() as db:
        fy = master_data.current_fiscal_year(db)
        year_id = fy.id
        date_g = fy.start_date_g
        date_j = fy.start_date_j
    a, b = rd.postable[0], rd.postable[1]
    cur = rd.currencies[0]
    t1 = rd.tafsilis_for(a.id, 1)
    t2 = rd.tafsilis_for(b.id, 1)
    for i in range(2):
        data = document_service.DocumentInput(
            fiscal_year_id=year_id,
            date_g=date_g,
            date_j=date_j,
            description=f"سند آزمایشی بازیابی {suffix}-{i}",
            lines=[
                document_service.LineInput(
                    a.id, cur.id, Decimal("10"), Decimal(0), t1[0].id if t1 else None, None, ""
                ),
                document_service.LineInput(
                    b.id, cur.id, Decimal(0), Decimal("10"), t2[0].id if t2 else None, None, ""
                ),
            ],
        )
        with window.ctx.session() as db:
            document_service.save_and_post(db, data)


def test_restore_replaces_list_and_clears_entry(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    settings = next(v for v in window.views if isinstance(v, SettingsView))
    listing = next(v for v in window.views if isinstance(v, DocumentListView))
    entry = next(v for v in window.views if isinstance(v, DocumentEntryView))

    snapshot = backup_service.create(engine_module.get_engine(), window.ctx.config)
    recorded = _snapshot_docs(window)
    n = len(recorded)

    _post_two(window, "after")
    window.go_to(1)
    qapp.processEvents()
    assert listing.table.rowCount() == n + 2

    with patch.object(SettingsView, "inform", lambda *args, **kwargs: None):
        settings.apply_restore(snapshot.path)
    qapp.processEvents()

    assert listing.table.rowCount() == n
    assert _table_docs(listing) == recorded
    assert entry.document_id is None
    with window.ctx.read_session() as db:
        year = master_data.current_fiscal_year(db)
        assert window.ctx.fiscal_year_id == year.id
        assert document_service.next_number_preview(db, year) == n + 1


def test_restore_corrupted_file_leaves_live_db(qapp, tmp_path):
    window = _window(tmp_path, qapp)
    listing = next(v for v in window.views if isinstance(v, DocumentListView))

    n = listing.table.rowCount()
    _post_two(window, "keep")
    window.go_to(1)
    qapp.processEvents()
    assert listing.table.rowCount() == n + 2

    junk = tmp_path / "broken.sqlite3"
    junk.write_bytes(os.urandom(2048))

    raised = None
    try:
        backup_service.restore(engine_module.get_engine(), window.ctx.config, junk)
    except BackupError as exc:
        raised = exc
    assert raised is not None
    with window.ctx.read_session() as db:
        assert len(list(db.execute(select(Document)).scalars())) == n + 2
