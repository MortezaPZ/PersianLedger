"""Write the portable build's marker and read-me files.

Kept in Python because Windows PowerShell 5.1 reads a BOM-less .ps1 as ANSI.
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

README = """PersianLedger {version}
Multi-currency ledger

How to start

1. Extract the whole folder from the zip (Desktop or D:\\, for example).
2. Double-click PersianLedger.exe.

Do not run the program from inside the zip. Extract it first.
Python is not required. The program works offline.

If Windows shows "Windows protected your PC", choose More info,
then Run anyway. The executable has no commercial code-signing certificate.


Where the data is

Everything is in the data folder next to this file:

  data\\ledger.sqlite3         database
  data\\backups\\              backups
  data\\attachments-cache\\    temporary cache for opening attachments
  data\\exports\\              Excel exports
  data\\logs\\app.log          error log

For a local file, use the in-app backup or copy ledger.sqlite3 while the
program is closed. Attachments are stored inside that file.


Network server

Open connection settings, enter the PostgreSQL address, and start the
program again. Details are in docs\\deploy-server.md.


Updating

1. Run the setup file and close the program first.
2. The install reads data from the previous folder and does not delete it.
3. Start the program.

Before a database structure change the program writes a backup, then
updates the structure. Nothing is lost.

This version:
1. Setup reads data from the previous folder.
2. Restore an older backup from basic settings.
3. The tafsili link attaches the tafsili itself and does not show it in the chart.
4. Choosing a tafsili does not change or lock the ledger account.
5. Home-office import is only for the admin, and only on the server.
Details are in docs\\user-guide.md.


Full guide

docs\\user-guide.md covers the chart, floating details, multi-currency
documents, reversing and correcting entries, and the five reports.
The illustrated network notes, if shipped beside the program, open in a browser.
"""

PERSIAN_README = """دفتر مالی چندارزی — نسخه {version}

شروع کار
۱. همه پوشه را از فایل ZIP استخراج کنید.
۲. روی PersianLedger.exe دوبار کلیک کنید.

برنامه را از داخل فایل ZIP اجرا نکنید. نیازی به نصب پایتون نیست و برنامه آفلاین است.

محل اطلاعات
پایگاه داده، پشتیبان‌ها، پیوست‌ها، خروجی‌ها و گزارش خطا در پوشه data کنار برنامه
ذخیره می‌شوند. نسخه‌های پشتیبان در data\\backups قرار دارند.

در صفحه «تنظیمات پایه» مسیر کامل پشتیبان نمایش داده می‌شود. دکمه «باز کردن پوشه
پشتیبان‌ها» آن را باز می‌کند. هنگام ساخت پشتیبان از کادر خروج هم پوشه باز می‌شود.

راهنمای کامل فارسی در docs\\user-guide-fa.md قرار دارد.

نکته‌های این نسخه
۱. انتخاب تفصیلی، معین را عوض یا قفل نمی‌کند؛ فهرست معین با تفصیلی انتخاب‌شده
   سازگار می‌شود.
۲. تفصیلی ۱ و تفصیلی ۲ دو خانه مستقل هستند و سلسله‌مراتب ندارند.
۳. درخت حساب‌ها شامل گروه حساب، کل و معین است؛ تفصیلی‌ها در آن شاخه نیستند.
۴. پیش از حذف سرفصل یا تفصیلی، برنامه استفاده‌نشدن آن را بررسی می‌کند.
۵. سند بدهکار/بستانکار پس از بستن و بازکردن دوباره برنامه حفظ می‌شود.
"""


def main() -> int:
    target = Path(sys.argv[1])
    (target / "portable.txt").write_text(MARKER, encoding="utf-8")
    (target / "GUIDE.txt").write_text(
        README.format(version=APP_VERSION).replace("\n", "\r\n"),
        encoding="utf-8-sig",
    )
    (target / "راهنما.txt").write_text(
        PERSIAN_README.format(version=APP_VERSION).replace("\n", "\r\n"),
        encoding="utf-8-sig",
    )
    print(f"wrote portable.txt, GUIDE.txt and راهنما.txt into {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
