"""Build a Persian illustrated PDF for office-network use."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QMarginsF, QSizeF, Qt  # noqa: E402
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config as config_module  # noqa: E402
from app.ui.connection_dialog import ConnectionDialog  # noqa: E402
from app.version import APP_NAME_FA, APP_VERSION  # noqa: E402

OUT = ROOT / "docs" / "persianledger-network-guide-fa.pdf"
SHOT = ROOT / "docs" / "_network_guide_shot.png"


def _shot() -> None:
    cfg = config_module.AppConfig()
    dlg = ConnectionDialog(cfg, persist=False)
    dlg.radio_pg.setChecked(True)
    dlg.pg_host.setText("192.168.1.10")
    dlg.pg_database.setText("persianledger")
    dlg.pg_user.setText("persianledger")
    dlg.resize(520, 480)
    dlg.show()
    QApplication.instance().processEvents()
    dlg.grab().save(str(SHOT))
    dlg.hide()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    _shot()
    uri = SHOT.resolve().as_posix()
    html = f"""
<html dir="rtl" lang="fa">
<head>
<meta charset="utf-8"/>
<style>
body {{ font-family: Tahoma, "Segoe UI", sans-serif; font-size: 11pt; color: #1a1a1a; }}
h1 {{ font-size: 16pt; }}
h2 {{ font-size: 13pt; margin-top: 18px; }}
ol, ul {{ line-height: 1.7; }}
.note {{ background: #f4f1ea; padding: 10px 14px; }}
img {{ max-width: 100%; }}
</style>
</head>
<body>
<h1>راهنمای استفاده تحت شبکه — {APP_NAME_FA} {APP_VERSION}</h1>
<p>تحت شبکه یعنی چند کاربر هم‌زمان به یک سرور دیتابیس داخل دفتر وصل می‌شوند.
گذاشتن فایل دفتر یا پشتیبان روی پوشهٔ اشتراکی جایگزین این کار نیست.</p>
<p class="note">این راهنما برای شبکهٔ داخلی دفتر است. اینترنت و VPN در این نسخه نیست.</p>

<h2>۱. روی یک رایانهٔ دفتر (سرور)</h2>
<ol>
<li>PostgreSQL نسخه ۱۶ را نصب کنید.</li>
<li>فایل <code>deploy/postgres/init_db.sql</code> را اجرا کنید و رمز نقش persianledger را عوض کنید.</li>
<li>در فایروال ویندوز فقط برای شبکهٔ داخلی، پورت 5432 را باز کنید.</li>
<li>نمونه‌های <code>pg_hba.conf.example</code> و <code>postgresql.conf.example</code> را با تنظیمات سرور ادغام کنید.</li>
<li>اختیاری: پشتیبان شبانه با <code>deploy/postgres/register_backup_task.ps1</code>.</li>
</ol>

<h2>۲. روی هر رایانهٔ کاربر</h2>
<ol>
<li>پوشهٔ پرتابل برنامه را استخراج کنید و PersianLedger.exe را اجرا کنید.</li>
<li>از صفحهٔ ورود یا تنظیمات، «تنظیمات اتصال» را باز کنید.</li>
<li>گزینهٔ «سرور شبکه (PostgreSQL)» را انتخاب کنید.</li>
<li>نشانی سرور دفتر، نام دیتابیس، نام کاربری و رمز را وارد کنید.</li>
<li>«آزمایش اتصال» را بزنید؛ اگر موفق بود ذخیره کنید و برنامه را دوباره اجرا کنید.</li>
</ol>
<p>نمونهٔ همین پنجره:</p>
<p><img src="file:///{uri}" width="480"/></p>

<h2>۳. انتقال دفتر فعلی از فایل محلی</h2>
<p>اگر تا امروز با فایل محلی کار می‌کردید، یک‌بار از داخل برنامه «انتقال دیتابیس فعلی به PostgreSQL»
را بزنید یا اسکریپت <code>scripts/migrate_sqlite_to_postgres.py</code> را اجرا کنید.
بعد از انتقال همه روی همان سرور کار می‌کنند.</p>

<h2>۴. پشتیبان</h2>
<p>در حالت شبکه، پشتیبان با pg_dump روی خود سرور ساخته می‌شود.
کپی آن فایل روی پوشهٔ اشتراکی فقط بایگانی است، نه محل کار روزمره.</p>

<h2>۵. بازیابی پشتیبان فایل محلی</h2>
<p>اگر هنوز فایل محلی است: برنامه را ببندید، از تنظیمات «بازیابی از فایل» را بزنید،
فایل sqlite3 خودتان را انتخاب کنید. بعد از پیام موفقیت، فهرست اسناد و گزارش سود و زیان
باید فقط سندهای همان فایل را نشان بدهد. نوار پایین پنجره مسیر دیتابیس فعال را نشان می‌دهد.</p>
</body>
</html>
"""
    doc = QTextDocument()
    doc.setHtml(html)
    writer = QPdfWriter(str(OUT))
    writer.setTitle(f"{APP_NAME_FA} — راهنمای شبکه")
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter)
    doc.setPageSize(QSizeF(writer.width(), writer.height()))
    doc.print_(writer)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
