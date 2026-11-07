"""Design tokens for the PersianLedger interface.

Qt Style Sheets have no variables, so the palette lives here and both the
generated stylesheet and the Python drawing code (table row brushes, icons)
read from the same object.  That keeps light and dark from drifting apart.

Spacing scale: 4 / 8 / 12 / 16 / 24 / 32
Radius:        6 (controls) / 10 (cards) / 999 (pills)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str

    # Surfaces
    canvas: str          # window background behind cards
    surface: str         # cards, inputs, tables
    surface_alt: str     # striped rows, subtle fills
    surface_muted: str   # read-only inputs, table headers
    overlay: str         # menus, popups

    # Lines
    line: str            # default borders
    line_strong: str     # emphasised dividers
    grid: str            # table gridlines

    # Text
    text: str
    text_muted: str
    text_faint: str
    text_on_brand: str

    # Brand
    ink: str             # sidebar background
    ink_alt: str         # sidebar hover
    ink_line: str        # sidebar dividers
    ink_text: str        # sidebar idle label
    ink_text_dim: str    # sidebar section caption
    brand: str           # primary buttons / active nav
    brand_hover: str
    brand_soft: str      # tinted selection background
    accent: str          # gold active marker

    # Feedback
    success: str
    danger: str
    danger_soft: str
    warning: str
    draft_row: str       # provisional (پیش‌نویس) row tint
    subtotal_row: str    # subtotal / total row tint
    focus: str


LIGHT = Palette(
    name="light",
    canvas="#f3f5f9",
    surface="#ffffff",
    surface_alt="#f8fafd",
    surface_muted="#edf2f8",
    overlay="#ffffff",
    line="#dfe6ef",
    line_strong="#c7d3e1",
    grid="#eaf0f6",
    text="#101a28",
    text_muted="#52667d",
    text_faint="#5f7389",
    text_on_brand="#ffffff",
    ink="#14243a",
    ink_alt="#1d3452",
    ink_line="#243c5c",
    ink_text="#c9d6e6",
    ink_text_dim="#7e93ae",
    brand="#1d5eab",
    brand_hover="#2a74c9",
    brand_soft="#e4effb",
    accent="#e4ae3d",
    success="#15803d",
    danger="#c02626",
    danger_soft="#fdecec",
    warning="#b45309",
    draft_row="#fff6e3",
    subtotal_row="#e7eefa",
    focus="#3b82f6",
)


DARK = Palette(
    name="dark",
    canvas="#0d1522",
    surface="#151f30",
    surface_alt="#1a2537",
    surface_muted="#1e2b3f",
    overlay="#1a2537",
    line="#2b3b52",
    line_strong="#425671",
    grid="#263750",
    text="#e6edf6",
    text_muted="#9bacc2",
    text_faint="#9aacc1",
    text_on_brand="#ffffff",
    ink="#0a1220",
    ink_alt="#16223a",
    ink_line="#223653",
    ink_text="#c2d0e2",
    ink_text_dim="#71849c",
    brand="#2a6fc4",
    brand_hover="#3b85dc",
    brand_soft="#1c3455",
    accent="#e0a92e",
    success="#3ecf7c",
    danger="#f87171",
    danger_soft="#3a1e21",
    warning="#e0a92e",
    draft_row="#332a15",
    subtotal_row="#1d2f4a",
    focus="#5aa2f5",
)


def get(dark: bool) -> Palette:
    return DARK if dark else LIGHT
