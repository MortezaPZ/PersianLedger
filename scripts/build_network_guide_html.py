"""Capture real UI shots and write an offline Persian HTML network guide."""
from __future__ import annotations

import base64
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1.25")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import bootstrap, config as config_module  # noqa: E402
from app.ui.connection_dialog import ConnectionDialog  # noqa: E402
from app.ui.context import AppContext  # noqa: E402
from app.ui.login_dialog import LoginDialog  # noqa: E402
from app.ui.main_window import PAGES, MainWindow  # noqa: E402
from app.ui import theme  # noqa: E402
from app.version import APP_NAME_FA, APP_VERSION  # noqa: E402

OUT_DIR = ROOT / "docs" / "network-guide-fa"
IMG = OUT_DIR / "images"
PORTABLE = ROOT / "dist" / "PersianLedger"


def _grab(widget, name: str, width: int, height: int) -> str:
    widget.setMinimumSize(width, height)
    widget.resize(width, height)
    widget.show()
    QApplication.instance().processEvents()
    path = IMG / name
    ok = widget.grab().save(str(path), "PNG")
    if not ok or path.stat().st_size < 8_000:
        raise SystemExit(f"screenshot too small or failed: {path} ok={ok} bytes={path.stat().st_size if path.exists() else 0}")
    widget.hide()
    return _data_uri(path)


def _data_uri(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _write_html(shots: dict[str, str]) -> None:
    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>راهنمای استفاده تحت شبکه — {APP_NAME_FA}</title>
  <style>
    body {{
      margin: 0;
      background: #f3efe6;
      color: #1c1914;
      font-family: Tahoma, "Segoe UI", Arial, sans-serif;
      font-size: 17px;
      line-height: 1.9;
    }}
    main {{
      max-width: 880px;
      margin: 0 auto;
      padding: 28px 22px 64px;
    }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    h2 {{
      font-size: 20px;
      margin: 36px 0 10px;
      padding-bottom: 6px;
      border-bottom: 2px solid #c9b48a;
    }}
    .meta {{ color: #5c564c; margin-bottom: 24px; }}
    .box {{
      background: #fff8ea;
      border: 1px solid #e0d0a8;
      border-radius: 10px;
      padding: 14px 16px;
      margin: 16px 0;
    }}
    .warn {{
      background: #fff1f0;
      border: 1px solid #e8b4b0;
    }}
    ol {{ padding-right: 22px; }}
    li {{ margin: 8px 0; }}
    figure {{
      margin: 18px 0 28px;
      background: #fff;
      border: 1px solid #ddd6c8;
      border-radius: 10px;
      padding: 10px;
    }}
    figure img {{
      display: block;
      width: 100%;
      height: auto;
      border-radius: 6px;
    }}
    figcaption {{
      margin-top: 8px;
      color: #4a453c;
      font-size: 15px;
    }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      background: #ece7dc;
      padding: 1px 6px;
      border-radius: 4px;
      direction: ltr;
      unicode-bidi: isolate;
    }}
  </style>
</head>
<body>
<main>
  <h1>راهنمای استفاده تحت شبکه</h1>
  <p class="meta">{APP_NAME_FA} نسخه {APP_VERSION}</p>

  <div class="box">
    <strong>معنی تحت شبکه:</strong>
    چند کاربر از رایانه‌های داخل دفتر هم‌زمان به یک سرور دیتابیس وصل می‌شوند.
    کار روزمره روی فایل داخل پوشهٔ اشتراکی انجام نمی‌شود.
  </div>
  <div class="box warn">
    این راهنما فقط برای شبکهٔ داخلی دفتر است. اتصال از اینترنت یا VPN در این نسخه نیست.
  </div>

  <h2>۱. یک رایانه را سرور کنید</h2>
  <ol>
    <li>روی همان رایانه <code>PostgreSQL 16</code> را نصب کنید.</li>
    <li>فایل <code>deploy/postgres/init_db.sql</code> را اجرا کنید و رمز نقش <code>persianledger</code> را عوض کنید.</li>
    <li>در فایروال ویندوز فقط برای شبکهٔ داخلی، پورت <code>5432</code> را باز کنید.</li>
    <li>نمونه‌های <code>pg_hba.conf.example</code> و <code>postgresql.conf.example</code> را با تنظیمات پستگرس ادغام کنید.</li>
    <li>اختیاری: پشتیبان شبانه با <code>deploy/postgres/register_backup_task.ps1</code>.</li>
  </ol>

  <h2>۲. از برنامه، تنظیمات اتصال را باز کنید</h2>
  <p>روی هر رایانهٔ کاربر، پوشهٔ پرتابل را استخراج کنید و <code>PersianLedger.exe</code> را اجرا کنید. برنامه را از داخل خود فایل زیپ باز نکنید.</p>
  <p>در پنجرهٔ ورود (یا ساخت حساب مدیر در اجرای اول) دکمهٔ «تنظیمات اتصال» پایین فرم است.</p>
  <figure>
    <img src="{shots['login']}" alt="پنجره ورود و دکمه تنظیمات اتصال"/>
    <figcaption>شکل ۱. پنجرهٔ ورود — دکمهٔ «تنظیمات اتصال» پایین سمت راست.</figcaption>
  </figure>
  <p>بعد از ورود هم از صفحهٔ «ارزها و سال مالی» می‌توانید اتصال را ببینید و عوض کنید.</p>
  <figure>
    <img src="{shots['settings']}" alt="صفحه تنظیمات و جعبه اتصال به دیتابیس"/>
    <figcaption>شکل ۲. صفحهٔ تنظیمات — جعبهٔ «اتصال به دیتابیس» و دکمهٔ «تغییر تنظیمات اتصال».</figcaption>
  </figure>

  <h2>۳. سرور شبکه را انتخاب کنید</h2>
  <ol>
    <li>گزینهٔ «سرور شبکه (PostgreSQL)» را بزنید.</li>
    <li>نشانی سرور دفتر را بنویسید (مثال: <code>192.168.1.10</code>).</li>
    <li>پورت معمولاً <code>5432</code> است.</li>
    <li>نام دیتابیس، نام کاربری و رمز همان مقادیری است که روی سرور ساختید.</li>
    <li>«آزمایش اتصال» را بزنید. اگر پیام موفقیت آمد، ذخیره کنید و برنامه را ببندید و دوباره باز کنید.</li>
  </ol>
  <figure>
    <img src="{shots['connection']}" alt="پنجره تنظیمات اتصال PostgreSQL"/>
    <figcaption>شکل ۳. پنجرهٔ تنظیمات اتصال — حالت سرور شبکه با فیلدهای نشانی، پورت، دیتابیس و کاربر.</figcaption>
  </figure>

  <h2>۴. دفتر فعلی را به سرور منتقل کنید</h2>
  <p>اگر تا امروز با فایل محلی کار می‌کردید، یک‌بار از همین صفحهٔ تنظیمات «انتقال دیتابیس فعلی به PostgreSQL» را بزنید (برای مدیر، در حالت فایل محلی دیده می‌شود). بعد از انتقال همه روی همان سرور کار می‌کنند.</p>

  <h2>۵. پشتیبان در حالت شبکه</h2>
  <p>پشتیبان روی خود سرور با <code>pg_dump</code> ساخته می‌شود. کپی آن فایل روی پوشهٔ اشتراکی فقط بایگانی است، نه محل کار روزانه.</p>
  <figure>
    <img src="{shots['backup']}" alt="دکمه‌های پشتیبان‌گیری و بازیابی"/>
    <figcaption>شکل ۴. بخش پشتیبان‌گیری و بازیابی در تنظیمات — تهیه پشتیبان، پشتیبان سریع، بازیابی از فایل.</figcaption>
  </figure>
  <p>اگر هنوز فایل محلی است: «بازیابی از فایل» را بزنید و فایل <code>sqlite3</code> خودتان را انتخاب کنید. بعد از پیام موفقیت، نوار پایین پنجره مسیر دیتابیس فعال را نشان می‌دهد. گزارش سود و زیان باید سندهای همان فایل باشد.</p>

  <h2>۶. مرور حساب‌ها و بازهٔ تاریخ</h2>
  <p>اگر بازه را «امروز تا امروز» می‌گذارید و هنوز گردش روزهای قبل را می‌بینید، تیک «نمایش مانده قبل از بازه» را بردارید. آن تیک ماندهٔ قبل را در ستون افتتاحیه می‌آورد، نه گردش همان روز.</p>
  <figure>
    <img src="{shots['browse']}" alt="صفحه مرور حسابها و فیلتر تاریخ"/>
    <figcaption>شکل ۵. مرور حساب‌ها — تاریخ از/تا، و گزینهٔ «نمایش مانده قبل از بازه».</figcaption>
  </figure>
</main>
</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    IMG.mkdir(parents=True)

    data = ROOT / ".localdata-guide"
    data.mkdir(parents=True, exist_ok=True)
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")

    app = QApplication.instance() or QApplication([])
    theme.apply(app, dark=False)

    startup = bootstrap.start(cfg, with_demo=True)
    ctx = AppContext(startup)
    ctx.is_admin = True

    login = LoginDialog(ctx)
    shots = {"login": _grab(login, "01-login.png", 520, 360)}

    conn = ConnectionDialog(cfg, persist=False)
    conn.radio_pg.setChecked(True)
    conn.pg_host.setText("192.168.1.10")
    conn.pg_port.setValue(5432)
    conn.pg_database.setText("persianledger")
    conn.pg_user.setText("persianledger")
    shots["connection"] = _grab(conn, "02-connection.png", 560, 620)

    window = MainWindow(ctx)
    window.resize(1280, 860)
    window.show()
    app.processEvents()
    index_of = {key: i for i, (key, *_rest) in enumerate(PAGES)}
    window.go_to(index_of["settings"])
    app.processEvents()
    window.grab().save(str(IMG / "03-settings.png"), "PNG")
    shots["settings"] = _data_uri(IMG / "03-settings.png")
    from PySide6.QtWidgets import QScrollArea

    for area in window.findChildren(QScrollArea):
        bar = area.verticalScrollBar()
        bar.setValue(bar.maximum())
    app.processEvents()
    window.grab().save(str(IMG / "04-backup.png"), "PNG")
    shots["backup"] = _data_uri(IMG / "04-backup.png")

    window.go_to(index_of["browse"])
    app.processEvents()
    browse = window.views[index_of["browse"]]
    browse.include_opening.setChecked(False)
    app.processEvents()
    window.grab().save(str(IMG / "05-browse.png"), "PNG")
    shots["browse"] = _data_uri(IMG / "05-browse.png")
    window.hide()

    for name in ("03-settings.png", "04-backup.png", "05-browse.png"):
        path = IMG / name
        if not path.exists() or path.stat().st_size < 8_000:
            raise SystemExit(f"window screenshot failed: {path}")

    _write_html(shots)
    html_path = OUT_DIR / "index.html"
    if PORTABLE.exists():
        dest_dir = PORTABLE / "راهنمای-شبکه"
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True)
        shutil.copy2(html_path, dest_dir / "index.html")
        shutil.copy2(html_path, PORTABLE / "راهنمای-شبکه.html")
    print(html_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
