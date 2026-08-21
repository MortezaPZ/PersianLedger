# بخش ۳ — چک‌لیست قبل از تحویل

نسخهٔ هدف: **۰٫۶٫۰**. تست upgrade با دیتابیس واقعی کارفرما نزدیک تحویل نهایی است، نه الان.

## الف) یازده مورد کارکردی (روی build پرتابل ۰٫۶٫۰)

تست خودکار با `pytest` و `scripts/smoke_section3.py` (offscreen) روی همین سورس و exe ساخته‌شده. موارد تعاملی با علامت دستی مشخص شده‌اند.

- [x] ۱. ComboBox در ثبت سند `SelectedClicked | CurrentChanged | EditKeyPressed` دارد (کد + smoke). تأیید حس یک‌کلیکی روی دسکتاپ: دستی.
- [x] ۲. ذخیرهٔ سند اتمی — `tests/test_project_scenario.py`.
- [x] ۳. شرح در گزارش‌ها — مدل‌های journal/statement/ledger.
- [x] ۴. سقف عرض ستون شرح ۳۰۰px در `fit_columns`.
- [x] ۵. کد پیشنهادی تفصیلی از گروه — `master_data.suggest_tafsili_code`.
- [x] ۶. عضویت چندگروه — مدل `tafsili_group_members` + فیلتر گزارش.
- [x] ۷. مرور چهارسطحی با breadcrumb — smoke روی `BrowseView`.
- [x] ۸. سناریوی پروژه A بدون تسعیر — pytest.
- [x] ۹. سؤال پشتیبان هنگام خروج — `tests/test_close_and_restore.py`.
- [x] ۱۰. بازیابی بکاپ، اتصال جدید، درخت بدون کش، clamp پنجره — `tests/test_close_and_restore.py`.
- [x] ۱۱. سوییچ ماندهٔ قبل از بازه — smoke روی `include_opening`.

## ب) Build و نسخه

- [x] `pyinstaller packaging/persianledger.spec` خروجی `dist/PersianLedger/PersianLedger.exe` ساخت (۲۱ مرداد ۱۴۰۵).
- [x] `portable.txt` کنار exe کپی می‌شود (در spec بعد از COLLECT).
- [x] شمارهٔ نسخه در عنوان پنجره ۰٫۶٫۰ است.
- [x] `CHANGELOG.md` به‌روز است.

## ج) دیتابیس واقعی کارفرما (نزدیک تحویل نهایی)

- [ ] کپی `ledger.sqlite3` از کارفرما گرفته شود.
- [ ] upgrade از revision موجود تا head بدون حذف migrationهای قدیمی.
- [ ] تعداد اسناد/ردیف‌ها پس از upgrade کم نشود.

## د) ارز

- [x] نرخ تسعیر وجود ندارد.
