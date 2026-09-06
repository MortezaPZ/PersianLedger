from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app import bootstrap, config as config_module, logging_setup
from app.db.migrate import SchemaTooNewError
from app.ui import theme
from app.ui.context import AppContext
from app.ui.login_dialog import LoginDialog
from app.ui.main_window import MainWindow
from app.version import APP_ID, APP_NAME_FA, APP_VERSION

log = logging.getLogger("main")


def _fatal(message: str, detail: str = "") -> int:
    log.critical("%s\n%s", message, detail)
    box = QMessageBox(QMessageBox.Critical, APP_NAME_FA, message)
    box.setInformativeText(f"شرح خطا در فایل زیر ثبت شد:\n{logging_setup.log_file()}")
    if detail:
        box.setDetailedText(detail)
    box.exec()
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    with_demo = "--demo" in argv
    logging_setup.configure()
    logging_setup.install_excepthook()
    log.info("starting %s %s (frozen=%s)", APP_ID, APP_VERSION, getattr(sys, "frozen", False))
    app = QApplication([a for a in argv if not a.startswith("--")])
    app.setApplicationName(APP_ID)
    app.setApplicationVersion(APP_VERSION)
    cfg = config_module.load()
    theme.apply(app, dark=cfg.dark_mode)
    while True:
        try:
            startup = bootstrap.start(cfg, with_demo=with_demo)
            break
        except SchemaTooNewError as exc:
            return _fatal(str(exc))
        except Exception as exc:
            detail = traceback.format_exc()
            log.critical("باز کردن دیتابیس ممکن نشد.\n%s\n%s", exc, detail)
            box = QMessageBox(QMessageBox.Critical, APP_NAME_FA, "باز کردن دیتابیس ممکن نشد.\n" + str(exc))
            box.setInformativeText(f"شرح خطا در فایل زیر ثبت شد:\n{logging_setup.log_file()}")
            box.setDetailedText(detail)
            settings_btn = box.addButton("تنظیمات اتصال", QMessageBox.ActionRole)
            box.addButton("خروج", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is settings_btn:
                from app.ui.connection_dialog import ConnectionDialog

                ConnectionDialog(cfg).exec()
                cfg = config_module.load()
                theme.apply(app, dark=cfg.dark_mode)
                continue
            return 1
    if startup.migration.applied and startup.migration.backup_path:
        QMessageBox.information(
            None,
            APP_NAME_FA,
            f"ساختار دیتابیس به‌روزرسانی شد.\nنسخه پشتیبان پیش از به‌روزرسانی:\n{startup.migration.backup_path}",
        )
    context = AppContext(startup)
    login = LoginDialog(context)
    if login.exec() != QDialog.Accepted:
        return 0
    context.user_id = login.user_id
    context.username = login.username
    context.display_name = login.display_name
    context.is_admin = login.is_admin
    window = MainWindow(context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
