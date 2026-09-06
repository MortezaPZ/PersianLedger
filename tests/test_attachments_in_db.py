from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.config import AppConfig
from app.db import seed
from app.db.models import AttachmentBlob, DocumentAttachment
from app.services import attachment_service, document_service, master_data
from tests.test_unpost_and_purge import _post


def test_attachments_roundtrip_reuse_and_legacy(db_session, tmp_path):
    session = db_session
    seed.seed_base(session)
    cfg = AppConfig(data_dir=tmp_path, sqlite_path=tmp_path / "ledger.sqlite3")
    doc = _post(session, "with-file")
    document_service.unpost(session, doc)
    other = _post(session, "other")
    document_service.unpost(session, other)
    src = tmp_path / "note.bin"
    payload = b"x" * 1024
    src.write_bytes(payload)
    first = attachment_service.add(session, cfg, doc, src)
    session.flush()
    blob = session.get(AttachmentBlob, first.sha256)
    assert blob is not None
    assert blob.size_bytes == 1024
    cache_cfg = AppConfig(data_dir=tmp_path / "cache2", sqlite_path=tmp_path / "cache2" / "x.sqlite3")
    out = attachment_service.materialize(session, cache_cfg, first)
    assert out.read_bytes() == payload
    second = attachment_service.add(session, cfg, other, src)
    session.flush()
    assert second.sha256 == first.sha256
    assert session.execute(select(AttachmentBlob)).scalars().all().__len__() == 1
    attachment_service.remove(session, cfg, first, doc)
    session.flush()
    assert session.get(AttachmentBlob, first.sha256) is not None
    attachment_service.remove(session, cfg, second, other)
    session.flush()
    assert session.get(AttachmentBlob, first.sha256) is None

    legacy_doc = _post(session, "legacy")
    document_service.unpost(session, legacy_doc)
    stored = "legacy.bin"
    dest = cfg.attachments_dir / stored
    dest.write_bytes(b"legacy-bytes")
    digest = __import__("hashlib").sha256(b"legacy-bytes").hexdigest()
    row = DocumentAttachment(
        document_id=legacy_doc.id,
        original_name="legacy.bin",
        stored_name=stored,
        size_bytes=12,
        sha256=digest,
    )
    session.add(row)
    session.flush()
    n = attachment_service.import_legacy_files(session, cfg)
    assert n == 1
    assert session.get(AttachmentBlob, digest) is not None
