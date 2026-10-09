# Interface redesign

The `after-<theme>-<screen>.png` files are produced by:

```bash
.venv/Scripts/python.exe scripts/capture_ui.py
```

That command captures every screen in both themes.

## Before (compiled 0.5.0)

Navy sidebar `#1f3350`, gold button `#f0a441`, no dark theme, tables without a clear hover.

## After (0.6.0)

- One color source. Colors live in `app/ui/palette.py`. `app/ui/stylesheet.py` builds both themes from that palette, so a light-theme rule is not forgotten in the dark theme.
- Icons are drawn with QPainter (`app/ui/icons.py`). This PySide6 build has no QtSvg module, so the old SVG icons rendered as empty squares.
- Labels sit above the field (`app/ui/widgets/fields.py`) instead of in a separate label column. Report filters use a four-column grid aligned to the top, so a tall widget does not shove its short neighbors.
- Tables are striped, with hover, right-aligned numbers and thousands separators, and without heavy grid lines. Columns size to content (description capped at 300 px) so more columns fit.
- A dark theme switch in settings. Sidebar icons are recolored when the theme changes.

## Right-to-left fixes in this round

- Letter-spacing was removed from Persian text. The script is joined, and extra letter spacing breaks the joins.
- `QGroupBox` titles are anchored with `subcontrol-position`. A `right:` offset in right-to-left mode pushed the title out of the frame and clipped the first letters.
- On the chart tree, the code/title column stretches. Qt's default stretches the last column, which was truncating account titles.
