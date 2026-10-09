"""Add a home SQLite ledger into the company database without replacing it.

Rows that already exist are matched by code (or fiscal-year title), never by
the numeric id from the home file. Existing company rows are left as they are.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import AppConfig
from app.db import engine as engine_module
from app.db import migrate as migrate_module
from app.db.models import (
    Account,
    AccountCurrency,
    AccountGroup,
    AccountTafsiliRule,
    AttachmentBlob,
    Currency,
    Document,
    DocumentAttachment,
    DocumentLine,
    FiscalYear,
    NumberSequence,
    Tafsili,
    TafsiliGroup,
    TafsiliGroupMember,
)
from app.repositories import sequences


@dataclass
class HomeMergeReport:
    added_documents: int = 0
    renumbered: list[str] = field(default_factory=list)
    created_codes: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    def summary_fa(self) -> str:
        lines = [
            f"{self.added_documents} سند اضافه شد.",
            f"{len(self.renumbered)} شماره به‌خاطر تکراری بودن عوض شد.",
        ]
        if self.renumbered:
            lines.extend(self.renumbered)
        if self.created_codes:
            lines.append("کدینگ نو: " + "، ".join(self.created_codes))
        else:
            lines.append("کدینگ نو ساخته نشد.")
        if self.rejected:
            lines.append("سندهای ردشده:")
            lines.extend(self.rejected)
        else:
            lines.append("سندی رد نشد.")
        return "\n".join(lines)


def merge_home_file(source: Path, cfg: AppConfig, user_id: int | None = None) -> HomeMergeReport:
    source = Path(source)
    temp_dir = Path(tempfile.mkdtemp(prefix="pl-home-"))
    copied = temp_dir / "home.sqlite3"
    _sqlite_snapshot(source, copied)
    src_cfg = AppConfig(backend="sqlite", sqlite_path=copied, data_dir=temp_dir)
    src_engine = engine_module.build_engine(src_cfg.database_url())
    try:
        dst_engine = engine_module.get_engine()
        own_dst = False
    except RuntimeError:
        dst_engine = engine_module.build_engine(cfg.database_url())
        own_dst = True
    try:
        migrate_module.upgrade_to_head(src_engine, src_cfg)
        migrate_module.upgrade_to_head(dst_engine, cfg)
        from app.domain.permissions import Perm
        from app.services import auth_service
        from sqlalchemy.orm import Session as SASession

        with SASession(dst_engine) as gate:
            auth_service.require(gate, user_id, Perm.RESTORE)
        if cfg.is_server():
            from app.services import server_backup

            server_backup.create(cfg, user_id)
        with Session(src_engine) as src, Session(dst_engine) as dst:
            report = HomeMergeReport()
            _merge(src, dst, report)
            dst.commit()
            return report
    finally:
        src_engine.dispose()
        if own_dst:
            dst_engine.dispose()
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


def _sqlite_snapshot(source: Path, dest: Path) -> None:
    """Copy a SQLite file without rewriting the original, WAL included."""
    raw = sqlite3.connect(source)
    try:
        snap = sqlite3.connect(dest)
        try:
            raw.backup(snap)
        finally:
            snap.close()
    finally:
        raw.close()


def _merge(src: Session, dst: Session, report: HomeMergeReport) -> HomeMergeReport:
    currencies = _copy_currencies(src, dst, report)
    years = _copy_years(src, dst, report)
    groups = _copy_account_groups(src, dst, report)
    tafsili_groups = _copy_tafsili_groups(src, dst, report)
    accounts = _copy_accounts(src, dst, report, groups)
    tafsilis = _copy_tafsilis(src, dst, report, tafsili_groups)
    _copy_members(src, dst, tafsilis, tafsili_groups)
    _copy_account_links(src, dst, accounts, currencies, tafsili_groups)
    _copy_documents(src, dst, report, years, accounts, tafsilis, currencies)
    _sync_sequences(dst)
    return report


def _index(session: Session, model, attr: str) -> dict:
    rows = session.execute(select(model)).scalars().all()
    return {getattr(row, attr): row for row in rows}


def _copy_currencies(src: Session, dst: Session, report: HomeMergeReport) -> dict[int, int]:
    have = _index(dst, Currency, "code")
    mapping = {}
    for row in src.execute(select(Currency)).scalars():
        found = have.get(row.code)
        if found is None:
            found = Currency(
                code=row.code, name=row.name, symbol=row.symbol, decimals=row.decimals,
                sort_order=row.sort_order, is_active=row.is_active, is_locked=row.is_locked,
            )
            dst.add(found)
            dst.flush()
            have[row.code] = found
            report.created_codes.append(row.code)
        mapping[row.id] = found.id
    return mapping


def _copy_years(src: Session, dst: Session, report: HomeMergeReport) -> dict[int, int]:
    have = _index(dst, FiscalYear, "title")
    mapping = {}
    for row in src.execute(select(FiscalYear)).scalars():
        found = have.get(row.title)
        if found is None:
            found = FiscalYear(
                title=row.title,
                start_date_g=row.start_date_g,
                end_date_g=row.end_date_g,
                start_date_j=row.start_date_j,
                end_date_j=row.end_date_j,
                is_closed=False,
            )
            dst.add(found)
            dst.flush()
            have[row.title] = found
            report.created_codes.append(row.title)
        mapping[row.id] = found.id
    return mapping


def _copy_account_groups(src: Session, dst: Session, report: HomeMergeReport) -> dict[int, int]:
    have = _index(dst, AccountGroup, "code")
    mapping = {}
    for row in src.execute(select(AccountGroup)).scalars():
        found = have.get(row.code)
        if found is None:
            found = AccountGroup(
                code=row.code, name=row.name, account_type=row.account_type,
                sort_order=row.sort_order, is_active=row.is_active,
            )
            dst.add(found)
            dst.flush()
            have[row.code] = found
            report.created_codes.append(row.code)
        mapping[row.id] = found.id
    return mapping


def _copy_tafsili_groups(src: Session, dst: Session, report: HomeMergeReport) -> dict[int, int]:
    have = _index(dst, TafsiliGroup, "code")
    mapping = {}
    for row in src.execute(select(TafsiliGroup)).scalars():
        found = have.get(row.code)
        if found is None:
            found = TafsiliGroup(code=row.code, name=row.name, is_active=row.is_active)
            dst.add(found)
            dst.flush()
            have[row.code] = found
            report.created_codes.append(row.code)
        mapping[row.id] = found.id
    return mapping


def _copy_accounts(src: Session, dst: Session, report: HomeMergeReport, groups: dict[int, int]) -> dict[int, int]:
    rows = list(src.execute(select(Account).order_by(Account.level, Account.code)).scalars())
    src_code = {row.id: row.code for row in rows}
    have: dict[tuple[str, str], Account] = {}
    for account in dst.execute(select(Account)).scalars():
        parent_code = src_code.get(account.parent_id, "")
        if account.parent_id:
            parent = dst.get(Account, account.parent_id)
            parent_code = parent.code if parent else ""
        have[(parent_code, account.code)] = account
    mapping: dict[int, int] = {}
    for row in rows:
        parent_code = src_code.get(row.parent_id, "") if row.parent_id else ""
        found = have.get((parent_code, row.code))
        if found is None:
            parent_id = mapping.get(row.parent_id) if row.parent_id else None
            found = Account(
                code=row.code,
                name=row.name,
                parent_id=parent_id,
                group_id=groups.get(row.group_id) if row.group_id else None,
                level=row.level,
                account_type=row.account_type,
                nature=row.nature,
                is_postable=row.is_postable,
                tafsili1_required=row.tafsili1_required,
                tafsili2_required=row.tafsili2_required,
                is_active=row.is_active,
                note=row.note,
            )
            dst.add(found)
            dst.flush()
            have[(parent_code, row.code)] = found
            report.created_codes.append(row.code)
        mapping[row.id] = found.id
    return mapping


def _copy_tafsilis(src: Session, dst: Session, report: HomeMergeReport, groups: dict[int, int]) -> dict[int, int]:
    have = _index(dst, Tafsili, "code")
    mapping = {}
    for row in src.execute(select(Tafsili)).scalars():
        found = have.get(row.code)
        if found is None:
            group_id = groups.get(row.group_id)
            if group_id is None:
                continue
            found = Tafsili(
                code=row.code, name=row.name, group_id=group_id, phone=row.phone,
                national_id=row.national_id, address=row.address, note=row.note, is_active=row.is_active,
            )
            dst.add(found)
            dst.flush()
            have[row.code] = found
            report.created_codes.append(row.code)
        mapping[row.id] = found.id
    return mapping


def _copy_members(src: Session, dst: Session, tafsilis: dict[int, int], groups: dict[int, int]) -> None:
    existing = {
        (row.tafsili_id, row.group_id)
        for row in dst.execute(select(TafsiliGroupMember)).scalars()
    }
    for row in src.execute(select(TafsiliGroupMember)).scalars():
        tid = tafsilis.get(row.tafsili_id)
        gid = groups.get(row.group_id)
        if tid and gid and (tid, gid) not in existing:
            dst.add(TafsiliGroupMember(tafsili_id=tid, group_id=gid))
            existing.add((tid, gid))
    dst.flush()


def _copy_account_links(src, dst, accounts, currencies, groups) -> None:
    have_cur = {(r.account_id, r.currency_id) for r in dst.execute(select(AccountCurrency)).scalars()}
    for row in src.execute(select(AccountCurrency)).scalars():
        key = (accounts.get(row.account_id), currencies.get(row.currency_id))
        if key[0] and key[1] and key not in have_cur:
            dst.add(AccountCurrency(account_id=key[0], currency_id=key[1]))
            have_cur.add(key)
    have_rule = {
        (r.account_id, r.tafsili_group_id, r.slot)
        for r in dst.execute(select(AccountTafsiliRule)).scalars()
    }
    for row in src.execute(select(AccountTafsiliRule)).scalars():
        key = (accounts.get(row.account_id), groups.get(row.tafsili_group_id), row.slot)
        if key[0] and key[1] and key not in have_rule:
            dst.add(AccountTafsiliRule(account_id=key[0], tafsili_group_id=key[1], slot=key[2]))
            have_rule.add(key)
    dst.flush()


def _copy_documents(src, dst, report, years, accounts, tafsilis, currencies) -> None:
    company = list(
        dst.execute(
            select(Document).options(selectinload(Document.lines), selectinload(Document.fiscal_year))
        ).scalars()
    )
    dst_account_code = {row.id: row.code for row in dst.execute(select(Account)).scalars()}
    dst_tafsili_code = {row.id: row.code for row in dst.execute(select(Tafsili)).scalars()}
    src_account_code = {row.id: row.code for row in src.execute(select(Account)).scalars()}
    src_tafsili_code = {row.id: row.code for row in src.execute(select(Tafsili)).scalars()}
    year_rows = {row.id: row for row in dst.execute(select(FiscalYear)).scalars()}
    def dst_account(aid: int) -> str:
        return dst_account_code.get(aid, "")

    def dst_tafsili(tid: int | None) -> str:
        if not tid:
            return ""
        return dst_tafsili_code.get(tid, "")

    used: dict[int, set[int]] = {}
    seen = set()
    by_fp: dict[tuple, int] = {}
    for doc in company:
        used.setdefault(doc.fiscal_year_id, set())
        if doc.number is not None:
            used[doc.fiscal_year_id].add(doc.number)
        fp = (doc.fiscal_year_id, _fingerprint(doc, dst_account, dst_tafsili))
        seen.add(fp)
        by_fp[fp] = doc.id
    home_docs = list(
        src.execute(
            select(Document).options(
                selectinload(Document.lines),
                selectinload(Document.attachments),
                selectinload(Document.fiscal_year),
            )
        ).scalars()
    )

    def home_account(aid: int) -> str:
        return dst_account_code.get(accounts.get(aid), src_account_code.get(aid, ""))

    def home_tafsili(tid: int | None) -> str:
        if not tid:
            return ""
        return dst_tafsili_code.get(tafsilis.get(tid), src_tafsili_code.get(tid, ""))

    id_map: dict[int, int] = {}
    pending = []
    for doc in home_docs:
        year_id = years.get(doc.fiscal_year_id)
        if year_id is None:
            report.rejected.append(f"سند «{doc.description}»: سال مالی در شرکت نیست")
            continue
        year = year_rows.get(year_id)
        if year is not None and year.is_closed:
            report.rejected.append(f"سند «{doc.description}»: سال مالی {year.title} بسته است")
            continue
        fp = (year_id, _fingerprint(doc, home_account, home_tafsili))
        if fp in seen:
            id_map[doc.id] = by_fp[fp]
            continue
        missing = _missing_line_code(doc, accounts, tafsilis, currencies)
        if missing:
            report.rejected.append(f"سند «{doc.description}»: {missing}")
            continue
        pending.append(doc)

    reserved = {year_id: set(numbers) for year_id, numbers in used.items()}
    assigned: dict[int, int | None] = {}
    for doc in sorted(pending, key=lambda d: (d.fiscal_year.title, d.number or 0, d.id)):
        year_id = years[doc.fiscal_year_id]
        bucket = reserved.setdefault(year_id, set())
        if doc.number is not None and doc.number not in bucket:
            assigned[doc.id] = doc.number
            bucket.add(doc.number)
        else:
            assigned[doc.id] = None
    for doc in sorted(pending, key=lambda d: (d.fiscal_year.title, d.number or 0, d.id)):
        if assigned[doc.id] is not None:
            continue
        year_id = years[doc.fiscal_year_id]
        bucket = reserved.setdefault(year_id, set())
        number = max(bucket or {0}) + 1
        while number in bucket:
            number += 1
        bucket.add(number)
        assigned[doc.id] = number
        report.renumbered.append(f"سند «{doc.description}» از شماره {doc.number} به {number} تغییر کرد.")

    pending_refs = []
    for doc in pending:
        year_id = years[doc.fiscal_year_id]
        number = assigned[doc.id]
        created = Document(
            fiscal_year_id=year_id,
            number=number,
            doc_type=doc.doc_type,
            date_g=doc.date_g,
            date_j=doc.date_j,
            description=doc.description,
            status=doc.status,
            is_reversed=False,
            created_at=doc.created_at,
            posted_at=doc.posted_at,
            row_version=1,
        )
        dst.add(created)
        dst.flush()
        for line in doc.lines:
            dst.add(
                DocumentLine(
                    document_id=created.id,
                    line_no=line.line_no,
                    account_id=accounts[line.account_id],
                    tafsili1_id=tafsilis.get(line.tafsili1_id) if line.tafsili1_id else None,
                    tafsili2_id=tafsilis.get(line.tafsili2_id) if line.tafsili2_id else None,
                    currency_id=currencies[line.currency_id],
                    debit=line.debit,
                    credit=line.credit,
                    description=line.description,
                )
            )
        _copy_attachments(src, dst, doc, created.id)
        id_map[doc.id] = created.id
        pending_refs.append((created, doc))
        report.added_documents += 1
    for created, doc in pending_refs:
        if doc.reverses_document_id and doc.reverses_document_id in id_map:
            created.reverses_document_id = id_map[doc.reverses_document_id]
        if doc.corrects_document_id and doc.corrects_document_id in id_map:
            created.corrects_document_id = id_map[doc.corrects_document_id]
        if doc.is_reversed and created.reverses_document_id is None and not doc.reverses_document_id:
            created.is_reversed = True
    dst.flush()


def _fingerprint(doc: Document, account_code, tafsili_code) -> tuple:
    lines = tuple(
        sorted(
            (
                account_code(line.account_id) if line.account_id else "",
                tafsili_code(line.tafsili1_id),
                tafsili_code(line.tafsili2_id),
                str(line.debit),
                str(line.credit),
                line.line_no,
            )
            for line in doc.lines
        )
    )
    return ((doc.description or "").strip(), doc.date_j, lines)


def _missing_line_code(doc: Document, accounts, tafsilis, currencies) -> str | None:
    for line in doc.lines:
        if line.account_id not in accounts:
            return "سرفصل ردیف در شرکت و فایل خانه پیدا نشد"
        if line.currency_id not in currencies:
            return "ارز ردیف در شرکت و فایل خانه پیدا نشد"
        if line.tafsili1_id and line.tafsili1_id not in tafsilis:
            return "تفصیلی ردیف در شرکت و فایل خانه پیدا نشد"
        if line.tafsili2_id and line.tafsili2_id not in tafsilis:
            return "تفصیلی ردیف در شرکت و فایل خانه پیدا نشد"
    return None


def _copy_attachments(src: Session, dst: Session, doc: Document, new_id: int) -> None:
    for att in doc.attachments:
        blob = src.get(AttachmentBlob, att.sha256)
        if blob is None and dst.get(AttachmentBlob, att.sha256) is None:
            continue
        if blob is not None and dst.get(AttachmentBlob, att.sha256) is None:
            dst.add(AttachmentBlob(sha256=blob.sha256, size_bytes=blob.size_bytes, data=blob.data))
        dst.add(DocumentAttachment(
            document_id=new_id,
            original_name=att.original_name,
            stored_name=att.stored_name,
            mime=att.mime,
            size_bytes=att.size_bytes,
            sha256=att.sha256,
            created_at=att.created_at,
        ))


def _sync_sequences(dst: Session) -> None:
    years = list(dst.execute(select(FiscalYear)).scalars())
    for year in years:
        top = dst.execute(
            select(Document.number).where(Document.fiscal_year_id == year.id, Document.number.is_not(None)).order_by(Document.number.desc())
        ).scalar()
        if not top:
            continue
        scope = sequences.document_scope(year.title)
        sequences.ensure_scope(dst, scope)
        row = dst.execute(select(NumberSequence).where(NumberSequence.scope == scope)).scalar_one()
        if row.last_value < top:
            row.last_value = top
    dst.flush()
