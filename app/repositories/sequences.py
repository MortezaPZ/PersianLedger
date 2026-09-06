"""Gapless counters.

The allocating UPDATE takes a write lock that is held until the surrounding
transaction commits, on SQLite and PostgreSQL alike. MAX(number)+1 is never used
because two concurrent writers would both read the same maximum.
"""
from __future__ import annotations

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import NumberSequence


def document_scope(fiscal_year_title: str) -> str:
    return f"document:{fiscal_year_title}"


def ensure_scope(session: Session, scope: str) -> None:
    exists = session.execute(select(NumberSequence.id).where(NumberSequence.scope == scope)).first()
    if exists:
        return
    try:
        with session.begin_nested():
            session.execute(insert(NumberSequence).values(scope=scope, last_value=0))
    except IntegrityError:
        pass


def next_value(session: Session, scope: str) -> int:
    ensure_scope(session, scope)
    result = session.execute(
        update(NumberSequence)
        .where(NumberSequence.scope == scope)
        .values(last_value=NumberSequence.last_value + 1)
        .returning(NumberSequence.last_value),
        execution_options={"synchronize_session": False},
    )
    return int(result.scalar_one())


def peek_value(session: Session, scope: str) -> int:
    value = session.execute(
        select(NumberSequence.last_value).where(NumberSequence.scope == scope)
    ).scalar_one_or_none()
    return int(value or 0)


def release_value(session: Session, scope: str, value: int) -> bool:
    """Give a number back, but only if it is still the last one issued.

    Keeps numbering gapless in the ordinary case — you create a draft and then
    discard it — without ever renumbering a document somebody else already has.
    """
    result = session.execute(
        update(NumberSequence)
        .where(NumberSequence.scope == scope, NumberSequence.last_value == value)
        .values(last_value=NumberSequence.last_value - 1),
        execution_options={"synchronize_session": False},
    )
    return bool(result.rowcount)
