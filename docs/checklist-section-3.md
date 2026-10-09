# Section 3 checklist before delivery

Target version: **0.6.0**. An upgrade test against the client's real database belongs next to the final delivery, not in this pass.

## A. Eleven functional items (portable 0.6.0 build)

Automated coverage is `pytest` and `scripts/smoke_section3.py` (offscreen) on this source and on the built executable. Items that need a hand on the desktop are marked.

- [x] 1. The document ComboBox uses `SelectedClicked | CurrentChanged | EditKeyPressed` (code plus smoke). One-click feel on a desktop: manual.
- [x] 2. Atomic document save. `tests/test_project_scenario.py`.
- [x] 3. Descriptions on reports. Journal, statement, and ledger models.
- [x] 4. Description column capped at 300 px in `fit_columns`.
- [x] 5. Suggested detail code from the group. `master_data.suggest_tafsili_code`.
- [x] 6. Membership in several groups. `tafsili_group_members` plus the report filter.
- [x] 7. Four-level browse with a breadcrumb. Smoke on `BrowseView`.
- [x] 8. Project A scenario with no exchange rate. pytest.
- [x] 9. Backup question on exit. `tests/test_close_and_restore.py`.
- [x] 10. Backup restore, a new connection, an uncached tree, window clamp. `tests/test_close_and_restore.py`.
- [x] 11. Balance-before-range switch. Smoke on `include_opening`.

## B. Build and version

- [x] `pyinstaller packaging/persianledger.spec` produced `dist/PersianLedger/PersianLedger.exe`.
- [x] `portable.txt` is copied next to the executable (in the spec, after COLLECT).
- [x] The window title shows 0.6.0.
- [x] `CHANGELOG.md` is current.

## C. The client's real database (near final delivery)

- [ ] Take a copy of the client's `ledger.sqlite3`.
- [ ] Upgrade from the existing revision to head without deleting old migrations.
- [ ] Document and line counts must not drop after the upgrade.

## D. Currency

- [x] There is no exchange rate.
