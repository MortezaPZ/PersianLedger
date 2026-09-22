"""Build a beginner Persian HTML guide with embedded screenshots."""
from __future__ import annotations

import base64
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QDialog,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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
RAW = OUT_DIR / "raw-os"


def lan_ipv4() -> str:
    try:
        raw = subprocess.check_output("ipconfig", text=True, encoding="oem", errors="replace")
    except Exception:
        raw = ""
    wifi = re.search(r"Wi-Fi[\s\S]*?IPv4 Address[.\s]*: *([0-9.]+)", raw)
    if wifi and not wifi.group(1).startswith("10."):
        return wifi.group(1)
    for match in re.finditer(r"IPv4 Address[.\s]*: *([0-9.]+)", raw):
        ip = match.group(1)
        if ip.startswith("192.168.") or ip.startswith("172."):
            return ip
    return socket.gethostbyname(socket.gethostname())


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def grab(widget: QWidget, name: str, width: int, height: int) -> str:
    widget.setMinimumSize(width, height)
    widget.resize(width, height)
    widget.show()
    QApplication.instance().processEvents()
    path = IMG / name
    widget.grab().save(str(path), "PNG")
    widget.hide()
    return data_uri(path)


def card(title: str, body: str, width=720, height=320) -> QWidget:
    w = QWidget()
    w.setLayoutDirection(Qt.RightToLeft)
    w.setStyleSheet("QWidget { background:#fff; color:#1a1a1a; font-family: Tahoma; }")
    lay = QVBoxLayout(w)
    t = QLabel(title)
    t.setFont(QFont("Tahoma", 16, QFont.Bold))
    b = QLabel(body)
    b.setWordWrap(True)
    b.setFont(QFont("Tahoma", 13))
    lay.addWidget(t)
    lay.addWidget(b)
    lay.addStretch()
    w.resize(width, height)
    return w


def wizard_page(heading: str, body: str, widgets: list[QWidget]) -> QWidget:
    w = QWidget()
    w.setLayoutDirection(Qt.LeftToRight)
    w.setStyleSheet(
        "QWidget { background:#f0f0f0; color:#1a1a1a; font-family:'Segoe UI'; font-size:13px; }"
        "QPushButton { min-width:88px; padding:4px 12px; }"
    )
    root = QVBoxLayout(w)
    banner = QLabel("New Inbound Rule Wizard")
    banner.setStyleSheet("background:#0078d4; color:white; padding:10px 14px; font-size:15px; font-weight:600;")
    root.addWidget(banner)
    inner = QFrame()
    inner.setStyleSheet("background:white;")
    box = QVBoxLayout(inner)
    h = QLabel(heading)
    h.setStyleSheet("font-size:16px; font-weight:600;")
    b = QLabel(body)
    b.setWordWrap(True)
    box.addWidget(h)
    box.addWidget(b)
    for item in widgets:
        item.setLayoutDirection(Qt.LeftToRight)
        box.addWidget(item)
    box.addStretch()
    root.addWidget(inner, 1)
    nav = QHBoxLayout()
    nav.addStretch()
    back = QPushButton("Back")
    back.setLayoutDirection(Qt.LeftToRight)
    nxt = QPushButton("Next")
    nxt.setLayoutDirection(Qt.LeftToRight)
    nxt.setDefault(True)
    cancel = QPushButton("Cancel")
    cancel.setLayoutDirection(Qt.LeftToRight)
    nav.addWidget(back)
    nav.addWidget(nxt)
    nav.addWidget(cancel)
    root.addLayout(nav)
    return w


def html_doc(shots: dict[str, str]) -> str:
    ip = lan_ipv4()
    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>آموزش قدم‌به‌قدم شبکه — {APP_NAME_FA}</title>
<style>
body {{ margin:0; background:#f4efe6; color:#1c1914; font-family:Tahoma,"Segoe UI",Arial,sans-serif; font-size:17px; line-height:1.95; }}
main {{ max-width:900px; margin:0 auto; padding:28px 20px 80px; }}
h1 {{ font-size:28px; margin:0 0 8px; }}
h2 {{ font-size:21px; margin:40px 0 12px; padding-bottom:6px; border-bottom:2px solid #c9b48a; }}
h3 {{ font-size:18px; margin:22px 0 8px; }}
.meta {{ color:#5c564c; margin-bottom:20px; }}
.box {{ background:#fff8ea; border:1px solid #e0d0a8; border-radius:10px; padding:14px 16px; margin:14px 0; }}
.warn {{ background:#fff1f0; border-color:#e8b4b0; }}
.ok {{ background:#eef8ee; border-color:#b7d7b7; }}
ol, ul {{ padding-right:22px; }}
li {{ margin:7px 0; }}
figure {{ margin:16px 0 26px; background:#fff; border:1px solid #ddd6c8; border-radius:10px; padding:10px; }}
figure img {{ display:block; width:100%; height:auto; border-radius:6px; direction:ltr; unicode-bidi:isolate; }}
figcaption {{ margin-top:8px; color:#4a453c; font-size:15px; }}
code {{ font-family:Consolas,"Courier New",monospace; background:#ece7dc; padding:1px 6px; border-radius:4px; direction:ltr; unicode-bidi:isolate; }}
</style>
</head>
<body>
<main>
<h1>آموزش از صفر: نصب، اجرا، و کار تحت شبکه</h1>
<p class="meta">{APP_NAME_FA} نسخه {APP_VERSION} — برای کسی که تا حالا سرور و فایروال کار نکرده است.</p>

<div class="box">دو حالت دارید: یک نفر روی یک رایانه (فایل محلی)، یا چند نفر در دفتر (یک رایانه سرور + بقیه وصل می‌شوند). اینترنت و VPN لازم نیست و در این نسخه پشتیبانی نمی‌شود.</div>

<h2>۱. فایل زیپ را باز نکنید؛ استخراج کنید</h2>
<p>روی فایل زیپ راست‌کلیک کنید، بعد <code>Extract All</code> را بزنید. یک پوشه انتخاب کنید (مثلاً دسکتاپ یا درایو <code>D</code>). داخل پوشه باید فایل <code>PersianLedger.exe</code> را ببینید.</p>
<figure>
<img src="{shots['explorer']}" alt="پوشه برنامه بعد از استخراج"/>
<figcaption>شکل ۱. بعد از استخراج، این فایل‌ها را می‌بینید. برنامه را از داخل خود زیپ اجرا نکنید.</figcaption>
</figure>
<p>روی <code>PersianLedger.exe</code> دابل‌کلیک کنید. اگر ویندوز نوشت Windows protected your PC، روی More info و بعد Run anyway بزنید. این به‌خاطر نداشتن امضای تجاری است، نه ویروس.</p>
<figure>
<img src="{shots['smartscreen']}" alt="پیام محافظت ویندوز"/>
<figcaption>شکل ۲. اگر این پیام آمد: <code>More info</code> و سپس <code>Run anyway</code>.</figcaption>
</figure>

<h2>۲. اولین ورود</h2>
<p>بار اول از شما می‌خواهد حساب مدیر بسازید. نام کاربری و رمز را جایی یادداشت کنید. بعداً همین‌ها برای ورود است.</p>
<figure>
<img src="{shots['login']}" alt="پنجره ورود یا ساخت حساب"/>
<figcaption>شکل ۳. ورود / ساخت حساب مدیر. پایین صفحه دکمهٔ تنظیمات اتصال است.</figcaption>
</figure>

<h2>۳. کار تک‌نفره (اگر شبکه نمی‌خواهید)</h2>
<p>کاری لازم نیست. برنامه فایل دفتر را در پوشه <code>data</code> کنار exe می‌سازد. نوار پایین پنجره مسیر را نشان می‌دهد. پشتیبان را از تنظیمات بگیرید.</p>
<div class="box ok">اگر فقط یک نفر کار می‌کند، همین کافی است. بقیهٔ این راهنما برای چند کاربر روی شبکهٔ دفتر است.</div>

<h2>۴. کدام رایانه سرور است؟</h2>
<ol>
<li>رایانه‌ای که بیشتر روشن می‌ماند (معمولاً سیستم حسابدار یا یک مینی‌کیس).</li>
<li>به وای‌فای/کابل همان دفتر وصل باشد، نه فقط به اینترنت موبایل.</li>
<li>روی همان یک دستگاه PostgreSQL نصب می‌شود. بقیه فقط برنامه را باز می‌کنند و نشانی این دستگاه را می‌نویسند.</li>
</ol>

<h2>۵. نشانی این رایانه در دفتر</h2>
<p>روی رایانهٔ سرور: منوی استارت را باز کنید، بنویسید <code>cmd</code>، Enter. در پنجره سیاه بنویسید <code>ipconfig</code> و Enter. زیر نوشتهٔ Wi-Fi یا Ethernet دنبال IPv4 بگردید. معمولاً با <code>192.168.</code> شروع می‌شود.</p>
<div class="box warn">اگر VPN روشن است یک عدد <code>10.</code> هم می‌بینید. آن را ننویسید. عدد شبکهٔ دفتر همین وای‌فای داخلی است. روی این رایانه الان {ip} است.</div>
<figure>
<img src="{shots['ip']}" alt="نمونه نشانی IPv4 شبکه دفتر"/>
<figcaption>شکل ۴. نمونهٔ نشانی شبکهٔ دفتر روی همین سیستم. عدد شما ممکن است فرق کند؛ همان IPv4 وای‌فای خودتان را بردارید.</figcaption>
</figure>

<h2>۶. نصب PostgreSQL روی سرور</h2>
<ol>
<li>در مرورگر بگردید: PostgreSQL 16 Windows installer (سایت EDB).</li>
<li>نصب را Next بزنید تا تمام شود. رمز کاربر postgres را جایی بنویسید.</li>
<li>پورت را روی 5432 بگذارید (پیش‌فرض).</li>
<li>Stack Builder را می‌توانید Skip کنید.</li>
</ol>
<p>بعد از نصب، برنامهٔ <code>pgAdmin</code> را باز کنید. روی سرور راست‌کلیک کنید، بعد <code>Query Tool</code> را بزنید. محتویات فایل <code>deploy/postgres/init_db.sql</code> داخل بسته را اجرا کنید. رمز <code>CHANGE_ME</code> را به یک رمز واقعی عوض کنید.</p>
<figure>
<img src="{shots['sql']}" alt="متن ساخت دیتابیس"/>
<figcaption>شکل ۵. همین دو خط، دیتابیس و کاربر برنامه را می‌سازد. رمز را عوض کنید.</figcaption>
</figure>
<p>در پوشهٔ نصب پستگرس، فایل <code>postgresql.conf</code> را با نوت‌پد باز کنید (معمولاً داخل پوشه data). این خط را پیدا کنید و این‌طور کنید:</p>
<p><code>listen_addresses = '*'</code></p>
<p>فایل <code>pg_hba.conf</code> را باز کنید و این خط را پایین اضافه کنید (اگر شبکه دفتر شما 192.168 است):</p>
<p><code>host persianledger persianledger 192.168.0.0/16 scram-sha-256</code></p>
<p>سرویس PostgreSQL را از Services ویندوز Restart کنید. استارت را باز کنید، <code>services.msc</code> را بزنید، سرویس <code>postgresql-x64-16</code> را پیدا کنید، بعد Restart.</p>

<h2>۷. باز کردن پورت فایروال (برای کسی که تابه‌حال نکرده)</h2>
<p>ویندوز به‌صورت پیش‌فرض ورود از شبکه را می‌بندد. باید بگویید «پورت 5432 برای دفتر مجاز است».</p>
<h3>راه ساده‌تر</h3>
<p>فایل <code>deploy/postgres/setup_office_server.ps1</code> را در پوشهٔ برنامه پیدا کنید. روی آن راست‌کلیک کنید، بعد <code>Run with PowerShell</code> را بزنید. اگر خطا گرفت، روی PowerShell در استارت راست‌کلیک کنید، <code>Run as administrator</code> را بزنید و دوباره همان فایل را اجرا کنید. این کار پورت را برای شبکهٔ خصوصی باز می‌کند و نشانی را هم چاپ می‌کند.</p>
<figure>
<img src="{shots['setup']}" alt="اسکریپت آماده‌سازی سرور"/>
<figcaption>شکل ۶. اسکریپت آماده‌سازی سرور دفتر. اگر Administrator باشد پورت را باز می‌کند.</figcaption>
</figure>
<h3>راه دستی با موس</h3>
<ol>
<li>استارت را بزنید و بنویسید <code>Windows Defender Firewall</code>. همان مورد Control Panel را باز کنید.</li>
<li>سمت چپ روی <code>Advanced settings</code> کلیک کنید.</li>
<li>سمت چپ <code>Inbound Rules</code> را بزنید.</li>
<li>سمت راست <code>New Rule</code> را بزنید.</li>
<li><code>Port</code> را انتخاب کنید، بعد <code>Next</code>.</li>
<li><code>TCP</code> و <code>Specific local ports</code> را بزنید و بنویسید <code>5432</code>، بعد <code>Next</code>.</li>
<li><code>Allow the connection</code> را بزنید، بعد <code>Next</code>.</li>
<li>تیک <code>Domain</code> و <code>Private</code> بماند. <code>Public</code> را اگر کافی‌نت است بردارید. در دفتر معمولاً <code>Private</code> کافی است. بعد <code>Next</code>.</li>
<li>اسم قانون را بگذارید <code>PersianLedger PostgreSQL 5432</code>، بعد <code>Finish</code>.</li>
</ol>
<figure>
<img src="{shots['firewall_cpl']}" alt="ویندوز فایروال"/>
<figcaption>شکل ۷. همین پنجره را از Control Panel می‌بینید. لینک <code>Advanced settings</code> سمت چپ است.</figcaption>
</figure>
<figure>
<img src="{shots['wf']}" alt="فایروال پیشرفته"/>
<figcaption>شکل ۸. فایروال پیشرفته. <code>Inbound Rules</code> سمت چپ، بعد <code>New Rule</code> سمت راست.</figcaption>
</figure>
<figure>
<img src="{shots['wiz1']}" alt="جادوگر قانون جدید — نوع پورت"/>
<figcaption>شکل ۹. جادوگر <code>New Rule</code>: گزینهٔ <code>Port</code>.</figcaption>
</figure>
<figure>
<img src="{shots['wiz2']}" alt="پورت 5432"/>
<figcaption>شکل ۱۰. <code>TCP</code> و پورت <code>5432</code>.</figcaption>
</figure>
<figure>
<img src="{shots['wiz3']}" alt="Allow the connection"/>
<figcaption>شکل ۱۱. <code>Allow the connection</code>.</figcaption>
</figure>
<figure>
<img src="{shots['wiz4']}" alt="پروفایل خصوصی"/>
<figcaption>شکل ۱۲. <code>Private</code> (و در صورت نیاز <code>Domain</code>). پایان کار با <code>Finish</code> و یک اسم مشخص.</figcaption>
</figure>
<div class="box warn">وای‌فای این رایانه ممکن است Public ثبت شده باشد. اگر کلاینت وصل نشد، در فایروال همان قانون را برای Public هم تیک بزنید، یا در Settings ویندوز شبکه را Private کنید.</div>

<h2>۸. روی هر رایانهٔ کاربر</h2>
<ol>
<li>همان پوشهٔ استخراج‌شده را کپی کنید (نیازی به پستگرس روی کلاینت نیست).</li>
<li>برنامه را باز کنید. از ورود یا از صفحهٔ ارزها و سال مالی، تنظیمات اتصال را باز کنید.</li>
<li>سرور شبکه (PostgreSQL) را انتخاب کنید.</li>
<li>نشانی همان IPv4 سرور است (مثال این دفتر: {ip}). پورت 5432. نام دیتابیس و کاربر همان <code>persianledger</code>. رمز همان که در SQL گذاشتید.</li>
<li>آزمایش اتصال. اگر OK شد ذخیره کنید، برنامه را ببندید و دوباره باز کنید.</li>
</ol>
<figure>
<img src="{shots['settings']}" alt="تنظیمات اتصال در برنامه"/>
<figcaption>شکل ۱۳. صفحهٔ تنظیمات برنامه — جعبهٔ اتصال به دیتابیس.</figcaption>
</figure>
<figure>
<img src="{shots['connection']}" alt="پنجره PostgreSQL"/>
<figcaption>شکل ۱۴. پر کردن نشانی سرور، پورت، دیتابیس، کاربر و رمز.</figcaption>
</figure>
<figure>
<img src="{shots['testok']}" alt="پیام موفقیت اتصال"/>
<figcaption>شکل ۱۵. اگر آزمایش اتصال موفق باشد چنین پیامی می‌آید. بعد برنامه را یک‌بار ببندید و باز کنید.</figcaption>
</figure>

<h2>۹. انتقال دفتر فعلی به سرور</h2>
<p>اگر تا امروز روی فایل محلی کار می‌کردید، روی رایانهٔ سرور (هنوز روی SQLite) با حساب مدیر بروید تنظیمات، بعد «انتقال دیتابیس فعلی به PostgreSQL». نشانی سرور را بدهید. بعد از موفقیت، اتصال را روی سرور ذخیره کنید.</p>
<figure>
<img src="{shots['migrate']}" alt="دکمه انتقال به PostgreSQL"/>
<figcaption>شکل ۱۶. دکمهٔ انتقال، فقط وقتی فایل محلی است و کاربر مدیر است دیده می‌شود.</figcaption>
</figure>

<h2>۱۰. پشتیبان و بازیابی</h2>
<p>در حالت فایل محلی، پشتیبان یک فایل sqlite3 است. در حالت شبکه، پشتیبان روی خود سرور ساخته می‌شود. کپی آن روی پوشهٔ اشتراکی فقط بایگانی است، نه محل کار روزانه.</p>
<figure>
<img src="{shots['backup']}" alt="پشتیبان‌گیری و بازیابی"/>
<figcaption>شکل ۱۷. تهیه پشتیبان و بازیابی از فایل. بعد از بازیابی به نوار پایین پنجره نگاه کنید که همان فایل شما باشد.</figcaption>
</figure>

<h2>۱۱. مرور حساب‌ها و تاریخ</h2>
<p>اگر از امروز تا امروز می‌گذارید و گردش روزهای قبل را می‌بینید، تیک «نمایش مانده قبل از بازه» را بردارید. آن تیک ماندهٔ قدیم را در ستون افتتاحیه می‌آورد.</p>
<figure>
<img src="{shots['browse']}" alt="مرور حسابها"/>
<figcaption>شکل ۱۸. مرور حساب‌ها. تیک ماندهٔ قبل از بازه پیش‌فرض خاموش است.</figcaption>
</figure>

<h2>۱۲. درخت سرفصل‌ها</h2>
<p>پیش‌فرض درخت تا سطح معین باز است. تفصیلی‌ها با کلیک روی معین باز می‌شوند. نام گروه (اشخاص، پروژه‌ها، …) نوشته می‌شود نه فقط «تفصیلی ۱».</p>
<figure>
<img src="{shots['tree']}" alt="درخت سرفصلها"/>
<figcaption>شکل ۱۹. درخت سرفصل‌ها تا معین.</figcaption>
</figure>

<h2>اگر وصل نشد</h2>
<ul>
<li>پستگرس روی سرور روشن است؟ از Services چک کنید.</li>
<li>عدد IP وای‌فای است نه VPN؟</li>
<li>قانون فایروال 5432 هست؟ اگر شبکه Public است تیک Public را هم بزنید.</li>
<li>listen_addresses و pg_hba ذخیره و سرویس Restart شده؟</li>
<li>رمز SQL همان است که در برنامه نوشتید؟</li>
</ul>
<p>نوار پایین برنامه نشان می‌دهد الان به SQLite وصلید یا به PostgreSQL.</p>
</main>
</body>
</html>
"""


def main() -> int:
    quick = "--quick" in sys.argv
    if IMG.exists() and not quick:
        shutil.rmtree(IMG)
    IMG.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    theme.apply(app, dark=False)
    shots: dict[str, str] = {}

    ip = lan_ipv4()
    shots["ip"] = grab(card("نشانی شبکهٔ دفتر", f"IPv4 وای‌فای این رایانه:\n{ip}\n\nعدد 10.x مربوط به VPN است؛ آن را ننویسید."), "ip.png", 700, 280)

    files = QWidget()
    files.setLayoutDirection(Qt.RightToLeft)
    fl = QVBoxLayout(files)
    fl.addWidget(QLabel("پوشه بعد از استخراج — روی PersianLedger.exe دابل‌کلیک کنید"))
    model = QFileSystemModel()
    model.setRootPath(str(PORTABLE if PORTABLE.exists() else ROOT))
    view = QListView()
    view.setModel(model)
    view.setRootIndex(model.index(str(PORTABLE if PORTABLE.exists() else ROOT)))
    fl.addWidget(view)
    shots["explorer"] = grab(files, "explorer.png", 820, 480)

    sm = card(
        "اگر ویندوز برنامه را رد کرد",
        "متن: Windows protected your PC\nدکمهٔ More info را بزنید.\nبعد Run anyway را بزنید.\nعلت: فایل امضای دیجیتال فروشگاهی ندارد.",
        700,
        260,
    )
    shots["smartscreen"] = grab(sm, "smartscreen.png", 700, 260)

    sql = QTextEdit()
    sql.setReadOnly(True)
    sql.setPlainText((ROOT / "deploy" / "postgres" / "init_db.sql").read_text(encoding="utf-8"))
    sqlw = QWidget()
    sl = QVBoxLayout(sqlw)
    sl.addWidget(QLabel("init_db.sql — رمز CHANGE_ME را عوض کنید"))
    sl.addWidget(sql)
    shots["sql"] = grab(sqlw, "sql.png", 720, 240)

    setup = QTextEdit()
    setup.setReadOnly(True)
    setup.setPlainText((ROOT / "deploy" / "postgres" / "setup_office_server.ps1").read_text(encoding="utf-8"))
    sw = QWidget()
    sl2 = QVBoxLayout(sw)
    sl2.addWidget(QLabel("setup_office_server.ps1 — راست‌کلیک، Run with PowerShell (ترجیحاً Administrator)"))
    sl2.addWidget(setup)
    shots["setup"] = grab(sw, "setup.png", 860, 520)

    if (RAW / "firewall-cpl-clean.png").exists():
        shots["firewall_cpl"] = data_uri(RAW / "firewall-cpl-clean.png")
    elif (RAW / "w03-firewall-cpl.png").exists():
        shots["firewall_cpl"] = data_uri(RAW / "w03-firewall-cpl.png")
    else:
        shots["firewall_cpl"] = shots["setup"]
    if (RAW / "wf-msc-clean.png").exists():
        shots["wf"] = data_uri(RAW / "wf-msc-clean.png")
    elif (RAW / "w04-wf-msc.png").exists():
        shots["wf"] = data_uri(RAW / "w04-wf-msc.png")
    else:
        shots["wf"] = shots["firewall_cpl"]

    app.setLayoutDirection(Qt.LeftToRight)
    p1 = wizard_page(
        "Rule Type",
        "What type of rule would you like to create?",
        [QRadioButton("Program"), QRadioButton("Port")],
    )
    p1.findChildren(QRadioButton)[1].setChecked(True)
    shots["wiz1"] = grab(p1, "wiz1.png", 720, 420)
    port_lbl = QLabel("Specific local ports:")
    port_val = QLabel("5432")
    p2 = wizard_page(
        "Protocol and Ports",
        "Does this rule apply to TCP or UDP?",
        [QRadioButton("TCP"), QRadioButton("UDP"), port_lbl, port_val],
    )
    p2.findChildren(QRadioButton)[0].setChecked(True)
    shots["wiz2"] = grab(p2, "wiz2.png", 720, 420)
    p3 = wizard_page(
        "Action",
        "What action should be taken when a connection matches the specified conditions?",
        [QRadioButton("Allow the connection"), QRadioButton("Block the connection")],
    )
    p3.findChildren(QRadioButton)[0].setChecked(True)
    shots["wiz3"] = grab(p3, "wiz3.png", 720, 420)
    p4w = QWidget()
    p4w.setLayoutDirection(Qt.LeftToRight)
    p4l = QVBoxLayout(p4w)
    for name, on in (("Domain", True), ("Private", True), ("Public", False)):
        c = QCheckBox(name)
        c.setChecked(on)
        p4l.addWidget(c)
    name_lbl = QLabel("Name: PersianLedger PostgreSQL 5432")
    p4 = wizard_page(
        "Profile",
        "When does this rule apply?",
        [p4w, name_lbl],
    )
    shots["wiz4"] = grab(p4, "wiz4.png", 720, 460)
    app.setLayoutDirection(Qt.RightToLeft)

    needed_app = {
        "login": "login.png",
        "connection": "connection.png",
        "testok": "testok.png",
        "settings": "settings.png",
        "migrate": "migrate.png",
        "browse": "browse.png",
        "tree": "tree.png",
    }
    if quick and all((IMG / fn).exists() for fn in needed_app.values()):
        for key, fn in needed_app.items():
            shots[key] = data_uri(IMG / fn)
        shots["backup"] = shots["migrate"]
        html_path = OUT_DIR / "index.html"
        html_path.write_text(html_doc(shots), encoding="utf-8")
        raw = html_path.read_bytes()
        if raw.count(b"data:image/png;base64,") < 12:
            raise SystemExit(f"too few embedded images: {raw.count(b'data:image/png;base64,')}")
        if PORTABLE.exists():
            dest = PORTABLE / "راهنمای-شبکه"
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir()
            shutil.copy2(html_path, dest / "index.html")
            shutil.copy2(html_path, PORTABLE / "راهنمای-شبکه.html")
        print(html_path, html_path.stat().st_size)
        return 0

    data = ROOT / ".localdata-guide"
    data.mkdir(parents=True, exist_ok=True)
    cfg = config_module.AppConfig(data_dir=data, sqlite_path=data / "ledger.sqlite3")
    ctx = AppContext(bootstrap.start(cfg, with_demo=False))
    ctx.is_admin = True

    login = LoginDialog(ctx)
    shots["login"] = grab(login, "login.png", 520, 400)

    conn = ConnectionDialog(cfg, persist=False)
    conn.radio_pg.setChecked(True)
    conn.pg_host.setText(ip)
    conn.pg_port.setValue(5432)
    conn.pg_database.setText("persianledger")
    conn.pg_user.setText("persianledger")
    shots["connection"] = grab(conn, "connection.png", 560, 640)

    ok = QDialog()
    ok.setWindowTitle(APP_NAME_FA)
    ol = QVBoxLayout(ok)
    ol.addWidget(QLabel("اتصال برقرار شد.\nPostgreSQL 16"))
    btn = QPushButton("باشه")
    ol.addWidget(btn)
    shots["testok"] = grab(ok, "testok.png", 420, 180)

    window = MainWindow(ctx)
    window.resize(1280, 900)
    window.show()
    app.processEvents()
    index_of = {key: i for i, (key, *_rest) in enumerate(PAGES)}
    window.go_to(index_of["settings"])
    app.processEvents()
    shots["settings"] = data_uri(IMG / "settings.png") if False else None
    path = IMG / "settings.png"
    window.grab().save(str(path), "PNG")
    shots["settings"] = data_uri(path)

    from PySide6.QtWidgets import QScrollArea

    for area in window.findChildren(QScrollArea):
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
    app.processEvents()
    path = IMG / "migrate.png"
    window.grab().save(str(path), "PNG")
    shots["migrate"] = data_uri(path)
    shots["backup"] = data_uri(path)

    window.go_to(index_of["browse"])
    app.processEvents()
    browse = window.views[index_of["browse"]]
    browse.include_opening.setChecked(False)
    app.processEvents()
    path = IMG / "browse.png"
    window.grab().save(str(path), "PNG")
    shots["browse"] = data_uri(path)

    window.go_to(index_of["accounts"])
    app.processEvents()
    path = IMG / "tree.png"
    window.grab().save(str(path), "PNG")
    shots["tree"] = data_uri(path)
    window.hide()

    html_path = OUT_DIR / "index.html"
    html_path.write_text(html_doc(shots), encoding="utf-8")
    raw = html_path.read_bytes()
    if raw.count(b"data:image/png;base64,") < 12:
        raise SystemExit(f"too few embedded images: {raw.count(b'data:image/png;base64,')}")
    if PORTABLE.exists():
        dest = PORTABLE / "راهنمای-شبکه"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir()
        shutil.copy2(html_path, dest / "index.html")
        shutil.copy2(html_path, PORTABLE / "راهنمای-شبکه.html")
    print(html_path, html_path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
