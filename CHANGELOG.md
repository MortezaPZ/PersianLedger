# PersianLedger changelog

## 0.8.1

- Updated the floating-detail screen to match the requested workflow: browse detail groups and parent-child details in a tree, then review the selected branch in a separate information table.
- Selecting a group, parent, or detail shows its applicable details and descendants while preserving group memberships and linked subsidiary accounts.

## 0.8.2

- Refined the floating-detail hierarchy with visible tree connectors, distinct icons, contextual actions, and branch/sub-branch wording.
- Prevented the same floating detail from being selected in both detail fields on one voucher line, with matching service validation.

## 0.8.0

- Added hierarchical floating-detail accounts with cycle validation across concurrent database sessions.
- Matrix drill-down uses the filters from the rendered report, including detail, date, and currency selections.
- SQLite startup migrations begin a real transaction before DDL and safely recover recognized interrupted mutex migrations.
- The Windows installer keeps the existing ledger data and applies schema upgrades to that database.

## 0.7.5

- Database upgrades take a consistent SQLite snapshot, disable foreign keys during table rebuilds, and recover cleanly from an interrupted migration.
- Restoring a backup validates and upgrades a staged copy before replacing the live database, so a failed restore leaves the current data in place.
- Backups use SQLite's online backup API, are stored by default in a visible Documents folder for installed builds, and the most recently used backup location is remembered.
- The update ZIP replaces application files in place without an installer or changing the existing database/configuration location.

## 0.7.4

- New currency and fiscal-year buttons use dark text on a light blue background for clearer labels.
- Selecting a detail keeps the account list focused on allowed subsidiaries; the two detail fields are documented as independent dimensions.
- Account and floating-detail deletion are available with safeguards for records referenced by documents.
- Backup messages show the resolved file path, open its folder, and settings display the backup location.
- Reopening a saved draft after restarting the application is covered for both debit and credit lines.

## 0.7.3

- Document reopen keeps both debit and credit lines.
- Moein list filtered by linked floating detail; picker no longer clears a detail on cancel.
- Same moein code allowed under different kol accounts; posting uses the combined code.
- Settings label clarified to «افزودن کار خانه»; backup path on Windows fixed.
- Installer and app still reuse the existing data folder (no fresh empty database on upgrade).

## 0.7.2

- A floating detail links to a subsidiary account only from the floating-detail screen. The chart tree stops at the subsidiary.
- On a document and in reports, picking a detail narrows the subsidiary list, and the reverse is true.
- Detail groups are created from that same screen.

## 0.7.1

- A beginner guide for the network connection, with screenshots of the real Windows and application windows.
- A script that prepares the office server: firewall port and the network address to show.
- The default chart tree goes down to the subsidiary, and the detail-group name is visible in the tree.
- Account browse: the balance-before-range switch defaults to off.
- A fresh install has no sample documents. Restoring a backup replaces the reports' data.

## 0.7.0

- Backup restore fixed.
- Return or delete a posted document, and clear experimental documents.
- PostgreSQL and a multi-user network connection.
- User roles.
- Attachments stored in the database.
- Server-side backup.
- Data migration.
- Concurrency control.

## 0.6.0

The source was rebuilt from the 0.5.0 portable build, reported bugs were fixed, and the interface was redesigned.

### Fixes

- Combo boxes and lists open on one click.
- Saving a document is atomic: number, header, and lines are one transaction, and an error rolls the whole thing back.
- Document and line descriptions show on the journal, the account card, and the related reports.
- The description column sizes to the text, capped at 300 pixels.
- A suggested detail code is built from the primary group.
- A detail that belongs to several groups can be filtered by group on reports.
- Four-level account browse with a breadcrumb.
- A backup prompt on exit: yes, no, or cancel.
- Restoring a backup closes the database connection and reloads the tree. The window is clamped to the current monitor.
- Reports can include or exclude the balance from before the selected range.

### Interface

- One palette, light and dark themes, Vazirmatn, sidebar icons drawn in code.

There is still no exchange rate. Each currency has its own columns and its own balance.
