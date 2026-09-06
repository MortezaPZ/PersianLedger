"""Document attachments stored in the database, keyed by SHA-256."""
from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import AppConfig
from app.db.models import AttachmentBlob, Document, DocumentAttachment
from app.domain.errors import ImmutableDocumentError, ValidationError

MAX_BYTES = 20 * 1024 * 1024
log = logging.getLogger(__name__)


def add(session: Session, cfg: AppConfig, document: Document, source: Path) -> DocumentAttachment:
    if document.is_posted:
        raise ImmutableDocumentError(document.number or 0)
    data = Path(source).read_bytes()
    if len(data) > MAX_BYTES:
        raise ValidationError("حجم هر پیوست حداکثر ۲۰ مگابایت است.")
    digest = hashlib.sha256(data).hexdigest()
    stored = f"{digest}{Path(source).suffix.lower()}"
    blob = session.get(AttachmentBlob, digest)
    if blob is None:
        blob = AttachmentBlob(sha256=digest, size_bytes=len(data), data=data)
        session.add(blob)
    row = DocumentAttachment(
        document_id=document.id,
        original_name=Path(source).name,
        stored_name=stored,
        mime=None,
        size_bytes=len(data),
        sha256=digest,
    )
    session.add(row)
    session.flush()
    return row


def materialize(session: Session, cfg: AppConfig, attachment: DocumentAttachment) -> Path:
    cache = Path(cfg.data_dir) / "attachments-cache"
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / attachment.stored_name
    blob = session.get(AttachmentBlob, attachment.sha256)
    if blob is None:
        raise ValidationError("محتوای پیوست در دیتابیس پیدا نشد.")
    if dest.exists() and dest.stat().st_size == blob.size_bytes:
        return dest
    dest.write_bytes(blob.data)
    return dest


def export_copy(session: Session, cfg: AppConfig, attachment: DocumentAttachment, dest: Path) -> Path:
    src = materialize(session, cfg, attachment)
    shutil.copy2(src, dest)
    return dest


def remove(session: Session, cfg: AppConfig, attachment: DocumentAttachment, document: Document) -> None:
    if document.is_posted:
        raise ImmutableDocumentError(document.number or 0)
    digest = attachment.sha256
    session.delete(attachment)
    session.flush()
    remaining = session.execute(
        select(func.count()).select_from(DocumentAttachment).where(DocumentAttachment.sha256 == digest)
    ).scalar_one()
    if remaining == 0:
        blob = session.get(AttachmentBlob, digest)
        if blob is not None:
            session.delete(blob)
            session.flush()


def import_legacy_files(session: Session, cfg: AppConfig) -> int:
    folder = Path(cfg.attachments_dir)
    if not folder.is_dir():
        return 0
    names = {
        row[0]
        for row in session.execute(select(DocumentAttachment.stored_name).distinct())
    }
    imported = 0
    for stored in names:
        path = folder / stored
        if not path.is_file():
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if session.get(AttachmentBlob, digest) is None:
            session.add(AttachmentBlob(sha256=digest, size_bytes=len(data), data=data))
            imported += 1
    if imported:
        session.flush()
        log.info("imported %s legacy attachment files into the database", imported)
    return imported
