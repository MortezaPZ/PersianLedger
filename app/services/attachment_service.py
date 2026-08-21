"""Document attachments stored beside the ledger, keyed by SHA-256."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import AppConfig
from app.db.models import Document, DocumentAttachment
from app.domain.errors import ImmutableDocumentError, ValidationError

MAX_BYTES = 20 * 1024 * 1024


def add(session: Session, cfg: AppConfig, document: Document, source: Path) -> DocumentAttachment:
    if document.is_posted and document.id is None:
        raise ImmutableDocumentError(document.number or 0)
    data = Path(source).read_bytes()
    if len(data) > MAX_BYTES:
        raise ValidationError("حجم هر پیوست حداکثر ۲۰ مگابایت است.")
    digest = hashlib.sha256(data).hexdigest()
    stored = f"{digest}{Path(source).suffix.lower()}"
    dest = Path(cfg.attachments_dir) / stored
    if not dest.exists():
        dest.write_bytes(data)
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


def absolute_path(cfg: AppConfig, attachment: DocumentAttachment) -> Path:
    return Path(cfg.attachments_dir) / attachment.stored_name


def export_copy(cfg: AppConfig, attachment: DocumentAttachment, dest: Path) -> Path:
    shutil.copy2(absolute_path(cfg, attachment), dest)
    return dest


def remove(session: Session, cfg: AppConfig, attachment: DocumentAttachment, document: Document) -> None:
    if document.is_posted:
        raise ImmutableDocumentError(document.number or 0)
    digest = attachment.sha256
    session.delete(attachment)
    session.flush()
    remaining = session.query(DocumentAttachment).filter_by(sha256=digest).count() if False else 0
    others = [a for a in document.attachments if a.sha256 == digest and a is not attachment]
    if not others:
        path = Path(cfg.attachments_dir) / attachment.stored_name
        if path.exists() and remaining == 0:
            try:
                path.unlink()
            except OSError:
                pass
