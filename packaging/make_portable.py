"""Write the portable build's marker and Persian read-me.

Kept in Python because Windows PowerShell 5.1 reads a BOM-less .ps1 as ANSI and
would double-encode any Persian text embedded in the build script.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.version import APP_VERSION  # noqa: E402

MARKER = """This file switches the application into portable mode.
While it is present, the database, backups, attachments and logs stay in the
'data' folder next to PersianLedger.exe instead of C:\\ProgramData.
Delete it only if you want the installed-application behaviour.
"""

README = """نرم‌افزار دفتر مالی چندارزی — نسخه {version}

═══════════════════════════════════════════════════════════
  روش اجرا
═══════════════════════════════════════════════════════════

  ۱. کل پوشه را از داخل فایل زیپ در یک مسیر دلخواه استخراج کنید
     (مثلاً روی Desktop یا در D:\\).

  ۲. روی فایل  PersianLedger.exe  دابل‌کلیک کنید.

  نکته مهم: برنامه را از داخل خود فایل زیپ اجرا نکنید؛ اول آن را استخراج کنید.

  نیازی به نصب پایتون یا هیچ برنامه دیگری نیست.
  برنامه کاملاً آفلاین کار می‌کند و به اینترنت وصل نمی‌شود.

  اگر ویندوز پیام «Windows protected your PC» نشان داد، روی
  «More info» و سپس «Run anyway» بزنید. این پیام به این دلیل است که
  فایل اجرایی امضای دیجیتال تجاری ندارد، نه به دلیل وجود مشکل.


═══════════════════════════════════════════════════════════
  محل نگهداری اطلاعات
═══════════════════════════════════════════════════════════

  همه اطلاعات شما در پوشه  data  کنار همین فایل ذخیره می‌شود:

    data\\ledger.sqlite3         فایل دیتابیس
    data\\backups\\               نسخه‌های پشتیبان
    data\\attachments-cache\\     کش موقت باز کردن پیوست‌ها
    data\\exports\\               خروجی‌های اکسل
    data\\logs\\app.log           فایل ثبت خطاها

  در حالت فایل محلی، پشتیبان‌گیری از داخل برنامه یا کپی فایل ledger.sqlite3
  (وقتی برنامه بسته است) کافی است. پیوست‌ها داخل همین فایل هستند.


═══════════════════════════════════════════════════════════
  اتصال به سرور شبکه
═══════════════════════════════════════════════════════════

  از داخل برنامه «تنظیمات اتصال» را باز کنید، نشانی PostgreSQL را بدهید
  و برنامه را دوباره اجرا کنید. جزئیات در docs\\deploy-server-fa.md است.


═══════════════════════════════════════════════════════════
  به‌روزرسانی به نسخه جدید
═══════════════════════════════════════════════════════════

  ۱. نسخه جدید را در یک پوشه دیگر استخراج کنید.
  ۲. پوشه  data  را از نسخه قدیمی به کنار فایل اجرایی نسخه جدید کپی کنید.
  ۳. برنامه را اجرا کنید.

  برنامه پیش از هر تغییری در ساختار دیتابیس، یک نسخه پشتیبان می‌سازد و
  سپس ساختار را به‌روز می‌کند. هیچ داده‌ای از بین نمی‌رود.


═══════════════════════════════════════════════════════════
  راهنمای کامل
═══════════════════════════════════════════════════════════

  پوشه  docs  →  فایل  user-guide-fa.md

  این فایل راهنمای کامل کار با سیستم است: تعریف سرفصل و تفصیلی،
  ثبت سند چندارزی، سند برگشتی و اصلاحی، و هر پنج گزارش.
"""


def main() -> int:
    target = Path(sys.argv[1])
    (target / "portable.txt").write_text(MARKER, encoding="utf-8")
    (target / "راهنما.txt").write_text(
        README.format(version=APP_VERSION).replace("\n", "\r\n"),
        encoding="utf-8-sig",
    )
    print(f"wrote portable.txt and the Persian read-me into {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
