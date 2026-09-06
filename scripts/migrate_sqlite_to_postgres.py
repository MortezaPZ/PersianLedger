from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.data_migration import migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--pg-url", required=True)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--attachments-dir")
    args = parser.parse_args(argv)
    report = migrate(
        Path(args.sqlite),
        args.pg_url,
        replace=args.replace,
        attachments_dir=Path(args.attachments_dir) if args.attachments_dir else None,
        progress=lambda name: print(name, file=sys.stderr),
    )
    for name, (src, dst) in report.table_counts.items():
        print(f"{name}\t{src}\t{dst}")
    if report.mismatches:
        for item in report.mismatches:
            print("MISMATCH", item)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
