"""A tafsili in several groups must be reportable per group.

The employer's case: "پروژه A" belongs to both "مرکز هزینه" and "پروژه‌ها",
and they need it reported with both groups together, or with either one on
its own.  This was reported fixed once and came back, so it is pinned here.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import seed
from app.db.models import Tafsili, TafsiliGroup
from app.services import ledger_reports
from app.services.report_service import StatementFilter, party_statement


def _seeded(session: Session) -> tuple[Session, Tafsili]:
    seed.seed_base(session)
    seed.seed_demo(session)
    seed.seed_project_example(session)
    project = session.execute(select(Tafsili).where(Tafsili.code == "3105")).scalar_one()
    return session, project


def test_project_belongs_to_more_than_one_group(db_session):
    session, project = _seeded(db_session)
    assert len(project.group_ids) >= 2, "the scenario needs a multi-group tafsili"


def test_each_group_on_its_own_and_both_together_all_report(db_session):
    session, project = _seeded(db_session)
    groups = sorted(project.group_ids)
    first, second = groups[0], groups[1]

    for label, ids in (
        ("both", [first, second]),
        ("first only", [first]),
        ("second only", [second]),
        ("no group filter", None),
    ):
        result = party_statement(
            session,
            StatementFilter(tafsili_any_id=project.id, group_ids=ids, include_drafts=False),
        )
        assert not result.is_empty, f"«پروژه A» reported nothing for {label}"


def test_filtering_by_an_unrelated_group_excludes_the_project(db_session):
    """The filter must actually narrow, not just always pass."""
    session, project = _seeded(db_session)
    others = [
        g.id
        for g in session.execute(select(TafsiliGroup)).scalars()
        if g.id not in project.group_ids
    ]
    assert others, "seed needs a group the project is not in"

    result = party_statement(
        session,
        StatementFilter(tafsili_any_id=project.id, group_ids=[others[0]], include_drafts=False),
    )
    assert result.is_empty


def test_trial_balance_group_filter_changes_the_rows(db_session):
    session, project = _seeded(db_session)
    groups = sorted(project.group_ids)

    def names(ids):
        res = ledger_reports.trial_balance(
            session,
            StatementFilter(group_ids=ids, include_drafts=False),
            level=ledger_reports.LEVEL_TAFSILI,
        )
        return {r.name for r in res.rows if r.kind != "total"}

    unfiltered = names(None)
    single = names([groups[0]])
    assert single, "filtering by a real group must still return rows"
    assert single <= unfiltered
    assert single != unfiltered, "the group filter had no effect"


def test_trial_balance_carries_line_descriptions(db_session):
    """The employer asked for شرح in the trial balance; rows aggregate many
    lines, so the distinct descriptions are joined rather than invented."""
    session, _project = _seeded(db_session)
    result = ledger_reports.trial_balance(
        session,
        StatementFilter(include_drafts=False),
        level=ledger_reports.LEVEL_MOIN,
    )
    described = [r for r in result.rows if r.kind != "total" and r.description]
    assert described, "no trial-balance row carried a description"
    assert all(len(r.description) <= ledger_reports.DESCRIPTION_LIMIT for r in described)
