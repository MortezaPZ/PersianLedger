"""Labelled field groups.

Every form in the app stacks a small caption above its control rather than
placing labels in a separate grid column, so fields line up no matter how tall
their neighbours are.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def labeled(label: str, widget: QWidget) -> QWidget:
    """Wrap *widget* with a caption above it.

    An empty *label* still reserves the caption slot, otherwise the control
    rides higher than the labelled fields beside it.
    """
    group = QWidget()
    group.setObjectName("FilterField")  # transparent, so a card shows through
    column = QVBoxLayout(group)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(4)
    caption = QLabel(label or " ")
    caption.setObjectName("FieldLabel")
    column.addWidget(caption)
    column.addWidget(widget)
    column.addStretch()
    return group
