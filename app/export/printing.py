from __future__ import annotations

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import QWidget

from app.domain import money


def preview(parent: QWidget | None, html: str) -> None:
    document = QTextDocument()
    document.setHtml(html)
    printer = QPrinter(QPrinter.HighResolution)
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.paintRequested.connect(document.print_)
    dialog.exec()


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table border='1' cellspacing='0' cellpadding='4'><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def statement_html(result) -> str:
    headers = ["تاریخ", "شماره", "نوع", "شرح", "تفصیلی"]
    for col in result.currencies:
        headers.extend([f"{col.code} بد", f"{col.code} بس", f"{col.code} مانده"])
    rows = []
    for row in result.rows:
        cells = [row.date_j, row.number, row.doc_type, row.description, row.tafsili]
        for col in result.currencies:
            debit, credit, balance = row.amounts.get(col.id, (0, 0, 0))
            cells.extend([
                money.format_amount(debit, col.decimals, True),
                money.format_amount(credit, col.decimals, True),
                money.format_amount(balance, col.decimals, True),
            ])
        rows.append(cells)
    return f"<html dir='rtl'><body><h2>{result.title}</h2><p>{result.subtitle}</p>{_table(headers, rows)}</body></html>"


def trial_balance_html(result) -> str:
    labels = {
        2: ["مانده بد", "مانده بس"],
        4: ["گردش بد", "گردش بس", "مانده بد", "مانده بس"],
        6: ["افتتاحیه بد", "افتتاحیه بس", "گردش بد", "گردش بس", "مانده بد", "مانده بس"],
    }[result.columns]
    headers = ["کد", "عنوان"]
    for col in result.currencies:
        headers.extend([f"{col.code} {label}" for label in labels])
    rows = []
    for row in result.rows:
        cells = [row.code, row.name]
        for col in result.currencies:
            for offset in range(result.columns):
                cells.append(money.format_amount(row.cell(result.columns, offset, col.id), col.decimals, True))
        rows.append(cells)
    return f"<html dir='rtl'><body><h2>{result.title}</h2><p>{result.subtitle}</p>{_table(headers, rows)}</body></html>"


def journal_html(result) -> str:
    headers = ["تاریخ", "شماره", "ردیف", "سرفصل", "تفصیلی", "شرح"]
    for col in result.currencies:
        headers.extend([f"{col.code} بد", f"{col.code} بس"])
    rows = []
    for row in result.rows:
        cells = [row.date_j, row.number, row.line_no, row.account, row.tafsili, row.description]
        for col in result.currencies:
            debit, credit = row.amounts.get(col.id, (0, 0))
            cells.extend([money.format_amount(debit, col.decimals, True), money.format_amount(credit, col.decimals, True)])
        rows.append(cells)
    return f"<html dir='rtl'><body><h2>{result.title}</h2><p>{result.subtitle}</p>{_table(headers, rows)}</body></html>"
