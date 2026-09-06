# استقرار سرور شبکه (PostgreSQL)

این راهنما برای دفتر محلی است. دسترسی از اینترنت یا VPN در این فاز نیست.

## نصب PostgreSQL ۱۶ روی سرور دفتر

۱. PostgreSQL 16 را نصب کنید.
۲. اسکریپت `deploy/postgres/init_db.sql` را اجرا کنید و رمز نقش `persianledger` را عوض کنید.
۳. در فایروال ویندوز فقط برای شبکه داخلی پورت `5432` را باز کنید.
۴. قطعه‌های `pg_hba.conf.example` و `postgresql.conf.example` را در تنظیمات سرور ادغام کنید.
۵. پشتیبان زمان‌بندی‌شده: `deploy/postgres/register_backup_task.ps1` (هر شب ۲۳:۰۰).
۶. روی هر کلاینت: «تنظیمات اتصال» → سرور شبکه، سپس برنامه را دوباره اجرا کنید.
۷. دفتر فعلی SQLite را با «انتقال دیتابیس فعلی به PostgreSQL» یا اسکریپت `scripts/migrate_sqlite_to_postgres.py` منتقل کنید.
