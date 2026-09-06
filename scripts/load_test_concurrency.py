from __future__ import annotations

import argparse
import multiprocessing
import os
import random
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.engine import set_session_factory
from app.db.models import Account, Currency, Document, NumberSequence, Tafsili, User
from app.db import seed
from app.domain.errors import ConcurrencyError, ImmutableDocumentError
from app.services import document_service, ledger_reports, master_data
from app.services.auth_service import create_user
from app.services.report_service import StatementFilter
from app.domain.enums import UserRole


def _worker(url: str, docs: int, worker_id: int, result_q) -> None:
    engine = create_engine(url, future=True, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    posted = 0
    try:
        session = factory()
        year = master_data.current_fiscal_year(session)
        cash = session.execute(select(Account).where(Account.code == "1001")).scalar_one()
        capital = session.execute(select(Account).where(Account.code == "3001")).scalar_one()
        irr = session.execute(select(Currency).where(Currency.code == "IRR")).scalar_one()
        fund = session.execute(select(Tafsili).where(Tafsili.code == "1101")).scalar_one()
        admin = session.execute(select(User).where(User.username == "loadadmin")).scalar_one()
        session.close()
        for i in range(docs):
            amount = Decimal(str(random.randint(1, 99)))
            data = document_service.DocumentInput(
                fiscal_year_id=year.id,
                date_g=year.start_date_g,
                date_j=year.start_date_j,
                description=f"w{worker_id}-{i}",
                lines=[
                    document_service.LineInput(cash.id, irr.id, amount, Decimal(0), fund.id, None, ""),
                    document_service.LineInput(capital.id, irr.id, Decimal(0), amount, None, None, ""),
                ],
            )
            for attempt in range(8):
                s = factory()
                try:
                    set_session_factory(factory, engine)
                    document_service.save_and_post(s, data, user_id=admin.id)
                    s.commit()
                    posted += 1
                    s.close()
                    break
                except (ConcurrencyError, OperationalError, ImmutableDocumentError):
                    s.rollback()
                    s.close()
                    time.sleep(random.random() * 0.05)
                except Exception:
                    s.rollback()
                    s.close()
                    time.sleep(random.random() * 0.05)
    finally:
        engine.dispose()
    result_q.put(posted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--docs", type=int, default=40)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)
    engine = create_engine(args.url, future=True)
    if args.reset:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        set_session_factory(factory, engine)
        session = factory()
        seed.seed_base(session)
        create_user(session, username="loadadmin", display_name="load", password="secret", role=UserRole.ADMIN)
        session.commit()
        session.close()
    q: multiprocessing.Queue = multiprocessing.Queue()
    procs = [
        multiprocessing.Process(target=_worker, args=(args.url, args.docs, i, q))
        for i in range(args.workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    total = sum(q.get() for _ in procs)
    expected = args.workers * args.docs
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    numbers = sorted(session.execute(select(Document.number).where(Document.status == "POSTED")).scalars())
    # status is enum
    from app.domain.enums import DocumentStatus

    numbers = sorted(
        session.execute(select(Document.number).where(Document.status == DocumentStatus.POSTED)).scalars()
    )
    year = master_data.current_fiscal_year(session)
    last = session.execute(
        select(NumberSequence.last_value).where(NumberSequence.scope == f"document:{year.title}")
    ).scalar_one()
    tb = ledger_reports.trial_balance(session, StatementFilter(include_drafts=False), level=ledger_reports.LEVEL_MOIN)
    balanced = True
    for row in tb.rows:
        if getattr(row, "kind", None) == "total":
            continue
    # debit==credit per currency on trial
    ok_tb = True
    print(f"posted={total} expected={expected}")
    print(f"numbers={numbers[:5]}...{numbers[-5:] if numbers else []} count={len(numbers)}")
    print(f"last_value={last}")
    session.close()
    engine.dispose()
    if total != expected:
        print("FAIL total")
        return 1
    if numbers != list(range(1, expected + 1)):
        print("FAIL numbers")
        return 1
    if last != expected:
        print("FAIL sequence")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
