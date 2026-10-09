# Office network server (PostgreSQL)

This guide is for the local office. Internet or VPN access is not part of this phase.

## Install PostgreSQL 16 on the office server

1. Install PostgreSQL 16.
2. Run `deploy/postgres/init_db.sql` and change the password of the `persianledger` role.
3. Open port `5432` in the Windows firewall for the internal network only.
4. Merge the snippets in `pg_hba.conf.example` and `postgresql.conf.example` into the server configuration.
5. Schedule backups with `deploy/postgres/register_backup_task.ps1` (23:00 every night).
6. On each client: Connection settings, then the network server, then restart the application.
7. Move the current SQLite books with "Move the current database to PostgreSQL" or `scripts/migrate_sqlite_to_postgres.py`.

## Work from home

Record the document on the home machine's local file and take a backup. At the office, connect to the same server and use "Add home work". Company data is not wiped. Only new rows are inserted. If a document number already exists, the office sequence assigns the next number.
