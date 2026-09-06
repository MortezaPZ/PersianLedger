# PersianLedger

دفتر مالی چندارزی رومیزی (PySide6 + SQLite). سند دوطرفه، تاریخ شمسی، چند ارز **بدون نرخ تسعیر**.

## اجرا از سورس

پایتون ۳٫۱۱:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python run.py --demo
```

بدون `--demo` فقط سرفصل پایه و سال مالی جاری ساخته می‌شود. داده در `.localdata\ledger.sqlite3` است.

### مهاجرت دیتابیس

برنامه هنگام شروع `alembic upgrade head` را خودش اجرا می‌کند. دستی:

```powershell
.\.venv\Scripts\alembic upgrade head
```

`alembic.ini` پیش‌فرض به `.localdata\ledger.sqlite3` اشاره دارد.

## ساخت نسخهٔ portable

```powershell
.\.venv\Scripts\pyinstaller packaging\persianledger.spec --noconfirm
```

خروجی در `dist\PersianLedger\` است. فایل `portable.txt` کنار exe داده را در پوشهٔ `data\` نگه می‌دارد.

## تست

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

اسناد قطعی برای غیرمدیر تغییرناپذیرند؛ مدیر می‌تواند با ردپای کامل در سوابق، سند را به پیش‌نویس برگرداند یا حذف کند.

