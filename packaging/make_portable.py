"""Write the portable build's marker and the English read-me.

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

1. Extract the new version into a different folder and close the program.
2. Run update_portable.ps1 with the current folder and the new folder.
   That replaces the program files and does not touch data.
3. Start the program from the same folder as before.

Before a database structure change the program writes a backup, then
updates the structure. Restore an older backup from inside the program.
Add home-office work to the office database with the home-work action.
Details are in docs\\user-guide.md.


Full guide

docs\\user-guide.md covers the chart, floating details, multi-currency
documents, reversing and correcting entries, and the five reports.
The illustrated network notes, if shipped beside the program, open in a browser.
"""


def main() -> int:
    target = Path(sys.argv[1])
    (target / "portable.txt").write_text(MARKER, encoding="utf-8")
    (target / "GUIDE.txt").write_text(
        README.format(version=APP_VERSION).replace("\n", "\r\n"),
        encoding="utf-8-sig",
    )
    print(f"wrote portable.txt and GUIDE.txt into {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
