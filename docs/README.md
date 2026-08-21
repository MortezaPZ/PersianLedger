# PersianLedger — Multi-Currency Desktop Accounting

Offline double-entry accounting for Windows. Persian RTL interface, Jalali dates,
several currencies side by side, and **no exchange rate anywhere in the system**.

- Architecture and data model: [docs/architecture.md](docs/architecture.md)
- User guide (Persian): [docs/user-guide-fa.md](docs/user-guide-fa.md)

---

## For the end user

The build produces two artifacts. Both contain the same application; pick whichever
suits the machine.

| Artifact | Use it when |
|---|---|
| `PersianLedger-Setup-0.3.0.exe` (40 MB) | normal install: Program Files, desktop icon, Add/Remove Programs entry. Needs administrator rights once. |
| `PersianLedger-0.3.0-portable.zip` (54 MB) | no install and no admin rights: extract anywhere and double-click `PersianLedger.exe`. |

Nothing else is required — Python, Qt and the Persian font are inside both.

**Where the data lives**

| What | Installed | Portable |
|---|---|---|
| Database | `C:\ProgramData\PersianLedger\ledger.sqlite3` | `data\ledger.sqlite3` beside the exe |
| Automatic backups | `…\PersianLedger\backups\` | `data\backups\` |
| Attachments | `…\PersianLedger\attachments\` | `data\attachments\` |
| Excel exports | `…\PersianLedger\exports\` | `data\exports\` |
| Error log | `…\PersianLedger\logs\app.log` | `data\logs\app.log` |
| Settings | `%APPDATA%\PersianLedger\config.ini` | `data\config.ini` |

Portable mode is switched on by the `portable.txt` file next to the executable, which
only the ZIP build ships. Delete that file and the folder behaves like an installed copy.

**Updating.** Install the new version over the old one — or, for the portable build,
extract the new ZIP and copy the old `data` folder next to the new executable. The
installer never touches `C:\ProgramData\PersianLedger`; this was verified by installing,
posting a document, reinstalling over the top and uninstalling — the ledger survived all
three. On the first launch after an update the app compares
the schema revision, copies the database into `backups\` and applies the pending
migrations. If a migration fails the backup is restored automatically and the error is
shown. If the database is *newer* than the program, the app refuses to open it rather
than risk corrupting it.

**Backups.** Copy `ledger.sqlite3` while the program is closed. That single file is the
whole ledger.

---

## For the developer

### Requirements

- Windows 10 or newer, 64-bit
- Python 3.11 (PySide6 and PyInstaller are tested against it; 3.14 is ahead of their matrix)
- Inno Setup 6 — only needed to produce the installer: <https://jrsoftware.org/isdl.php>

### Setup

```bash
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### Run

```bash
.venv\Scripts\python.exe run.py
```

Add `--demo` on a *fresh* database to load the sample dataset (5 currencies, 22 accounts
— 5 kol and 17 moin — 11 tafsili records, and 7 posted documents / 19 lines including the
combined 50,000 EUR entry from the brief):

```bash
.venv\Scripts\python.exe run.py --demo
```

In development the database is `.localdata\ledger.sqlite3` under the project folder,
so it never collides with an installed copy.

### Tests

```bash
.venv\Scripts\python.exe -m pytest -q
```

Covers exact-decimal arithmetic, Jalali conversion, per-currency balancing, gapless
numbering, immutability of posted documents, reversal and correction, every report
(including that the trial balance balances within each currency at 2, 4 and 6 columns,
and that a ledger section matches the standalone kardex), and the upgrade path — a
synthetic future migration is applied to a seeded database and every document is
compared before and after.

### Build

```bash
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

Runs the tests, regenerates the icon, produces `dist\PersianLedger\` with PyInstaller
(one-dir, ~125 MB), packs the portable `dist\PersianLedger-<version>-portable.zip`, then
wraps the payload into `dist\PersianLedger-Setup-<version>.exe` with Inno Setup.
`-SkipTests` and `-SkipInstaller` are available. If Inno Setup is missing the script
still delivers the executable and the ZIP, and says so.

The Persian read-me inside the ZIP is written by `packaging/make_portable.py` rather than
by the build script, because Windows PowerShell 5.1 reads a BOM-less `.ps1` as ANSI and
double-encodes any Persian text embedded in it.

### Migrations

```bash
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "what changed"
.venv\Scripts\python.exe -m alembic upgrade head
```

Always review the generated file. SQLite needs `batch_alter_table` for anything beyond
adding a column; `render_as_batch` is already enabled in `env.py`.

---

## Layout

```
app/
  domain/        Money (Decimal only), Jalali dates, enums, errors
  db/            models, engine, Alembic migrations, seed data
  repositories/  gapless number sequences
  services/      document, account, master data, report use-cases
  export/        Excel (openpyxl) and print preview (QTextDocument)
  ui/            PySide6 views, widgets, theme
packaging/       PyInstaller spec, Inno Setup script, build script, icon
tests/           pytest suite
docs/            architecture, user guide
```

---

## Design rules the code enforces

1. **No exchange rate.** No rate column exists in the schema. Every aggregate is
   `GROUP BY currency_id`; a document must balance *within each currency*, never on a
   cross-currency total.
2. **Decimal only.** Amounts are stored as `BIGINT` counts of 1/10,000 of a unit and
   surface as `Decimal` through a SQLAlchemy `TypeDecorator`. `float` never touches an
   amount, including in the Excel exporter.
3. **Posted documents are immutable.** No update, no delete. Correction happens through
   a linked reversing (`REVERSAL`) or correcting (`CORRECTION`) document. Drafts are
   editable and discardable, and every action is written to `audit_log`.
4. **Accounts with history cannot be deleted or renumbered** — only deactivated.
5. **Numbering is gapless.** Numbers are taken from a locked `number_sequences` row at
   posting time, never `MAX(number)+1`, and never assigned to a draft.
6. **PostgreSQL-ready.** No SQLite-specific SQL, one short transaction per use-case,
   `row_version` optimistic locking on every mutable row. Switching backends is a change
   to `config.ini`.

---

## Reports

All five share one shell: filter panel → grid → Excel export → print preview.

| Report | Shape |
|---|---|
| Account statement (کاردکس) | one row per line, a debit/credit/balance column group per currency, running balance |
| Trial balance (تراز آزمایشی) | 2, 4 or 6 columns at kol / moin / tafsili level; one row per (account, currency) with a subtotal per currency |
| Journal (دفتر روزنامه) | every line in date order, a total row per document per currency, plus a period total |
| General ledger (دفتر کل و معین) | the kardex repeated for each account with activity; Excel writes one sheet per account |
| Party statement (صورت وضعیت اشخاص) | every movement of one tafsili across all accounts, with the account column shown |

## Known limits in this build

- Users and permissions are phase 2. Documents already carry `created_by` / `posted_by`,
  and the audit log viewer is live, but there is no login yet so those columns stay empty.
- The installer wizard itself is in English; Inno Setup 6 ships no Persian language file.
  Dropping a `Persian.isl` into the Inno Setup `Languages` folder switches it over — the
  script already picks it up when present. Shortcuts and the application are Persian
  either way.
- The executables are not code-signed, so Windows SmartScreen shows a "protected your PC"
  prompt on first run. Buying a signing certificate is the only real fix; the Persian
  read-me tells the user to click "More info" → "Run anyway".
- `config.ini` holds the PostgreSQL password in plain text. Before phase 2 goes live this
  should move to the Windows Credential Manager.
