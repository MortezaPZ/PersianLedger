from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Account, Currency, Tafsili, TafsiliGroup
from app.services import account_service, master_data


@dataclass
class RefData:
    accounts: list[Account] = field(default_factory=list)
    postable: list[Account] = field(default_factory=list)
    currencies: list[Currency] = field(default_factory=list)
    groups: list[TafsiliGroup] = field(default_factory=list)
    tafsilis: list[Tafsili] = field(default_factory=list)
    account_by_id: dict[int, Account] = field(default_factory=dict)
    tafsili_by_id: dict[int, Tafsili] = field(default_factory=dict)
    currency_by_id: dict[int, Currency] = field(default_factory=dict)

    @classmethod
    def load(cls, session: Session) -> RefData:
        data = cls()
        data.reload(session)
        return data

    def reload(self, session: Session) -> None:
        self.accounts = account_service.all_accounts(session, include_inactive=True)
        self.postable = [a for a in self.accounts if a.is_postable and a.is_active]
        self.currencies = master_data.currencies(session)
        self.groups = master_data.tafsili_groups(session)
        self.tafsilis = master_data.tafsilis(session)
        self.account_by_id = {a.id: a for a in self.accounts}
        self.tafsili_by_id = {t.id: t for t in self.tafsilis}
        self.currency_by_id = {c.id: c for c in self.currencies}

    def slot_enabled(self, account_id: int | None, slot: int) -> bool:
        account = self.account_by_id.get(account_id or 0)
        if account is None:
            return False
        return any(r.slot == slot for r in account.tafsili_rules)

    def slot_required(self, account_id: int | None, slot: int) -> bool:
        account = self.account_by_id.get(account_id or 0)
        if account is None:
            return False
        return account.tafsili1_required if slot == 1 else account.tafsili2_required

    def tafsilis_for(self, account_id: int | None, slot: int) -> list[Tafsili]:
        account = self.account_by_id.get(account_id or 0)
        if account is None:
            return []
        allowed = {r.tafsili_group_id for r in account.tafsili_rules if r.slot == slot}
        if not allowed:
            return []
        return [t for t in self.tafsilis if t.is_active and t.group_ids & allowed]

    def moein_accounts_for_groups(self, group_ids: set[int]) -> list[Account]:
        """معین accounts whose تفصیلی rules accept any of the given تفصیلی groups."""
        if not group_ids:
            return []
        out = []
        for account in self.accounts:
            if any(r.tafsili_group_id in group_ids for r in account.tafsili_rules):
                out.append(account)
        return out

    def currencies_for(self, account_id: int | None) -> list[Currency]:
        account = self.account_by_id.get(account_id or 0)
        active = [c for c in self.currencies if c.is_active]
        if account is None:
            return active
        allowed = {row.currency_id for row in account.allowed_currencies}
        if not allowed:
            return active
        return [c for c in active if c.id in allowed]
