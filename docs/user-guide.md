# PersianLedger user guide

Desktop multi-currency ledger. Each currency has its own columns and its own balance. There is no exchange rate.

## 1. Install

Two builds carry the same application.

| Build | When to use it |
| --- | --- |
| `PersianLedger-Setup-0.7.4.exe` | Normal install. Needs administrator rights once. |
| `PersianLedger-0.7.4-portable.zip` | No install. Extract and run `PersianLedger.exe`. |

Python, Qt, and the font are inside both builds.

| | Installed | Portable |
| --- | --- | --- |
| Database | `C:\ProgramData\PersianLedger\ledger.sqlite3` | `data\ledger.sqlite3` next to the exe |
| Backups | `…\PersianLedger\backups\` | `data\backups\` |
| Attachments | `…\PersianLedger\attachments\` | `data\attachments\` |
| Excel | `…\PersianLedger\exports\` | `data\exports\` |
| Log | `…\PersianLedger\logs\app.log` | `data\logs\app.log` |
| Settings | `%APPDATA%\PersianLedger\config.ini` | `data\config.ini` |

In an installed copy, Windows keeps `ProgramData` hidden by default. The basic
settings page shows the full backup path and can open that folder. The exit
backup prompt also opens the folder after creating a backup.

Portable mode is the `portable.txt` file next to the executable. The ZIP ships that file. Deleting it makes the folder behave like an installed copy.

Updating an install does not touch `C:\ProgramData\PersianLedger`. For a portable folder, extract the new ZIP elsewhere and run `packaging/update_portable.ps1 -InstallDir <current> -UpdateDir <new>`. The script replaces the executable and `_internal` and does not copy or delete `data`.

From source:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python run.py --demo
```

## 2. First setup

1. Currencies (`Ctrl+0`). Add each currency you will post. They are not converted into each other. Set decimal places before the first document in that currency. After that, the decimal count is locked.
2. Fiscal year (`Ctrl+0`). A year runs from the first day of Farvardin to the last day of Esfand. A document belongs to one year.
3. Detail groups and detail accounts (`Ctrl+9`).
4. Chart of accounts (`Ctrl+8`). Documents post to a subsidiary account, not to a ledger account.

A detail belongs to a group. A subsidiary account allows one or more groups on detail slot 1 and detail slot 2. The detail is not tied to a single subsidiary. That is what "floating" means. The primary group is itself a membership and is the basis of the suggested code.

Suggested roles: detail 1 is the party (person, cash, bank). Detail 2 is the allocation (project, cost center).

## 3. Documents (`Ctrl+1`)

A document has a header and lines. Each line can carry two detail labels. The document type is a label for filtering. It does not create lines and it does not change the arithmetic. The application sets the reversing and correcting types itself.

Lines must balance in each currency before anything is stored. Saving is one transaction: number, header, and lines. A failure rolls all of them back.

Drafts can be edited. A posted document is immutable for a non-admin. An admin can return it to draft or delete it, and the action stays in the audit log (`Ctrl+L`).

Attachments are stored with the database. The attachment list is loaded before the session closes, so saving a draft does not crash the panel.

## 4. Document list (`Ctrl+2`)

Filter and open documents from here. Correct a posted document by returning it to draft (admin) or by a reversing document, depending on the role. Do not expect a silent edit of a posted row.

## 5. Reports

All five reports share one shell: filters, grid, Excel, print.

| Screen | Shortcut | What it shows |
| --- | --- | --- |
| Account statement | `Ctrl+3` | One account, every currency, a running balance |
| Trial balance | `Ctrl+4` | 2, 4, or 6 columns |
| Journal | `Ctrl+5` | Every line in date order, with a total per document per currency |
| General ledger | `Ctrl+6` | Movement and balance of each account |
| Party statement | `Ctrl+7` | One detail across every account |

A group filter on the trial balance shows a slice. Debits and credits in that slice do not have to match. The unfiltered trial balance does.

The group filter is multi-select. No selection means no filter. Several groups means rows that belong to any of those groups.

"Balance before the range" defaults to off.

## 6. Project example

A project is a detail in the Projects group, usually in detail slot 2. Do not create a chart account per project.

| Event | Where it is posted |
| --- | --- |
| Cash received for a project | Cash or bank account, detail 1 = the cash account, detail 2 = the project |
| Amount still owed by the client | Receivables, detail 1 = the client, detail 2 = the project |
| Project cost | The expense account, detail 2 = the project |

The sample data includes a project that is a member of both Projects and Cost centers, one record and one code. Sample documents for that project are created on a fresh demo database.

## 7. Server mode

Several people can share one PostgreSQL database on the office network. See `deploy-server.md`. The PostgreSQL password is kept in the Windows keyring when that is available.

Home work is recorded on the local file, backed up, and imported at the office. Existing company rows are not deleted. A colliding document number takes the next office number.

## 8. Roles

Posted documents cannot be changed by a non-admin. The admin path leaves an audit row. Menu hiding is not the access check. The check is in the application services.

## 9. Not in this version

There is no exchange rate and no automatic conversion. A future version may add reports. It will not add a rate unless that is an explicit new decision.
