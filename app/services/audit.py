from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.domain.enums import AuditAction


def record(
    session: Session,
    *,
    entity_type: str,
    action: AuditAction,
    entity_id: int | None = None,
    user_id: int | None = None,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> AuditLog:
    from app.services import auth_service

    row = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=auth_service.valid_user_id(session, user_id),
        before_json=json.dumps(before, ensure_ascii=False, default=str) if before else None,
        after_json=json.dumps(after, ensure_ascii=False, default=str) if after else None,
        note=note,
    )
    session.add(row)
    return row
