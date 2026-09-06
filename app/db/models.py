from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import JalaliDateColumn, MoneyColumn, utcnow
from app.domain.enums import AccountNature, AccountType, AuditAction, DocumentStatus, DocumentType, UserRole


def _enum(py_enum, name: str) -> Enum:
    return Enum(py_enum, name=name, native_enum=False, length=24)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class Currency(Base):
    __tablename__ = "currencies"
    __table_args__ = (CheckConstraint("decimals >= 0 AND decimals <= 4", name="decimals_range"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    decimals: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<Currency {self.code}>"


class FiscalYear(Base):
    __tablename__ = "fiscal_years"
    __table_args__ = (CheckConstraint("end_date_g >= start_date_g", name="range_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    start_date_g: Mapped[_dt.date] = mapped_column(Date, nullable=False)
    end_date_g: Mapped[_dt.date] = mapped_column(Date, nullable=False)
    start_date_j: Mapped[str] = mapped_column(JalaliDateColumn(length=10), nullable=False)
    end_date_j: Mapped[str] = mapped_column(JalaliDateColumn(length=10), nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AccountGroup(Base):
    """گروه — the level above کل, e.g. دارایی‌های جاری, هزینه‌ها.

    Completes the tree the employer asked for: گروه > کل > معین > تفصیلی ۱/۲.
    """

    __tablename__ = "account_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(_enum(AccountType, "account_type"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    accounts: Mapped[list[Account]] = relationship(back_populates="group")

    @property
    def display(self) -> str:
        return f"{self.code} {self.name}"


class Account(Base):
    """کل (level 1) and معین (level 2) in one self-referencing tree."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("level IN (1, 2)", name="level_range"),
        Index("ix_accounts_parent_id", "parent_id"),
        Index("ix_accounts_group_id", "group_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("account_groups.id"))
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account_type: Mapped[AccountType] = mapped_column(_enum(AccountType, "account_type"), nullable=False)
    nature: Mapped[AccountNature] = mapped_column(
        _enum(AccountNature, "account_nature"), nullable=False, default=AccountNature.BOTH
    )
    is_postable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tafsili1_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tafsili2_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}

    group: Mapped[AccountGroup | None] = relationship(back_populates="accounts")
    parent: Mapped[Account | None] = relationship(remote_side="Account.id", back_populates="children")
    children: Mapped[list[Account]] = relationship(back_populates="parent")
    allowed_currencies: Mapped[list[AccountCurrency]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    tafsili_rules: Mapped[list[AccountTafsiliRule]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    @property
    def display(self) -> str:
        return f"{self.code} {self.name}"


class AccountCurrency(Base):
    """Optional whitelist. No rows for an account = every active currency allowed."""

    __tablename__ = "account_currencies"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"), primary_key=True)
    account: Mapped[Account] = relationship(back_populates="allowed_currencies")
    currency: Mapped[Currency] = relationship()


class TafsiliGroup(Base):
    __tablename__ = "tafsili_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    items: Mapped[list[Tafsili]] = relationship(back_populates="group")


class TafsiliGroupMember(Base):
    """A tafsili may sit in several groups at once.

    "پروژه A" can be both a پروژه and a مرکز هزینه, so it can be reported under
    either heading, or both together, without being duplicated.
    """

    __tablename__ = "tafsili_group_members"

    tafsili_id: Mapped[int] = mapped_column(
        ForeignKey("tafsilis.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(ForeignKey("tafsili_groups.id"), primary_key=True)
    tafsili: Mapped[Tafsili] = relationship(back_populates="memberships")
    group: Mapped[TafsiliGroup] = relationship()


class Tafsili(Base):
    """Floating analytic account: person, fund, project, cost centre ..."""

    __tablename__ = "tafsilis"
    __table_args__ = (Index("ix_tafsilis_group_id", "group_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("tafsili_groups.id"), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    national_id: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}

    group: Mapped[TafsiliGroup] = relationship(back_populates="items")
    memberships: Mapped[list[TafsiliGroupMember]] = relationship(
        back_populates="tafsili", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def display(self) -> str:
        return f"{self.code} {self.name}"

    @property
    def group_ids(self) -> set[int]:
        """Every group this tafsili belongs to, home group included."""
        ids = {m.group_id for m in self.memberships}
        ids.add(self.group_id)
        return ids


class AccountTafsiliRule(Base):
    """Which tafsili group may be used on which معین, in which slot."""

    __tablename__ = "account_tafsili_rules"
    __table_args__ = (
        UniqueConstraint("account_id", "tafsili_group_id", "slot"),
        CheckConstraint("slot IN (1, 2)", name="slot_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    tafsili_group_id: Mapped[int] = mapped_column(ForeignKey("tafsili_groups.id"), nullable=False)
    slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account: Mapped[Account] = relationship(back_populates="tafsili_rules")
    group: Mapped[TafsiliGroup] = relationship()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), nullable=False, default=UserRole.ACCOUNTANT)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_login_at: Mapped[_dt.datetime | None] = mapped_column(DateTime)


class NumberSequence(Base):
    """Gapless counters. Allocated with a locking UPDATE, never MAX()+1."""

    __tablename__ = "number_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("fiscal_year_id", "number"),
        Index("ix_documents_date_g", "date_g"),
        Index("ix_documents_date_j", "date_j"),
        Index("ix_documents_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(ForeignKey("fiscal_years.id"), nullable=False)
    number: Mapped[int | None] = mapped_column(Integer)
    doc_type: Mapped[DocumentType] = mapped_column(
        _enum(DocumentType, "document_type"), nullable=False, default=DocumentType.GENERAL
    )
    date_g: Mapped[_dt.date] = mapped_column(Date, nullable=False)
    date_j: Mapped[str] = mapped_column(JalaliDateColumn(length=10), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        _enum(DocumentStatus, "document_status"), nullable=False, default=DocumentStatus.DRAFT
    )
    reverses_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    corrects_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    is_reversed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    posted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[_dt.datetime | None] = mapped_column(DateTime)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": row_version}

    fiscal_year: Mapped[FiscalYear] = relationship()
    lines: Mapped[list[DocumentLine]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentLine.line_no",
    )
    attachments: Mapped[list[DocumentAttachment]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    reverses: Mapped[Document | None] = relationship(
        foreign_keys=[reverses_document_id], remote_side="Document.id"
    )
    corrects: Mapped[Document | None] = relationship(
        foreign_keys=[corrects_document_id], remote_side="Document.id"
    )
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    posted_by: Mapped[User | None] = relationship(foreign_keys=[posted_by_user_id])

    @property
    def is_posted(self) -> bool:
        return self.status == DocumentStatus.POSTED

    @property
    def number_display(self) -> str:
        return str(self.number) if self.number is not None else "—"


class DocumentLine(Base):
    __tablename__ = "document_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="non_negative"),
        CheckConstraint("debit = 0 OR credit = 0", name="one_side_only"),
        CheckConstraint("debit + credit > 0", name="non_zero"),
        Index("ix_document_lines_account_id_currency_id", "account_id", "currency_id"),
        Index("ix_document_lines_document_id_line_no", "document_id", "line_no"),
        Index("ix_document_lines_tafsili1_id", "tafsili1_id"),
        Index("ix_document_lines_tafsili2_id", "tafsili2_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    tafsili1_id: Mapped[int | None] = mapped_column(ForeignKey("tafsilis.id"))
    tafsili2_id: Mapped[int | None] = mapped_column(ForeignKey("tafsilis.id"))
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"), nullable=False)
    debit: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, default=Decimal(0))
    credit: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, default=Decimal(0))
    description: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="lines")
    account: Mapped[Account] = relationship()
    tafsili1: Mapped[Tafsili | None] = relationship(foreign_keys=[tafsili1_id])
    tafsili2: Mapped[Tafsili | None] = relationship(foreign_keys=[tafsili2_id])
    currency: Mapped[Currency] = relationship()


class DocumentAttachment(Base):
    __tablename__ = "document_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    document: Mapped[Document] = relationship(back_populates="attachments")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity_type_entity_id", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[_dt.datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[AuditAction] = mapped_column(_enum(AuditAction, "audit_action"), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    user: Mapped[User | None] = relationship()
